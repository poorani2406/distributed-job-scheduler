// frontend/src/pages/Projects.jsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function Projects() {
  const [projects, setProjects] = useState([])
  const [name, setName] = useState('')

  const load = () => api.listProjects().then(setProjects)
  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    await api.createProject(name)
    setName('')
    load()
  }

  return (
    <div>
      <h2>Projects</h2>
      <form onSubmit={create} className="inline-form">
        <input placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit">Create</button>
      </form>
      <ul className="list">
        {projects.map((p) => (
          <li key={p.id}>
            <Link to={`/projects/${p.id}/queues`}>{p.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  )
}