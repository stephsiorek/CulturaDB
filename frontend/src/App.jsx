import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import axios from 'axios'
import './App.css'
import MovieList from './components/MovieList'
import MovieStats from './components/MovieStats'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function App() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    // Check API health
    axios.get(`${API_BASE}/api/health`)
      .then(res => {
        console.log('Health check successful:', res.data)
        setHealth(res.data)
      })
      .catch(err => {
        console.error('Health check failed:', err)
        setHealth({ status: 'error', message: err.message })
      })
    
    // Test endpoint
    axios.get(`${API_BASE}/api/test`)
      .then(res => console.log('Test endpoint successful:', res.data))
      .catch(err => console.error('Test endpoint failed:', err))
  }, [])

  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <h1>🎬 CulturaDB</h1>
          <nav>
            <Link to="/">Movies</Link>
            <Link to="/stats">Statistics</Link>
          </nav>
          {health && (
            <div className={`health-status ${health.status === 'healthy' ? 'healthy' : 'error'}`}>
              API: {health.status}
            </div>
          )}
        </header>

        <main className="app-main">
          <Routes>
            <Route path="/" element={<MovieList />} />
            <Route path="/stats" element={<MovieStats />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

