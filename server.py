from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import sqlite3
from datetime import datetime, timedelta
import secrets

app = FastAPI(title="CHOTU", version="1.0.0")

# CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
DB_PATH = '/data/chotu.db' if os.path.exists('/data') else 'chotu.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize ALL tables for Phase 1-5"""
    db = get_db()
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
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    -- PHASE 1: CORE
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        exam_name TEXT NOT NULL,
        subject TEXT,
        exam_date TEXT,
        estimated_hours INTEGER,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS exam_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER,
        day_number INTEGER,
        date TEXT,
        topics TEXT,
        hours_planned INTEGER,
        status TEXT DEFAULT 'pending'
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
        goal_date TEXT,
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
        title TEXT,
        content TEXT,
        subject TEXT,
        topic TEXT,
        color TEXT DEFAULT '#4a5568',
        pinned BOOLEAN DEFAULT FALSE,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
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
        FOREIGN KEY (user_id) REFERENCES users(id)
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
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS user_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        goal_name TEXT,
        goal_type TEXT,
        target_value TEXT,
        deadline TEXT,
        progress INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        theme TEXT DEFAULT 'default',
        dark_mode BOOLEAN DEFAULT TRUE,
        notifications_enabled BOOLEAN DEFAULT TRUE,
        language TEXT DEFAULT 'en',
        focus_session_duration INTEGER DEFAULT 25,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        plan TEXT DEFAULT 'free',
        status TEXT DEFAULT 'active',
        started_at TEXT DEFAULT (datetime('now')),
        expires_at TEXT,
        auto_renew BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS premium_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        feature_name TEXT,
        unlocked_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, feature_name),
        FOREIGN KEY (user_id) REFERENCES users(id)
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
        FOREIGN KEY (user_id) REFERENCES users(id)
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
        FOREIGN KEY (user_id) REFERENCES users(id)
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
        FOREIGN KEY (tutor_id) REFERENCES users(id),
        FOREIGN KEY (student_id) REFERENCES users(id)
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
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    
    CREATE TABLE IF NOT EXISTS focus_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT,
        duration_minutes INTEGER DEFAULT 25,
        completed BOOLEAN DEFAULT FALSE,
        started_at TEXT DEFAULT (datetime('now')),
        ended_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
    db.commit()
    db.close()

init_db()

# Auth Helper
def require_user(request: Request):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        raise HTTPException(status_code=401)
    db = get_db()
    session = db.execute('SELECT user_id FROM sessions WHERE token=?', (token,)).fetchone()
    if not session:
        db.close()
        raise HTTPException(status_code=401)
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    db.close()
    return dict(user) if user else None

# ═══════════════════════════════════════════════════════════════════════════
# STATIC & AUTH
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/')
def index():
    return FileResponse('index.html')

@app.post('/auth/login')
def login(req: dict):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE email=?', (req.get('email'),)).fetchone()
    if not user:
        db.execute('INSERT INTO users (email, name) VALUES(?,?)', (req.get('email'), req.get('name', 'User')))
        db.commit()
        user = db.execute('SELECT * FROM users WHERE email=?', (req.get('email'),)).fetchone()
    token = secrets.token_urlsafe(32)
    db.execute('INSERT INTO sessions (token, user_id) VALUES(?,?)', (token, user['id']))
    db.commit()
    db.close()
    return {'token': token, 'user': dict(user)}

@app.get('/auth/me')
def get_me(request: Request):
    return require_user(request)

@app.get('/health')
def health():
    return {'status': 'ok'}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: CORE
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/exams/create')
def create_exam(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO exams (user_id, exam_name, subject, exam_date, estimated_hours) VALUES(?,?,?,?,?)',
              (user['id'], req.get('exam_name'), req.get('subject'), req.get('exam_date'), req.get('estimated_hours', 0)))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/exams')
def get_exams(request: Request):
    user = require_user(request)
    db = get_db()
    exams = db.execute('SELECT * FROM exams WHERE user_id=?', (user['id'],)).fetchall()
    db.close()
    return {'exams': [dict(e) for e in exams]}

@app.get('/streaks')
def get_streaks(request: Request):
    user = require_user(request)
    db = get_db()
    streak = db.execute('SELECT * FROM streaks WHERE user_id=?', (user['id'],)).fetchone()
    db.close()
    return dict(streak) if streak else {'current_streak': 0, 'longest_streak': 0}

@app.post('/streaks/log')
def log_streak(request: Request):
    user = require_user(request)
    db = get_db()
    today = datetime.now().date().isoformat()
    streak = db.execute('SELECT * FROM streaks WHERE user_id=?', (user['id'],)).fetchone()
    if not streak:
        db.execute('INSERT INTO streaks (user_id, current_streak, longest_streak, last_study_date) VALUES(?,?,?,?)',
                  (user['id'], 1, 1, today))
    else:
        if streak['last_study_date'] != today:
            new_current = 1
            if streak['last_study_date']:
                last = datetime.fromisoformat(streak['last_study_date']).date()
                if (datetime.now().date() - last).days == 1:
                    new_current = streak['current_streak'] + 1
            new_longest = max(new_current, streak['longest_streak'])
            db.execute('UPDATE streaks SET current_streak=?, longest_streak=?, last_study_date=? WHERE user_id=?',
                      (new_current, new_longest, today, user['id']))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/daily-report')
def get_daily_report(request: Request):
    user = require_user(request)
    today = datetime.now().date().isoformat()
    db = get_db()
    log = db.execute('SELECT * FROM daily_study_log WHERE user_id=? AND study_date=?', (user['id'], today)).fetchone()
    db.close()
    if not log:
        return {'minutes': 0, 'points': 0}
    minutes = log['minutes_studied'] or 0
    points = (minutes // 15) * 5
    return {'minutes': minutes, 'points': points}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/mock-exam/generate')
def gen_mock(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO mock_exams (user_id, subject, total_questions) VALUES(?,?,?)',
              (user['id'], req.get('subject', 'General'), 10))
    exam_id = db.lastrowid
    db.commit()
    db.close()
    return {'exam_id': exam_id, 'questions': [{'id': i, 'question': f'Q{i+1}?', 'options': ['A','B','C','D']} for i in range(10)]}

@app.post('/mock-exam/{exam_id}/submit')
def submit_mock(exam_id: int, req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('UPDATE mock_exams SET score=?, accuracy=? WHERE id=? AND user_id=?', (req.get('score'), req.get('accuracy'), exam_id, user['id']))
    db.commit()
    db.close()
    return {'status': 'ok'}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: HABITS
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/daily-goal')
def get_goal(request: Request):
    user = require_user(request)
    today = datetime.now().date().isoformat()
    db = get_db()
    goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?', (user['id'], today)).fetchone()
    db.close()
    if not goal:
        return {'goal_minutes': 60, 'completed_minutes': 0, 'progress': 0}
    d = dict(goal)
    return {'goal_minutes': d['goal_minutes'], 'completed_minutes': d['completed_minutes'], 'progress': int((d['completed_minutes']/d['goal_minutes'])*100)}

@app.post('/daily-goal/update')
def update_goal(req: dict, request: Request):
    user = require_user(request)
    today = datetime.now().date().isoformat()
    db = get_db()
    goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?', (user['id'], today)).fetchone()
    if goal:
        db.execute('UPDATE daily_goals SET completed_minutes=? WHERE user_id=? AND goal_date=?', (goal['completed_minutes'] + req.get('minutes', 0), user['id'], today))
    else:
        db.execute('INSERT INTO daily_goals (user_id, goal_date, completed_minutes) VALUES(?,?,?)', (user['id'], today, req.get('minutes', 0)))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/leaderboard/global')
def leaderboard():
    db = get_db()
    users = db.execute('SELECT * FROM leaderboard ORDER BY total_points DESC LIMIT 100').fetchall()
    db.close()
    return {'leaderboard': [dict(u) for u in users]}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════

@app.get('/notifications')
def notifs(request: Request):
    user = require_user(request)
    db = get_db()
    n = db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC', (user['id'],)).fetchall()
    db.close()
    return {'notifications': [dict(x) for x in n]}

@app.post('/challenges/create')
def create_challenge(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO challenges (creator_id, challenge_type, subject, target_value) VALUES(?,?,?,?)',
              (user['id'], req.get('type'), req.get('subject'), req.get('target')))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.post('/friends/connect')
def connect(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT OR IGNORE INTO friend_connections (user_id, friend_id) VALUES(?,?)',
              (user['id'], req.get('friend_id')))
    db.commit()
    db.close()
    return {'status': 'ok'}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5: PREMIUM & PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════

@app.post('/notes/create')
def note_create(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO user_notes (user_id, title, content) VALUES(?,?,?)', (user['id'], req.get('title'), req.get('content')))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/notes')
def notes_get(request: Request):
    user = require_user(request)
    db = get_db()
    notes = db.execute('SELECT * FROM user_notes WHERE user_id=? ORDER BY updated_at DESC', (user['id'],)).fetchall()
    db.close()
    return {'notes': [dict(n) for n in notes]}

@app.post('/bookmarks/add')
def bookmark_add(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO bookmarks (user_id, resource_type, resource_title, resource_url) VALUES(?,?,?,?)',
              (user['id'], req.get('type'), req.get('title'), req.get('url')))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/bookmarks')
def bookmarks_get(request: Request):
    user = require_user(request)
    db = get_db()
    b = db.execute('SELECT * FROM bookmarks WHERE user_id=?', (user['id'],)).fetchall()
    db.close()
    return {'bookmarks': [dict(x) for x in b]}

@app.post('/study/log')
def study_log(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO study_history (user_id, subject, duration_minutes, accuracy) VALUES(?,?,?,?)',
              (user['id'], req.get('subject'), req.get('duration'), req.get('accuracy')))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/study/history')
def history_get(request: Request):
    user = require_user(request)
    db = get_db()
    h = db.execute('SELECT * FROM study_history WHERE user_id=? ORDER BY date DESC LIMIT 50', (user['id'],)).fetchall()
    db.close()
    return {'history': [dict(x) for x in h]}

@app.post('/goals/create')
def goal_create(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO user_goals (user_id, goal_name, target_value, deadline) VALUES(?,?,?,?)',
              (user['id'], req.get('name'), req.get('target'), req.get('deadline')))
    db.commit()
    db.close()
    return {'status': 'ok'}

@app.get('/goals')
def goals_get(request: Request):
    user = require_user(request)
    db = get_db()
    g = db.execute('SELECT * FROM user_goals WHERE user_id=? AND status=?', (user['id'], 'active')).fetchall()
    db.close()
    return {'goals': [dict(x) for x in g]}

@app.post('/ai-mentor/ask')
def mentor_ask(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    sub = db.execute('SELECT plan FROM subscriptions WHERE user_id=?', (user['id'],)).fetchone()
    if not sub or sub['plan'] == 'free':
        db.close()
        return {'error': 'Premium feature'}
    answer = f"Explanation of {req.get('topic')}: This is important content that requires understanding of prerequisites..."
    db.execute('INSERT INTO ai_mentor_sessions (user_id, subject, topic, question, ai_response) VALUES(?,?,?,?,?)',
              (user['id'], req.get('subject'), req.get('topic'), req.get('question'), answer))
    db.commit()
    db.close()
    return {'answer': answer}

@app.post('/interview-prep/start')
def interview_start(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    sub = db.execute('SELECT plan FROM subscriptions WHERE user_id=?', (user['id'],)).fetchone()
    if not sub or sub['plan'] == 'free':
        db.close()
        return {'error': 'Premium feature'}
    question = f"Interview question for {req.get('company')}: Tell us about yourself"
    db.execute('INSERT INTO interview_prep_sessions (user_id, company, question) VALUES(?,?,?)',
              (user['id'], req.get('company'), question))
    sid = db.lastrowid
    db.commit()
    db.close()
    return {'session_id': sid, 'question': question}

@app.post('/interview-prep/{session_id}/submit')
def interview_submit(session_id: int, req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('UPDATE interview_prep_sessions SET user_answer=?, feedback=?, score=? WHERE id=? AND user_id=?',
              (req.get('answer'), 'Great response!', 85, session_id, user['id']))
    db.commit()
    db.close()
    return {'score': 85, 'feedback': 'Great response!'}

@app.get('/subscription/status')
def sub_status(request: Request):
    user = require_user(request)
    db = get_db()
    sub = db.execute('SELECT plan FROM subscriptions WHERE user_id=?', (user['id'],)).fetchone()
    db.close()
    return {'plan': dict(sub)['plan'] if sub else 'free'}

@app.post('/subscription/upgrade')
def sub_upgrade(req: dict, request: Request):
    user = require_user(request)
    plan = req.get('plan', 'pro')
    db = get_db()
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    db.execute('INSERT OR REPLACE INTO subscriptions (user_id, plan, expires_at) VALUES(?,?,?)',
              (user['id'], plan, expires))
    db.commit()
    db.close()
    return {'status': 'ok', 'plan': plan}

@app.post('/focus-session/start')
def focus_start(req: dict, request: Request):
    user = require_user(request)
    db = get_db()
    db.execute('INSERT INTO focus_sessions (user_id, subject, duration_minutes) VALUES(?,?,?)',
              (user['id'], req.get('subject', 'General'), req.get('duration', 25)))
    sid = db.lastrowid
    db.commit()
    db.close()
    return {'session_id': sid}

@app.post('/focus-session/{session_id}/end')
def focus_end(session_id: int, req: dict, request: Request):
    user = require_user(request)
    duration = req.get('duration', 25)
    db = get_db()
    db.execute('UPDATE focus_sessions SET completed=TRUE, ended_at=datetime("now") WHERE id=? AND user_id=?',
              (session_id, user['id']))
    today = datetime.now().date().isoformat()
    goal = db.execute('SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?', (user['id'], today)).fetchone()
    if goal:
        db.execute('UPDATE daily_goals SET completed_minutes=? WHERE user_id=? AND goal_date=?',
                  (goal['completed_minutes'] + duration, user['id'], today))
    else:
        db.execute('INSERT INTO daily_goals (user_id, goal_date, completed_minutes) VALUES(?,?,?)',
                  (user['id'], today, duration))
    db.commit()
    db.close()
    return {'status': 'ok'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
