// frontend/src/App.jsx
import { Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Projects from './pages/Projects.jsx'
import Queues from './pages/Queues.jsx'
import Jobs from './pages/Jobs.jsx'
import Workers from './pages/Workers.jsx'
import Metrics from './pages/Metrics.jsx'

function Private({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="center">Loading...</div>
  if (!user) return <Navigate to="/login" />
  return children
}

function Shell({ children }) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div>
      <header className="topbar">
        <Link to="/projects" className="brand">Job Scheduler</Link>
        <nav>
          <Link to="/projects">Projects</Link>
          <Link to="/workers">Workers</Link>
          <Link to="/metrics">Metrics</Link>
        </nav>
        {user && (
          <div className="user-box">
            <span>{user.email}</span>
            <button onClick={() => { logout(); nav('/login') }}>Logout</button>
          </div>
        )}
      </header>
      <main className="content">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/projects" element={<Private><Shell><Projects /></Shell></Private>} />
        <Route path="/projects/:projectId/queues" element={<Private><Shell><Queues /></Shell></Private>} />
        <Route path="/projects/:projectId/queues/:queueId/jobs" element={<Private><Shell><Jobs /></Shell></Private>} />
        <Route path="/workers" element={<Private><Shell><Workers /></Shell></Private>} />
        <Route path="/metrics" element={<Private><Shell><Metrics /></Shell></Private>} />
        <Route path="*" element={<Navigate to="/projects" />} />
      </Routes>
    </AuthProvider>
  )
}