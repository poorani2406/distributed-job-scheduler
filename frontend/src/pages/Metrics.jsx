// frontend/src/pages/Metrics.jsx
import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Metrics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    api.metrics()
      .then(setData)
      .catch((err) => console.error("Metrics load failure", err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])

  if (loading) return <div className="center">Loading Dashboard Metrics...</div>
  if (!data) return <div className="center error">Failed to load metrics. Check API status.</div>

  // Calculate some simple insights
  const totalJobs = Object.values(data.jobs_by_status).reduce((a, b) => a + b, 0)
  const succeededCount = data.jobs_by_status['succeeded'] || 0
  const failedCount = (data.jobs_by_status['failed'] || 0) + (data.jobs_by_status['dead'] || 0)
  const successRate = totalJobs > 0 ? ((succeededCount / (succeededCount + failedCount || 1)) * 100).toFixed(1) : '100'

  const activeWorkers = Object.values(data.workers_by_status).reduce((a, b) => a + b, 0)

  return (
    <div>
      <h2>System Dashboard & Metrics</h2>
      
      <div className="metric-cards">
        <div className="metric-card running">
          <div className="metric-value">{data.jobs_by_status['running'] || 0}</div>
          <div className="metric-label">Running Jobs</div>
        </div>
        <div className="metric-card pending">
          <div className="metric-value">
            {(data.jobs_by_status['pending'] || 0) + 
             (data.jobs_by_status['scheduled'] || 0) + 
             (data.jobs_by_status['retrying'] || 0)}
          </div>
          <div className="metric-label">Queued / Scheduled</div>
        </div>
        <div className="metric-card succeeded">
          <div className="metric-value">{succeededCount}</div>
          <div className="metric-label">Total Succeeded</div>
        </div>
        <div className="metric-card dead">
          <div className="metric-value">{data.jobs_by_status['dead'] || 0}</div>
          <div className="metric-label">DLQ / Dead Jobs</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{data.succeeded_last_hour}</div>
          <div className="metric-label">Throughput (Succeeded 1h)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{successRate}%</div>
          <div className="metric-label">Success Rate</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{activeWorkers}</div>
          <div className="metric-label">Active Workers</div>
        </div>
      </div>

      <div style={{ marginTop: 40 }}>
        <h3>Queue Performance</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Queue Name</th>
              <th>Active Jobs</th>
              <th>Queued / Retry</th>
              <th>Dead (DLQ)</th>
              <th>Concurrency Limit</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.queues.map((q) => (
              <tr key={q.id}>
                <td><strong>{q.name}</strong></td>
                <td><span className="status-running" style={{ padding: '2px 8px', borderRadius: 4 }}>{q.running}</span></td>
                <td><span className="status-pending" style={{ padding: '2px 8px', borderRadius: 4 }}>{q.queued}</span></td>
                <td>
                  <span className={q.dead > 0 ? "status-dead" : ""} style={{ padding: '2px 8px', borderRadius: 4 }}>
                    {q.dead}
                  </span>
                </td>
                <td>{q.max_concurrency}</td>
                <td>
                  <span className={q.is_paused ? "status-dead" : "status-succeeded"} style={{ padding: '4px 8px', borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
                    {q.is_paused ? 'Paused' : 'Active'}
                  </span>
                </td>
              </tr>
            ))}
            {data.queues.length === 0 && (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', color: '#666' }}>No active queues found. Create one in a project.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 40, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div>
          <h3>Worker Node Distribution</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Workers Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.workers_by_status).map(([status, count]) => (
                <tr key={status}>
                  <td>
                    <span className={status === 'online' ? "status-succeeded" : "status-dead"} style={{ padding: '4px 8px', borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
                      {status.toUpperCase()}
                    </span>
                  </td>
                  <td>{count}</td>
                </tr>
              ))}
              {Object.keys(data.workers_by_status).length === 0 && (
                <tr>
                  <td colSpan="2" style={{ textAlign: 'center', color: '#666' }}>No workers registered.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}