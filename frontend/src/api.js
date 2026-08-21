// frontend/src/api.js
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function authHeaders() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  register: (data) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (email, password) => {
    const form = new URLSearchParams()
    form.set('username', email)
    form.set('password', password)
    return fetch(`${BASE_URL}/api/auth/login`, { method: 'POST', body: form })
      .then(async (r) => {
        if (!r.ok) throw new Error('Invalid credentials')
        return r.json()
      })
  },
  me: () => request('/api/auth/me'),

  listProjects: () => request('/api/projects'),
  createProject: (name) => request('/api/projects', { method: 'POST', body: JSON.stringify({ name }) }),

  listQueues: (projectId) => request(`/api/projects/${projectId}/queues`),
  createQueue: (projectId, data) => request(`/api/projects/${projectId}/queues`, { method: 'POST', body: JSON.stringify(data) }),
  pauseQueue: (projectId, queueId) => request(`/api/projects/${projectId}/queues/${queueId}/pause`, { method: 'POST' }),
  resumeQueue: (projectId, queueId) => request(`/api/projects/${projectId}/queues/${queueId}/resume`, { method: 'POST' }),
  updateQueue: (projectId, queueId, data) => request(`/api/projects/${projectId}/queues/${queueId}`, { method: 'PATCH', body: JSON.stringify(data) }),

  listJobs: (queueId, status) => request(`/api/queues/${queueId}/jobs${status ? `?status=${status}` : ''}`),
  createJob: (queueId, data) => request(`/api/queues/${queueId}/jobs`, { method: 'POST', body: JSON.stringify(data) }),
  createBatch: (projectId, queueId, data) => request(`/api/projects/${projectId}/queues/${queueId}/batches`, { method: 'POST', body: JSON.stringify(data) }),
  getJob: (jobId) => request(`/api/jobs/${jobId}`),
  getJobExecutions: (jobId) => request(`/api/jobs/${jobId}/executions`),
  cancelJob: (jobId) => request(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),
  retryJob: (jobId) => request(`/api/jobs/${jobId}/retry`, { method: 'POST' }),

  listWorkers: () => request('/api/workers'),
  metrics: () => request('/api/metrics'),
  recentLogs: () => request('/api/logs/recent'),
}