# POSTLINK Public Deployment Guide

This project is deployment-ready as two public services:

- `backend/`: FastAPI API that analyzes and downloads media.
- `frontend/`: Next.js website that anyone can open and use.

## Option A: Render Backend + Vercel Frontend

### 1. Push The Project To GitHub

Commit and push the whole project folder to GitHub. The root files that matter for deployment are:

- `render.yaml`
- `docker/backend.Dockerfile`
- `frontend/vercel.json`
- `backend/.env.example`
- `frontend/.env.example`
- `.dockerignore`

### 2. Deploy The Backend On Render

1. Open Render.
2. Choose **New** -> **Blueprint**.
3. Connect your GitHub repository.
4. Render will detect `render.yaml`.
5. Create the `postlink-api` web service and `postlink-db` Postgres database.

Render will set `DATABASE_URL` automatically from the blueprint. It also creates a persistent disk at `/var/data/downloads` so completed files can be served back to users.

After deployment, your API URL will look like:

```text
https://postlink-api.onrender.com
```

Health check:

```text
https://postlink-api.onrender.com/api/health
```

The health response may show Redis as `unhealthy` if you do not add Redis. That is acceptable for simple public deployment because the app falls back to local background tasks.

### 3. Deploy The Frontend On Vercel

1. Open Vercel.
2. Import the same GitHub repository.
3. Set the project root directory to:

```text
frontend
```

4. Add this environment variable:

```text
NEXT_PUBLIC_API_URL=https://postlink-api.onrender.com/api
NEXT_PUBLIC_SITE_URL=https://your-project.vercel.app
```

5. Deploy.

Your public website will look like:

```text
https://your-project.vercel.app
```

### 4. Connect CORS

In Render, update the backend environment variable:

```text
BACKEND_CORS_ORIGINS=https://your-project.vercel.app
```

The project also includes this default preview regex:

```text
BACKEND_CORS_ORIGIN_REGEX=https://.*\.vercel\.app
```

That lets Vercel preview deployments call the API too.

Restart the Render backend after changing environment variables.

### 5. Search Engine Readiness

The frontend generates:

```text
/robots.txt
/sitemap.xml
```

Set `NEXT_PUBLIC_SITE_URL` to your final public URL before submitting the site to Google Search Console.

## Option B: One Server With Docker Compose

Use this when deploying to a VPS such as an Ubuntu server.

1. Install Docker and Docker Compose.
2. Point your domain to the server.
3. From the project root, run:

```bash
docker compose up --build -d
```

4. Configure HTTPS in `nginx/nginx.conf` or put Cloudflare in front of the server.

This runs frontend, backend, Postgres, Redis, RabbitMQ, NGINX, and workers together.

## Important Production Notes

- Public YouTube/Instagram media works when the platform allows anonymous extraction.
- Private, age-restricted, bot-protected, or login-gated media may require cookies on a trusted private deployment.
- Downloads are stored temporarily. The backend cleanup task removes old files.
- For serious public traffic, add Redis and RabbitMQ instead of relying on local fallback mode.
- Keep `SECRET_KEY` private.
- Do not commit `.env`, database files, local logs, `downloads/`, `backend/venv/`, or `frontend/.next/`.

## Quick Local Check

Backend:

```bash
cd backend
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:3000
```
