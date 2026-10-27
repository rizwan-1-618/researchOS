This is a demo video

https://drive.google.com/file/d/1lmIIhFp5MbBLjrfRMGhXCj-GByE1Hcbq/view?usp=sharing

# ResearchOS

A research desk for finding papers, reading them, and keeping the notes, questions, and citations in one place.

The site is Next.js. The API is FastAPI. Papers, accounts, and search live in Postgres with pgvector. Background jobs use Redis.

## What you can do

- Search OpenAlex, Semantic Scholar, and arXiv, then save papers into a library
- Upload a PDF, read it, and attach highlights to notes
- Group work into collections, projects, questions, and tasks
- Search the library by keyword or by meaning
- Open a citation graph, with papers colored by community
- See recommendations and a short analytics view

## Layout

| Path | Role |
| --- | --- |
| `frontend` | Next.js app. The browser talks only to this app. |
| `backend` | FastAPI API, database migrations, and the job worker |
| `.env` | Shared settings. Copy from `.env.example`. Never commit this file. |

Requests to `/api/...` on the site are forwarded to the API. Locally that target is `http://127.0.0.1:8000`.

## Run it locally

You need Python 3.12, Node.js 22, Postgres 17 with the `vector` extension, and Redis.

```bash
cp .env.example .env
```

Set `JWT_SECRET` to a long random hex string. Leave `COOKIE_SECURE=false` on your machine.

Create the database and enable vectors:

```sql
CREATE DATABASE researchos;
\c researchos
CREATE EXTENSION IF NOT EXISTS vector;
```

Start Redis, then the API, the worker, and the site in separate terminals.

```bash
# API
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# Worker. PDF uploads and citation jobs stay pending without this.
cd backend
source .venv/bin/activate
python -m app.workers
```

```bash
# Site
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

### Demo account

This pulls a small set of real AI and physics papers from OpenAlex and fills one account. It needs a network connection.

```bash
cd backend
source .venv/bin/activate
python -m app.seed_demo
```

Sign in with `demo@example.com` and `ResearchOS-demo`.

### Docker

`docker compose up --build` starts Postgres, Redis, MinIO, the API, the worker, and the site. The compose file switches file storage to MinIO. Put the same `.env` values in the repo root first.

## Settings

| Variable | What it does |
| --- | --- |
| `DATABASE_URL` | Async Postgres URL. Must start with `postgresql+asyncpg://`. |
| `DATABASE_URL_SYNC` | Same database, for migrations. Must start with `postgresql+psycopg://`. |
| `REDIS_URL` | Queue and login rate limit. The API refuses to start if this is down. |
| `JWT_SECRET` | Signs the login cookies. Use a new value for every deployment. |
| `CORS_ORIGINS` | The site address the API will accept. No trailing slash. |
| `COOKIE_SECURE` | `false` on http://localhost. `true` on HTTPS. |
| `API_PROXY_URL` | Where the Next.js app forwards `/api`. Read when the site is built. |
| `STORAGE_BACKEND` | `local` keeps PDFs on disk. `s3` uses the `S3_*` settings. |
| `EMBEDDING_PROVIDER` | `fastembed` runs the local model. `openai` uses the API settings. `fake` is for tests. |
| `CONTACT_EMAIL` | Sent with OpenAlex requests. Use a real address in public use. |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional. Search still works without it. |

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

Tests use their own database, `researchos_test`, and do not touch the demo data. Create that database and its `vector` extension before running them.

## Put it on the public internet

Vercel can host the site, and only the site. The API, Redis, and Postgres have to run elsewhere.

1. Create a Postgres database that supports `vector` (Neon or Supabase). Run `CREATE EXTENSION IF NOT EXISTS vector;`.
2. Create a Redis database (Upstash is enough).
3. Deploy `backend` as two services that share one environment: the API (`uvicorn`, which also runs migrations on startup in Docker) and the worker (`python -m app.workers`).
4. On Vercel, set the project root to `frontend` and set `API_PROXY_URL` to the public API address. Deploy again if you change it. The value is fixed at build time.
5. Set `CORS_ORIGINS` on the API to the exact Vercel address, set `COOKIE_SECURE=true`, and restart the API.
6. Sign up on the live site, or run `python -m app.seed_demo` against the hosted database. The laptop’s demo data does not move with the code.

`STORAGE_BACKEND=local` loses uploaded PDFs when the API container restarts. For a public site, use `s3` and fill in `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, and `S3_REGION`.

Without the worker, accounts and existing library data still work. New PDF processing and citation expansion do not.
