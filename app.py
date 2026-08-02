"""
CHOTU v2.0 - COMPLETE PRODUCTION AI STUDY PLATFORM
Advanced RAG Chatbot + All 5 Phases + Enterprise Security

Entrypoint only. Config/db/auth/RAG live in core.py, routes live in
routers/*.py — this file just wires them together. Split out of a single
1200-line app.py; no route logic changed in the split itself (see
routers/auth.py for the one behavioral fix: /auth/login now requires a
password instead of trusting any email).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from core import ALLOWED_ORIGINS, init_db
from routers import pages, auth, exams, notes, focus, study, misc, memory

app = FastAPI(title="CHOTU v2.0", version="2.0.1")

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                  allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE"],
                  allow_headers=["Content-Type", "Authorization"], max_age=3600)

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(exams.router)
app.include_router(notes.router)
app.include_router(focus.router)
app.include_router(study.router)
app.include_router(misc.router)
app.include_router(memory.router)


@app.on_event("startup")
def _startup():
    init_db()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
