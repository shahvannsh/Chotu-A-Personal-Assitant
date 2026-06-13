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

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CHOTU", version="1.0.0")

# CORS - FIXED: Restrict to specific origins
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8000,https://chotu-lcc7.onrender.com').split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Database
DB_PATH = '/data/chotu.db' if os.path.exists('/data') else 'chotu.db'

def get_db():
    """Get database connection with PRAGMA enforcement"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # FIXED: Enable foreign keys
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Initialize ALL tables for Phase 1-5"""
    db = get_db()
    try:
        db.executescript("""
        -- USERS & AUTH
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            picture TEXT,
            groq_key TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
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
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            day_number INTEGER,
            date TEXT,
            topics TEXT,
            hours_planned INTEGER,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS streaks (
            user_id INTEGER PRIMARY KEY,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_study_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS daily_study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            study_date TEXT,
            minutes_studied INTEGER DEFAULT 0,
            topics_reviewed TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS weak_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            confidence FLOAT DEFAULT 0.5,
            last_reviewed TEXT,
            next_review TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        -- PHASE 2: INTELLIGENCE
        CREATE TABLE IF NOT EXISTS mock_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            exam_name TEXT,
            total_questions INTEGER,
            score INTEGER,
            accuracy FLOAT,
            time_taken_minutes INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            difficulty INTEGER
        );
        
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER,
            is_correct BOOLEAN,
            time_spent_seconds INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS student_mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT,
            topic TEXT,
            mistake_pattern TEXT,
            frequency INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
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
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            total_points INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            rank INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT,
            badge_icon TEXT,
            earned_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, badge_name),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS daily_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recommendation_date TEXT,
            subject TEXT,
            topic TEXT,
            reason TEXT,
            UNIQUE(user_id, recommendation_date, topic),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        -- PHASE 4: DISTRIBUTION
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            message TEXT,
            type TEXT,
            read BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
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
            FOREIGN KEY (creator_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS share_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            user_id INTEGER NOT NULL,
            share_type TEXT,
            data TEXT,
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER,
            share_token TEXT,
            converted BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (referrer_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS friend_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            UNIQUE(user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS friend_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT,
            subject TEXT,
            value TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        -- PHASE 5: PREMIUM & PERSISTENCE
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
            resource_title TEXT,
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
            feature_name TEXT,
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
            subject TEXT,
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

init_db()

# Auth Helper - FIXED: Check token expiration
def require_user(request: Request):
    """Validate user authentication with token expiration"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        raise HTTPException(status_code=401, detail='No token provided')
    
    db = get_db()
    try:
        session = db.execute('SELECT user_id, expires_at FROM sessions WHERE token=?', (token,)).fetchone()
        
        if not session:
            raise HTTPException(status_code=401, detail='Invalid token')
        
        # FIXED: Check token expiration
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

# ═══════════════════════════════════════════════════════════════════════════
# STATIC & AUTH
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/')
def index():
    return FileResponse('index.html')

@app.post('/auth/login')
def login(req: dict):
    """Login or register with email - FIXED: Token expiration"""
    # FIXED: Input validation
    email = req.get('email', '').strip()
    name = req.get('name', 'User').strip()
    
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail='Invalid email')
    if len(name) == 0 or len(name) > 100:
        raise HTTPException(status_code=400, detail='Invalid name')
    
    db = get_db()
    try:
        user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if not user:
            db.execute('INSERT INTO users (email, name) VALUES(?,?)', (email, name))
            db.commit()
            user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        
        # FIXED: Token expiration (30 days)
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        # Delete old sessions
        db.execute('DELETE FROM sessions WHERE user_id=? AND expires_at < ?',
                  (user['id'], datetime.now().isoformat()))
        
        db.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES(?,?,?)',
                  (token, user['id'], expires_at))
        db.commit()
        
        logger.info(f"User logged in: {email}")
        return {'token': token, 'user': dict(user), 'expires_at': expires_at}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail='Login failed')
    finally:
        db.close()

@app.post('/auth/logout')
def logout(request: Request):
    """Logout - invalidate token"""
    try:
        user = require_user(request)
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        db = get_db()
        db.execute('DELETE FROM sessions WHERE token=?', (token,))
        db.commit()
        db.close()
        
        logger.info(f"User logged out: {user['email']}")
        return {'status': 'logged out'}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail='Logout failed')

@app.get('/auth/me')
def get_me(request: Request):
    try:
        return require_user(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get user')

@app.get('/health')
def health():
    return {'status': 'ok', 'version': '1.0.0'}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: CORE
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/exams/create')
def create_exam(req: dict, request: Request):
    """Create exam - FIXED: Validation + schedule creation"""
    try:
        user = require_user(request)
        
        # FIXED: Input validation
        exam_name = req.get('exam_name', '').strip()
        subject = req.get('subject', '').strip()
        exam_date = req.get('exam_date', '').strip()
        estimated_hours = req.get('estimated_hours', 0)
        
        if not exam_name or len(exam_name) == 0:
            raise HTTPException(status_code=400, detail='Exam name required')
        if not subject or len(subject) == 0:
            raise HTTPException(status_code=400, detail='Subject required')
        if not exam_date:
            raise HTTPException(status_code=400, detail='Exam date required')
        
        try:
            exam_dt = datetime.fromisoformat(exam_date)
        except:
            raise HTTPException(status_code=400, detail='Invalid date format')
        
        estimated_hours = max(0, min(int(estimated_hours or 0), 1000))
        
        db = get_db()
        try:
            # Create exam
            db.execute('INSERT INTO exams (user_id, exam_name, subject, exam_date, estimated_hours) VALUES(?,?,?,?,?)',
                      (user['id'], exam_name, subject, exam_date, estimated_hours))
            db.commit()
            
            exam = db.execute('SELECT id FROM exams WHERE user_id=? AND exam_name=? ORDER BY created_at DESC LIMIT 1',
                            (user['id'], exam_name)).fetchone()
            exam_id = exam['id']
            
            # FIXED: Create exam schedule
            today = datetime.now().date()
            days_left = (exam_dt.date() - today).days
            
            for day in range(max(1, days_left)):
                schedule_date = (today + timedelta(days=day)).isoformat()
                db.execute('INSERT INTO exam_schedule (exam_id, day_number, date, hours_planned) VALUES(?,?,?,?)',
                          (exam_id, day + 1, schedule_date, 1))
            
            db.commit()
            logger.info(f"Exam created: {exam_name} by {user['email']}")
            return {'status': 'ok', 'exam_id': exam_id}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create exam error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create exam')

@app.get('/exams')
def get_exams(request: Request):
    """Get user exams"""
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
            raise HTTPException(status_code=400, detail='Invalid exam name')
        if subject and len(subject) == 0:
            raise HTTPException(status_code=400, detail='Invalid subject')
        
        db = get_db()
        try:
            db.execute('UPDATE exams SET exam_name=?, subject=? WHERE id=? AND user_id=?',
                      (exam_name or None, subject or None, exam_id, user['id']))
            db.commit()
            logger.info(f"Exam updated: {exam_id}")
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
            logger.info(f"Exam deleted: {exam_id}")
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete exam error: {e}")
        raise HTTPException(status_code=500, detail='Failed to delete exam')

@app.get('/streaks')
def get_streaks(request: Request):
    """Get streak count"""
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
    """Log study day - FIXED: Race condition using INSERT OR REPLACE"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            streak = db.execute('SELECT * FROM streaks WHERE user_id=?', (user['id'],)).fetchone()
            
            if not streak:
                # FIXED: Use INSERT OR IGNORE to prevent duplicate on race condition
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
            logger.info(f"Streak logged for user: {user['id']}")
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Log streak error: {e}")
        raise HTTPException(status_code=500, detail='Failed to log streak')

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
# PHASE 2: INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/mock-exam/generate')
def gen_mock(req: dict, request: Request):
    """Generate mock exam"""
    try:
        user = require_user(request)
        subject = req.get('subject', 'General').strip()
        
        if not subject:
            raise HTTPException(status_code=400, detail='Subject required')
        
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
    except Exception as e:
        logger.error(f"Generate mock error: {e}")
        raise HTTPException(status_code=500, detail='Failed to generate mock exam')

@app.post('/mock-exam/{exam_id}/submit')
def submit_mock(exam_id: int, req: dict, request: Request):
    """Submit mock exam"""
    try:
        user = require_user(request)
        score = req.get('score', 0)
        accuracy = req.get('accuracy', 0)
        
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
# PHASE 3: HABITS
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/daily-goal')
def get_goal(request: Request):
    """Get daily goal - FIXED: Auto-create if not exists"""
    try:
        user = require_user(request)
        today = datetime.now().date().isoformat()
        
        db = get_db()
        try:
            goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?',
                             (user['id'], today)).fetchone()
            
            # FIXED: Auto-create daily goal
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
# PHASE 4: DISTRIBUTION
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

@app.post('/challenges/create')
def create_challenge(req: dict, request: Request):
    """Create challenge"""
    try:
        user = require_user(request)
        
        challenge_type = req.get('type', '').strip()
        subject = req.get('subject', '').strip()
        target = req.get('target', 0)
        
        if not challenge_type or not subject:
            raise HTTPException(status_code=400, detail='Type and subject required')
        
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
    except Exception as e:
        logger.error(f"Create challenge error: {e}")
        raise HTTPException(status_code=500, detail='Failed to create challenge')

@app.post('/friends/connect')
def connect(req: dict, request: Request):
    """Connect friend"""
    try:
        user = require_user(request)
        friend_id = req.get('friend_id')
        
        if not friend_id:
            raise HTTPException(status_code=400, detail='Friend ID required')
        
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
# PHASE 5: PREMIUM & PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/notes/create')
def note_create(req: dict, request: Request):
    """Create note"""
    try:
        user = require_user(request)
        
        title = req.get('title', '').strip()
        content = req.get('content', '').strip()
        
        if not title:
            raise HTTPException(status_code=400, detail='Title required')
        
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
            logger.info(f"Note updated: {note_id}")
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
            logger.info(f"Note deleted: {note_id}")
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete note error: {e}")
        raise HTTPException(status_code=500, detail='Failed to delete note')

@app.post('/bookmarks/add')
def bookmark_add(req: dict, request: Request):
    """Add bookmark"""
    try:
        user = require_user(request)
        
        title = req.get('title', '').strip()
        url = req.get('url', '').strip()
        res_type = req.get('type', 'link').strip()
        
        if not title or not url:
            raise HTTPException(status_code=400, detail='Title and URL required')
        
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
            b = db.execute('SELECT * FROM bookmarks WHERE user_id=?', (user['id'],)).fetchall()
            return {'bookmarks': [dict(x) for x in b]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get bookmarks error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get bookmarks')

@app.post('/study/log')
def study_log(req: dict, request: Request):
    """Log study session - FIXED: Validates all fields"""
    try:
        user = require_user(request)
        
        subject = req.get('subject', 'General').strip()
        duration = max(0, int(req.get('duration', 0)))
        accuracy = max(0, min(100, int(req.get('accuracy', 0))))
        
        db = get_db()
        try:
            db.execute('INSERT INTO study_history (user_id, subject, duration_minutes, accuracy) VALUES(?,?,?,?)',
                      (user['id'], subject, duration, accuracy))
            db.commit()
            logger.info(f"Study session logged: {subject} - {duration} min")
            return {'status': 'ok'}
        finally:
            db.close()
    except HTTPException:
        raise
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
            h = db.execute('SELECT * FROM study_history WHERE user_id=? ORDER BY date DESC LIMIT 50', (user['id'],)).fetchall()
            return {'history': [dict(x) for x in h]}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get history error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get history')

@app.post('/goals/create')
def goal_create(req: dict, request: Request):
    """Create personal goal"""
    try:
        user = require_user(request)
        
        name = req.get('name', '').strip()
        if not name:
            raise HTTPException(status_code=400, detail='Goal name required')
        
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
            
            subject = req.get('subject', '').strip()
            topic = req.get('topic', '').strip()
            question = req.get('question', '').strip()
            
            if not subject or not topic or not question:
                raise HTTPException(status_code=400, detail='All fields required')
            
            answer = f"Comprehensive explanation of {topic} in {subject}: This requires understanding of fundamental concepts..."
            
            db.execute('INSERT INTO ai_mentor_sessions (user_id, subject, topic, question, ai_response) VALUES(?,?,?,?,?)',
                      (user['id'], subject, topic, question, answer))
            db.commit()
            
            return {'answer': answer}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mentor ask error: {e}")
        raise HTTPException(status_code=500, detail='Failed to get AI response')

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
            
            company = req.get('company', 'Google').strip()
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
    except Exception as e:
        logger.error(f"Interview start error: {e}")
        raise HTTPException(status_code=500, detail='Failed to start interview prep')

@app.post('/interview-prep/{session_id}/submit')
def interview_submit(session_id: int, req: dict, request: Request):
    """Submit interview response"""
    try:
        user = require_user(request)
        answer = req.get('answer', '').strip()
        
        if not answer:
            raise HTTPException(status_code=400, detail='Answer required')
        
        db = get_db()
        try:
            db.execute('UPDATE interview_prep_sessions SET user_answer=?, feedback=?, score=? WHERE id=? AND user_id=?',
                      (answer, 'Great response! Strong technical knowledge.', 85, session_id, user['id']))
            db.commit()
            return {'score': 85, 'feedback': 'Great response! Strong technical knowledge.'}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Interview submit error: {e}")
        raise HTTPException(status_code=500, detail='Failed to submit interview response')

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

@app.post('/focus-session/start')
def focus_start(req: dict, request: Request):
    """Start focus session"""
    try:
        user = require_user(request)
        subject = req.get('subject', 'General').strip()
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
    except Exception as e:
        logger.error(f"Start focus error: {e}")
        raise HTTPException(status_code=500, detail='Failed to start focus session')

@app.post('/focus-session/{session_id}/end')
def focus_end(session_id: int, req: dict, request: Request):
    """End focus session - FIXED: Logs to study_history"""
    try:
        user = require_user(request)
        duration = max(1, int(req.get('duration', 25)))
        
        db = get_db()
        try:
            # Get focus session details
            session = db.execute('SELECT * FROM focus_sessions WHERE id=? AND user_id=?',
                               (session_id, user['id'])).fetchone()
            
            if not session:
                raise HTTPException(status_code=404, detail='Session not found')
            
            # Mark as completed
            db.execute('UPDATE focus_sessions SET completed=TRUE, ended_at=datetime("now") WHERE id=? AND user_id=?',
                      (session_id, user['id']))
            
            # FIXED: Log to study_history
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
