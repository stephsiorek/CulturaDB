"""
Snowflake service for querying movie data
"""
import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import date
from dotenv import load_dotenv
import snowflake.connector
from concurrent.futures import ThreadPoolExecutor

load_dotenv()


class SnowflakeService:
    """Service for querying Snowflake database"""
    
    def __init__(self):
        self.account = os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = os.getenv("SNOWFLAKE_USER")
        self.password = os.getenv("SNOWFLAKE_PASSWORD")
        self.warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
        self.database = os.getenv("SNOWFLAKE_DATABASE")
        self.schema = os.getenv("SNOWFLAKE_SCHEMA")
        self.role = os.getenv("SNOWFLAKE_ROLE")
        self.table = os.getenv("SNOWFLAKE_TABLE", "TMDB_MOVIES")
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def _get_connection(self):
        """Get Snowflake connection"""
        return snowflake.connector.connect(
            account=self.account,
            user=self.user,
            password=self.password,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
            role=self.role or None,
        )
    
    async def _run_query(self, query: str, params: Optional[Dict] = None):
        """Run a query asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._execute_query, query, params)
    
    def _transform_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Snowflake row to API format - normalize column names to lowercase"""
        from datetime import date, datetime
        
        transformed = {}
        for key, value in row.items():
            # Normalize column name to lowercase (Snowflake returns uppercase)
            normalized_key = key.lower()
            
            if value is None:
                transformed[normalized_key] = None
            elif isinstance(value, (date, datetime)):
                # Convert date/datetime to date object
                if isinstance(value, datetime):
                    transformed[normalized_key] = value.date()
                else:
                    transformed[normalized_key] = value
            elif isinstance(value, (int, float, str, bool)):
                transformed[normalized_key] = value
            else:
                # Convert other types to string
                transformed[normalized_key] = str(value)
        return transformed
    
    def _execute_query(self, query: str, params: Optional[Dict] = None):
        """Execute a query synchronously"""
        # Validate connection parameters
        if not all([self.account, self.user, self.password, self.warehouse, self.database, self.schema]):
            missing = [k for k, v in {
                "account": self.account,
                "user": self.user,
                "password": self.password,
                "warehouse": self.warehouse,
                "database": self.database,
                "schema": self.schema
            }.items() if not v]
            raise ValueError(f"Missing Snowflake env vars: {', '.join(missing)}")
        
        ctx = self._get_connection()
        try:
            cs = ctx.cursor()
            try:
                if params:
                    cs.execute(query, params)
                else:
                    cs.execute(query)
                columns = [desc[0] for desc in cs.description] if cs.description else []
                rows = cs.fetchall()
                print(f"Fetched {len(rows)} rows from Snowflake")
                if len(rows) > 0:
                    print(f"First row raw: {rows[0]}")
                    print(f"Columns: {columns}")
                
                # Transform rows to dictionaries and normalize data types
                result = []
                for idx, row in enumerate(rows):
                    row_dict = dict(zip(columns, row))
                    if idx == 0:
                        print(f"First row dict before transform: {row_dict}")
                    transformed = self._transform_row(row_dict)
                    if idx == 0:
                        print(f"First row dict after transform: {transformed}")
                    result.append(transformed)
                print(f"Transformed {len(result)} rows")
                return result
            finally:
                cs.close()
        finally:
            ctx.close()
    
    async def get_movies(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        min_vote_average: Optional[float] = None,
        min_popularity: Optional[float] = None,
        min_vote_count: Optional[int] = None,
        release_date_from: Optional[date] = None,
        release_date_to: Optional[date] = None,
        year: Optional[int] = None,
        order_by: Optional[str] = "release_date",
        order_direction: Optional[str] = "desc",
    ) -> List[Dict[str, Any]]:
        """Get movies with optional filtering"""
        conditions = []
        params = {}
        
        if search:
            conditions.append("(LOWER(title) LIKE LOWER(%(search)s) OR LOWER(original_title) LIKE LOWER(%(search)s))")
            params["search"] = f"%{search}%"
        
        if min_vote_average is not None:
            conditions.append("vote_average >= %(min_vote_average)s")
            params["min_vote_average"] = min_vote_average
        
        if min_popularity is not None:
            conditions.append("popularity >= %(min_popularity)s")
            params["min_popularity"] = min_popularity
        
        if min_vote_count is not None:
            conditions.append("vote_count >= %(min_vote_count)s")
            params["min_vote_count"] = min_vote_count
        
        if release_date_from:
            conditions.append("release_date >= %(release_date_from)s")
            params["release_date_from"] = release_date_from.isoformat()
        
        if release_date_to:
            conditions.append("release_date <= %(release_date_to)s")
            params["release_date_to"] = release_date_to.isoformat()
        
        if year is not None:
            # Filter by year using EXTRACT(YEAR FROM release_date)
            conditions.append("EXTRACT(YEAR FROM release_date) = %(year)s")
            params["year"] = year
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Validate and sanitize order_by field
        valid_order_fields = {
            "release_date": "release_date",
            "vote_average": "vote_average",
            "vote_count": "vote_count",
            "title": "title"
        }
        order_field = valid_order_fields.get(order_by, "release_date")
        
        # Validate order direction
        order_dir = "DESC" if order_direction and order_direction.lower() == "desc" else "ASC"
        
        query = f"""
        SELECT 
            id, title, original_title, release_date, overview,
            vote_average, vote_count, popularity, adult, genre_ids,
            original_language, backdrop_path, poster_path, video, ds
        FROM {self.table}
        {where_clause}
        ORDER BY {order_field} {order_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """
        params["limit"] = limit
        params["offset"] = offset
        
        print(f"Executing query: {query}")
        print(f"With params: {params}")
        results = await self._run_query(query, params)
        print(f"Query returned {len(results)} rows")
        return results
    
    async def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get a movie by ID"""
        query = f"""
        SELECT 
            id, title, original_title, release_date, overview,
            vote_average, vote_count, popularity, adult, genre_ids,
            original_language, backdrop_path, poster_path, video, ds
        FROM {self.table}
        WHERE id = %(movie_id)s
        ORDER BY ds DESC
        LIMIT 1
        """
        params = {"movie_id": movie_id}
        results = await self._run_query(query, params)
        return results[0] if results else None
    
    async def get_movie_stats(self) -> Dict[str, Any]:
        """Get movie statistics"""
        query = f"""
        SELECT 
            COUNT(*) as total_movies,
            COUNT(release_date) as movies_with_release_date,
            AVG(vote_average) as avg_vote_average,
            AVG(popularity) as avg_popularity,
            MAX(ds) as latest_snapshot_date
        FROM {self.table}
        """
        results = await self._run_query(query)
        return results[0] if results else {}

