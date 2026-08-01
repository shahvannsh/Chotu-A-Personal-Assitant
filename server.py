"""
NOT USED. Do not run this file.

This is an older SQLite-based prototype, superseded by app.py (FastAPI +
Postgres, split across core.py / routers/*.py). Procfile already points
at app.py; start.bat and launch_chotu.bat were fixed to do the same.
Kept only for history — delete once you've confirmed nothing references it.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import sqlite3
from datetime import datetime, timedelta
import secrets
import logging
from functools import lru_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CHOTU", version="1.0.0")

# FIX #1: CORS - Restrict origins instead of allow-all
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

# Database configuration
DB_PATH = '/data/chotu.db' if os.path.exists('/data') else 'chotu.db'

def get_db():
    """Get database connection with PRAGMA enforcement"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # FIX #9: Enable foreign keys enforcement
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Initialize database with all tables"""
    db = get_db()
    try:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            picture TEXT,
            groq_key TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
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
        
        CREATE TABLE IF NOT EXISTS student_mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            mistake_pattern TEXT,
            frequency INTEGER DEFAULT 1,
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
        
        CREATE TABLE IF NOT EXISTS daily_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recommendation_date TEXT,
            subject TEXT,
            topic TEXT,
            reason TEXT,
            UNIQUE(user_id, recommendation_date, topic),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
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
        
        CREATE TABLE IF NOT EXISTS share_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            user_id INTEGER NOT NULL,
            share_type TEXT,
            data TEXT,
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER,
            share_token TEXT,
            converted BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS friend_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            UNIQUE(user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS friend_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT,
            subject TEXT,
            value TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            subject TEXT,
            topic TEXT,
            color TEXT DEFAULT '#4a5568',
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
            notes TEXT,
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
        
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'default',
            dark_mode BOOLEAN DEFAULT TRUE,
            notifications_enabled BOOLEAN DEFAULT TRUE,
            language TEXT DEFAULT 'en',
            focus_session_duration INTEGER DEFAULT 25,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            plan TEXT DEFAULT 'free',
            status TEXT DEFAULT 'active',
            started_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            auto_renew BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS premium_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feature_name TEXT NOT NULL,
            unlocked_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, feature_name),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS ai_mentor_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            question TEXT,
            ai_response TEXT,
            student_rating INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS interview_prep_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_type TEXT,
            company TEXT,
            question TEXT,
            user_answer TEXT,
            feedback TEXT,
            score INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS peer_tutoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            session_status TEXT DEFAULT 'requested',
            completed_at TEXT,
            student_rating INTEGER,
            tutor_earnings FLOAT DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (tutor_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS adaptive_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            current_level INTEGER DEFAULT 1,
            mastered_topics INTEGER DEFAULT 0,
            total_topics INTEGER,
            estimated_completion_days INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, subject),
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
        """)
        db.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database init error: {e}")
        raise
    finally:
        db.close()

# Initialize database on startup
init_db()

# FIX #4: Input validation helper
def validate_string(value, field_name, min_len=1, max_len=255):
    """Validate string input"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be string")
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        raise ValueError(f"{field_name} must be {min_len}-{max_len} characters")
    return value

def validate_email(email):
    """Validate email format"""
    email = email.strip().lower()
    if '@' not in email or len(email) < 5:
        raise ValueError("Invalid email format")
    return email

# FIX #4 & #5: Authentication with token expiration
def require_user(request: Request):
    """Validate user with token expiration check"""
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
            
            # FIX #4: Check token expiration
            expires_at = datetime.fromisoformat(session['expires_at'])
            if expires_at < datetime.now():
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

# ═══════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/')
def index():
    return FileResponse('index.html')

@app.post('/auth/login')
def login(req: dict):
    """Login or register user"""
    try:
        email = validate_email(req.get('email', ''))
        name = validate_string(req.get('name', 'User'), 'name', min_len=1, max_len=100)
        
        db = get_db()
        try:
            user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if not user:
                db.execute('INSERT INTO users (email, name) VALUES(?,?)', (email, name))
                db.commit()
                user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            
            # FIX #4: Token with 30-day expiration
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
    """Get current user"""
    try:
        return require_user(request)
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get user')

@app.get('/health')
def health():
    return {'status': 'ok', 'version': '1.0.0'}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: EXAMS
# ═══════════════════════════════════════════════════════════════════════════

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
            
            # FIX #10: Create exam schedule
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

@app.get('/exams/{exam_id}')
def get_exam(exam_id: int, request: Request):
    """Get exam with schedule"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            exam = db.execute('SELECT * FROM exams WHERE id=? AND user_id=?', (exam_id, user['id'])).fetchone()
            if not exam:
                raise HTTPException(status_code=404, detail='Exam not found')
            
            schedule = db.execute('SELECT * FROM exam_schedule WHERE exam_id=? ORDER BY day_number', (exam_id,)).fetchall()
            return {'exam': dict(exam), 'schedule': [dict(s) for s in schedule]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get exam error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get exam')

@app.put('/exams/{exam_id}')
def update_exam(exam_id: int, req: dict, request: Request):
    """Update exam"""
    try:
        user = require_user(request)
        
        exam_name = req.get('exam_name', '').strip()
        subject = req.get('subject', '').strip()
        
        if exam_name and len(exam_name) == 0:
            raise HTTPException(status_code=400, detail='Invalid exam_name')
        if subject and len(subject) == 0:
            raise HTTPException(status_code=400, detail='Invalid subject')
        
        db = get_db()
        try:
            db.execute('UPDATE exams SET exam_name=?, subject=? WHERE id=? AND user_id=?',
                      (exam_name or None, subject or None, exam_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update exam error: {e}")
        raise HTTPException(status_code=500, detail='Failed to update exam')

@app.delete('/exams/{exam_id}')
def delete_exam(exam_id: int, request: Request):
    """Delete exam"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            db.execute('DELETE FROM exams WHERE id=? AND user_id=?', (exam_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete exam error: {e}")
        raise HTTPException(status_code=500, detail='Failed to delete exam')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: STREAKS
# ═══════════════════════════════════════════════════════════════════════════

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
    """Log study day - FIX #1: Race condition"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            streak = db.execute('SELECT * FROM streaks WHERE user_id=?', (user['id'],)).fetchone()
            
            if not streak:
                # FIX #1: Use INSERT OR IGNORE to prevent race condition
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

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: DAILY REPORT
# ═══════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: MOCK EXAMS
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/mock-exam/generate')
def gen_mock(req: dict, request: Request):
    """Generate mock exam"""
    try:
        user = require_user(request)
        subject = validate_string(req.get('subject', 'General'), 'subject')
        
        db = get_db()
        try:
            db.execute('INSERT INTO mock_exams (user_id, subject, total_questions) VALUES(?,?,?)',
                      (user['id'], subject, 10))
            exam_id = db.lastrowid
            db.commit()
            
            return {
                'exam_id': exam_id,
                'questions': [
                    {'id': i, 'question': f'Question {i+1}?', 'options': ['A','B','C','D']}
                    for i in range(10)
                ]
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Generate mock error: {e}")
        raise HTTPException(status_code=500, detail='Failed to generate mock exam')

@app.post('/mock-exam/{exam_id}/submit')
def submit_mock(exam_id: int, req: dict, request: Request):
    """Submit mock exam"""
    try:
        user = require_user(request)
        score = max(0, min(100, int(req.get('score', 0))))
        accuracy = max(0, min(100, int(req.get('accuracy', 0))))
        
        db = get_db()
        try:
            db.execute('UPDATE mock_exams SET score=?, accuracy=? WHERE id=? AND user_id=?',
                      (score, accuracy, exam_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit mock error: {e}")
        raise HTTPException(status_code=500, detail='Failed to submit mock exam')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: DAILY GOALS
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/daily-goal')
def get_goal(request: Request):
    """Get daily goal - FIX #11: Auto-create"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?',
                             (user['id'], today)).fetchone()
            
            # FIX #11: Auto-create daily goal
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

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/notifications')
def notifs(request: Request):
    """Get notifications"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            n = db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC', (user['id'],)).fetchall()
            return {'notifications': [dict(x) for x in n]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get notifications')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: CHALLENGES
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/challenges/create')
def create_challenge(req: dict, request: Request):
    """Create challenge"""
    try:
        user = require_user(request)
        
        challenge_type = validate_string(req.get('type', ''), 'type', min_len=1)
        subject = validate_string(req.get('subject', ''), 'subject', min_len=1)
        target = max(0, int(req.get('target', 0)))
        
        db = get_db()
        try:
            db.execute('INSERT INTO challenges (creator_id, challenge_type, subject, target_value) VALUES(?,?,?,?)',
                      (user['id'], challenge_type, subject, target))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create challenge error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create challenge')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: FRIENDS
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/friends/connect')
def connect(req: dict, request: Request):
    """Connect friend"""
    try:
        user = require_user(request)
        friend_id = req.get('friend_id')
        
        if not friend_id:
            raise HTTPException(status_code=400, detail='friend_id required')
        
        if friend_id == user['id']:
            raise HTTPException(status_code=400, detail='Cannot add yourself')
        
        db = get_db()
        try:
            db.execute('INSERT OR IGNORE INTO friend_connections (user_id, friend_id) VALUES(?,?)',
                      (user['id'], friend_id))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connect friend error: {e}")
        raise HTTPException(status_code=500, detail='Failed to connect friend')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: NOTES
# ═══════════════════════════════════════════════════════════════════════════

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

@app.put('/notes/{note_id}')
def update_note(note_id: int, req: dict, request: Request):
    """Update note"""
    try:
        user = require_user(request)
        content = req.get('content', '').strip()
        
        db = get_db()
        try:
            db.execute('UPDATE user_notes SET content=?, updated_at=datetime("now") WHERE id=? AND user_id=?',
                      (content, note_id, user['id']))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update note error: {e}")
        raise HTTPException(status_code=500, detail='Failed to update note')

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

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: BOOKMARKS
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/bookmarks/add')
def bookmark_add(req: dict, request: Request):
    """Add bookmark"""
    try:
        user = require_user(request)
        
        title = validate_string(req.get('title', ''), 'title')
        url = validate_string(req.get('url', ''), 'url', min_len=5)
        res_type = req.get('type', 'link').strip()
        
        db = get_db()
        try:
            db.execute('INSERT INTO bookmarks (user_id, resource_type, resource_title, resource_url) VALUES(?,?,?,?)',
                      (user['id'], res_type, title, url))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Add bookmark error: {e}")
        raise HTTPException(status_code=500, detail='Failed to add bookmark')

@app.get('/bookmarks')
def bookmarks_get(request: Request):
    """Get bookmarks"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            b = db.execute('SELECT * FROM bookmarks WHERE user_id=? ORDER BY created_at DESC', (user['id'],)).fetchall()
            return {'bookmarks': [dict(x) for x in b]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get bookmarks error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get bookmarks')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: STUDY HISTORY
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/study/log')
def study_log(req: dict, request: Request):
    """Log study session - FIX #2: Logs all sessions"""
    try:
        user = require_user(request)
        
        subject = validate_string(req.get('subject', 'General'), 'subject', min_len=1)
        duration = max(1, int(req.get('duration', 0)))
        accuracy = max(0, min(100, int(req.get('accuracy', 0))))
        
        db = get_db()
        try:
            db.execute('INSERT INTO study_history (user_id, subject, duration_minutes, accuracy, session_type) VALUES(?,?,?,?,?)',
                      (user['id'], subject, duration, accuracy, 'study'))
            db.commit()
            logger.info(f"Study logged: {subject} - {duration} min")
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Log study error: {e}")
        raise HTTPException(status_code=500, detail='Failed to log study session')

@app.get('/study/history')
def history_get(request: Request):
    """Get study history"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            h = db.execute('SELECT * FROM study_history WHERE user_id=? ORDER BY date DESC LIMIT 100', (user['id'],)).fetchall()
            return {'history': [dict(x) for x in h]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get history')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: GOALS
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/goals/create')
def goal_create(req: dict, request: Request):
    """Create goal"""
    try:
        user = require_user(request)
        
        name = validate_string(req.get('name', ''), 'name')
        
        db = get_db()
        try:
            db.execute('INSERT INTO user_goals (user_id, goal_name, target_value, deadline) VALUES(?,?,?,?)',
                      (user['id'], name, req.get('target', ''), req.get('deadline', '')))
            db.commit()
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create goal error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create goal')

@app.get('/goals')
def goals_get(request: Request):
    """Get goals"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            g = db.execute('SELECT * FROM user_goals WHERE user_id=? AND status=?', (user['id'], 'active')).fetchall()
            return {'goals': [dict(x) for x in g]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get goals error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get goals')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: AI MENTOR (Premium)
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/ai-mentor/ask')
def mentor_ask(req: dict, request: Request):
    """Ask AI mentor"""
    try:
        user = require_user(request)
        
        db = get_db()
        try:
            sub = db.execute('SELECT plan FROM subscriptions WHERE user_id=?', (user['id'],)).fetchone()
            
            if not sub or sub['plan'] == 'free':
                raise HTTPException(status_code=403, detail='Premium feature required')
            
            subject = validate_string(req.get('subject', ''), 'subject', min_len=1)
            topic = validate_string(req.get('topic', ''), 'topic', min_len=1)
            question = validate_string(req.get('question', ''), 'question', min_len=1)
            
            answer = f"Comprehensive explanation of {topic} in {subject}: This requires deep understanding of foundational concepts and their applications."
            
            db.execute('INSERT INTO ai_mentor_sessions (user_id, subject, topic, question, ai_response) VALUES(?,?,?,?,?)',
                      (user['id'], subject, topic, question, answer))
            db.commit()
            
            return {'answer': answer}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Mentor ask error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get AI response')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: INTERVIEW PREP (Premium)
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/interview-prep/start')
def interview_start(req: dict, request: Request):
    """Start interview prep"""
    try:
        user = require_user(request)
        
        db = get_db()
        try:
            sub = db.execute('SELECT plan FROM subscriptions WHERE user_id=?', (user['id'],)).fetchone()
            
            if not sub or sub['plan'] == 'free':
                raise HTTPException(status_code=403, detail='Premium feature required')
            
            company = validate_string(req.get('company', 'Google'), 'company', min_len=1)
            session_type = req.get('type', 'behavioral').strip()
            
            questions = {
                'behavioral': f'Tell me about a time you overcame a challenge at {company}.',
                'technical': f'Design a scalable system for {company}.',
                'coding': f'Write an efficient algorithm for {company}.',
            }
            
            question = questions.get(session_type, 'Answer this interview question.')
            
            db.execute('INSERT INTO interview_prep_sessions (user_id, session_type, company, question) VALUES(?,?,?,?)',
                      (user['id'], session_type, company, question))
            sid = db.lastrowid
            db.commit()
            
            return {'session_id': sid, 'question': question}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Interview start error: {e}")
        raise HTTPException(status_code=500, detail='Failed to start interview prep')

@app.post('/interview-prep/{session_id}/submit')
def interview_submit(session_id: int, req: dict, request: Request):
    """Submit interview response"""
    try:
        user = require_user(request)
        answer = validate_string(req.get('answer', ''), 'answer', min_len=1)
        
        db = get_db()
        try:
            db.execute('UPDATE interview_prep_sessions SET user_answer=?, feedback=?, score=? WHERE id=? AND user_id=?',
                      (answer, 'Great response! Strong technical knowledge demonstrated.', 85, session_id, user['id']))
            db.commit()
            return {'score': 85, 'feedback': 'Great response! Strong technical knowledge demonstrated.'}
        finally:
            db.close()
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Interview submit error: {e}")
        raise HTTPException(status_code=500, detail='Failed to submit interview response')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: SUBSCRIPTIONS
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/subscription/status')
def sub_status(request: Request):
    """Get subscription status"""
    try:
        user = require_user(request)
        db = get_db()
        try:
            sub = db.execute('SELECT plan FROM subscriptions WHERE user_id=?', (user['id'],)).fetchone()
            return {'plan': dict(sub)['plan'] if sub else 'free'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get subscription error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get subscription')

@app.post('/subscription/upgrade')
def sub_upgrade(req: dict, request: Request):
    """Upgrade subscription"""
    try:
        user = require_user(request)
        plan = req.get('plan', 'pro').strip()
        
        if plan not in ['free', 'pro', 'premium']:
            raise HTTPException(status_code=400, detail='Invalid plan')
        
        db = get_db()
        try:
            expires = (datetime.now() + timedelta(days=30)).isoformat()
            db.execute('INSERT OR REPLACE INTO subscriptions (user_id, plan, expires_at) VALUES(?,?,?)',
                      (user['id'], plan, expires))
            db.commit()
            logger.info(f"Subscription upgraded to: {plan}")
            return {'status': 'ok', 'plan': plan}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upgrade subscription error: {e}")
        raise HTTPException(status_code=500, detail='Failed to upgrade subscription')

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: FOCUS SESSIONS
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/focus-session/start')
def focus_start(req: dict, request: Request):
    """Start focus session"""
    try:
        user = require_user(request)
        subject = validate_string(req.get('subject', 'General'), 'subject', min_len=1)
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
    """End focus session - FIX #2: Logs to study_history"""
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
            
            # FIX #2: Log to study_history
            db.execute('INSERT INTO study_history (user_id, subject, session_type, duration_minutes) VALUES(?,?,?,?)',
                      (user['id'], session['subject'], 'focus', duration))
            
            # Update daily goal
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

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
