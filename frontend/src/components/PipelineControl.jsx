import { useState, useEffect } from 'react'
import axios from 'axios'
import './PipelineControl.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function PipelineControl() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    endpoint: 'movie/popular',
    pages: 1,
    page_start: 1,
    page_end: '',
    primary_release_date_gte: '',
    primary_release_date_lte: '',
    since_days: '',
    use_discover: false,
    params: ''
  })

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Poll every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/pipeline/status`)
      console.log('Pipeline status:', response.data)
      setStatus(response.data)
    } catch (err) {
      console.error('Error fetching status:', err)
      setStatus({ status: 'error', message: err.message })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const payload = {
        ...formData,
        pages: parseInt(formData.pages) || 1,
        page_start: parseInt(formData.page_start) || 1,
        page_end: formData.page_end ? parseInt(formData.page_end) : null,
        since_days: formData.since_days ? parseInt(formData.since_days) : null,
        use_discover: formData.use_discover
      }
      
      console.log('Running pipeline with payload:', payload)
      const response = await axios.post(`${API_BASE}/api/pipeline/run`, payload)
      console.log('Pipeline run response:', response.data)
      await fetchStatus()
    } catch (err) {
      console.error('Error running pipeline:', err)
      alert(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="pipeline-control">
      <h2>Pipeline Control</h2>
      
      {status && (
        <div className={`status-badge status-${status.status}`}>
          Status: {status.status}
          {status.message && <p>{status.message}</p>}
        </div>
      )}

      <form onSubmit={handleSubmit} className="pipeline-form">
        <div className="form-group">
          <label>Endpoint</label>
          <input
            type="text"
            value={formData.endpoint}
            onChange={(e) => setFormData({...formData, endpoint: e.target.value})}
            placeholder="movie/popular"
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Pages</label>
            <input
              type="number"
              value={formData.pages}
              onChange={(e) => setFormData({...formData, pages: e.target.value})}
              min="1"
            />
          </div>
          <div className="form-group">
            <label>Page Start</label>
            <input
              type="number"
              value={formData.page_start}
              onChange={(e) => setFormData({...formData, page_start: e.target.value})}
              min="1"
            />
          </div>
          <div className="form-group">
            <label>Page End (optional)</label>
            <input
              type="number"
              value={formData.page_end}
              onChange={(e) => setFormData({...formData, page_end: e.target.value})}
              min="1"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Since Days (optional)</label>
            <input
              type="number"
              value={formData.since_days}
              onChange={(e) => setFormData({...formData, since_days: e.target.value})}
              min="1"
            />
          </div>
          <div className="form-group">
            <label>Release Date From</label>
            <input
              type="date"
              value={formData.primary_release_date_gte}
              onChange={(e) => setFormData({...formData, primary_release_date_gte: e.target.value})}
            />
          </div>
          <div className="form-group">
            <label>Release Date To</label>
            <input
              type="date"
              value={formData.primary_release_date_lte}
              onChange={(e) => setFormData({...formData, primary_release_date_lte: e.target.value})}
            />
          </div>
        </div>

        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={formData.use_discover}
              onChange={(e) => setFormData({...formData, use_discover: e.target.checked})}
            />
            Use Discover Endpoint
          </label>
        </div>

        <div className="form-group">
          <label>Extra Params (JSON)</label>
          <textarea
            value={formData.params}
            onChange={(e) => setFormData({...formData, params: e.target.value})}
            placeholder='{"with_original_language":"en"}'
            rows="3"
          />
        </div>

        <button type="submit" disabled={loading} className="submit-button">
          {loading ? 'Running...' : 'Run Pipeline'}
        </button>
      </form>
    </div>
  )
}

export default PipelineControl

