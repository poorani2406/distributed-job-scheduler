// frontend/src/pages/Register.jsx
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'

export default function Register() {
  const { register } = useAuth()
  const [form, setForm] = useState({ email: '', password: '', org_name: '' })
  const [error, setError] = useState('')
  const nav = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await register(form)
      nav('/projects')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="auth-card">
      <h2>Register</h2>
      <form onSubmit={submit}>
        <input placeholder="Organization" value={form.org_name} onChange={(e) => setForm({ ...form, org_name: e.target.value })} />
        <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input placeholder="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button type="submit">Create account</button>
      </form>
      {error && <p className="error">{error}</p>}
      <p>Have an account? <Link to="/login">Login</Link></p>
    </div>
  )
}