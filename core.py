"""
CHOTU v2.0 — shared core: config, db access, validation, auth, RAG.

Extracted from the original single-file app.py so routers/*.py can import
one thing instead of each other. Logic is unchanged from app.py — this is
a mechanical split, not a rewrite.
"""

from fastapi import HTTPException, Request
import os, logging, time, re, math, hashlib, hmac, secrets
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import List, Dict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from functools import wraps

# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION LOGGING (SECURE)
# ═══════════════════════════════════════════════════════════════════════════

class SecureFormatter(logging.Formatter):
    def format(self, record):
        msg = str(record.msg)
        if any(x in msg.lower() for x in ['key', 'token', 'password', 'secret']):
            record.msg = "[REDACTED]"
        return super().format(record)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(SecureFormatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.handlers = [handler]

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:8000",
                  "https://chotu-lcc7.onrender.com", "https://chotu.onrender.com"]

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Create/attach a Postgres instance on Render and it will be injected automatically, "
        "or set it manually if using an external Postgres provider."
    )
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

UPLOADS_DIR = '/data/uploads' if os.path.exists('/data') else './uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
MAX_PDF_SIZE = 50 * 1024 * 1024
MAX_UPLOAD_LIMIT = 100
REQUEST_COUNTS = {}

# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITING DECORATOR
# ═══════════════════════════════════════════════════════════════════════════

def rate_limit(max_requests=100, seconds=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ip = kwargs.get('request', None)
            if ip:
                ip = ip.client.host
            else:
                ip = "unknown"
            key = f"{ip}:{func.__name__}"
            now = time.time()

            if key not in REQUEST_COUNTS:
                REQUEST_COUNTS[key] = []
            REQUEST_COUNTS[key] = [t for t in REQUEST_COUNTS[key] if now - t < seconds]

            if len(REQUEST_COUNTS[key]) >= max_requests:
                raise HTTPException(status_code=429, detail="Too many requests")
            REQUEST_COUNTS[key].append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════

class PGConnWrapper:
    """
    Thin wrapper so the rest of this codebase's `db.execute(sql, params).fetchone()`
    style calls (a sqlite3.Connection convenience method) keep working against a
    real psycopg2 connection, which has no such method on the connection itself.
    """
    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        cur.execute(query, params if params is not None else None)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return self._conn.cursor()

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return PGConnWrapper(conn)

def init_db():
    db = get_db()
    try:
        db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            picture TEXT,
            password_hash TEXT,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            ip_address TEXT,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS exams (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            exam_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            estimated_hours INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS exam_schedule (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER NOT NULL,
            day_number INTEGER,
            date TEXT,
            topics TEXT,
            hours_planned INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS streaks (
            user_id INTEGER PRIMARY KEY,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_study_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS daily_study_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            study_date TEXT NOT NULL,
            minutes_studied INTEGER DEFAULT 0,
            topics_reviewed TEXT,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS weak_topics (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            confidence FLOAT DEFAULT 0.5,
            last_reviewed TEXT,
            next_review TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mock_exams (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            exam_name TEXT,
            total_questions INTEGER DEFAULT 10,
            score INTEGER,
            accuracy FLOAT,
            time_taken_minutes INTEGER,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quiz_questions (
            id SERIAL PRIMARY KEY,
            subject TEXT,
            topic TEXT,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            difficulty INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            question_id INTEGER,
            is_correct BOOLEAN,
            time_spent_seconds INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_graph (
            id SERIAL PRIMARY KEY,
            source_topic TEXT,
            target_topic TEXT,
            relationship TEXT,
            strength FLOAT DEFAULT 0.5,
            subject TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            goal_date TEXT NOT NULL,
            goal_minutes INTEGER DEFAULT 60,
            completed_minutes INTEGER DEFAULT 0,
            UNIQUE(user_id, goal_date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS leaderboard (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            total_points INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            rank INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_badges (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            earned_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            UNIQUE(user_id, badge_name),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            type TEXT,
            read BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS challenges (
            id SERIAL PRIMARY KEY,
            creator_id INTEGER NOT NULL,
            challenge_type TEXT,
            subject TEXT,
            target_value INTEGER,
            participants TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS friend_connections (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            UNIQUE(user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            subject TEXT,
            topic TEXT,
            pinned BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            updated_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bookmarks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            resource_type TEXT,
            resource_title TEXT NOT NULL,
            resource_url TEXT,
            subject TEXT,
            topic TEXT,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS study_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            session_type TEXT,
            duration_minutes INTEGER,
            score INTEGER,
            accuracy FLOAT,
            date TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            goal_name TEXT NOT NULL,
            goal_type TEXT,
            target_value TEXT,
            deadline TEXT,
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            plan TEXT DEFAULT 'free',
            status TEXT DEFAULT 'active',
            started_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS focus_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            subject TEXT,
            duration_minutes INTEGER DEFAULT 25,
            completed BOOLEAN DEFAULT FALSE,
            started_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            ended_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pdf_documents (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER,
            upload_date TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            chunk_index INTEGER,
            embedding BYTEA,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (document_id) REFERENCES pdf_documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            relevant_chunks TEXT,
            relevance_score FLOAT,
            confidence INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD"T"HH24:MI:SS.US')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        # Migration for pre-existing databases created before password_hash existed.
        db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT")
        db.commit()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"DB error: {type(e).__name__}")
        raise
    finally:
        db.close()

# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION & SECURITY
# ═══════════════════════════════════════════════════════════════════════════

def validate_string(value: str, field: str, min_len=1, max_len=255) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string")
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        raise ValueError(f"{field} must be {min_len}-{max_len} chars")
    if any(c in value for c in ['<', '>', '"', "'"]):
        raise ValueError(f"{field} contains invalid chars")
    return value

def validate_email(email: str) -> str:
    email = email.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError("Invalid email")
    return email

def validate_token(token: str) -> str:
    if not token or len(token) < 20 or len(token) > 100:
        raise ValueError("Invalid token")
    if not re.match(r'^[A-Za-z0-9_-]+$', token):
        raise ValueError("Invalid token format")
    return token

def require_user(request: Request) -> dict:
    try:
        auth_header = request.headers.get('Authorization', '').strip()
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail='Invalid auth header')

        token = auth_header[7:].strip()
        if not token:
            raise HTTPException(status_code=401, detail='Token missing')

        validate_token(token)

        db = get_db()
        try:
            session = db.execute('SELECT user_id, expires_at FROM sessions WHERE token=%s', (token,)).fetchone()
            if not session:
                raise HTTPException(status_code=401, detail='Invalid token')

            if datetime.fromisoformat(session['expires_at']) < datetime.now():
                db.execute('DELETE FROM sessions WHERE token=%s', (token,))
                db.commit()
                raise HTTPException(status_code=401, detail='Token expired')

            user = db.execute('SELECT * FROM users WHERE id=%s', (session['user_id'],)).fetchone()
            if not user:
                raise HTTPException(status_code=401, detail='User not found')

            return dict(user)
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail='Auth failed')

# ═══════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING (stdlib only — no new dependency)
#
# PBKDF2-HMAC-SHA256, 260k iterations (OWASP 2023 minimum), random salt per
# user. Stored as "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>".
# ═══════════════════════════════════════════════════════════════════════════

_PBKDF2_ITERATIONS = 260_000

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations, salt, hash_hex = stored_hash.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════════════════
# ADVANCED RAG PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

class AdvancedRAG:
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            self.has_embedder = True
        except Exception as e:
            self.has_embedder = False
            logger.error(
                f"sentence-transformers unavailable ({type(e).__name__}): "
                "falling back to non-semantic hash embeddings. RAG search quality "
                "will be degraded until this dependency is installed."
            )

    def embed(self, text: str) -> np.ndarray:
        if self.has_embedder:
            return self.embedder.encode(text[:512])
        else:
            hash_val = hash(text) % 100
            return np.array([float(hash_val)] * 384)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def bm25_score(self, query: str, chunks: List[str]) -> List[float]:
        query_terms = self._tokenize(query)
        scores = []
        tokenized_chunks = [self._tokenize(c) for c in chunks]
        avg_len = sum(len(t) for t in tokenized_chunks) / max(1, len(tokenized_chunks))

        for terms in tokenized_chunks:
            score = 0.0
            for term in query_terms:
                tf = terms.count(term)
                if tf > 0:
                    k1, b = 1.5, 0.75
                    idf = math.log((len(chunks) - 1 + 0.5) / (1 + 0.5))
                    bm25 = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(terms) / avg_len))
                    score += bm25
            scores.append(score)
        return scores

    def hybrid_search(self, query: str, chunks: List[str], top_k=3) -> List[Dict]:
        if not chunks:
            return []

        query_emb = self.embed(query)
        dense_scores = []
        for chunk in chunks:
            chunk_emb = self.embed(chunk)
            sim = cosine_similarity([query_emb], [chunk_emb])[0][0]
            dense_scores.append(sim)

        bm25_scores = self.bm25_score(query, chunks)

        combined = []
        max_dense = max(dense_scores) if dense_scores and max(dense_scores) > 0 else 1
        max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1

        for i, chunk in enumerate(chunks):
            alpha = 0.6
            combined_score = alpha * (dense_scores[i] / max_dense) + (1-alpha) * (bm25_scores[i] / max_bm25)
            combined.append({'text': chunk, 'score': combined_score})

        combined.sort(key=lambda x: x['score'], reverse=True)

        for result in combined[:top_k]:
            result['confidence'] = int(min(100, result['score'] * 100))

        return combined[:top_k]

rag = AdvancedRAG()
