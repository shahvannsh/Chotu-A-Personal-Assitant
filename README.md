# Chotu — AI Study Assistant

Chotu is a personal study assistant: track exams and study streaks, run focus sessions, upload PDFs, and ask questions about them through a RAG-backed chatbot.

## What's actually in this repo

- **Backend**: FastAPI (`app.py`), single-file, ~1200 lines
- **Database**: PostgreSQL via `psycopg2` (raw SQL, no ORM, no migrations tool)
- **Frontend**: plain HTML/JS pages (`index.html`, `dashboard.html`, `study.html`, `history.html`, `notes.html`, `login.html`)
- **LLM**: Groq (`llama-3.3-70b-versatile`) for chat answers, called only if `GROQ_API_KEY` is set — otherwise the endpoint returns a plain-text fallback instead of failing
- **Retrieval**: hybrid BM25 + embedding search over PDF chunks stored in Postgres (`document_chunks.embedding` as raw bytes, brute-force cosine similarity — no vector DB)
- **Auth**: email-based login issuing a 30-day bearer token, stored in a `sessions` table
- **Deployed at**: https://chotu-lcc7.onrender.com

## Features

- Exam tracking with an auto-generated day-by-day study schedule
- Study streak tracking
- Daily study-time goals
- Pomodoro-style focus sessions, logged to study history
- Notes (create/list/delete)
- PDF upload → text extraction (PyMuPDF) → chunking → embeddings
- Chat over uploaded PDFs (RAG + Wikipedia snippet fallback) via Groq
- Global leaderboard, notifications (tables exist; UI coverage varies)

## Running locally

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:pass@localhost:5432/chotu
export GROQ_API_KEY=your_key   # optional — chat falls back to a stub message without it
uvicorn app:app --reload
```

Requires a running Postgres instance; `init_db()` creates all tables on startup.

## Known limitations / roadmap

- No automated tests yet
- No Docker/CI setup
- No real vector database (embeddings are brute-force compared in Python)
- `sentence-transformers` is used for embeddings if installed, otherwise silently falls back to a non-semantic hash-based stand-in — see requirements.txt
- Single-file backend; would benefit from splitting into routers/services as it grows

## License

Not yet specified.
