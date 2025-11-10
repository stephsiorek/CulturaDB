"""
Movies API endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import date

from api.services.snowflake_service import SnowflakeService

router = APIRouter()


class MovieResponse(BaseModel):
    """Movie response model"""
    id: int
    title: Optional[str] = None
    original_title: Optional[str] = None
    release_date: Optional[date] = None
    overview: Optional[str] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    adult: Optional[bool] = None
    genre_ids: Optional[str] = None
    original_language: Optional[str] = None
    backdrop_path: Optional[str] = None
    poster_path: Optional[str] = None
    video: Optional[bool] = None
    ds: Optional[date] = None


class MovieStatsResponse(BaseModel):
    """Movie statistics response model"""
    total_movies: int
    movies_with_release_date: int
    avg_vote_average: Optional[float] = None
    avg_popularity: Optional[float] = None
    latest_snapshot_date: Optional[date] = None


@router.get("/", response_model=List[MovieResponse])
async def get_movies(
    limit: int = Query(100, ge=1, le=1000, description="Number of movies to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search by title"),
    min_vote_average: Optional[float] = Query(None, ge=0, le=10, description="Minimum vote average"),
    min_popularity: Optional[float] = Query(None, ge=0, description="Minimum popularity"),
    min_vote_count: Optional[int] = Query(None, ge=0, le=40000, description="Minimum vote count"),
    release_date_from: Optional[date] = Query(None, description="Filter by release date from"),
    release_date_to: Optional[date] = Query(None, description="Filter by release date to"),
    year: Optional[int] = Query(None, ge=1900, le=2100, description="Filter by release year"),
    order_by: Optional[str] = Query("release_date", description="Order by field (release_date, vote_average, vote_count, title)"),
    order_direction: Optional[str] = Query("desc", description="Order direction (asc, desc)"),
):
    """
    Get movies from Snowflake with optional filtering and pagination
    """
    try:
        import traceback
        service = SnowflakeService()
        movies = await service.get_movies(
            limit=limit,
            offset=offset,
            search=search,
            min_vote_average=min_vote_average,
            min_popularity=min_popularity,
            min_vote_count=min_vote_count,
            release_date_from=release_date_from,
            release_date_to=release_date_to,
            year=year,
            order_by=order_by,
            order_direction=order_direction,
        )
        # Validate and convert to response model
        print(f"Received {len(movies)} movies from Snowflake")
        result = []
        for idx, movie in enumerate(movies):
            try:
                # Debug: print first movie structure
                if idx == 0:
                    print(f"First movie data: {movie}")
                    print(f"First movie keys: {list(movie.keys())}")
                    print(f"First movie id type: {type(movie.get('id'))}, value: {movie.get('id')}")
                
                # Ensure id is int (required field) - check both lowercase and uppercase
                movie_id = movie.get('id') or movie.get('ID')
                if movie_id is None:
                    print(f"Skipping movie at index {idx}: missing or None id")
                    continue
                movie['id'] = int(movie_id)
                validated = MovieResponse(**movie)
                result.append(validated)
            except Exception as e:
                print(f"Error validating movie {movie.get('id', 'unknown')} at index {idx}: {e}")
                print(f"Movie data: {movie}")
                import traceback
                print(traceback.format_exc())
                continue
        
        print(f"Successfully validated {len(result)} movies")
        return result
    except Exception as e:
        import traceback
        error_detail = f"Error fetching movies: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # Log to console
        raise HTTPException(status_code=500, detail=f"Error fetching movies: {str(e)}")


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie_by_id(movie_id: int):
    """
    Get a specific movie by ID
    """
    try:
        service = SnowflakeService()
        movie = await service.get_movie_by_id(movie_id)
        if not movie:
            raise HTTPException(status_code=404, detail=f"Movie with ID {movie_id} not found")
        # Ensure id is int
        movie['id'] = int(movie['id'])
        return MovieResponse(**movie)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching movie: {str(e)}")


@router.get("/stats/summary", response_model=MovieStatsResponse)
async def get_movie_stats():
    """
    Get movie statistics from Snowflake
    """
    try:
        import traceback
        service = SnowflakeService()
        stats = await service.get_movie_stats()
        print(f"Raw stats from Snowflake: {stats}")
        
        # Ensure required fields are present - normalize keys to lowercase
        if not stats:
            stats = {
                "total_movies": 0,
                "movies_with_release_date": 0,
                "avg_vote_average": None,
                "avg_popularity": None,
                "latest_snapshot_date": None
            }
        else:
            # Normalize keys to lowercase (Snowflake returns uppercase)
            normalized_stats = {}
            for key, value in stats.items():
                normalized_key = key.lower()
                normalized_stats[normalized_key] = value
            stats = normalized_stats
        
        # Ensure required int fields
        stats['total_movies'] = int(stats.get('total_movies', 0) or 0)
        stats['movies_with_release_date'] = int(stats.get('movies_with_release_date', 0) or 0)
        
        print(f"Normalized stats: {stats}")
        return MovieStatsResponse(**stats)
    except Exception as e:
        import traceback
        error_detail = f"Error fetching stats: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")

