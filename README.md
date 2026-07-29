# LeadMaster AI

A full-stack enterprise lead-intelligence platform: AI-powered lead search,
website scanning, map-based discovery, team/billing management, and an
admin panel — built as a premium SaaS product.

```
.
├── src/            Next.js 16 frontend (TypeScript, Tailwind v4, App Router)
├── backend/         FastAPI backend (PostgreSQL, Redis, Celery, Stripe)
├── docker/           nginx + frontend Dockerfile (shared/production configs)
└── docker-compose.yml  full-stack orchestration
```

## Quick start

**Frontend** (Next.js — mock data by default):
```bash
npm install
npm run dev
```
Visit http://localhost:3000. See the component/page structure under `src/`.

**Backend** (FastAPI — real database, real APIs):
```bash
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # (venv/bin/pip on macOS/Linux)
cp .env.example .env
# set up Postgres + Redis — see backend/README.md for full instructions
./venv/Scripts/python -m alembic upgrade head
./venv/Scripts/python -m scripts.seed_data
./venv/Scripts/python -m uvicorn main:app --reload --port 8000
```
Visit http://localhost:8000/docs for the interactive API docs.

**Full stack via Docker** (requires Docker):
```bash
cp backend/.env.example backend/.env
docker compose up --build
```

See **[backend/README.md](backend/README.md)** for full backend
documentation: architecture, ER diagram, environment variables, testing,
deployment, and a clear breakdown of which integrations (Stripe, Google
Maps, Google OAuth, SMTP) are real-but-need-your-own-API-keys vs. the two
features (lead search, website scanner) that use documented, deterministic
placeholder data generation in the absence of paid third-party provider
credentials.

## Stack

- **Frontend:** Next.js 16, TypeScript, Tailwind CSS v4, Framer Motion, Recharts, TanStack Table/Query, Zustand
- **Backend:** FastAPI, PostgreSQL (SQLAlchemy 2.0 async + Alembic), Redis, Celery, JWT auth, Stripe, Google OAuth/Maps
- **Deployment:** Docker Compose, Nginx reverse proxy
