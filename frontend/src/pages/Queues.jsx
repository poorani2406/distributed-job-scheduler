// frontend/src/pages/Queues.jsx
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'

export default function Queues() {
  const { projectId } = useParams()
  const [queues, setQueues] = useState([])
  const [form, setForm] = useState({ name: '', max_concurrency: 5 })

  const load = () => api.listQueues(projectId).then(setQueues)
  useEffect(() => { load() }, [projectId])

  const create = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) return
    await api.createQueue(projectId, form)
    setForm({ name: '', max_concurrency: 5 })
    load()
  }

  const togglePause = async (q) => {
    if (q.is_paused) await api.resumeQueue(projectId, q.id)
    else await api.pauseQueue(projectId, q.id)
    load()
  }

  const updateConcurrency = async (q, val) => {
    await api.updateQueue(projectId, q.id, { max_concurrency: Number(val) })
    load()
  }

  return (
    <div>
      <h2>Queues</h2>
      <form onSubmit={create} className="inline-form">
        <input placeholder="Queue name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input type="number" min="1" value={form.max_concurrency} onChange={(e) => setForm({ ...form, max_concurrency: e.target.value })} />
        <button type="submit">Create</button>
      </form>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Concurrency</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {queues.map((q) => (
            <tr key={q.id}>
              <td><Link to={`/projects/${projectId}/queues/${q.id}/jobs`}>{q.name}</Link></td>
              <td>
                <input type="number" min="1" defaultValue={q.max_concurrency}
                  onBlur={(e) => updateConcurrency(q, e.target.value)} style={{ width: 60 }} />
              </td>
              <td>{q.is_paused ? 'Paused' : 'Active'}</td>
              <td><button onClick={() => togglePause(q)}>{q.is_paused ? 'Resume' : 'Pause'}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}