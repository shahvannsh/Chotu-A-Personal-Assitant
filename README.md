# Chotu — AI Study Assistant

Chotu is a personal study assistant: track exams and study streaks, run
focus sessions with ambient sound, upload PDFs, and ask questions about
them through a RAG-backed chatbot with a choice of AI providers.

## What's actually in this repo

- **Backend**: FastAPI, split into `app.py` (thin entrypoint) +
  `core.py` (config/db/auth/RAG helpers) + `routers/` (one file per
  domain: `auth`, `exams`, `notes`, `focus`, `study`, `misc`, `pages`).
  ~1500 lines total across the split.
- **Database**: PostgreSQL via `psycopg2` (raw SQL, no ORM, no
  migrations tool)
- **Frontend**: plain HTML/JS pages (`index.html`, `dashboard.html`,
  `study.html`, `history.html`, `notes.html`, `login.html`) — no
  build step, no framework
- **LLM providers**: pluggable — Groq (`llama-3.3-70b-versatile`),
  Ollama (any locally pulled model, reached via
  `host.docker.internal` from inside Docker), and Gemini
  (`gemini-2.0-flash`). Whichever have a real key/are reachable show
  up in the model picker; nothing fake is listed.
- **Retrieval**: hybrid BM25 + embedding search over PDF chunks
  stored in Postgres (`document_chunks.embedding` as raw bytes,
  brute-force cosine similarity — no vector DB)
- **Auth**: email + password (PBKDF2-SHA256, 260k iterations, stdlib
  only). First login for a new email creates the account; a
  password is required on every subsequent login for that email —
  this replaced an earlier version that logged anyone in as any
  email with no verification at all.
- **Deployed at**: https://chotu-lcc7.onrender.com

## Features

- Exam tracking with an auto-generated day-by-day study schedule
- Study streak tracking
- Daily study-time goals
- **Focus timer** — Pomodoro-style (25/50/90/custom), circular
  progress ring, logs real elapsed time to study history and daily
  goals on stop (not just on natural completion)
- **Ambient focus sound** — white/brown/pink noise and a rain-like
  variant, synthesized live in-browser via the Web Audio API. No
  audio files, no licensing exposure. Auto-plays when a focus
  session starts, auto-pauses when it ends.
- Notes (create/list/delete)
- PDF upload → text extraction (PyMuPDF) → chunking → embeddings
- Chat over uploaded PDFs (RAG + Wikipedia snippet fallback),
  routed to whichever provider you pick
- **Compare Mode** — ask one question, get answers from 2-4 models
  side by side, dispatched in parallel with real per-model latency
  and independent error handling (one model failing doesn't break
  the others)
- **Ctrl+K search** — across notes, exams, and past chat history,
  auth-scoped to the logged-in user
- Global leaderboard, notifications (tables exist; UI coverage varies)

## Running locally

See `RUN.txt` for full setup (Docker and local-Python paths, plus a
troubleshooting section for the Windows/WSL/Docker Desktop issues
that came up getting this running the first time). Quick version:

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:pass@localhost:5432/chotu
export GROQ_API_KEY=your_key        # optional — chat falls back to a stub message without it
export GEMINI_API_KEY=your_key      # optional
export OLLAMA_BASE_URL=http://localhost:11434   # optional, only if not using Docker
uvicorn app:app --reload
```

Requires a running Postgres instance; `init_db()` creates all tables
on startup.

### Docker

```bash
docker build -t chotu .
docker network create chotu-net
docker run -d --name chotu-db --network chotu-net -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=chotu postgres:16
docker run -d --name chotu-app --network chotu-net -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:postgres@chotu-db:5432/chotu \
  -e GROQ_API_KEY=your_key chotu
```

No spaces around `=` in `-e KEY=value` — PowerShell in particular
will silently break the whole command if you add them.

## Tests

```bash
pip install pytest
DATABASE_URL=postgresql://test:test@localhost:5432/test pytest tests/ -v
```

20 unit tests over validators and the RAG scoring functions
(`tests/test_validators.py`). These don't hit a real database. No
integration or end-to-end test suite yet — everything else in this
README was verified manually against a live Postgres instance and a
live server during development, not by an automated suite.

## Known limitations / roadmap

- No automated integration/e2e tests — only unit tests on pure
  functions
- No CI (GitHub Actions etc.)
- No real vector database (embeddings are brute-force compared in
  Python)
- `sentence-transformers` is used for embeddings if installed,
  otherwise silently falls back to a non-semantic hash-based
  stand-in — see `requirements.txt`
- `/focus-sessions` shows the *planned* duration for each session,
  not the actual elapsed time recorded on stop — the aggregate
  minutes (daily goals, study history) are correct, but the
  per-session list isn't. Known, not yet fixed.
- No consensus/ranking mode on top of Compare Mode — it shows raw
  side-by-side answers, nothing evaluates or merges them
- `server.py` and `study_routes.py` are dead code from an earlier
  prototype, kept only for history — see the notice at the top of
  each file. Safe to delete once confirmed nothing depends on them.
- Auth has no email verification (no SMTP configured) — a password
  is required and checked correctly, but nothing confirms the email
  address is actually owned by whoever's signing up

## License

Not yet specified.
