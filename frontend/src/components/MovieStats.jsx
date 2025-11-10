import { useState, useEffect } from 'react'
import axios from 'axios'
import './MovieStats.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function MovieStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('Fetching stats from:', `${API_BASE}/api/movies/stats/summary`)
      const response = await axios.get(`${API_BASE}/api/movies/stats/summary`)
      console.log('Stats response:', response.data)
      setStats(response.data)
    } catch (err) {
      console.error('Error fetching stats:', err)
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="stats-container">Loading statistics...</div>
  if (error) return <div className="stats-container error">Error: {error}</div>
  if (!stats) return <div className="stats-container">No statistics available</div>

  return (
    <div className="stats-container">
      <h2>Movie Statistics</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Movies</h3>
          <p className="stat-value">{stats.total_movies?.toLocaleString() || 0}</p>
        </div>
        <div className="stat-card">
          <h3>With Release Date</h3>
          <p className="stat-value">{stats.movies_with_release_date?.toLocaleString() || 0}</p>
        </div>
        <div className="stat-card">
          <h3>Average Vote</h3>
          <p className="stat-value">
            {stats.avg_vote_average ? stats.avg_vote_average.toFixed(2) : 'N/A'}
          </p>
        </div>
        <div className="stat-card">
          <h3>Average Popularity</h3>
          <p className="stat-value">
            {stats.avg_popularity ? stats.avg_popularity.toFixed(2) : 'N/A'}
          </p>
        </div>
        <div className="stat-card">
          <h3>Latest Snapshot</h3>
          <p className="stat-value">
            {stats.latest_snapshot_date 
              ? new Date(stats.latest_snapshot_date).toLocaleDateString()
              : 'N/A'}
          </p>
        </div>
      </div>
    </div>
  )
}

export default MovieStats

