// frontend/src/pages/Jobs.jsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api.js'

const STATUSES = ['', 'pending', 'scheduled', 'running', 'succeeded', 'failed', 'retrying', 'dead', 'cancelled']

export default function Jobs() {
  const { projectId, queueId } = useParams()
  const [jobs, setJobs] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [form, setForm] = useState({ name: 'default', payload: '{}', priority: 0, delaySeconds: 0, cron_expression: '' })
  const [selectedJob, setSelectedJob] = useState(null)
  const [executions, setExecutions] = useState([])

  const load = () => api.listJobs(queueId, statusFilter || undefined).then(setJobs)
  useEffect(() => { load() }, [queueId, statusFilter])
  useEffect(() => { const id = setInterval(load, 4000); return () => clearInterval(id) }, [queueId, statusFilter])

  const submit = async (e) => {
    e.preventDefault()
    let payload = {}
    try { payload = JSON.parse(form.payload) } catch { /* ignore bad json */ }
    const run_at = form.delaySeconds > 0
      ? new Date(Date.now() + form.delaySeconds * 1000).toISOString()
      : null
    await api.createJob(queueId, {
      name: form.name,
      payload,
      priority: Number(form.priority),
      run_at,
      cron_expression: form.cron_expression || null,
    })
    load()
  }

  const viewJob = async (job) => {
    setSelectedJob(job)
    setExecutions(await api.getJobExecutions(job.id))
  }

  const cancel = async (id) => { await api.cancelJob(id); load() }
  const retry = async (id) => { await api.retryJob(id); load() }

  return (
    <div className="jobs-layout">
      <div>
        <h2>Jobs</h2>
        <form onSubmit={submit} className="job-form">
          <input placeholder="handler name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input placeholder="payload JSON" value={form.payload} onChange={(e) => setForm({ ...form, payload: e.target.value })} />
          <input type="number" placeholder="priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} />
          <input type="number" placeholder="delay seconds" value={form.delaySeconds} onChange={(e) => setForm({ ...form, delaySeconds: Number(e.target.value) })} />
          <input placeholder="cron (optional)" value={form.cron_expression} onChange={(e) => setForm({ ...form, cron_expression: e.target.value })} />
          <button type="submit">Submit Job</button>
        </form>

        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'all'}</option>)}
        </select>

        <table className="table">
          <thead><tr><th>Name</th><th>Status</th><th>Priority</th><th>Retries</th><th>Actions</th></tr></thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className={`status-${j.status}`}>
                <td><a onClick={() => viewJob(j)} style={{ cursor: 'pointer' }}>{j.name}</a></td>
                <td>{j.status}</td>
                <td>{j.priority}</td>
                <td>{j.retry_count}/{j.max_retries}</td>
                <td>
                  {['pending', 'scheduled', 'retrying'].includes(j.status) && <button onClick={() => cancel(j.id)}>Cancel</button>}
                  {j.status === 'dead' && <button onClick={() => retry(j.id)}>Retry</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedJob && (
        <div className="job-detail">
          <h3>{selectedJob.name}</h3>
          <pre>{JSON.stringify(selectedJob.payload, null, 2)}</pre>
          <h4>Execution History</h4>
          {executions.map((ex) => (
            <div key={ex.id} className="exec-row">
              <div>#{ex.attempt} — {ex.status}</div>
              <div>{new Date(ex.started_at).toLocaleString()}</div>
              {ex.error && <pre className="error">{ex.error}</pre>}
              {ex.logs && <pre>{ex.logs}</pre>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
