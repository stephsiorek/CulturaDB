"""
movies.py - TMDB → Snowflake pipeline (optional CSV)

Usage:
  python movies.py [options]

Key behavior:
  - Always loads fetched rows into Snowflake (upsert/merge by (id, release_date), keeps earliest ds)
  - Optionally writes results to a local CSV when --write-csv is provided
  - Supports incremental fetching via date filters (auto-switches to discover/movie when needed)
  - Can be scheduled to run daily at a specific local time

Environment (.env):
  TMDB_ACCESS_TOKEN=<v4_bearer_token>   # preferred
  TMDB_API_KEY=<v3_api_key>             # fallback if no v4 token

  SNOWFLAKE_ACCOUNT=...
  SNOWFLAKE_USER=...
  SNOWFLAKE_PASSWORD=...
  SNOWFLAKE_WAREHOUSE=...
  SNOWFLAKE_DATABASE=...
  SNOWFLAKE_SCHEMA=...
  SNOWFLAKE_ROLE=...
  SNOWFLAKE_TABLE=TMDB_MOVIES

CLI Options:
  --endpoint TEXT            TMDB v3 endpoint path (default: movie/popular).
                             Examples: movie/popular, search/movie, discover/movie
  --pages INT                Number of pages to fetch for paginated endpoints (default: 1)
  --page-start INT           First page to fetch (default: 1)
  --page-end INT             Last page to fetch (inclusive). If set, overrides --pages
  --write-csv                Also write fetched rows to a local CSV
  --output PATH              CSV output path (default: tmdb_output.csv). Used only with --write-csv
  --params JSON              Extra query params as JSON string, e.g. '{"with_original_language":"en"}'
  --schedule-daily HH:MM     Run the pipeline daily at the given local time and keep running

Incremental filters (discover/movie):
  --primary-release-date-gte YYYY-MM-DD
  --primary-release-date-lte YYYY-MM-DD
  --since-days INT           Convenience: sets gte to (today - N days)
  --use-discover             Force endpoint to discover/movie

Examples:
  # Default: fetch 1 page of popular movies and load to Snowflake
  python movies.py

  # Fetch 3 pages, also write CSV
  python movies.py --pages 3 --write-csv --output popular.csv

  # Incremental last 7 days using discover/movie (auto-switch)
  python movies.py --since-days 7

  # Explicit release window
  python movies.py --primary-release-date-gte 2025-10-01 --primary-release-date-lte 2025-10-31

  # Add extra TMDB filters
  python movies.py --use-discover --since-days 30 --params '{"with_original_language":"en"}'

  # Schedule nightly at 02:30 with last 1 day window
  python movies.py --since-days 1 --schedule-daily 02:30
"""
import os
import csv
import json
import argparse
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, date, timedelta
import time

import requests
from dotenv import load_dotenv
import snowflake.connector
import schedule
# Target Snowflake table columns (ordered)
COLUMNS: List[str] = [
    "id",
    "title",
    "original_title",
    "release_date",
    "overview",
    "vote_average",
    "vote_count",
    "popularity",
    "adult",
    "genre_ids",
    "original_language",
    "backdrop_path",
    "poster_path",
    "video",
    "ds",
]

def _safe_date_from_str(value: Any) -> Optional[date]:
    """
    Convert a YYYY-MM-DD string to a date; return None for blanks/invalids.
    Snowflake DATE accepts None for NULL.
    """
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def get_tmdb_session() -> Dict[str, Any]:
    """
    Create a configured requests session and base URL for TMDB.
    Supports either:
      - Bearer token via TMDB_ACCESS_TOKEN (preferred)
      - API key via TMDB_API_KEY as query parameter (fallback)
    """
    load_dotenv()
    access_token = os.getenv("TMDB_ACCESS_TOKEN")
    api_key = os.getenv("TMDB_API_KEY")

    if not access_token and not api_key:
        raise RuntimeError(
            "TMDB credentials not found. Set TMDB_ACCESS_TOKEN or TMDB_API_KEY in .env"
        )

    session = requests.Session()
    headers: Dict[str, str] = {"Accept": "application/json"}
    default_params: Dict[str, str] = {}

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        # v3 API key as query param fallback
        default_params["api_key"] = api_key or ""

    session.headers.update(headers)
    return {
        "session": session,
        "base_url": "https://api.themoviedb.org/3",
        "default_params": default_params,
        "auth_mode": "bearer" if access_token else "api_key",
    }


def fetch_tmdb_endpoint(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    pages: int = 1,
    page_start: int = 1,
    page_end: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch data from a TMDB endpoint, optionally paginating 'pages' times.
    For list endpoints that return 'results', concatenates across pages.
    For non-paginated endpoints, returns a single-item list with the response.
    """
    cfg = get_tmdb_session()
    session: requests.Session = cfg["session"]
    base_url: str = cfg["base_url"]
    default_params: Dict[str, Any] = cfg["default_params"]
    auth_mode: str = cfg.get("auth_mode", "unknown")

    merged_params = dict(default_params)
    if params:
        merged_params.update(params)

    url = f"{base_url}/{endpoint.lstrip('/')}"
    all_items: List[Dict[str, Any]] = []

    # Determine page iteration range
    start = max(1, int(page_start))
    if page_end is not None and int(page_end) >= start:
        page_iter = range(start, int(page_end) + 1)
    else:
        total = max(1, int(pages))
        page_iter = range(start, start + total)

    # Try to paginate if 'page' applies; otherwise just request once
    total_pages_seen: Optional[int] = None
    for page_idx in page_iter:
        # Stop early if we know we've exceeded total_pages from a previous response
        if total_pages_seen is not None and page_idx > total_pages_seen:
            break
        
        merged_params["page"] = page_idx
        resp = session.get(url, params=merged_params, timeout=30)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "").strip()
            msg = "TMDB rate limit hit (HTTP 429)."
            if retry_after:
                msg += f" Retry-After: {retry_after}s."
            raise RuntimeError(
                f"{msg} Reduce requested pages/range or add incremental filters (e.g., --since-days)."
            )
        if resp.status_code == 400:
            # 400 often means page limit exceeded (TMDB typically maxes at 500 pages)
            try:
                error_data = resp.json()
                error_msg = error_data.get("status_message", resp.text[:200])
            except Exception:
                error_msg = resp.text[:200]
            raise RuntimeError(
                f"TMDB returned 400 Bad Request (likely page limit exceeded). "
                f"TMDB typically limits pagination to 500 pages. "
                f"Requested page: {page_idx}. Error: {error_msg}"
            )
        if resp.status_code == 401:
            hint = (
                "TMDB returned 401 Unauthorized. "
                f"Auth mode used: {auth_mode}. "
                "Ensure your .env contains a valid TMDB_ACCESS_TOKEN (preferred, v4) "
                "or TMDB_API_KEY (v3). If you just added it, restart your shell or reload the env."
            )
            try:
                details = resp.json()
            except Exception:
                details = {"message": resp.text[:200]}
            raise RuntimeError(f"{hint} Details: {details}")
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
            all_items.extend(data["results"])
            # Track total_pages from response to stop early on subsequent iterations
            total_pages = data.get("total_pages")
            if isinstance(total_pages, int):
                if total_pages_seen is None:
                    total_pages_seen = total_pages
                # Stop if we've reached or exceeded the last available page
                if page_idx >= total_pages:
                    break
        else:
            # Non-list response; return as a single item
            return [data]

    return all_items


def _normalize_value(value: Any) -> Any:
    """
    Normalize nested or non-primitive values into JSON strings for CSV safety.
    """
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    # Lists, dicts, and other types -> JSON string
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def write_csv(rows: List[Dict[str, Any]], output_path: str) -> None:
    if not rows:
        # Create empty file with no rows but still write header if possible
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
        return

    # Align CSV to Snowflake schema; fill missing values and compute ds consistently
    ds_value = _get_run_ds_date()
    fieldnames = COLUMNS
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Skip rows without a valid release_date
            if _safe_date_from_str(row.get("release_date")) is None:
                continue
            normalized_row: Dict[str, Any] = {}
            for k in fieldnames:
                if k == "ds":
                    normalized_row[k] = ds_value
                else:
                    normalized_row[k] = _normalize_value(row.get(k))
            normalized = normalized_row
            writer.writerow(normalized)


def _get_run_ds_date() -> date:
    # Using UTC date of run to match Snowflake DATE column
    return datetime.now(timezone.utc).date()


def _ensure_snowflake_env() -> Dict[str, str]:
    load_dotenv()
    required = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing Snowflake env vars in .env: {', '.join(missing)}. "
            "Please set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, "
            "SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA."
        )
    # Optional role and table
    role = os.getenv("SNOWFLAKE_ROLE")
    table = os.getenv("SNOWFLAKE_TABLE", "TMDB_MOVIES")
    required["role"] = role if role else ""
    required["table"] = table
    return required


def load_rows_into_snowflake(rows: List[Dict[str, Any]]) -> int:
    """
    Upsert rows into Snowflake table defined by env var SNOWFLAKE_TABLE (default TMDB_MOVIES).
    - Stages incoming rows into a TEMP table
    - MERGEs into target on (id, release_date)
      - WHEN MATCHED: update all descriptive fields, ds = LEAST(target.ds, source.ds)
      - WHEN NOT MATCHED: insert new row
    Adds a ds DATE column = UTC run date to each staged row.
    """
    if not rows:
        return 0

    env = _ensure_snowflake_env()

    ctx = snowflake.connector.connect(
        account=env["account"],
        user=env["user"],
        password=env["password"],
        warehouse=env["warehouse"],
        database=env["database"],
        schema=env["schema"],
        role=env["role"] or None,
    )
    try:
        cs = ctx.cursor()
        try:
            ds_value = _get_run_ds_date()
            target_table = env["table"]

            # 1) Create a session-scoped temp staging table matching the target schema
            temp_table = f"TEMP_{target_table}_STAGE_{int(datetime.now(timezone.utc).timestamp())}"
            cs.execute(f"CREATE TEMPORARY TABLE {temp_table} LIKE {target_table}")

            # 2) Insert staged rows
            # Build VALUES-based multi-row insert for executemany() into the temp table
            value_exprs = ["%(" + c + ")s" for c in COLUMNS]
            placeholders = ", ".join(value_exprs)
            stage_sql = f"INSERT INTO {temp_table} ({', '.join(COLUMNS)}) VALUES ({placeholders})"

            param_rows: List[Dict[str, Any]] = []
            for r in rows:
                # Skip rows without a valid release_date
                safe_release_date = _safe_date_from_str(r.get("release_date"))
                if safe_release_date is None:
                    continue
                # Ensure genre_ids is a JSON string (target column VARCHAR)
                raw_genre = r.get("genre_ids")
                if isinstance(raw_genre, (list, dict)):
                    genre_str = json.dumps(raw_genre)
                elif raw_genre is None:
                    genre_str = None
                else:
                    genre_str = str(raw_genre)
                param: Dict[str, Any] = {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "original_title": r.get("original_title"),
                    "release_date": safe_release_date,
                    "overview": r.get("overview"),
                    "vote_average": r.get("vote_average"),
                    "vote_count": r.get("vote_count"),
                    "popularity": r.get("popularity"),
                    "adult": r.get("adult"),
                    "genre_ids": genre_str,
                    "original_language": r.get("original_language"),
                    "backdrop_path": r.get("backdrop_path"),
                    "poster_path": r.get("poster_path"),
                    "video": r.get("video"),
                    "ds": ds_value,
                }
                param_rows.append(param)

            cs.executemany(stage_sql, param_rows)

            # 3) MERGE into target, keeping earliest ds
            merge_sql = f"""
MERGE INTO {target_table} AS t
USING (
  SELECT
    CAST(id AS NUMBER) AS id,
    release_date,
    title,
    original_title,
    overview,
    vote_average,
    vote_count,
    popularity,
    adult,
    genre_ids,
    original_language,
    backdrop_path,
    poster_path,
    video,
    ds
  FROM (
    SELECT
      id,
      release_date,
      title,
      original_title,
      overview,
      vote_average,
      vote_count,
      popularity,
      adult,
      genre_ids,
      original_language,
      backdrop_path,
      poster_path,
      video,
      ds,
      ROW_NUMBER() OVER (
        PARTITION BY CAST(id AS NUMBER), NVL(release_date, TO_DATE('0001-01-01'))
        ORDER BY ds ASC
      ) AS rn
    FROM {temp_table}
  )
  WHERE rn = 1
) AS s
ON  t.id = s.id
AND NVL(t.release_date, TO_DATE('0001-01-01')) = NVL(s.release_date, TO_DATE('0001-01-01'))
WHEN MATCHED THEN UPDATE SET
  title = s.title,
  original_title = s.original_title,
  release_date = s.release_date,
  overview = s.overview,
  vote_average = s.vote_average,
  vote_count = s.vote_count,
  popularity = s.popularity,
  adult = s.adult,
  genre_ids = s.genre_ids,
  original_language = s.original_language,
  backdrop_path = s.backdrop_path,
  poster_path = s.poster_path,
  video = s.video,
  ds = LEAST(t.ds, s.ds)
WHEN NOT MATCHED THEN INSERT (
  id, title, original_title, release_date, overview, vote_average, vote_count,
  popularity, adult, genre_ids, original_language, backdrop_path, poster_path, video, ds
) VALUES (
  s.id, s.title, s.original_title, s.release_date, s.overview, s.vote_average, s.vote_count,
  s.popularity, s.adult, s.genre_ids, s.original_language, s.backdrop_path, s.poster_path, s.video, s.ds
)
"""
            cs.execute(merge_sql)

            return len(param_rows)
        finally:
            cs.close()
    finally:
        ctx.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch data from TMDB and load into Snowflake. Optionally write CSV."
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="movie/popular",
        help="TMDB v3 endpoint path, e.g. 'movie/popular' or 'search/movie'",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Number of pages to fetch for paginated endpoints (default: 1).",
    )
    parser.add_argument(
        "--page-start",
        type=int,
        default=1,
        help="First page to fetch (default: 1).",
    )
    parser.add_argument(
        "--page-end",
        type=int,
        default=0,
        help="Last page to fetch (inclusive). If set (>0), overrides --pages.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tmdb_output.csv",
        help="Output CSV file path (default: tmdb_output.csv). Used only with --write-csv.",
    )
    parser.add_argument(
        "--write-csv",
        action="store_true",
        help="If set, also write the fetched rows to a local CSV file.",
    )
    parser.add_argument(
        "--params",
        type=str,
        default="",
        help="Optional JSON string of extra query params, e.g. '{\"query\": \"Inception\"}'.",
    )
    parser.add_argument(
        "--schedule-daily",
        type=str,
        default="",
        help="Schedule the pipeline to run daily at HH:MM (24h, local time). If set, the script runs continuously.",
    )
    # Incremental/date filtering options (TMDB discover/movie supports these)
    parser.add_argument(
        "--primary-release-date-gte",
        type=str,
        default="",
        help="Filter: primary_release_date.gte (YYYY-MM-DD). Uses discover/movie.",
    )
    parser.add_argument(
        "--primary-release-date-lte",
        type=str,
        default="",
        help="Filter: primary_release_date.lte (YYYY-MM-DD). Uses discover/movie.",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=0,
        help="Shortcut: sets primary_release_date.gte to today-<since-days>. Uses discover/movie.",
    )
    parser.add_argument(
        "--use-discover",
        action="store_true",
        help="If set, force endpoint to discover/movie (useful with date filters).",
    )
    args = parser.parse_args()

    def run_pipeline_once() -> None:
        extra_params: Dict[str, Any] = {}
        if args.params:
            try:
                extra_params.update(json.loads(args.params))
                if not isinstance(extra_params, dict):
                    raise ValueError("params must decode to an object")
            except Exception as exc:
                raise SystemExit(f"Invalid --params JSON: {exc}")

        # Apply incremental filters
        if args.since_days and not args.primary_release_date_gte:
            gte_date = datetime.now(timezone.utc).date() - timedelta(days=args.since_days)
            extra_params["primary_release_date.gte"] = gte_date.isoformat()
        if args.primary_release_date_gte:
            extra_params["primary_release_date.gte"] = args.primary_release_date_gte
        if args.primary_release_date_lte:
            extra_params["primary_release_date.lte"] = args.primary_release_date_lte

        # If using date filters and default endpoint, switch to discover/movie unless overridden
        effective_endpoint = args.endpoint
        date_filters_present = any(
            k in extra_params for k in ("primary_release_date.gte", "primary_release_date.lte")
        )
        if (args.use_discover or date_filters_present) and args.endpoint == "movie/popular":
            effective_endpoint = "discover/movie"
            extra_params.setdefault("sort_by", "primary_release_date.desc")

        end_val = args.page_end if args.page_end and args.page_end > 0 else None
        rows = fetch_tmdb_endpoint(
            endpoint=effective_endpoint,
            params=extra_params,
            pages=args.pages,
            page_start=args.page_start,
            page_end=end_val,
        )
        # Filter out records without a valid release_date (skip both Snowflake and CSV)
        rows = [r for r in rows if _safe_date_from_str(r.get("release_date")) is not None]
        try:
            loaded = load_rows_into_snowflake(rows)
            print(f"Inserted {loaded} row(s) into Snowflake table")
        except Exception as exc:
            raise SystemExit(f"Failed loading into Snowflake: {exc}")

        if args.write_csv:
            write_csv(rows, args.output)
            print(f"Wrote {len(rows)} row(s) to {args.output}")

    if args.schedule_daily:
        schedule.clear()
        schedule.every().day.at(args.schedule_daily).do(run_pipeline_once)
        print(f"Scheduled daily run at {args.schedule_daily}. Press Ctrl+C to exit.")
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        run_pipeline_once()


if __name__ == "__main__":
    main()
