# POSTLINK media downloader

POSTLINK media downloader is a web-ready application that allows users to open a public link, paste a supported media URL, analyze it, and download available video, audio, or image formats.

Built using a highly modular plugin provider architecture, it supports YouTube, Instagram reels/images, Twitter/X, and direct media links out of the box while maintaining strict input isolation, database telemetry logging, background task queuing, reverse NGINX proxy optimization, and an administrative dashboard panel.

---

## Public Deployment Shape

```text
POSTLINK-media-downloader/
├── backend/                  # FastAPI public API service
│   ├── app/                  # API, providers, database, tasks
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Backend cloud/local variables
├── frontend/                 # Next.js public web app
│   ├── src/app/              # POSTLINK UI and admin dashboard
│   ├── vercel.json           # Vercel frontend config
│   ├── package.json
│   └── .env.example          # Frontend public URL/API templates
├── docker/                   # Dockerfiles for cloud/VPS builds
├── nginx/                    # Optional reverse proxy for VPS Docker deploys
├── docs/                     # API and operations notes
├── tests/                    # Backend test suite
├── render.yaml               # Render backend + Postgres blueprint
├── docker-compose.yml        # Full local/VPS stack
├── .dockerignore             # Keeps cloud Docker builds small
├── .gitignore
└── DEPLOYMENT.md             # Step-by-step public deployment guide
```

Recommended public setup:

1. Deploy `backend/` with `render.yaml` on Render.
2. Deploy `frontend/` on Vercel.
3. Set `NEXT_PUBLIC_API_URL` in Vercel to your Render API URL, ending in `/api`.
4. Set `NEXT_PUBLIC_SITE_URL` in Vercel to your public website URL.
5. Add your Vercel frontend domain to `BACKEND_CORS_ORIGINS` in Render.

The frontend includes `robots.txt` and `sitemap.xml` routes for Google Search Console indexing.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the exact steps.

---

## Technical Stack

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, TailwindCSS v4, Framer Motion, Axios, React Hook Form
- **Backend**: FastAPI, Python 3.11, Uvicorn, Pydantic v2
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Caching**: Redis
- **Background Workers**: Celery (RabbitMQ message broker)
- **Proxy/Reverse Delivery**: NGINX
- **Containerization**: Docker & Docker Compose

---

## Features

1. **Auto Platform Detection**: Dynamically validates URLs to light up platform badges (YouTube, Instagram, Twitter/X).
2. **Analysis Cache**: Analysis queries are cached in Redis for 10 minutes to bypass external platform calls.
3. **Background Processing**: Heavy download/merging operations run in background worker containers via RabbitMQ + Celery.
4. **Static Speed Booster**: Once downloads finish, NGINX intercepts files directly from a shared directory volume bypassing the FastAPI thread pool.
5. **Mobile Transfer (QR Code)**: Offers a QR Code view for completed items so users can scan and pull files instantly to mobile devices.
6. **Telemetry & Dashboard**: `/admin` tracks daily volume, container states, platform distributions, and displays backend logger streams.
7. **Production Grade Defenses**: Integrated double-layer rate limiting (FastAPI SlowAPI & NGINX rate-limit zone mapping) and temporary file auto-expiration cron running every hour.
