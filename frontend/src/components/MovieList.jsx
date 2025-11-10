import { useState, useEffect } from 'react'
import axios from 'axios'
import './MovieList.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function MovieList() {
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({
    min_vote_average: '',
    min_vote_count: '',
    release_date_from: '',
    release_date_to: '',
    year: ''
  })
  const [orderBy, setOrderBy] = useState('release_date')
  const [orderDirection, setOrderDirection] = useState('desc')

  const limit = 20

  useEffect(() => {
    fetchMovies()
  }, [page, search, filters, orderBy, orderDirection])

  const fetchMovies = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {
        limit,
        offset: (page - 1) * limit,
      }
      
      if (search) params.search = search
      if (filters.min_vote_average && filters.min_vote_average !== '') {
        params.min_vote_average = parseFloat(filters.min_vote_average)
      }
      if (filters.min_vote_count && filters.min_vote_count !== '') {
        params.min_vote_count = parseInt(filters.min_vote_count)
      }
      if (filters.release_date_from) params.release_date_from = filters.release_date_from
      if (filters.release_date_to) params.release_date_to = filters.release_date_to
      if (filters.year && filters.year !== '') {
        params.year = parseInt(filters.year)
      }
      
      if (orderBy) {
        params.order_by = orderBy
        params.order_direction = orderDirection
      }

      console.log('Fetching movies from:', `${API_BASE}/api/movies/`, params)
      const response = await axios.get(`${API_BASE}/api/movies/`, { params })
      console.log('Movies response:', response.data)
      console.log('Number of movies:', response.data?.length || 0)
      setMovies(response.data || [])
    } catch (err) {
      console.error('Error fetching movies:', err)
      const errorMessage = err.response?.data?.detail || err.message || 'Network Error - Is the backend running?'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1) // Reset to first page on filter change
  }

  return (
    <div className="movie-list">
      <div className="movie-list-header">
        <h2>Movies</h2>
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search movies..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
        </div>
      </div>

      <div className="filters">
        <div className="filter-group">
          <label>Min Rating</label>
          <select
            value={filters.min_vote_average}
            onChange={(e) => handleFilterChange('min_vote_average', e.target.value)}
            className={filters.min_vote_average ? 'filter-active' : ''}
          >
            <option value="">All</option>
            <option value="0">0+</option>
            <option value="1">1+</option>
            <option value="2">2+</option>
            <option value="3">3+</option>
            <option value="4">4+</option>
            <option value="5">5+</option>
            <option value="6">6+</option>
            <option value="7">7+</option>
            <option value="8">8+</option>
            <option value="9">9+</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Min Vote Count</label>
          <select
            value={filters.min_vote_count}
            onChange={(e) => handleFilterChange('min_vote_count', e.target.value)}
            className={filters.min_vote_count ? 'filter-active' : ''}
          >
            <option value="">All</option>
            <option value="10">10+</option>
            <option value="50">50+</option>
            <option value="100">100+</option>
            <option value="500">500+</option>
            <option value="1000">1,000+</option>
            <option value="5000">5,000+</option>
            <option value="10000">10,000+</option>
            <option value="20000">20,000+</option>
            <option value="30000">30,000+</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Release Date From</label>
          <input
            type="date"
            value={filters.release_date_from}
            onChange={(e) => handleFilterChange('release_date_from', e.target.value)}
            className={filters.release_date_from ? 'filter-active' : ''}
          />
        </div>
        <div className="filter-group">
          <label>Release Date To</label>
          <input
            type="date"
            value={filters.release_date_to}
            onChange={(e) => handleFilterChange('release_date_to', e.target.value)}
            className={filters.release_date_to ? 'filter-active' : ''}
          />
        </div>
        <div className="filter-group">
          <label>Year</label>
          <select
            value={filters.year}
            onChange={(e) => handleFilterChange('year', e.target.value)}
            className={filters.year ? 'filter-active' : ''}
          >
            <option value="">All</option>
            {Array.from({ length: 125 }, (_, i) => {
              const currentYear = new Date().getFullYear();
              const year = currentYear - i; // Start from current year and go back
              return (
                <option key={year} value={year}>
                  {year}
                </option>
              );
            })}
          </select>
        </div>
        <div className="filter-group">
          <label>Order By</label>
          <select
            value={orderBy}
            onChange={(e) => setOrderBy(e.target.value)}
            className={orderBy ? 'filter-active' : ''}
          >
            <option value="release_date">Release Date</option>
            <option value="vote_average">Rating</option>
            <option value="vote_count">Vote Count</option>
            <option value="title">Title</option>
          </select>
        </div>
        <div className="filter-group">
          <label>Direction</label>
          <select
            value={orderDirection}
            onChange={(e) => setOrderDirection(e.target.value)}
            className={orderDirection ? 'filter-active' : ''}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </div>
      </div>

      {loading && <div className="loading">Loading movies...</div>}
      {error && <div className="error">Error: {error}</div>}
      {!loading && !error && movies.length === 0 && (
        <div className="no-movies">No movies found. Try adjusting your filters or check if data exists in Snowflake.</div>
      )}

      <div className="movies-grid">
        {movies.length > 0 && movies.map(movie => (
          <div key={movie.id} className="movie-card">
            {movie.poster_path && (
              <img
                src={`https://image.tmdb.org/t/p/w200${movie.poster_path}`}
                alt={movie.title || movie.original_title}
                className="movie-poster"
              />
            )}
            <div className="movie-info">
              <h3>{movie.title || movie.original_title}</h3>
              {movie.release_date && (
                <p className="release-date">{new Date(movie.release_date).getFullYear()}</p>
              )}
              {movie.vote_average && (
                <p className="vote-average">
                  ⭐ {movie.vote_average.toFixed(1)}
                  {movie.vote_count && (
                    <span className="vote-count"> ({movie.vote_count.toLocaleString()} votes)</span>
                  )}
                </p>
              )}
              {movie.overview && (
                <p className="overview">{movie.overview}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="pagination">
        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button
          onClick={() => setPage(p => p + 1)}
          disabled={movies.length < limit}
        >
          Next
        </button>
      </div>
    </div>
  )
}

export default MovieList

