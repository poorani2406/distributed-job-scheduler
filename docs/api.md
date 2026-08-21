# API Documentation

The platform provides a secure REST API for dashboard monitoring and worker daemon communication.

## 🔐 Authentication
All routes except `/api/auth/register` and `/api/auth/login` require JWT token authentication via header:
`Authorization: Bearer <JWT_TOKEN>`

---

## Endpoint Reference

### 1. Authentication
* **POST `/api/auth/register`**: Registers a new user.
  - *Payload*:
    ```json
    {"email": "operator@test.com", "password": "password123", "org_name": "AcmeCorp"}
    ```
* **POST `/api/auth/login`**: Obtains a JWT Token (OAuth2 Password flow).
  - *Form Data*: `username=operator@test.com&password=password123`
  - *Response*:
    ```json
    {"access_token": "eyJhbGciOi...", "token_type": "bearer"}
    ```
* **GET `/api/auth/me`**: Returns currently logged-in user profile.

### 2. Organizations & Projects
* **POST `/api/organizations`**: Creates a new organization.
* **POST `/api/projects`**: Creates a project under the user's organization.
  - *Payload*: `{"name": "DataPipeline"}`
* **GET `/api/projects`**: Lists projects owned by organization.
* **PATCH `/api/projects/{project_id}`**: Renames a project.
* **DELETE `/api/projects/{project_id}`**: Deletes a project and all its child resources.

### 3. Queues (Nested & Flat)
* **POST `/api/projects/{project_id}/queues`**: Creates a queue.
  - *Payload*:
    ```json
    {
      "name": "image-processing",
      "description": "Handles thumbnail resizing",
      "priority": 10,
      "max_concurrency": 2,
      "retry_policy_id": "8a32b21c..."
    }
    ```
* **GET `/api/projects/{project_id}/queues`**: Lists queues for a project with current statistics.
* **GET `/api/queues/{queue_id}`**: Returns flat queue details including stats.
* **PATCH `/api/queues/{queue_id}`**: Updates queue properties.
* **POST `/api/queues/{queue_id}/pause`**: Pauses queue execution.
* **POST `/api/queues/{queue_id}/resume`**: Resumes queue execution.
* **DELETE `/api/queues/{queue_id}`**: Deletes a queue.

### 4. Retry Policies
* **POST `/api/projects/{project_id}/retry-policies`**: Creates a retry policy.
  - *Payload*:
    ```json
    {"name": "ExponentialBackoff", "strategy": "exponential", "max_retries": 3, "delay_seconds": 10}
    ```
* **GET `/api/projects/{project_id}/retry-policies`**: Lists policies for a project.
* **DELETE `/api/retry-policies/{policy_id}`**: Deletes a policy.

### 5. Jobs Submission & Management
* **POST `/api/queues/{queue_id}/jobs`**: Submits a single job.
  - *Payload (Immediate)*: `{"name": "resize_image", "payload": {"img": "http://..."}}`
  - *Payload (Delayed)*: `{"name": "clean_tmp", "job_type": "delayed", "delay_seconds": 60}`
  - *Payload (Recurring)*: `{"name": "hourly_report", "cron_expression": "0 * * * *"}`
* **POST `/api/projects/{project_id}/queues/{queue_id}/batches`**: Submits a batch of jobs.
  - *Payload*:
    ```json
    {
      "batch_name": "nightly-cleanup",
      "jobs": [
        {"name": "clear_logs", "idempotency_key": "log-day1"},
        {"name": "clear_temp", "idempotency_key": "temp-day1"}
      ]
    }
    ```
* **GET `/api/jobs/{job_id}`**: Returns job details.
* **GET `/api/jobs/dlq`**: Lists dead letter queue jobs for the user's organization.
* **GET `/api/jobs/{job_id}/executions`**: Lists the execution history of a job.
* **GET `/api/jobs/{job_id}/logs`**: Returns state transition and execution audit logs.
* **POST `/api/jobs/{job_id}/cancel`**: Cancels a pending, scheduled, or retrying job.
* **POST `/api/jobs/{job_id}/retry`**: Resets a dead letter queue job back to pending.

### 6. Workers API
* **POST `/api/workers/register`**: Registers a worker node.
  - *Payload*: `{"hostname": "worker-us-east-1", "concurrency": 8}`
* **GET `/api/workers`**: Lists registered workers.
* **POST `/api/workers/claim`**: Polls and claims jobs.
  - *Payload*: `{"worker_id": "f5b21d...", "limit": 4}`
* **POST `/api/workers/heartbeat`**: Reports active jobs to maintain online status.
  - *Payload*: `{"worker_id": "f5b21d...", "job_ids": ["3a2b1c..."]}`
* **POST `/api/workers/{worker_id}/deregister`**: Gracefully deregisters a worker.

### 7. Observability & Metrics
* **GET `/api/metrics`**: Computes organization-wide statistics: job statuses count, worker distribution, and queue performance.
