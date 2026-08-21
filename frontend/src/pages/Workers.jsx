// frontend/src/pages/Workers.jsx
import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Workers() {
  const [workers, setWorkers] = useState([])
  const load = () => api.listWorkers().then(setWorkers)
  useEffect(() => { load(); const id = setInterval(load, 4000); return () => clearInterval(id) }, [])

  return (
    <div>
      <h2>Workers</h2>
      <table className="table">
        <thead><tr><th>Host</th><th>Status</th><th>Concurrency</th><th>Last Heartbeat</th></tr></thead>
        <tbody>
          {workers.map((w) => (
            <tr key={w.id}>
              <td>{w.hostname}</td>
              <td>{w.status}</td>
              <td>{w.concurrency}</td>
              <td>{new Date(w.last_heartbeat).toLocaleTimeString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}