# CulturaDB

A unified data hub for movies and books, powered by Python and Snowflake.

## Overview

CulturaDB is a data pipeline that fetches movie data from The Movie Database (TMDB) API and loads it into Snowflake with automatic deduplication and incremental updates. The pipeline supports flexible filtering, pagination, and optional CSV export.

## Features

- **TMDB Integration**: Fetches movie data from TMDB API (v3/v4)
- **Snowflake Loading**: Automatic upsert/merge into Snowflake with deduplication by (id, release_date)
- **Incremental Updates**: Date-based filtering to fetch only new or updated movies
- **Flexible Pagination**: Support for page ranges and limits to manage API rate limits
- **Optional CSV Export**: Write results to local CSV files
- **Daily Scheduling**: Run the pipeline automatically at specified times
- **Data Quality**: Filters out records without valid release dates

## Setup

### Prerequisites

- Python 3.10+ (Python 3.12 recommended)
- Snowflake account with appropriate permissions
- TMDB API credentials (v4 access token preferred, or v3 API key)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/stephsiorek/CulturaDB.git
   cd CulturaDB
   ```

2. Create a virtual environment:
   ```bash
   python -m venv pythonenv
   source pythonenv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your credentials:
   ```env
   # TMDB API (choose one)
   TMDB_ACCESS_TOKEN=your_v4_bearer_token  # preferred
   TMDB_API_KEY=your_v3_api_key            # fallback

   # Snowflake
   SNOWFLAKE_ACCOUNT=your_account
   SNOWFLAKE_USER=your_username
   SNOWFLAKE_PASSWORD=your_password
   SNOWFLAKE_WAREHOUSE=your_warehouse
   SNOWFLAKE_DATABASE=your_database
   SNOWFLAKE_SCHEMA=your_schema
   SNOWFLAKE_ROLE=your_role
   SNOWFLAKE_TABLE=TMDB_MOVIES
   ```

## Movies Pipeline

### Quick Start

Fetch 1 page of popular movies and load to Snowflake:
```bash
python movies.py
```

### Common Usage Examples

**Incremental daily load (last 1 day):**
```bash
python movies.py --since-days 1
```

**Fetch last 7 days with 3 pages:**
```bash
python movies.py --since-days 7 --pages 3
```

**Explicit date range:**
```bash
python movies.py --primary-release-date-gte 2025-10-01 --primary-release-date-lte 2025-10-31
```

**Fetch specific page range (e.g., pages 6-10):**
```bash
python movies.py --page-start 6 --page-end 10
```

**Also write to CSV:**
```bash
python movies.py --since-days 7 --write-csv --output movies.csv
```

**Schedule daily at 02:30:**
```bash
python movies.py --since-days 1 --schedule-daily 02:30
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--endpoint` | TMDB endpoint path | `movie/popular` |
| `--pages` | Number of pages to fetch | `1` |
| `--page-start` | First page to fetch | `1` |
| `--page-end` | Last page (inclusive, overrides `--pages`) | `0` (disabled) |
| `--write-csv` | Also write to CSV | `False` |
| `--output` | CSV output path | `tmdb_output.csv` |
| `--params` | Extra query params (JSON) | `""` |
| `--schedule-daily` | Daily schedule (HH:MM) | `""` (disabled) |
| `--primary-release-date-gte` | Filter: release date >= (YYYY-MM-DD) | `""` |
| `--primary-release-date-lte` | Filter: release date <= (YYYY-MM-DD) | `""` |
| `--since-days` | Shortcut: last N days | `0` (disabled) |
| `--use-discover` | Force `discover/movie` endpoint | `False` |

### Snowflake Table Schema

The pipeline expects a table with the following schema:

```sql
CREATE TABLE tmdb_movies (
  id BIGINT,
  title VARCHAR,
  original_title VARCHAR,
  release_date DATE,
  overview VARCHAR,
  vote_average NUMBER(5,3),
  vote_count BIGINT,
  popularity NUMBER(12,4),
  adult BOOLEAN,
  genre_ids VARCHAR,              -- JSON array stored as string
  original_language VARCHAR,
  backdrop_path VARCHAR,
  poster_path VARCHAR,
  video BOOLEAN,
  ds DATE                         -- Data snapshot date (UTC)
);
```

### Deduplication

The pipeline automatically deduplicates records by `(id, release_date)`:
- **Upsert logic**: Updates existing records, keeps earliest `ds` (data snapshot date)
- **Source deduplication**: Removes duplicates within the same fetch batch
- **Null-safe matching**: Handles NULL release dates correctly

### Error Handling

- **Rate limits (429)**: Clear error message with Retry-After header
- **Page limits (400)**: Detects when exceeding TMDB's ~500 page limit
- **Auth errors (401)**: Helpful guidance for credential issues
- **Invalid dates**: Automatically filters out records without valid release dates

## Books Pipeline

**Status**: TBD (To Be Done)

The books pipeline is planned for future implementation.
