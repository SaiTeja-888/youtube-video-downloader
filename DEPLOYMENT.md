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

- Public Instagram media works out-of-the-box using the built-in `InstagramProvider` without cookies.
- Downloads are stored temporarily. The backend cleanup task removes old files.
- For serious public traffic, add Redis and RabbitMQ instead of relying on local fallback mode.
- Keep `SECRET_KEY` private.
- Do not commit `.env`, database files, local logs, `downloads/`, `backend/venv/`, or `frontend/.next/`.

## Why YouTube Blocks Render Requests & How To Bypass It

### Why YouTube Blocks Cloud Hosts (Render, AWS, DigitalOcean)
Render runs on AWS datacenter IP ranges. Google/YouTube actively flags requests coming from cloud hosting IPs with:
- `Sign in to confirm you're not a bot`
- `HTTP 429 Too Many Requests`
- `Video unavailable`

Because bots scrape heavily from cloud servers, YouTube requires an authenticated session (cookies), Proof-of-Origin (`po_token`), or residential IP routing.

### 3 Ways To Bypass YouTube Blocks On Render

#### Method 1: Add Cookies (Recommended — 100% Reliable)
Passing your browser's YouTube session cookies tells YouTube you are a real logged-in user:

1. In your browser (Chrome or Firefox), install an extension like **Get cookies.txt LOCALLY**.
2. Go to `https://www.youtube.com/` while logged into any Google account (a secondary/alt account is fine).
3. Open the extension and click **Export / Copy** to get your cookies in Netscape format.
4. On your **Render Dashboard** -> Go to your `postlink-api` service -> **Environment**:
   - **Option A (Secret File)**: Under **Secret Files**, add a file named `/etc/secrets/cookies.txt` and paste the cookie content.
   - **Option B (Env Variable)**: Add an environment variable `COOKIES_TEXT` and paste the cookie content directly.
5. Deploy or restart the Render service.

#### Method 2: Use a Residential / Web Proxy (Zero Cookie Maintenance)
If you do not want to manage cookies, route Render's yt-dlp traffic through a proxy:

1. Get a proxy (e.g. from Webshare, IPRoyal, or any HTTP/SOCKS5 proxy provider).
2. On your **Render Dashboard** -> `postlink-api` -> **Environment**:
   - Add environment variable `HTTP_PROXY` or `YTDL_PROXY`:
     ```text
     http://username:password@proxy-host:port
     ```
3. The backend automatically routes YouTube requests through the proxy IP instead of Render's AWS IP.

#### Method 3: PO Token (Proof of Origin)
If using the Web client without cookies:
1. Generate a PO Token using [youtube-po-token-generator](https://github.com/YunzheZJU/youtube-po-token-generator).
2. On Render Dashboard, set:
   - `PO_TOKEN=<your_po_token>`
   - `VISITOR_DATA=<your_visitor_data>`

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
