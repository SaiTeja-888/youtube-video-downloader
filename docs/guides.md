# Universal Media Downloader - Technical Guides

This document contains step-by-step instructions for installation, Docker configuration, deployment, and API usage.

---

## 1. Local Installation Guide (Development)

To run the application locally without Docker, you need to set up PostgreSQL, Redis, RabbitMQ, FFmpeg, Python, and Node.js on your computer.

### System Prerequisites
- **FFmpeg**: Must be installed on your path (vital for merging audio/video streams).
- **PostgreSQL**: Running instance with database `downloader`.
- **Redis**: Running instance at `redis://localhost:6379/0`.
- **RabbitMQ**: Running instance at `amqp://guest:guest@localhost:5672//`.

### Backend Setup
1. Open a terminal, go to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
5. Run the Celery worker (in a new terminal with virtualenv active):
   ```bash
   celery -A app.celery_app.celery_app worker --loglevel=info
   ```
6. Run the Celery beat scheduler (in a third terminal):
   ```bash
   celery -A app.celery_app.celery_app beat --loglevel=info
   ```

### Frontend Setup
1. Open a terminal and go to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
4. Access the web interface at `http://localhost:3000`.

---

## 2. Docker & Docker Compose Guide

Docker Compose automatically orchestrates all dependencies, services, and shared disk volumes.

### Starting Services
Ensure Docker Desktop is running, go to the project root directory, and launch:
```bash
docker compose up --build
```
This builds custom backend and frontend images, starts Redis, Postgres, RabbitMQ, NGINX, and mounting folders automatically.

### Port Mappings
- **NGINX Reverse Proxy**: `http://localhost:80` (Default entry point)
- **Next.js Client**: `http://localhost:3000` (Proxied through NGINX)
- **FastAPI Core**: `http://localhost:8000` (Proxied through NGINX to `/api`)
- **RabbitMQ Dashboard**: `http://localhost:15672` (Credentials: `guest` / `guest`)
- **PostgreSQL Database**: `localhost:5432`

### Stopping Services
```bash
docker compose down -v
```
*(The `-v` flag removes active container volumes if you want a complete clean reset of the Postgres database).*

---

## 3. Production Deployment Guide

For public deployment, we recommend running NGINX with SSL/HTTPS.

### NGINX SSL Block (Example Setup)
Update `nginx/nginx.conf` to redirect HTTP traffic (80) to HTTPS (443):
```text
server {
    listen 80;
    server_name media.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name media.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/media.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/media.yourdomain.com/privkey.pem;

    # Secure Header Injections
    add_header X-Frame-Options "DENY";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
    add_header Content-Security-Policy "default-src 'self' 'unsafe-inline' 'unsafe-eval' data:; img-src * data:;";

    location / {
        proxy_pass http://frontend:3000;
        ...
    }
    
    location /api {
        proxy_pass http://backend:8000;
        ...
    }
}
```

---

## 4. API Endpoints Reference

### 1. `POST /api/analyze`
Extracts formats and title metadata for a URL.
- **Payload**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }
  ```
- **Response**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
    "duration": 212,
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "uploader": "Rick Astley",
    "views": 1400000000,
    "upload_date": "20091025",
    "description": "The official video...",
    "platform": "youtube",
    "formats": [
      {
        "format_id": "137",
        "resolution": "1080p",
        "fps": 25,
        "codec": "av01.0.08M.08",
        "filesize": 45678901,
        "container": "mp4",
        "media_type": "video"
      }
    ]
  }
  ```

### 2. `POST /api/download`
Creates a Celery task queue job.
- **Payload**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "format_id": "137"
  }
  ```
- **Response**:
  ```json
  {
    "job_id": "8a3d5e21-0a6f-4318-971c-62cbfef4b89e"
  }
  ```

### 3. `GET /api/status/{job_id}`
Retrieves extraction status.
- **Response**:
  ```json
  {
    "job_id": "8a3d5e21-0a6f-4318-971c-62cbfef4b89e",
    "status": "completed",
    "progress": 100.0,
    "file_url": "/api/files/Never_Gonna_Give_You_Up_dQw4w9WgXcQ.mp4",
    "file_size": 45678901,
    "error": null,
    "title": "Rick Astley - Never Gonna Give You Up",
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "platform": "youtube"
  }
  ```

### 4. `GET /api/health`
Checks container microservice health logs.
- **Response**:
  ```json
  {
    "status": "healthy",
    "postgres": "healthy",
    "redis": "healthy",
    "rabbitmq": "healthy"
  }
  ```
