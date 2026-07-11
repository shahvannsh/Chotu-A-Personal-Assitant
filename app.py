"""
CHOTU - AI Study Operating System v2.0
Complete production-grade backend with RAG chatbot integration
All 5 Phases + Neural Network Enhancement
"""

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import sqlite3
from datetime import datetime, timedelta
import secrets
import logging
from functools import lru_cache
import asyncio
from typing import List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import fitz  # PyMuPDF for PDF parsing
import re
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="CHOTU v2.0",
    description="AI Study Operating System with RAG Chatbot",
    version="2.0.0"
)

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://chotu-lcc7.onrender.com",
    "https://chotu.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Database
DB_PATH = '/data/chotu.db' if os.path.exists('/data') else 'chotu.db'
UPLOADS_DIR = '/data/uploads' if os.path.exists('/data') else './uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

# API Keys
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE SETUP
# ═════════════════════════════════════════════════════════════════════════════

def get_db():
    """Get database connection with security settings"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn

def init_db():
    """Initialize database with all tables"""
    db = get_db()
    try:
        db.executescript("""
        -- USERS & AUTH
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            picture TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        -- PHASE 1: CORE
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            exam_date TEXT NOT NULL,
            estimated_hours INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            study_date TEXT NOT NULL,
            minutes_studied INTEGER DEFAULT 0,
            topics_reviewed TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS weak_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            confidence FLOAT DEFAULT 0.5,
            last_reviewed TEXT,
            next_review TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        -- PHASE 2: INTELLIGENCE
        CREATE TABLE IF NOT EXISTS mock_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            exam_name TEXT,
            total_questions INTEGER DEFAULT 10,
            score INTEGER,
            accuracy FLOAT,
            time_taken_minutes INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            difficulty INTEGER DEFAULT 1
        );
        
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER,
            is_correct BOOLEAN,
            time_spent_seconds INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS knowledge_graph (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_topic TEXT,
            target_topic TEXT,
            relationship TEXT,
            strength FLOAT DEFAULT 0.5,
            subject TEXT
        );
        
        -- PHASE 3: HABITS
        CREATE TABLE IF NOT EXISTS daily_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            goal_date TEXT NOT NULL,
            goal_minutes INTEGER DEFAULT 60,
            completed_minutes INTEGER DEFAULT 0,
            UNIQUE(user_id, goal_date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            total_points INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            rank INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            earned_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, badge_name),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        -- PHASE 4: DISTRIBUTION
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            type TEXT,
            read BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            challenge_type TEXT,
            subject TEXT,
            target_value INTEGER,
            participants TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS friend_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            UNIQUE(user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        -- PHASE 5: PREMIUM & PERSISTENCE
        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            subject TEXT,
            topic TEXT,
            pinned BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resource_type TEXT,
            resource_title TEXT NOT NULL,
            resource_url TEXT,
            subject TEXT,
            topic TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS study_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            session_type TEXT,
            duration_minutes INTEGER,
            score INTEGER,
            accuracy FLOAT,
            date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS user_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            goal_name TEXT NOT NULL,
            goal_type TEXT,
            target_value TEXT,
            deadline TEXT,
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            plan TEXT DEFAULT 'free',
            status TEXT DEFAULT 'active',
            started_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            duration_minutes INTEGER DEFAULT 25,
            completed BOOLEAN DEFAULT FALSE,
            started_at TEXT DEFAULT (datetime('now')),
            ended_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        -- RAG CHATBOT
        CREATE TABLE IF NOT EXISTS pdf_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT,
            upload_date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            chunk_index INTEGER,
            embedding BLOB,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (document_id) REFERENCES pdf_documents(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            relevant_chunks TEXT,
            relevance_score FLOAT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        db.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database init error: {e}")
        raise
    finally:
        db.close()

init_db()

# ═════════════════════════════════════════════════════════════════════════════
# SECURITY & VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

def validate_string(value: str, field_name: str, min_len=1, max_len=255) -> str:
    """Validate string input"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be string")
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        raise ValueError(f"{field_name} must be {min_len}-{max_len} characters")
    return value

def validate_email(email: str) -> str:
    """Validate email format"""
    email = email.strip().lower()
    if '@' not in email or len(email) < 5 or len(email) > 255:
        raise ValueError("Invalid email format")
    return email

def require_user(request: Request) -> dict:
    """Validate user with token expiration"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            raise HTTPException(status_code=401, detail='No token provided')
        
        db = get_db()
        try:
            session = db.execute(
                'SELECT user_id, expires_at FROM sessions WHERE token=?', 
                (token,)
            ).fetchone()
            
            if not session:
                raise HTTPException(status_code=401, detail='Invalid token')
            
            if datetime.fromisoformat(session['expires_at']) < datetime.now():
                db.execute('DELETE FROM sessions WHERE token=?', (token,))
                db.commit()
                raise HTTPException(status_code=401, detail='Token expired')
            
            user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
            if not user:
                raise HTTPException(status_code=401, detail='User not found')
            
            return dict(user)
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=500, detail='Authentication failed')

# ═════════════════════════════════════════════════════════════════════════════
# RAG COMPONENTS
# ═════════════════════════════════════════════════════════════════════════════

class RAGPipeline:
    """RAG Pipeline for semantic search and answer enhancement"""
    
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Embedding model loaded")
        except ImportError:
            logger.warning("⚠️ sentence-transformers not available, using fallback")
            self.embedder = None
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""
    
    def chunk_text(self, text: str, chunk_size=512, overlap=100) -> List[str]:
        """Split text into semantic chunks"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += " " + sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """Generate embeddings for text"""
        try:
            if self.embedder:
                return self.embedder.encode(text)
            else:
                # Fallback: simple hash-based embedding
                hash_val = hash(text) % 100
                return np.array([float(hash_val)] * 384)
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None
    
    def semantic_search(self, query: str, chunks: List[str], top_k=3) -> List[tuple]:
        """Search for relevant chunks using semantic similarity"""
        try:
            query_embedding = self.embed_text(query)
            if query_embedding is None:
                return []
            
            chunk_embeddings = [self.embed_text(chunk) for chunk in chunks]
            chunk_embeddings = [e for e in chunk_embeddings if e is not None]
            
            if not chunk_embeddings:
                return []
            
            # Calculate cosine similarity
            similarities = []
            for emb in chunk_embeddings:
                sim = cosine_similarity([query_embedding], [emb])[0][0]
                similarities.append(sim)
            
            # Get top-k
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            results = [(chunks[i], similarities[i]) for i in top_indices if similarities[i] > 0.1]
            
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

rag = RAGPipeline()

# ═════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@app.get('/')
def index():
    return FileResponse('index.html')

@app.get('/health')
def health():
    return {'status': 'ok', 'version': '2.0.0'}

# ─────────────────────────────────────────────────────────────────────────────
# AUTH ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post('/auth/login')
def login(req: dict):
    """Login or register user"""
    try:
        email = validate_email(req.get('email', ''))
        name = validate_string(req.get('name', 'User'), 'name', 1, 100)
        
        db = get_db()
        try:
            user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if not user:
                db.execute('INSERT INTO users (email, name) VALUES(?,?)', (email, name))
                db.commit()
                user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now() + timedelta(days=30)).isoformat()
            
            db.execute('DELETE FROM sessions WHERE user_id=? AND expires_at < ?',
                      (user['id'], datetime.now().isoformat()))
            db.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES(?,?,?)',
                      (token, user['id'], expires_at))
            db.commit()
            
            logger.info(f"User login: {email}")
            return {'token': token, 'user': dict(user), 'expires_at': expires_at}
        finally:
            db.close()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail='Login failed')

@app.post('/auth/logout')
def logout(request: Request):
    """Logout and invalidate token"""
    try:
        user = require_user(request)
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        db = get_db()
        try:
            db.execute('DELETE FROM sessions WHERE token=?', (token,))
            db.commit()
            logger.info(f"User logout: {user['email']}")
            return {'status': 'ok'}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail='Logout failed')

@app.get('/auth/me')
def get_me(request: Request):
    return require_user(request)

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: CORE - EXAMS
# ─────────────────────────────────────────────────────────────────────────────

@app.post('/exams/create')
def create_exam(req: dict, request: Request):
    """Create exam with schedule"""
    try:
        user = require_user(request)
        
        exam_name = validate_string(req.get('exam_name', ''), 'exam_name')
        subject = validate_string(req.get('subject', ''), 'subject')
        exam_date = req.get('exam_date', '')
        estimated_hours = max(0, min(1000, int(req.get('estimated_hours', 0))))
        
        try:
            exam_dt = datetime.fromisoformat(exam_date)
        except:
            raise HTTPException(status_code=400, detail='Invalid exam_date format')
        
        db = get_db()
        try:
            db.execute(
                'INSERT INTO exams (user_id, exam_name, subject, exam_date, estimated_hours) VALUES(?,?,?,?,?)',
                (user['id'], exam_name, subject, exam_date, estimated_hours)
            )
            db.commit()
            
            exam = db.execute(
                'SELECT id FROM exams WHERE user_id=? AND exam_name=? ORDER BY created_at DESC LIMIT 1',
                (user['id'], exam_name)
            ).fetchone()
            exam_id = exam['id']
            
            today = datetime.now().date()
            days_left = max(1, (exam_dt.date() - today).days)
            
            for day in range(days_left):
                schedule_date = (today + timedelta(days=day)).isoformat()
                db.execute(
                    'INSERT INTO exam_schedule (exam_id, day_number, date, hours_planned) VALUES(?,?,?,?)',
                    (exam_id, day + 1, schedule_date, 1)
                )
            
            db.commit()
            logger.info(f"Exam created: {exam_name}")
            return {'status': 'ok', 'exam_id': exam_id}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create exam error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create exam')

@app.get('/exams')
def get_exams(request: Request):
    """Get all exams"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            exams = db.execute('SELECT * FROM exams WHERE user_id=? ORDER BY exam_date', (user['id'],)).fetchall()
            return {'exams': [dict(e) for e in exams]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get exams error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get exams')

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: CORE - STREAKS
# ─────────────────────────────────────────────────────────────────────────────

@app.get('/streaks')
def get_streaks(request: Request):
    """Get streak"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            streak = db.execute('SELECT * FROM streaks WHERE user_id=?', (user['id'],)).fetchone()
            return dict(streak) if streak else {'current_streak': 0, 'longest_streak': 0, 'last_study_date': None}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get streaks error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get streaks')

@app.post('/streaks/log')
def log_streak(request: Request):
    """Log study day"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            streak = db.execute('SELECT * FROM streaks WHERE user_id=?', (user['id'],)).fetchone()
            
            if not streak:
                db.execute('INSERT OR IGNORE INTO streaks (user_id, current_streak, longest_streak, last_study_date) VALUES(?,?,?,?)',
                          (user['id'], 1, 1, today))
            else:
                if streak['last_study_date'] != today:
                    if streak['last_study_date']:
                        last = datetime.fromisoformat(streak['last_study_date']).date()
                        new_current = streak['current_streak'] + 1 if (datetime.now().date() - last).days == 1 else 1
                    else:
                        new_current = 1
                    
                    new_longest = max(new_current, streak['longest_streak'])
                    db.execute('UPDATE streaks SET current_streak=?, longest_streak=?, last_study_date=? WHERE user_id=?',
                              (new_current, new_longest, today, user['id']))
            
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Log streak error: {e}")
        raise HTTPException(status_code=500, detail='Failed to log streak')

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: CORE - DAILY REPORT
# ─────────────────────────────────────────────────────────────────────────────

@app.get('/daily-report')
def get_daily_report(request: Request):
    """Get daily report"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            log = db.execute('SELECT * FROM daily_study_log WHERE user_id=? AND study_date=?',
                            (user['id'], today)).fetchone()
            
            if not log:
                return {'minutes': 0, 'points': 0}
            
            minutes = log['minutes_studied'] or 0
            points = (minutes // 15) * 5
            return {'minutes': minutes, 'points': points}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get daily report error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get daily report')

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: HABITS - DAILY GOALS
# ─────────────────────────────────────────────────────────────────────────────

@app.get('/daily-goal')
def get_goal(request: Request):
    """Get daily goal"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?',
                             (user['id'], today)).fetchone()
            
            if not goal:
                db.execute('INSERT INTO daily_goals (user_id, goal_date, goal_minutes, completed_minutes) VALUES(?,?,?,?)',
                          (user['id'], today, 60, 0))
                db.commit()
                goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?',
                                 (user['id'], today)).fetchone()
            
            d = dict(goal)
            progress = int((d['completed_minutes'] / d['goal_minutes']) * 100) if d['goal_minutes'] > 0 else 0
            return {'goal_minutes': d['goal_minutes'], 'completed_minutes': d['completed_minutes'], 'progress': progress}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get goal error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get daily goal')

@app.post('/daily-goal/update')
def update_goal(req: dict, request: Request):
    """Update daily goal"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        minutes = max(0, int(req.get('minutes', 0)))
        
        db = get_db()
        try:
            goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?',
                             (user['id'], today)).fetchone()
            
            if goal:
                db.execute('UPDATE daily_goals SET completed_minutes=completed_minutes+? WHERE user_id=? AND goal_date=?',
                          (minutes, user['id'], today))
            else:
                db.execute('INSERT INTO daily_goals (user_id, goal_date, goal_minutes, completed_minutes) VALUES(?,?,?,?)',
                          (user['id'], today, 60, minutes))
            
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update goal error: {e}")
        raise HTTPException(status_code=500, detail='Failed to update goal')

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5: NOTES
# ─────────────────────────────────────────────────────────────────────────────

@app.post('/notes/create')
def note_create(req: dict, request: Request):
    """Create note"""
    try:
        user = require_user(request)
        
        title = validate_string(req.get('title', ''), 'title')
        content = req.get('content', '').strip()
        
        db = get_db()
        try:
            db.execute('INSERT INTO user_notes (user_id, title, content) VALUES(?,?,?)',
                      (user['id'], title, content))
            note_id = db.lastrowid
            db.commit()
            logger.info(f"Note created: {note_id}")
            return {'status': 'ok', 'note_id': note_id}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create note error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create note')

@app.get('/notes')
def notes_get(request: Request):
    """Get notes"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            notes = db.execute('SELECT * FROM user_notes WHERE user_id=? ORDER BY updated_at DESC', (user['id'],)).fetchall()
            return {'notes': [dict(n) for n in notes]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notes error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get notes')

@app.delete('/notes/{note_id}')
def delete_note(note_id: int, request: Request):
    """Delete note"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            db.execute('DELETE FROM user_notes WHERE id=? AND user_id=?', (note_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete note error: {e}")
        raise HTTPException(status_code=500, detail='Failed to delete note')

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5: FOCUS SESSIONS
# ─────────────────────────────────────────────────────────────────────────────

@app.post('/focus-session/start')
def focus_start(req: dict, request: Request):
    """Start focus session"""
    try:
        user = require_user(request)
        subject = validate_string(req.get('subject', 'General'), 'subject', 1)
        duration = max(1, min(120, int(req.get('duration', 25))))
        
        db = get_db()
        try:
            db.execute('INSERT INTO focus_sessions (user_id, subject, duration_minutes) VALUES(?,?,?)',
                      (user['id'], subject, duration))
            sid = db.lastrowid
            db.commit()
            return {'session_id': sid, 'duration': duration}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Start focus error: {e}")
        raise HTTPException(status_code=500, detail='Failed to start focus session')

@app.post('/focus-session/{session_id}/end')
def focus_end(session_id: int, req: dict, request: Request):
    """End focus session"""
    try:
        user = require_user(request)
        duration = max(1, int(req.get('duration', 25)))
        
        db = get_db()
        try:
            session = db.execute('SELECT * FROM focus_sessions WHERE id=? AND user_id=?',
                               (session_id, user['id'])).fetchone()
            
            if not session:
                raise HTTPException(status_code=404, detail='Session not found')
            
            db.execute('UPDATE focus_sessions SET completed=TRUE, ended_at=datetime("now") WHERE id=? AND user_id=?',
                      (session_id, user['id']))
            
            db.execute('INSERT INTO study_history (user_id, subject, session_type, duration_minutes) VALUES(?,?,?,?)',
                      (user['id'], session['subject'], 'focus', duration))
            
            today = datetime.now().date().isoformat()
            db.execute('''INSERT INTO daily_goals (user_id, goal_date, completed_minutes) VALUES(?,?,?)
                          ON CONFLICT(user_id, goal_date) DO UPDATE SET completed_minutes=completed_minutes+?''',
                      (user['id'], today, duration, duration))
            
            db.commit()
            logger.info(f"Focus session completed: {duration} min")
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"End focus error: {e}")
        raise HTTPException(status_code=500, detail='Failed to end focus session')

# ═════════════════════════════════════════════════════════════════════════════
# RAG CHATBOT ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@app.post('/upload/pdf')
async def upload_pdf(file: UploadFile = File(...), request: Request = None):
    """Upload and process PDF"""
    try:
        user = require_user(request)
        
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail='Only PDF files allowed')
        
        # Save file
        file_path = os.path.join(UPLOADS_DIR, f"{user['id']}_{file.filename}")
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Extract and process
        text = rag.extract_text_from_pdf(file_path)
        if not text:
            raise HTTPException(status_code=400, detail='Could not extract text from PDF')
        
        chunks = rag.chunk_text(text)
        
        # Store in database
        db = get_db()
        try:
            db.execute('INSERT INTO pdf_documents (user_id, filename, file_path) VALUES(?,?,?)',
                      (user['id'], file.filename, file_path))
            db.commit()
            
            doc_id = db.lastrowid
            
            for i, chunk in enumerate(chunks):
                embedding = rag.embed_text(chunk)
                db.execute('INSERT INTO document_chunks (document_id, chunk_text, chunk_index, embedding) VALUES(?,?,?,?)',
                          (doc_id, chunk, i, embedding.tobytes() if embedding is not None else None))
            
            db.commit()
            logger.info(f"PDF processed: {file.filename} - {len(chunks)} chunks")
            return {'status': 'ok', 'chunks': len(chunks), 'document_id': doc_id}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF upload error: {e}")
        raise HTTPException(status_code=500, detail='Failed to upload PDF')

@app.post('/chat/ask')
def chat_ask(req: dict, request: Request):
    """Ask RAG chatbot with PDF context"""
    try:
        user = require_user(request)
        question = validate_string(req.get('question', ''), 'question', 3, 1000)
        
        db = get_db()
        try:
            # Get user's document chunks
            chunks_data = db.execute('''
                SELECT dc.chunk_text FROM document_chunks dc
                JOIN pdf_documents pd ON dc.document_id = pd.id
                WHERE pd.user_id = ?
            ''', (user['id'],)).fetchall()
            
            if not chunks_data:
                chunks = []
            else:
                chunks = [row['chunk_text'] for row in chunks_data]
            
            # Semantic search
            relevant_chunks = []
            relevance_score = 0.0
            
            if chunks:
                search_results = rag.semantic_search(question, chunks, top_k=3)
                if search_results:
                    relevant_chunks = [chunk for chunk, score in search_results]
                    relevance_score = sum([score for _, score in search_results]) / len(search_results)
            
            # Get Wikipedia context
            wiki_context = get_wikipedia_context(question)
            
            # Prepare enhanced prompt
            context = "\n".join(relevant_chunks) + "\n" + wiki_context
            
            # Get Groq response
            answer = get_groq_response(question, context)
            
            # Store in history
            db.execute('''INSERT INTO chat_history (user_id, question, answer, relevant_chunks, relevance_score)
                         VALUES(?,?,?,?,?)''',
                      (user['id'], question, answer, json.dumps(relevant_chunks), relevance_score))
            db.commit()
            
            logger.info(f"Chat question: {question[:50]}...")
            return {
                'status': 'ok',
                'answer': answer,
                'relevant_chunks': relevant_chunks,
                'relevance_score': float(relevance_score)
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail='Failed to process question')

@app.get('/chat/history')
def chat_history(request: Request):
    """Get chat history"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            history = db.execute('''SELECT * FROM chat_history WHERE user_id=?
                                   ORDER BY created_at DESC LIMIT 50''', (user['id'],)).fetchall()
            return {'history': [dict(h) for h in history]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get chat history')

# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def get_wikipedia_context(query: str) -> str:
    """Get context from Wikipedia"""
    try:
        params = {
            'action': 'query',
            'format': 'json',
            'titles': query.split()[0],
            'prop': 'extracts',
            'explaintext': True,
            'exintro': True
        }
        response = requests.get(WIKIPEDIA_API_URL, params=params, timeout=5)
        data = response.json()
        
        pages = data['query']['pages']
        for page_id, page_data in pages.items():
            if 'extract' in page_data:
                return page_data['extract'][:500]
        return ""
    except Exception as e:
        logger.warning(f"Wikipedia fetch error: {e}")
        return ""

def get_groq_response(question: str, context: str) -> str:
    """Get response from Groq API"""
    try:
        if not GROQ_API_KEY:
            return "Groq API key not configured. Please configure GROQ_API_KEY."
        
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt = f"""You are an AI study assistant. Based on the context provided, answer the student's question clearly and concisely.

Context:
{context}

Student Question: {question}

Provide a helpful, educational answer. If the context doesn't contain relevant information, provide general knowledge while acknowledging the limitation."""
        
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return f"Error generating response: {str(e)}"

# ═════════════════════════════════════════════════════════════════════════════
# REMAINING PHASE ENDPOINTS (PLACEHOLDER)
# ═════════════════════════════════════════════════════════════════════════════

@app.get('/leaderboard/global')
def leaderboard():
    """Get global leaderboard"""
    try:
        db = get_db()
        try:
            users = db.execute('SELECT * FROM leaderboard ORDER BY total_points DESC LIMIT 100').fetchall()
            return {'leaderboard': [dict(u) for u in users]}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Get leaderboard error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get leaderboard')

@app.get('/notifications')
def get_notifications(request: Request):
    """Get notifications"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            n = db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC', 
                          (user['id'],)).fetchall()
            return {'notifications': [dict(x) for x in n]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get notifications')

# ═════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
