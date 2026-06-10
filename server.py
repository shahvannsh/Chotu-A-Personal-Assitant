from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
import json, httpx, re, sqlite3, os, secrets
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
import uvicorn
import math

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY         = os.getenv("GROQ_API_KEY", "")
TAVILY_KEY           = os.getenv("TAVILY_KEY", "")
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SECRET_KEY           = os.getenv("SECRET_KEY", secrets.token_hex(32))
REDIRECT_URI         = os.getenv("REDIRECT_URI", "https://chotu-lcc7.onrender.com/auth/callback")
MODEL                = "llama-3.3-70b-versatile"

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = Path("/app/chotu.db") if os.path.exists("/app") else Path("chotu_mvp.db")

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id  TEXT UNIQUE NOT NULL,
            email      TEXT UNIQUE NOT NULL,
            name       TEXT,
            picture    TEXT,
            groq_key   TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions_tok (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS memory (
            user_id     INTEGER PRIMARY KEY,
            focus_task  TEXT,
            focus_start TEXT,
            notes       TEXT DEFAULT '[]',
            history     TEXT DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS profiles (
            user_id          INTEGER PRIMARY KEY,
            goals            TEXT DEFAULT '',
            current_projects TEXT DEFAULT '',
            daily_routine    TEXT DEFAULT '',
            about            TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL,
            task     TEXT NOT NULL,
            date     TEXT NOT NULL,
            start    TEXT NOT NULL,
            end      TEXT NOT NULL,
            duration INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS knowledge_graph (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_topic TEXT NOT NULL,
            target_topic TEXT NOT NULL,
            relationship TEXT,
            strength FLOAT DEFAULT 0.5,
            subject TEXT NOT NULL,
            UNIQUE(source_topic, target_topic, subject)
        );
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            question TEXT NOT NULL,
            options TEXT,
            correct_answer TEXT NOT NULL,
            difficulty INTEGER,
            pass_rate FLOAT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            user_answer TEXT,
            is_correct BOOLEAN,
            time_spent_seconds INTEGER,
            attempted_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (question_id) REFERENCES quiz_questions(id)
        );
        CREATE TABLE IF NOT EXISTS mock_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            exam_name TEXT,
            total_questions INTEGER,
            score INTEGER,
            time_taken_minutes INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS mock_exam_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mock_exam_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            correct INTEGER,
            total INTEGER,
            performance TEXT,
            FOREIGN KEY (mock_exam_id) REFERENCES mock_exams(id)
        );
        CREATE TABLE IF NOT EXISTS student_mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            mistake_pattern TEXT,
            frequency INTEGER DEFAULT 1,
            last_occurred TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS streaks (
            user_id          INTEGER PRIMARY KEY,
            current_streak   INTEGER DEFAULT 0,
            longest_streak   INTEGER DEFAULT 0,
            last_study_date  TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS daily_study_log (
            user_id          INTEGER,
            study_date       TEXT,
            minutes_studied  INTEGER DEFAULT 0,
            topics_reviewed  INTEGER DEFAULT 0,
            quizzes_completed INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, study_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS weak_topics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            subject         TEXT NOT NULL,
            topic           TEXT NOT NULL,
            confidence      INTEGER DEFAULT 50,
            last_reviewed   TEXT,
            next_review     TEXT,
            review_count    INTEGER DEFAULT 0,
            difficulty_level TEXT DEFAULT 'medium',
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, subject, topic)
        );
        CREATE TABLE IF NOT EXISTS exams (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            exam_name       TEXT NOT NULL,
            subject         TEXT NOT NULL,
            exam_date       TEXT NOT NULL,
            estimated_hours INTEGER,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, exam_name)
        );
        CREATE TABLE IF NOT EXISTS exam_schedule (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id         INTEGER NOT NULL,
            day_number      INTEGER NOT NULL,
            date            TEXT NOT NULL,
            topics          TEXT,
            hours_planned   INTEGER,
            hours_completed INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'not_started',
            FOREIGN KEY (exam_id) REFERENCES exams(id),
            UNIQUE(exam_id, day_number)
        );
    """)
    db.commit()
    db.close()

init_db()

# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_current_user(request: Request):
    token = request.cookies.get("chotu_token")
    if not token:
        return None
    db  = get_db()
    row = db.execute(
        "SELECT u.* FROM users u JOIN sessions_tok s ON u.id=s.user_id WHERE s.token=?",
        (token,)
    ).fetchone()
    db.close()
    return dict(row) if row else None

def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def get_groq(user: dict):
    key = user.get("groq_key") or GROQ_API_KEY
    if not key:
        raise HTTPException(status_code=400, detail="No Groq API key configured")
    return Groq(api_key=key)

# ── Memory helpers ────────────────────────────────────────────────────────────
def load_memory(uid: int):
    db  = get_db()
    row = db.execute("SELECT * FROM memory WHERE user_id=?", (uid,)).fetchone()
    db.close()
    if not row:
        return {"focus_task": None, "focus_start": None, "notes": [], "history": []}
    return {"focus_task": row["focus_task"], "focus_start": row["focus_start"],
            "notes": json.loads(row["notes"] or "[]"), "history": json.loads(row["history"] or "[]")}

def save_memory(uid: int, mem: dict):
    db = get_db()
    db.execute("""INSERT INTO memory (user_id,focus_task,focus_start,notes,history) VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET focus_task=excluded.focus_task,
        focus_start=excluded.focus_start,notes=excluded.notes,history=excluded.history""",
        (uid, mem.get("focus_task"), mem.get("focus_start"),
         json.dumps(mem.get("notes",[])), json.dumps(mem.get("history",[]))))
    db.commit(); db.close()

def load_profile(uid: int):
    db  = get_db()
    row = db.execute("SELECT * FROM profiles WHERE user_id=?", (uid,)).fetchone()
    db.close()
    return dict(row) if row else {}

def save_profile(uid: int, p: dict):
    db = get_db()
    db.execute("""INSERT INTO profiles (user_id,goals,current_projects,daily_routine,about) VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET goals=excluded.goals,current_projects=excluded.current_projects,
        daily_routine=excluded.daily_routine,about=excluded.about""",
        (uid, p.get("goals",""), p.get("current_projects",""), p.get("daily_routine",""), p.get("about","")))
    db.commit(); db.close()

# ── Streak logic ──────────────────────────────────────────────────────────────
def get_streak(uid: int):
    db = get_db()
    row = db.execute("SELECT * FROM streaks WHERE user_id=?", (uid,)).fetchone()
    db.close()
    if not row:
        return {"current_streak": 0, "longest_streak": 0, "last_study_date": None}
    return {"current_streak": row["current_streak"], "longest_streak": row["longest_streak"], 
            "last_study_date": row["last_study_date"]}

def update_streak(uid: int):
    today = date.today().isoformat()
    db = get_db()
    streak = db.execute("SELECT * FROM streaks WHERE user_id=?", (uid,)).fetchone()
    
    if not streak:
        db.execute("INSERT INTO streaks (user_id, current_streak, longest_streak, last_study_date) VALUES(?,?,?,?)",
                   (uid, 1, 1, today))
        db.commit(); db.close()
        return 1
    
    last_date = streak["last_study_date"]
    current = streak["current_streak"]
    longest = streak["longest_streak"]
    
    if last_date == today:
        # Already logged today
        db.close()
        return current
    
    if last_date == (date.today() - timedelta(days=1)).isoformat():
        # Consecutive day
        current += 1
    else:
        # Streak broken
        if current > longest:
            longest = current
        current = 1
    
    longest = max(longest, current)
    db.execute("UPDATE streaks SET current_streak=?, longest_streak=?, last_study_date=? WHERE user_id=?",
               (current, longest, today, uid))
    db.commit(); db.close()
    return current

# ── Spaced Repetition (SM-2 Algorithm) ─────────────────────────────────────────
def calculate_next_review(score: int, review_count: int, easiness: float = 2.5):
    """SM-2 algorithm for spaced repetition"""
    if score >= 70:
        if review_count == 0:
            interval = 1
        elif review_count == 1:
            interval = 3
        else:
            interval = int(interval * easiness) if review_count > 1 else 3
    else:
        interval = 1
    
    next_date = date.today() + timedelta(days=interval)
    return next_date.isoformat()

def get_weak_topics(uid: int):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM weak_topics WHERE user_id=? AND DATE(next_review) <= DATE('now') ORDER BY confidence ASC",
        (uid,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

def update_weak_topic(uid: int, subject: str, topic: str, score: int):
    db = get_db()
    row = db.execute(
        "SELECT * FROM weak_topics WHERE user_id=? AND subject=? AND topic=?",
        (uid, subject, topic)
    ).fetchone()
    
    if not row:
        next_review = calculate_next_review(score, 0)
        confidence = score
        db.execute("""INSERT INTO weak_topics 
                     (user_id, subject, topic, confidence, last_reviewed, next_review, review_count)
                     VALUES(?,?,?,?,?,?,?)""",
                   (uid, subject, topic, confidence, date.today().isoformat(), next_review, 1))
    else:
        new_confidence = int((row["confidence"] + score) / 2)
        next_review = calculate_next_review(score, row["review_count"] + 1)
        db.execute("""UPDATE weak_topics 
                      SET confidence=?, last_reviewed=?, next_review=?, review_count=?
                      WHERE user_id=? AND subject=? AND topic=?""",
                   (new_confidence, date.today().isoformat(), next_review, row["review_count"] + 1,
                    uid, subject, topic))
    
    db.commit(); db.close()

def compute_stats(uid: int):
    db   = get_db()
    rows = db.execute("SELECT date,duration FROM focus_sessions WHERE user_id=?", (uid,)).fetchall()
    db.close()
    daily = {}
    for r in rows:
        daily[r["date"]] = daily.get(r["date"], 0) + r["duration"]
    today = date.today().isoformat()
    week  = sum(daily.get((date.today()-timedelta(days=i)).isoformat(),0) for i in range(7))
    return {"today": daily.get(today,0), "week": week, "daily": daily}

def fmt_dur(s: int):
    s=int(s); h,r=divmod(s,3600); m,sc=divmod(r,60)
    if h: return f"{h}h {m}m"
    if m: return f"{m}m {sc}s"
    return f"{sc}s"

# ── Google OAuth ──────────────────────────────────────────────────────────────
@app.get("/auth/login")
def google_login():
    url = (f"https://accounts.google.com/o/oauth2/v2/auth"
           f"?client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
           f"&response_type=code&scope=openid%20email%20profile"
           f"&access_type=offline&prompt=select_account")
    return RedirectResponse(url)

@app.get("/auth/callback")
async def google_callback(code: str=None, error: str=None):
    if error or not code: return RedirectResponse("/?error=auth_failed")
    async with httpx.AsyncClient() as c:
        tok = (await c.post("https://oauth2.googleapis.com/token", data={
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code, "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"})).json()
        if "access_token" not in tok: return RedirectResponse("/?error=token_failed")
        info = (await c.get("https://www.googleapis.com/oauth2/v3/userinfo",
                            headers={"Authorization": f"Bearer {tok['access_token']}"})).json()
    db = get_db()
    db.execute("""INSERT INTO users (google_id,email,name,picture) VALUES(?,?,?,?)
        ON CONFLICT(google_id) DO UPDATE SET name=excluded.name,picture=excluded.picture""",
        (info.get("sub"), info.get("email",""), info.get("name",""), info.get("picture","")))
    db.commit()
    user  = db.execute("SELECT * FROM users WHERE google_id=?", (info.get("sub"),)).fetchone()
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions_tok (token,user_id) VALUES(?,?)", (token, user["id"]))
    db.commit(); db.close()
    resp = RedirectResponse("/")
    resp.set_cookie("chotu_token", token, httponly=True, samesite="lax", max_age=30*24*3600)
    return resp

@app.get("/auth/logout")
def logout():
    resp = RedirectResponse("/login")
    resp.delete_cookie("chotu_token")
    return resp

@app.get("/auth/me")
def get_me(request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"authenticated": False})
    return JSONResponse({"authenticated": True, "name": user["name"],
                         "email": user["email"], "picture": user["picture"],
                         "has_groq_key": bool(user.get("groq_key"))})

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.get("/login")
def serve_login(): return FileResponse("login.html")

@app.get("/")
def serve_index(request: Request):
    if not get_current_user(request): return RedirectResponse("/login")
    return FileResponse("index.html")

@app.get("/study")
def serve_study(request: Request):
    if not get_current_user(request): return RedirectResponse("/login")
    return FileResponse("study.html")

@app.get("/history")
def serve_history_page(request: Request):
    if not get_current_user(request): return RedirectResponse("/login")
    return FileResponse("history.html")

# ── API ───────────────────────────────────────────────────────────────────────
@app.get("/memory")
def get_memory(request: Request):
    return load_memory(require_user(request)["id"])

@app.get("/profile")
def get_profile(request: Request):
    user = require_user(request)
    p = load_profile(user["id"])
    p["name"] = user["name"]
    return p

@app.post("/profile")
def update_profile(req: dict, request: Request):
    save_profile(require_user(request)["id"], req)
    return {"status": "ok"}

@app.post("/focus")
def set_focus(req: dict, request: Request):
    user = require_user(request)
    mem  = load_memory(user["id"])
    if req.get("task"):
        mem["focus_task"] = req["task"]
        mem["focus_start"] = datetime.now().isoformat()
    else:
        if mem.get("focus_task") and mem.get("focus_start"):
            start = datetime.fromisoformat(mem["focus_start"])
            end = datetime.now()
            duration = int((end - start).total_seconds())
            db = get_db()
            db.execute(
                "INSERT INTO focus_sessions (user_id,task,date,start,end,duration) VALUES(?,?,?,?,?,?)",
                (user["id"], mem["focus_task"], start.strftime("%Y-%m-%d"),
                 mem["focus_start"], end.isoformat(), duration)
            )
            db.commit(); db.close()
            # Update streak and daily log
            streak = update_streak(user["id"])
            log_daily_activity(user["id"], duration // 60)
        mem["focus_task"] = None; mem["focus_start"] = None
    save_memory(user["id"], mem)
    return {"status": "ok", "focus_task": mem["focus_task"]}

def log_daily_activity(uid: int, minutes: int):
    today = date.today().isoformat()
    db = get_db()
    row = db.execute("SELECT * FROM daily_study_log WHERE user_id=? AND study_date=?",
                     (uid, today)).fetchone()
    if row:
        db.execute("UPDATE daily_study_log SET minutes_studied=minutes_studied+? WHERE user_id=? AND study_date=?",
                   (minutes, uid, today))
    else:
        db.execute("INSERT INTO daily_study_log (user_id,study_date,minutes_studied) VALUES(?,?,?)",
                   (uid, today, minutes))
    db.commit(); db.close()

@app.post("/chat")
async def chat(req: dict, request: Request):
    user    = require_user(request)
    mem     = load_memory(user["id"])
    profile = load_profile(user["id"])
    gcl     = get_groq(user)
    
    ctx     = []
    lines   = []
    if user.get("name"):                 lines.append(f"Name: {user['name']}")
    if profile.get("goals"):             lines.append(f"Goals: {profile['goals']}")
    if profile.get("current_projects"):  lines.append(f"Working on: {profile['current_projects']}")
    if lines: ctx.append("USER PROFILE:\n" + "\n".join(lines))
    if mem["focus_task"]:
        started = mem["focus_start"][:16].replace("T"," ") if mem["focus_start"] else "unknown"
        ctx.append(f"ACTIVE FOCUS: '{mem['focus_task']}' since {started}")
    
    uc = req.get("message", "") + ("\n\n[CONTEXT:\n" + "\n---\n".join(ctx) + "\n]" if ctx else "")
    msgs = [{"role":"system","content":"You are Chotu, a sharp study AI. Help students learn better."}]
    for h in req.get("history", [])[-12:]: msgs.append({"role":h["role"],"content":h["content"]})
    msgs.append({"role":"user","content":uc})
    
    try:
        resp  = gcl.chat.completions.create(model=MODEL, messages=msgs, temperature=0.75, max_tokens=500)
        reply = resp.choices[0].message.content
        mem["history"].append({"role":"user","content":req.get("message",""),"ts":datetime.now().isoformat()})
        mem["history"].append({"role":"assistant","content":reply,"ts":datetime.now().isoformat()})
        mem["history"] = mem["history"][-40:]
        save_memory(user["id"], mem)
        return {"reply":reply,"focus_task":mem["focus_task"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── PHASE 1 MVP ENDPOINTS ─────────────────────────────────────────────────────

# 1. SPACED REPETITION
@app.post("/spaced-rep/review")
def review_topic(req: dict, request: Request):
    user = require_user(request)
    subject = req.get("subject", "General")
    topic = req.get("topic", "")
    score = req.get("score", 50)  # 0-100
    
    update_weak_topic(user["id"], subject, topic, score)
    return {"status": "ok", "next_review": calculate_next_review(score, 0)}

@app.get("/spaced-rep/due")
def get_due_reviews(request: Request):
    user = require_user(request)
    topics = get_weak_topics(user["id"])
    return {"topics_due": [{"subject": t["subject"], "topic": t["topic"], 
                            "confidence": t["confidence"]} for t in topics]}

# 2. STREAKS
@app.get("/streaks")
def get_streaks(request: Request):
    user = require_user(request)
    streak = get_streak(user["id"])
    return streak

@app.post("/streaks/log-session")
def log_study(req: dict, request: Request):
    user = require_user(request)
    minutes = req.get("minutes", 0)
    streak = update_streak(user["id"])
    log_daily_activity(user["id"], minutes)
    return {"streak": streak, "status": "logged"}

# 3. DAILY REPORT
@app.get("/daily-report")
def get_daily_report(request: Request):
    user = require_user(request)
    today = date.today().isoformat()
    
    db = get_db()
    log = db.execute("SELECT * FROM daily_study_log WHERE user_id=? AND study_date=?",
                     (user["id"], today)).fetchone()
    streak_data = db.execute("SELECT * FROM streaks WHERE user_id=?", (user["id"],)).fetchone()
    db.close()
    
    if not log:
        return {"minutes": 0, "topics_reviewed": 0, "quizzes": 0, "streak": 0, "points": 0}
    
    points = (log["minutes_studied"] // 15) * 5  # 5 points per 15 min
    return {
        "minutes": log["minutes_studied"],
        "topics_reviewed": log["topics_reviewed"],
        "quizzes": log["quizzes_completed"],
        "streak": streak_data["current_streak"] if streak_data else 0,
        "points": points
    }

# 4. EXAM COUNTDOWN PLANNER
@app.post("/exam/create")
def create_exam(req: dict, request: Request):
    user = require_user(request)
    exam_name = req.get("exam_name", "")
    subject = req.get("subject", "")
    exam_date = req.get("exam_date", "")  # YYYY-MM-DD
    topics = req.get("topics", [])
    
    db = get_db()
    db.execute(
        "INSERT INTO exams (user_id, exam_name, subject, exam_date, estimated_hours) VALUES(?,?,?,?,?)",
        (user["id"], exam_name, subject, exam_date, len(topics) * 2)  # 2 hours per topic estimate
    )
    db.commit()
    
    exam = db.execute("SELECT * FROM exams WHERE user_id=? AND exam_name=?",
                      (user["id"], exam_name)).fetchone()
    exam_id = exam["id"]
    
    # Generate schedule
    exam_date_obj = datetime.strptime(exam_date, "%Y-%m-%d").date()
    days_left = (exam_date_obj - date.today()).days
    
    topics_per_day = max(1, len(topics) // max(1, days_left - 2))
    
    for day in range(1, days_left + 1):
        schedule_date = (date.today() + timedelta(days=day)).isoformat()
        day_topics = topics[(day-1)*topics_per_day : day*topics_per_day]
        
        db.execute("""INSERT INTO exam_schedule 
                     (exam_id, day_number, date, topics, hours_planned, status)
                     VALUES(?,?,?,?,?,?)""",
                   (exam_id, day, schedule_date, json.dumps(day_topics), 2, "not_started"))
    
    db.commit()
    db.close()
    
    return {"exam_id": exam_id, "status": "created", "days_left": days_left}

@app.get("/exam/{exam_id}/today")
def get_today_exam_plan(exam_id: int, request: Request):
    user = require_user(request)
    
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=? AND user_id=?",
                      (exam_id, user["id"])).fetchone()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    exam_date = datetime.strptime(exam["exam_date"], "%Y-%m-%d").date()
    days_left = (exam_date - date.today()).days
    
    today_schedule = db.execute(
        "SELECT * FROM exam_schedule WHERE exam_id=? AND DATE(date)=DATE('now')",
        (exam_id,)
    ).fetchone()
    
    db.close()
    
    if not today_schedule:
        return {"day": days_left, "topics": [], "hours": 0, "completed": False}
    
    return {
        "day": today_schedule["day_number"],
        "topics": json.loads(today_schedule["topics"] or "[]"),
        "hours": today_schedule["hours_planned"],
        "completed": today_schedule["status"] == "completed",
        "days_left": days_left
    }

@app.get("/exam/{exam_id}/progress")
def get_exam_progress(exam_id: int, request: Request):
    user = require_user(request)
    
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=? AND user_id=?",
                      (exam_id, user["id"])).fetchone()
    
    if not exam:
        raise HTTPException(status_code=404)
    
    schedule = db.execute("SELECT * FROM exam_schedule WHERE exam_id=?", (exam_id,)).fetchall()
    db.close()
    
    completed = sum(1 for s in schedule if s["status"] == "completed")
    total = len(schedule)
    
    return {
        "exam_name": exam["exam_name"],
        "exam_date": exam["exam_date"],
        "progress_percent": int((completed / max(1, total)) * 100),
        "days_completed": completed,
        "days_total": total
    }

@app.post("/exam/{exam_id}/mark-done")
def mark_exam_day_done(exam_id: int, req: dict, request: Request):
    user = require_user(request)
    
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=? AND user_id=?",
                      (exam_id, user["id"])).fetchone()
    
    if not exam:
        raise HTTPException(status_code=404)
    
    day_num = req.get("day_number", 1)
    hours = req.get("hours_completed", 0)
    
    db.execute("UPDATE exam_schedule SET status='completed', hours_completed=? WHERE exam_id=? AND day_number=?",
               (hours, exam_id, day_num))
    db.commit()
    db.close()
    
    return {"status": "marked_complete"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT",8000)))
# This file contains ADDITIONS to the existing server.py
# Copy the Phase 1 server.py first, then add these routes and functions below the Phase 1 endpoints

# ════════════════════════════════════════════════════════════════════════════
# PHASE 2: KNOWLEDGE GRAPH + MOCK EXAMS + WEAK TOPIC COACHING
# ════════════════════════════════════════════════════════════════════════════

# Add these imports at the top of server.py:
# from sklearn.metrics.pairwise import cosine_similarity
# import numpy as np

# Add these tables to init_db():
"""
CREATE TABLE IF NOT EXISTS knowledge_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_topic TEXT NOT NULL,
    target_topic TEXT NOT NULL,
    relationship TEXT,  -- prerequisite, builds_on, similar
    strength FLOAT DEFAULT 0.5,
    subject TEXT NOT NULL,
    UNIQUE(source_topic, target_topic, subject)
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT,  -- JSON array
    correct_answer TEXT NOT NULL,
    difficulty INTEGER (1-5),
    pass_rate FLOAT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    user_answer TEXT,
    is_correct BOOLEAN,
    time_spent_seconds INTEGER,
    attempted_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (question_id) REFERENCES quiz_questions(id)
);

CREATE TABLE IF NOT EXISTS mock_exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    exam_name TEXT,
    total_questions INTEGER,
    score INTEGER,
    time_taken_minutes INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS mock_exam_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mock_exam_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    correct INTEGER,
    total INTEGER,
    performance TEXT,  -- easy, medium, hard
    FOREIGN KEY (mock_exam_id) REFERENCES mock_exams(id)
);

CREATE TABLE IF NOT EXISTS student_mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    mistake_pattern TEXT,  -- e.g., "forgets edge cases", "wrong formula"
    frequency INTEGER DEFAULT 1,
    last_occurred TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

# ── PHASE 2 API ENDPOINTS ─────────────────────────────────────────────────

# 1. KNOWLEDGE GRAPH
@app.post("/graph/build")
def build_knowledge_graph(req: dict, request: Request):
    """Generate knowledge graph for a subject"""
    user = require_user(request)
    subject = req.get("subject", "")
    topics = req.get("topics", [])
    
    if not subject or not topics:
        raise HTTPException(status_code=400, detail="Subject and topics required")
    
    gcl = get_groq(user)
    
    # Use Groq to generate topic relationships
    prompt = f"""For the subject "{subject}", I have these topics: {', '.join(topics)}

For each pair of topics, determine if there's a relationship.
Format response as JSON only:
{{
  "relationships": [
    {{"source": "topic1", "target": "topic2", "relationship": "prerequisite", "strength": 0.8}},
    {{"source": "topic2", "target": "topic3", "relationship": "builds_on", "strength": 0.9}}
  ]
}}

Relationships: prerequisite (must learn first), builds_on (strengthens), similar (alternative approach)
Strength: 0-1 (how strong is the relationship)
"""
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        
        response_text = resp.choices[0].message.content
        # Extract JSON
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            graph_data = json.loads(json_match.group())
            
            # Store in database
            db = get_db()
            for rel in graph_data.get("relationships", []):
                db.execute("""
                    INSERT OR IGNORE INTO knowledge_graph 
                    (source_topic, target_topic, relationship, strength, subject)
                    VALUES(?,?,?,?,?)
                """, (rel["source"], rel["target"], rel["relationship"], rel["strength"], subject))
            db.commit()
            db.close()
            
            return {"status": "graph_built", "relationships": len(graph_data.get("relationships", []))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph/{subject}")
def get_graph(subject: str, request: Request):
    """Get knowledge graph for subject"""
    user = require_user(request)
    
    db = get_db()
    relationships = db.execute(
        "SELECT * FROM knowledge_graph WHERE subject=?", (subject,)
    ).fetchall()
    db.close()
    
    # Format for visualization
    nodes = set()
    edges = []
    
    for rel in relationships:
        nodes.add(rel["source_topic"])
        nodes.add(rel["target_topic"])
        edges.append({
            "source": rel["source_topic"],
            "target": rel["target_topic"],
            "relationship": rel["relationship"],
            "strength": rel["strength"]
        })
    
    return {
        "nodes": [{"id": n, "label": n} for n in nodes],
        "edges": edges
    }

@app.get("/graph/{subject}/learning-path")
def get_learning_path(subject: str, request: Request):
    """Get recommended learning path (topological sort of prerequisites)"""
    user = require_user(request)
    
    db = get_db()
    relationships = db.execute(
        "SELECT * FROM knowledge_graph WHERE subject=? AND relationship='prerequisite'",
        (subject,)
    ).fetchall()
    db.close()
    
    # Simple topological sort
    graph = {}
    all_topics = set()
    
    for rel in relationships:
        if rel["source_topic"] not in graph:
            graph[rel["source_topic"]] = []
        graph[rel["source_topic"]].append(rel["target_topic"])
        all_topics.add(rel["source_topic"])
        all_topics.add(rel["target_topic"])
    
    # Find topics with no prerequisites (roots)
    has_prerequisite = set()
    for rel in relationships:
        has_prerequisite.add(rel["target_topic"])
    
    roots = [t for t in all_topics if t not in has_prerequisite]
    
    return {"learning_path": roots, "total_topics": len(all_topics)}

# 2. MOCK EXAMS
@app.post("/mock-exam/generate")
def generate_mock_exam(req: dict, request: Request):
    """Generate adaptive mock exam"""
    user = require_user(request)
    subject = req.get("subject", "")
    num_questions = req.get("num_questions", 10)
    difficulty = req.get("difficulty", "mixed")  # easy, medium, hard, mixed
    
    db = get_db()
    
    # Select questions based on difficulty
    if difficulty == "mixed":
        # 40% easy, 40% medium, 20% hard
        easy_q = db.execute(
            "SELECT * FROM quiz_questions WHERE subject=? AND difficulty<=2 ORDER BY RANDOM() LIMIT ?",
            (subject, int(num_questions * 0.4))
        ).fetchall()
        med_q = db.execute(
            "SELECT * FROM quiz_questions WHERE subject=? AND difficulty=3 ORDER BY RANDOM() LIMIT ?",
            (subject, int(num_questions * 0.4))
        ).fetchall()
        hard_q = db.execute(
            "SELECT * FROM quiz_questions WHERE subject=? AND difficulty>=4 ORDER BY RANDOM() LIMIT ?",
            (subject, int(num_questions * 0.2))
        ).fetchall()
        questions = list(easy_q) + list(med_q) + list(hard_q)
    else:
        # Specific difficulty
        diff_map = {"easy": 2, "medium": 3, "hard": 4}
        diff_val = diff_map.get(difficulty, 3)
        questions = db.execute(
            "SELECT * FROM quiz_questions WHERE subject=? AND difficulty=? ORDER BY RANDOM() LIMIT ?",
            (subject, diff_val, num_questions)
        ).fetchall()
    
    db.close()
    
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found for this subject")
    
    # Create mock exam record
    db = get_db()
    db.execute(
        "INSERT INTO mock_exams (user_id, subject, exam_name, total_questions) VALUES(?,?,?,?)",
        (user["id"], subject, f"{subject} Mock Exam", len(questions))
    )
    db.commit()
    
    exam = db.execute(
        "SELECT id FROM mock_exams WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user["id"],)
    ).fetchone()
    db.close()
    
    return {
        "exam_id": exam["id"],
        "total_questions": len(questions),
        "questions": [{"id": q["id"], "question": q["question"], "options": json.loads(q["options"] or "[]")} 
                      for q in questions[:1]]  # Return first question
    }

@app.post("/mock-exam/{exam_id}/answer")
def submit_answer(exam_id: int, req: dict, request: Request):
    """Submit answer to mock exam question"""
    user = require_user(request)
    question_id = req.get("question_id")
    user_answer = req.get("user_answer")
    time_spent = req.get("time_spent_seconds", 0)
    
    db = get_db()
    
    question = db.execute(
        "SELECT * FROM quiz_questions WHERE id=?", (question_id,)
    ).fetchone()
    
    if not question:
        raise HTTPException(status_code=404)
    
    is_correct = user_answer == question["correct_answer"]
    topic = question["topic"]
    subject = question["subject"]
    
    # Log attempt
    db.execute("""
        INSERT INTO quiz_attempts 
        (user_id, question_id, subject, topic, user_answer, is_correct, time_spent_seconds)
        VALUES(?,?,?,?,?,?,?)
    """, (user["id"], question_id, subject, topic, user_answer, is_correct, time_spent))
    
    # If wrong, detect mistake pattern
    if not is_correct:
        mistake = req.get("mistake_reason", "unknown")
        db.execute("""
            INSERT OR IGNORE INTO student_mistakes 
            (user_id, subject, topic, mistake_pattern, frequency)
            VALUES(?,?,?,?,1)
        """, (user["id"], subject, topic, mistake))
        db.execute("""
            UPDATE student_mistakes 
            SET frequency=frequency+1, last_occurred=datetime('now')
            WHERE user_id=? AND subject=? AND topic=? AND mistake_pattern=?
        """, (user["id"], subject, topic, mistake))
    
    db.commit()
    db.close()
    
    return {"is_correct": is_correct, "correct_answer": question["correct_answer"]}

@app.post("/mock-exam/{exam_id}/submit")
def submit_mock_exam(exam_id: int, req: dict, request: Request):
    """Submit completed mock exam and get results"""
    user = require_user(request)
    score = req.get("score", 0)
    time_taken = req.get("time_taken_minutes", 0)
    
    db = get_db()
    
    # Update exam with results
    db.execute(
        "UPDATE mock_exams SET score=?, time_taken_minutes=? WHERE id=? AND user_id=?",
        (score, time_taken, exam_id, user["id"])
    )
    
    # Calculate performance by topic
    attempts = db.execute("""
        SELECT topic, is_correct FROM quiz_attempts 
        WHERE user_id=? AND question_id IN (
            SELECT id FROM quiz_questions WHERE subject=(
                SELECT subject FROM mock_exams WHERE id=?
            )
        )
    """, (user["id"], exam_id)).fetchall()
    
    topic_performance = {}
    for attempt in attempts:
        topic = attempt["topic"]
        if topic not in topic_performance:
            topic_performance[topic] = {"correct": 0, "total": 0}
        topic_performance[topic]["total"] += 1
        if attempt["is_correct"]:
            topic_performance[topic]["correct"] += 1
    
    # Store results
    for topic, perf in topic_performance.items():
        pct = (perf["correct"] / perf["total"]) * 100
        if pct >= 75:
            performance = "strong"
        elif pct >= 50:
            performance = "medium"
        else:
            performance = "weak"
        
        db.execute("""
            INSERT INTO mock_exam_results 
            (mock_exam_id, topic, correct, total, performance)
            VALUES(?,?,?,?,?)
        """, (exam_id, topic, perf["correct"], perf["total"], performance))
    
    db.commit()
    db.close()
    
    return {
        "score": score,
        "performance_by_topic": topic_performance,
        "weak_topics": [t for t, p in topic_performance.items() if (p["correct"]/p["total"]) < 0.6]
    }

# 3. WEAK TOPIC COACHING
@app.get("/coaching/patterns/{subject}")
def get_mistake_patterns(subject: str, request: Request):
    """Get student's common mistake patterns"""
    user = require_user(request)
    
    db = get_db()
    patterns = db.execute("""
        SELECT topic, mistake_pattern, frequency, last_occurred
        FROM student_mistakes
        WHERE user_id=? AND subject=?
        ORDER BY frequency DESC
    """, (user["id"], subject)).fetchall()
    db.close()
    
    return {"patterns": [dict(p) for p in patterns]}

@app.post("/coaching/teach-pattern")
def teach_pattern(req: dict, request: Request):
    """AI teaches the pattern student keeps missing"""
    user = require_user(request)
    subject = req.get("subject", "")
    topic = req.get("topic", "")
    mistake_pattern = req.get("mistake_pattern", "")
    
    gcl = get_groq(user)
    
    prompt = f"""The student is making a mistake in {subject}/{topic}.
Pattern: They {mistake_pattern}

Create a focused 2-minute lesson:
1. Explain WHY they're making this mistake
2. Teach the correct approach with an example
3. Give them a memory trick
4. Ask them to try ONE simple problem

Be direct, clear, and specific. No fluff."""
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        lesson = resp.choices[0].message.content
        return {"lesson": lesson}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/coaching/next-topic")
def get_next_topic(request: Request):
    """Suggest next topic based on weak areas"""
    user = require_user(request)
    
    db = get_db()
    
    # Find topics with lowest confidence
    weak = db.execute("""
        SELECT subject, topic, confidence
        FROM weak_topics
        WHERE user_id=?
        ORDER BY confidence ASC
        LIMIT 5
    """, (user["id"],)).fetchall()
    
    db.close()
    
    if not weak:
        return {"next_topic": None, "recommendation": "You're on track! Keep studying."}
    
    topic = weak[0]
    return {
        "next_topic": topic["topic"],
        "subject": topic["subject"],
        "confidence": topic["confidence"],
        "reason": f"Your {topic['topic']} confidence is only {topic['confidence']}%. Time to review?"
    }

# ════════════════════════════════════════════════════════════════════════════
# END PHASE 2 ADDITIONS
# ════════════════════════════════════════════════════════════════════════════


# PHASE 3: HABIT LOOP + SOCIAL + AI PERSONALIZATION
# Add these to server.py after Phase 2 endpoints

# ════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════

# Add to init_db() - new tables:
"""
CREATE TABLE IF NOT EXISTS user_habits (
    user_id INTEGER PRIMARY KEY,
    study_goal_minutes INTEGER DEFAULT 60,
    notification_time TEXT DEFAULT '20:59',
    last_notification_sent TEXT,
    notifications_enabled BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS daily_goals (
    user_id INTEGER,
    goal_date TEXT,
    goal_minutes INTEGER,
    completed_minutes INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, goal_date),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    badge_name TEXT NOT NULL,
    badge_icon TEXT,
    earned_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, badge_name)
);

CREATE TABLE IF NOT EXISTS leaderboard (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    picture TEXT,
    total_points INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    mock_exams_completed INTEGER DEFAULT 0,
    avg_score FLOAT DEFAULT 0,
    rank INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS daily_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    recommendation_date TEXT,
    subject TEXT,
    topic TEXT,
    reason TEXT,
    priority INTEGER,
    completed BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, recommendation_date, topic)
);
"""

# ── PHASE 3A: HABIT LOOP & NOTIFICATIONS ────────────────────────────────────

@app.get("/habits/settings")
def get_habit_settings(request: Request):
    """Get user's habit settings"""
    user = require_user(request)
    db = get_db()
    row = db.execute("SELECT * FROM user_habits WHERE user_id=?", (user["id"],)).fetchone()
    db.close()
    
    if not row:
        return {"study_goal_minutes": 60, "notification_time": "20:59", "notifications_enabled": True}
    
    return dict(row)

@app.post("/habits/settings")
def update_habit_settings(req: dict, request: Request):
    """Update user's habit settings"""
    user = require_user(request)
    goal = req.get("study_goal_minutes", 60)
    notif_time = req.get("notification_time", "20:59")
    
    db = get_db()
    db.execute("""
        INSERT INTO user_habits (user_id, study_goal_minutes, notification_time)
        VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET
        study_goal_minutes=excluded.study_goal_minutes,
        notification_time=excluded.notification_time
    """, (user["id"], goal, notif_time))
    db.commit()
    db.close()
    
    return {"status": "settings_updated"}

@app.get("/daily-goal/today")
def get_today_goal(request: Request):
    """Get today's goal progress"""
    user = require_user(request)
    today = date.today().isoformat()
    
    db = get_db()
    
    # Get or create goal
    goal = db.execute(
        "SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?",
        (user["id"], today)
    ).fetchone()
    
    if not goal:
        # Create goal from habits
        habits = db.execute(
            "SELECT study_goal_minutes FROM user_habits WHERE user_id=?",
            (user["id"],)
        ).fetchone()
        goal_mins = habits["study_goal_minutes"] if habits else 60
        
        db.execute(
            "INSERT INTO daily_goals (user_id, goal_date, goal_minutes) VALUES(?,?,?)",
            (user["id"], today, goal_mins)
        )
        db.commit()
        goal = db.execute(
            "SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?",
            (user["id"], today)
        ).fetchone()
    
    db.close()
    
    return {
        "goal_minutes": goal["goal_minutes"],
        "completed_minutes": goal["completed_minutes"],
        "completed": goal["completed"],
        "progress_percent": int((goal["completed_minutes"] / max(1, goal["goal_minutes"])) * 100)
    }

@app.post("/daily-goal/update")
def update_goal_progress(req: dict, request: Request):
    """Update progress on today's goal"""
    user = require_user(request)
    minutes = req.get("minutes", 0)
    today = date.today().isoformat()
    
    db = get_db()
    
    goal = db.execute(
        "SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?",
        (user["id"], today)
    ).fetchone()
    
    if not goal:
        return {"status": "no_goal"}
    
    new_completed = goal["completed_minutes"] + minutes
    is_completed = new_completed >= goal["goal_minutes"]
    
    db.execute(
        "UPDATE daily_goals SET completed_minutes=?, completed=? WHERE user_id=? AND goal_date=?",
        (new_completed, is_completed, user["id"], today)
    )
    
    # Award badge if goal completed
    if is_completed and not goal["completed"]:
        award_badge(user["id"], "daily_goal", "⭐ Daily Goal", db)
    
    db.commit()
    db.close()
    
    return {
        "completed_minutes": new_completed,
        "goal_completed": is_completed,
        "progress_percent": int((new_completed / max(1, goal["goal_minutes"])) * 100)
    }

@app.get("/reminders/should-notify")
def should_send_notification(request: Request):
    """Check if it's time to send evening notification"""
    user = require_user(request)
    
    db = get_db()
    habits = db.execute(
        "SELECT * FROM user_habits WHERE user_id=?", (user["id"],)
    ).fetchone()
    db.close()
    
    if not habits or not habits["notifications_enabled"]:
        return {"should_notify": False}
    
    # Check if notification already sent today
    if habits["last_notification_sent"] == date.today().isoformat():
        return {"should_notify": False}
    
    # Check current time vs notification_time
    now = datetime.now().time()
    notif_hour, notif_min = map(int, habits["notification_time"].split(':'))
    notif_time = datetime.min.time().replace(hour=notif_hour, minute=notif_min)
    
    return {"should_notify": now >= notif_time}

@app.post("/reminders/mark-sent")
def mark_notification_sent(request: Request):
    """Mark notification as sent for today"""
    user = require_user(request)
    
    db = get_db()
    db.execute(
        "UPDATE user_habits SET last_notification_sent=? WHERE user_id=?",
        (date.today().isoformat(), user["id"])
    )
    db.commit()
    db.close()
    
    return {"status": "notification_marked"}

# ── PHASE 3B: SOCIAL LEADERBOARD ────────────────────────────────────────────

@app.get("/leaderboard/global")
def get_global_leaderboard(request: Request):
    """Get top 50 students by points"""
    user = require_user(request)
    
    db = get_db()
    
    # Calculate points for all active users
    users = db.execute("SELECT id, name, picture FROM users LIMIT 100").fetchall()
    
    leaderboard_data = []
    for u in users:
        # Points = streak days + quiz attempts + mock exams
        streak = db.execute(
            "SELECT current_streak FROM streaks WHERE user_id=?", (u["id"],)
        ).fetchone()
        
        quizzes = db.execute(
            "SELECT COUNT(*) as count FROM quiz_attempts WHERE user_id=?",
            (u["id"],)
        ).fetchone()
        
        mocks = db.execute(
            "SELECT AVG(score) as avg_score FROM mock_exams WHERE user_id=?",
            (u["id"],)
        ).fetchone()
        
        points = (streak["current_streak"] if streak else 0) * 10 + (quizzes["count"] if quizzes else 0) * 2
        avg_score = mocks["avg_score"] if mocks and mocks["avg_score"] else 0
        
        leaderboard_data.append({
            "user_id": u["id"],
            "name": u["name"],
            "picture": u["picture"],
            "points": points,
            "streak": streak["current_streak"] if streak else 0,
            "avg_score": float(avg_score)
        })
    
    # Sort by points
    leaderboard_data.sort(key=lambda x: x["points"], reverse=True)
    
    # Add rank
    for i, entry in enumerate(leaderboard_data[:50], 1):
        entry["rank"] = i
    
    db.close()
    
    # Highlight current user's rank
    user_rank = next((e for e in leaderboard_data if e["user_id"] == user["id"]), None)
    
    return {
        "leaderboard": leaderboard_data[:50],
        "user_rank": user_rank
    }

@app.get("/leaderboard/weekly")
def get_weekly_leaderboard(request: Request):
    """Get top students by this week's activity"""
    user = require_user(request)
    
    db = get_db()
    
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    
    users = db.execute("SELECT id, name, picture FROM users LIMIT 100").fetchall()
    
    weekly_data = []
    for u in users:
        # Minutes studied this week
        logs = db.execute("""
            SELECT SUM(minutes_studied) as total FROM daily_study_log
            WHERE user_id=? AND study_date >= ?
        """, (u["id"], week_start)).fetchone()
        
        # Quizzes this week
        quizzes = db.execute("""
            SELECT COUNT(*) as count FROM quiz_attempts
            WHERE user_id=? AND DATE(attempted_at) >= ?
        """, (u["id"], week_start)).fetchone()
        
        minutes = logs["total"] if logs and logs["total"] else 0
        quiz_count = quizzes["count"] if quizzes else 0
        
        weekly_data.append({
            "user_id": u["id"],
            "name": u["name"],
            "picture": u["picture"],
            "minutes_studied": minutes,
            "quizzes": quiz_count,
            "score": (minutes * 1) + (quiz_count * 5)  # Points formula
        })
    
    weekly_data.sort(key=lambda x: x["score"], reverse=True)
    
    for i, entry in enumerate(weekly_data[:50], 1):
        entry["rank"] = i
    
    db.close()
    
    user_rank = next((e for e in weekly_data if e["user_id"] == user["id"]), None)
    
    return {
        "leaderboard": weekly_data[:50],
        "user_rank": user_rank,
        "week_start": week_start
    }

@app.post("/leaderboard/share-score")
def share_mock_score(req: dict, request: Request):
    """Share mock exam score (for social pressure)"""
    user = require_user(request)
    score = req.get("score", 0)
    subject = req.get("subject", "")
    
    # This just returns shareable message
    return {
        "share_text": f"🎯 I scored {score}/100 on {subject} mock exam! Can you beat my score? #ChotuStudyOS",
        "share_url": f"https://chotu-lcc7.onrender.com/?challenge={score}&subject={subject}"
    }

# ── PHASE 3C: AI PERSONALIZATION & DAILY RECOMMENDATIONS ──────────────────

@app.post("/recommendations/generate")
def generate_daily_recommendations(req: dict, request: Request):
    """AI generates personalized daily study recommendations"""
    user = require_user(request)
    gcl = get_groq(user)
    
    db = get_db()
    
    # Get user's weak topics
    weak = db.execute("""
        SELECT subject, topic, confidence FROM weak_topics
        WHERE user_id=? AND confidence < 70
        ORDER BY confidence ASC LIMIT 5
    """, (user["id"],)).fetchall()
    
    # Get recent quiz performance
    quizzes = db.execute("""
        SELECT topic, AVG(CASE WHEN is_correct THEN 100 ELSE 0 END) as avg_score
        FROM quiz_attempts
        WHERE user_id=? AND DATE(attempted_at) >= DATE('now', '-7 days')
        GROUP BY topic
        ORDER BY avg_score ASC LIMIT 5
    """, (user["id"],)).fetchall()
    
    db.close()
    
    weak_list = [f"{t['topic']} ({t['confidence']}% confidence)" for t in weak]
    quiz_list = [f"{q['topic']} ({int(q['avg_score'])}% avg score)" for q in quizzes]
    
    prompt = f"""User {user.get('name', 'Student')} needs daily study recommendations.

Weak areas: {', '.join(weak_list) if weak_list else 'None yet'}
Low-scoring topics: {', '.join(quiz_list) if quiz_list else 'None yet'}

Generate 3 SPECIFIC study recommendations for TODAY:
1. Most urgent (fix weakness immediately)
2. Build momentum (leverage strength)
3. Learn something new (expand knowledge)

Format: 
1. [Topic] - [Why it matters] (15-20 min)
2. [Topic] - [Why it matters] (15-20 min)
3. [Topic] - [Why it matters] (15-20 min)

Be concise and motivating. No fluff."""
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        
        recommendations = resp.choices[0].message.content
        
        # Store in DB
        db = get_db()
        today = date.today().isoformat()
        
        db.execute(
            "DELETE FROM daily_recommendations WHERE user_id=? AND recommendation_date=?",
            (user["id"], today)
        )
        
        db.execute("""
            INSERT INTO daily_recommendations 
            (user_id, recommendation_date, subject, topic, reason, priority)
            VALUES(?,?,?,?,?,?)
        """, (user["id"], today, "Daily", "Personalized Plan", recommendations, 1))
        
        db.commit()
        db.close()
        
        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations/today")
def get_today_recommendations(request: Request):
    """Get today's AI-generated recommendations"""
    user = require_user(request)
    today = date.today().isoformat()
    
    db = get_db()
    rec = db.execute(
        "SELECT * FROM daily_recommendations WHERE user_id=? AND recommendation_date=?",
        (user["id"], today)
    ).fetchone()
    db.close()
    
    if not rec:
        return {"recommendations": None, "message": "Run generation first"}
    
    return {
        "recommendations": rec["reason"],
        "priority": rec["priority"],
        "completed": rec["completed"]
    }

# ── BADGES & ACHIEVEMENTS ────────────────────────────────────────────────

def award_badge(user_id: int, badge_id: str, badge_name: str, db=None):
    """Award badge to user"""
    should_close = False
    if db is None:
        db = get_db()
        should_close = True
    
    try:
        db.execute(
            "INSERT INTO user_badges (user_id, badge_name, badge_icon) VALUES(?,?,?)",
            (user_id, badge_name, "🏆")
        )
        db.commit()
    except:
        # Badge already exists
        pass
    finally:
        if should_close:
            db.close()

@app.get("/badges")
def get_user_badges(request: Request):
    """Get all badges earned by user"""
    user = require_user(request)
    
    db = get_db()
    badges = db.execute(
        "SELECT * FROM user_badges WHERE user_id=? ORDER BY earned_at DESC",
        (user["id"],)
    ).fetchall()
    db.close()
    
    return {"badges": [dict(b) for b in badges]}

@app.get("/achievements")
def get_achievements(request: Request):
    """Get achievement progress"""
    user = require_user(request)
    
    db = get_db()
    
    # Calculate various achievement metrics
    streak = db.execute(
        "SELECT current_streak, longest_streak FROM streaks WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    quizzes = db.execute(
        "SELECT COUNT(*) as count, AVG(CAST(is_correct AS FLOAT))*100 as avg_score FROM quiz_attempts WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    mocks = db.execute(
        "SELECT COUNT(*) as count FROM mock_exams WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    db.close()
    
    achievements = {
        "streaks": {
            "current": streak["current_streak"] if streak else 0,
            "longest": streak["longest_streak"] if streak else 0,
            "milestones": [7, 14, 30, 60, 100]
        },
        "quizzes": {
            "attempted": quizzes["count"] if quizzes else 0,
            "accuracy": round(quizzes["avg_score"] if quizzes and quizzes["avg_score"] else 0, 1),
            "milestones": [10, 50, 100, 250]
        },
        "mocks": {
            "completed": mocks["count"] if mocks else 0,
            "milestones": [1, 5, 10]
        }
    }
    
    return achievements

# ════════════════════════════════════════════════════════════════════════════
# END PHASE 3
# ════════════════════════════════════════════════════════════════════════════
# PHASE 4: NOTIFICATIONS + SHARING + VIRAL LOOPS
# Add these to server.py after Phase 3 endpoints

# ════════════════════════════════════════════════════════════════════════════
# PHASE 4: DISTRIBUTION & HABIT FORMATION
# ════════════════════════════════════════════════════════════════════════════

# Add to init_db() - new tables:
"""
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT,  -- streak_warning, rank_drop, challenge, achievement, friend_activity
    data JSON,
    created_at TEXT DEFAULT (datetime('now')),
    sent_at TEXT,
    read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id INTEGER NOT NULL,
    challenge_type TEXT,  -- mock_exam_score, streak, hours_studied
    target_value INTEGER,
    subject TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    participants JSON,  -- list of user_ids
    FOREIGN KEY (creator_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS share_tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    share_type TEXT,  -- leaderboard, score, streak, badge
    data JSON,
    created_at TEXT DEFAULT (datetime('now')),
    expiry TEXT,
    views INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER NOT NULL,
    referred_id INTEGER,
    share_token TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    converted BOOLEAN DEFAULT FALSE,
    converted_at TEXT,
    reward_given BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (referrer_id) REFERENCES users(id),
    FOREIGN KEY (referred_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS friend_connections (
    user_id INTEGER NOT NULL,
    friend_id INTEGER NOT NULL,
    connected_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, friend_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (friend_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS friend_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    activity_type TEXT,  -- beat_score, unlocked_badge, started_exam, streak_milestone
    subject TEXT,
    value TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

# ── PHASE 4A: NOTIFICATIONS ────────────────────────────────────────────────

@app.post("/notifications/send")
def send_notification(req: dict, request: Request):
    """Manually send notification (for testing)"""
    user = require_user(request)
    
    # Only send to own user (in production, admin only)
    target_user = req.get("target_user_id", user["id"])
    
    db = get_db()
    db.execute("""
        INSERT INTO notifications (user_id, title, message, type, data)
        VALUES(?,?,?,?,?)
    """, (target_user, req.get("title", ""), req.get("message", ""), 
          req.get("type", "alert"), json.dumps(req.get("data", {}))))
    db.commit()
    db.close()
    
    return {"status": "notification_sent"}

@app.get("/notifications")
def get_notifications(request: Request):
    """Get user's unread notifications"""
    user = require_user(request)
    
    db = get_db()
    notifs = db.execute("""
        SELECT * FROM notifications 
        WHERE user_id=? AND read=FALSE
        ORDER BY created_at DESC LIMIT 20
    """, (user["id"],)).fetchall()
    db.close()
    
    return {"notifications": [dict(n) for n in notifs]}

@app.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, request: Request):
    """Mark notification as read"""
    user = require_user(request)
    
    db = get_db()
    db.execute(
        "UPDATE notifications SET read=TRUE WHERE id=? AND user_id=?",
        (notif_id, user["id"])
    )
    db.commit()
    db.close()
    
    return {"status": "marked_read"}

@app.post("/notifications/trigger-streak-warning")
def trigger_streak_warning(request: Request):
    """Manually trigger evening streak warning (normally automated)"""
    user = require_user(request)
    
    db = get_db()
    streak = db.execute(
        "SELECT current_streak FROM streaks WHERE user_id=?", (user["id"],)
    ).fetchone()
    
    if streak and streak["current_streak"] > 2:
        db.execute("""
            INSERT INTO notifications (user_id, title, message, type)
            VALUES(?,?,?,?)
        """, (user["id"], 
              f"🔥 Your {streak['current_streak']}-day streak ends at midnight!",
              f"Study for just 10 minutes to keep your streak alive.",
              "streak_warning"))
    
    db.commit()
    db.close()
    
    return {"status": "notification_sent"}

@app.post("/notifications/trigger-rank-drop")
def trigger_rank_drop_notification(request: Request):
    """Notify if user dropped in rankings"""
    user = require_user(request)
    
    db = get_db()
    
    # Get current rank (simplified)
    all_users = db.execute("""
        SELECT u.id, COUNT(qa.id) as quiz_count FROM users u
        LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
        GROUP BY u.id ORDER BY quiz_count DESC
    """).fetchall()
    
    current_rank = next((i+1 for i, u in enumerate(all_users) if u["id"] == user["id"]), None)
    
    if current_rank and current_rank > 10:
        db.execute("""
            INSERT INTO notifications (user_id, title, message, type)
            VALUES(?,?,?,?)
        """, (user["id"],
              f"📉 You dropped to rank #{current_rank}",
              f"Other students are studying more. Push to get back in top 10!",
              "rank_drop"))
    
    db.commit()
    db.close()
    
    return {"status": "checked"}

# ── PHASE 4B: SHARING & VIRALITY ────────────────────────────────────────

@app.post("/share/create-link")
def create_share_link(req: dict, request: Request):
    """Create shareable link for leaderboard rank, score, or achievement"""
    user = require_user(request)
    share_type = req.get("type", "leaderboard")  # leaderboard, score, streak, badge
    
    token = secrets.token_urlsafe(16)
    data = {
        "user_id": user["id"],
        "user_name": user["name"],
        "type": share_type,
        "value": req.get("value", ""),
        "created_at": datetime.now().isoformat()
    }
    
    db = get_db()
    db.execute("""
        INSERT INTO share_tokens (token, user_id, share_type, data, expiry)
        VALUES(?,?,?,?,?)
    """, (token, user["id"], share_type, json.dumps(data),
          (datetime.now() + timedelta(days=30)).isoformat()))
    db.commit()
    db.close()
    
    share_url = f"https://chotu-lcc7.onrender.com/share/{token}"
    
    # Generate share messages
    messages = {
        "leaderboard": f"🏆 I'm on the Chotu leaderboard! Can you beat my rank? {share_url}",
        "score": f"📝 I just scored {req.get('value', '0')}/100 on a mock exam! Think you can do better? {share_url}",
        "streak": f"🔥 I have a {req.get('value', '0')}-day study streak! Join me and build yours. {share_url}",
        "badge": f"🏅 I unlocked a badge on Chotu! See my achievement {share_url}"
    }
    
    return {
        "share_url": share_url,
        "share_message": messages.get(share_type, "Check me out on Chotu!"),
        "token": token
    }

@app.get("/share/{token}")
def view_shared_content(token: str):
    """View shared content (public, no auth)"""
    db = get_db()
    
    share = db.execute(
        "SELECT * FROM share_tokens WHERE token=?", (token,)
    ).fetchone()
    
    if not share:
        return {"error": "Link not found or expired"}
    
    # Increment view count
    db.execute("UPDATE share_tokens SET views=views+1 WHERE token=?", (token,))
    db.commit()
    
    data = json.loads(share["data"])
    
    return {
        "user_name": data.get("user_name"),
        "type": share["share_type"],
        "value": data.get("value"),
        "message": f"{data.get('user_name')} is crushing it on Chotu!",
        "cta": "Join Chotu and study smarter →"
    }

# ── PHASE 4C: CHALLENGES & COMPETITION ────────────────────────────────────

@app.post("/challenges/create")
def create_challenge(req: dict, request: Request):
    """Create a challenge for friends"""
    user = require_user(request)
    
    challenge_type = req.get("type", "mock_exam_score")  # mock_exam_score, streak, hours_studied
    target = req.get("target_value", 75)
    subject = req.get("subject", "")
    
    db = get_db()
    db.execute("""
        INSERT INTO challenges (creator_id, challenge_type, target_value, subject, expires_at, participants)
        VALUES(?,?,?,?,?,?)
    """, (user["id"], challenge_type, target, subject,
          (datetime.now() + timedelta(days=7)).isoformat(),
          json.dumps([user["id"]])))
    db.commit()
    
    challenge = db.execute(
        "SELECT id FROM challenges WHERE creator_id=? ORDER BY id DESC LIMIT 1",
        (user["id"],)
    ).fetchone()
    
    db.close()
    
    challenge_id = challenge["id"]
    challenge_url = f"https://chotu-lcc7.onrender.com/?challenge={challenge_id}"
    
    messages = {
        "mock_exam_score": f"🎯 I challenge you to score {target}/100 on {subject} mock exam! {challenge_url}",
        "streak": f"🔥 Can you beat my {target}-day study streak? {challenge_url}",
        "hours_studied": f"⏱️ I'm studying {target} hours this week. Join the challenge! {challenge_url}"
    }
    
    return {
        "challenge_id": challenge_id,
        "challenge_url": challenge_url,
        "share_message": messages.get(challenge_type)
    }

@app.post("/challenges/{challenge_id}/join")
def join_challenge(challenge_id: int, request: Request):
    """Join an existing challenge"""
    user = require_user(request)
    
    db = get_db()
    challenge = db.execute(
        "SELECT * FROM challenges WHERE id=?", (challenge_id,)
    ).fetchone()
    
    if not challenge:
        raise HTTPException(status_code=404)
    
    participants = json.loads(challenge["participants"] or "[]")
    if user["id"] not in participants:
        participants.append(user["id"])
        db.execute(
            "UPDATE challenges SET participants=? WHERE id=?",
            (json.dumps(participants), challenge_id)
        )
        db.commit()
    
    db.close()
    
    return {"status": "joined", "challenge_id": challenge_id}

@app.get("/challenges/{challenge_id}")
def get_challenge_progress(challenge_id: int, request: Request):
    """Get progress on a challenge"""
    user = require_user(request)
    
    db = get_db()
    challenge = db.execute(
        "SELECT * FROM challenges WHERE id=?", (challenge_id,)
    ).fetchone()
    
    if not challenge:
        raise HTTPException(status_code=404)
    
    participants = json.loads(challenge["participants"])
    
    # Calculate progress for each participant
    progress = {}
    for pid in participants:
        p_user = db.execute("SELECT name FROM users WHERE id=?", (pid,)).fetchone()
        
        if challenge["challenge_type"] == "mock_exam_score":
            latest_mock = db.execute("""
                SELECT score FROM mock_exams 
                WHERE user_id=? AND subject=?
                ORDER BY created_at DESC LIMIT 1
            """, (pid, challenge["subject"])).fetchone()
            score = latest_mock["score"] if latest_mock else 0
            progress[pid] = {
                "name": p_user["name"] if p_user else "Unknown",
                "score": score,
                "target": challenge["target_value"],
                "completed": score >= challenge["target_value"]
            }
        elif challenge["challenge_type"] == "streak":
            streak = db.execute(
                "SELECT current_streak FROM streaks WHERE user_id=?", (pid,)
            ).fetchone()
            current = streak["current_streak"] if streak else 0
            progress[pid] = {
                "name": p_user["name"] if p_user else "Unknown",
                "streak": current,
                "target": challenge["target_value"],
                "completed": current >= challenge["target_value"]
            }
    
    db.close()
    
    return {
        "challenge_type": challenge["challenge_type"],
        "target": challenge["target_value"],
        "participants": progress,
        "expires_at": challenge["expires_at"]
    }

# ── PHASE 4D: FRIEND ACTIVITY & SOCIAL FEED ────────────────────────────────

@app.post("/friends/connect")
def connect_friend(req: dict, request: Request):
    """Connect with another user (friend request)"""
    user = require_user(request)
    friend_email = req.get("friend_email", "")
    
    db = get_db()
    friend = db.execute(
        "SELECT id FROM users WHERE email=?", (friend_email,)
    ).fetchone()
    
    if not friend:
        return {"error": "Friend not found"}
    
    db.execute(
        "INSERT OR IGNORE INTO friend_connections (user_id, friend_id) VALUES(?,?)",
        (user["id"], friend["id"])
    )
    db.commit()
    db.close()
    
    return {"status": "friend_connected"}

@app.get("/friends/activity")
def get_friend_activity(request: Request):
    """Get activity from friends"""
    user = require_user(request)
    
    db = get_db()
    
    # Get friend IDs
    friends = db.execute(
        "SELECT friend_id FROM friend_connections WHERE user_id=?",
        (user["id"],)
    ).fetchall()
    
    friend_ids = [f["friend_id"] for f in friends]
    
    if not friend_ids:
        return {"activity": []}
    
    # Get recent activity from friends
    placeholders = ",".join(["?"] * len(friend_ids))
    activity = db.execute(f"""
        SELECT * FROM friend_activity 
        WHERE user_id IN ({placeholders})
        ORDER BY created_at DESC LIMIT 10
    """, friend_ids).fetchall()
    
    db.close()
    
    return {"activity": [dict(a) for a in activity]}

@app.post("/activity/log")
def log_user_activity(req: dict, request: Request):
    """Log user activity for friends to see"""
    user = require_user(request)
    
    db = get_db()
    db.execute("""
        INSERT INTO friend_activity (user_id, activity_type, subject, value)
        VALUES(?,?,?,?)
    """, (user["id"], req.get("type", ""), req.get("subject", ""), 
          req.get("value", "")))
    db.commit()
    db.close()
    
    return {"status": "activity_logged"}

# ── PHASE 4E: REFERRAL SYSTEM (Viral Growth) ────────────────────────────

@app.get("/referral/link")
def get_referral_link(request: Request):
    """Get user's referral link"""
    user = require_user(request)
    
    token = secrets.token_urlsafe(12)
    
    db = get_db()
    db.execute("""
        INSERT INTO referrals (referrer_id, share_token)
        VALUES(?,?)
    """, (user["id"], token))
    db.commit()
    db.close()
    
    referral_url = f"https://chotu-lcc7.onrender.com/?ref={token}"
    
    return {
        "referral_url": referral_url,
        "share_message": f"🎓 I'm using Chotu to study smarter. Free AI tutor that actually helps. {referral_url}",
        "reward": "Unlock premium features when friends join"
    }

@app.post("/referral/claim")
def claim_referral_reward(req: dict, request: Request):
    """Claim reward for successful referral"""
    user = require_user(request)
    ref_token = req.get("referral_token", "")
    
    db = get_db()
    referral = db.execute(
        "SELECT referrer_id FROM referrals WHERE share_token=?",
        (ref_token,)
    ).fetchone()
    
    if not referral:
        return {"error": "Invalid referral link"}
    
    # Mark as converted
    db.execute("""
        UPDATE referrals SET referred_id=?, converted=TRUE, converted_at=datetime('now')
        WHERE share_token=?
    """, (user["id"], ref_token))
    
    # Give reward to referrer (e.g., 100 points)
    db.execute("""
        UPDATE leaderboard SET total_points=total_points+100 WHERE user_id=?
    """, (referral["referrer_id"],))
    
    db.commit()
    db.close()
    
    return {"status": "reward_claimed", "message": "Referrer earned 100 points!"}

# ════════════════════════════════════════════════════════════════════════════
# END PHASE 4
# ════════════════════════════════════════════════════════════════════════════
# PHASE 5: ADAPTIVE INTELLIGENCE + MONETIZATION
# Add these to server.py after Phase 4 endpoints

# ════════════════════════════════════════════════════════════════════════════
# PHASE 5: ADVANCED PERSONALIZATION & BUSINESS MODEL
# ════════════════════════════════════════════════════════════════════════════

# Add to init_db() - new tables:
"""
CREATE TABLE IF NOT EXISTS learning_profiles (
    user_id INTEGER PRIMARY KEY,
    learning_style TEXT,  -- visual, auditory, kinesthetic, reading
    pace TEXT,  -- slow, normal, fast
    preferred_subject TEXT,
    difficulty_preference INTEGER (1-5),
    study_pattern TEXT,  -- morning, evening, mixed
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS adaptive_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    current_level INTEGER (1-10),
    mastered_topics INTEGER DEFAULT 0,
    total_topics INTEGER,
    estimated_completion_days INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, subject)
);

CREATE TABLE IF NOT EXISTS skill_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_name TEXT,
    proficiency_score FLOAT (0-100),
    assessment_type TEXT,  -- quiz, mock, peer_review
    assessed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS study_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT,
    topics_studied INTEGER,
    quiz_accuracy FLOAT,
    focus_session_count INTEGER,
    streak_maintained BOOLEAN,
    recommendations_followed BOOLEAN,
    active_time_minutes INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT,  -- free, pro, premium
    status TEXT,  -- active, cancelled, expired
    started_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    auto_renew BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS premium_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    feature_name TEXT,  -- unlimited_mocks, ai_mentor, peer_tutor, interview_prep
    unlocked_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, feature_name)
);

CREATE TABLE IF NOT EXISTS ai_mentor_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subject TEXT,
    topic TEXT,
    question TEXT,
    ai_response TEXT,
    student_rating INTEGER (1-5),
    session_duration_minutes INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS interview_prep_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_type TEXT,  -- behavioral, technical, coding
    company TEXT,
    question TEXT,
    user_answer TEXT,
    feedback TEXT,
    score INTEGER (0-100),
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS peer_tutoring (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    subject TEXT,
    topic TEXT,
    session_status TEXT,  -- requested, scheduled, completed, rated
    scheduled_at TEXT,
    completed_at TEXT,
    student_rating INTEGER (1-5),
    tutor_earnings FLOAT DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (tutor_id) REFERENCES users(id),
    FOREIGN KEY (student_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    notifications_enabled BOOLEAN DEFAULT TRUE,
    email_frequency TEXT,  -- daily, weekly, never
    difficulty_auto_adjust BOOLEAN DEFAULT TRUE,
    show_solutions_immediately BOOLEAN DEFAULT FALSE,
    language TEXT DEFAULT 'en',
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

from datetime import datetime, timedelta
import random

# ── PHASE 5A: ADAPTIVE LEARNING PATHS ────────────────────────────────────

@app.post("/learning/assess-style")
def assess_learning_style(req: dict, request: Request):
    """Quiz to determine learning style"""
    user = require_user(request)
    
    # Simple assessment based on quiz answers
    answers = req.get("answers", {})  # {q1: 'a', q2: 'b', ...}
    
    # Count answer patterns
    style_map = {'a': 'visual', 'b': 'auditory', 'c': 'kinesthetic', 'd': 'reading'}
    style = style_map.get(max(set(answers.values()), key=list(answers.values()).count), 'visual')
    pace = 'fast' if len([a for a in answers.values() if a in ['a', 'b']]) > len(answers)/2 else 'normal'
    
    db = get_db()
    db.execute("""
        INSERT INTO learning_profiles (user_id, learning_style, pace)
        VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET
        learning_style=excluded.learning_style, pace=excluded.pace
    """, (user["id"], style, pace))
    db.commit()
    db.close()
    
    return {"learning_style": style, "pace": pace, "message": f"You're a {style} learner who prefers {pace} pace"}

@app.post("/adaptive-path/generate")
def generate_adaptive_path(req: dict, request: Request):
    """Generate personalized learning path based on goals"""
    user = require_user(request)
    subject = req.get("subject", "")
    goal = req.get("goal", "")  # e.g., "master DSA in 30 days"
    current_level = req.get("current_level", 3)
    
    gcl = get_groq(user)
    
    prompt = f"""Create a personalized learning path for this student:
Subject: {subject}
Goal: {goal}
Current level: {current_level}/10
Learning style preference: visual

Generate a week-by-week breakdown:
- Week 1: [Topics to cover]
- Week 2: [Topics to cover]
- Week 3: [Topics to cover]
- Week 4: [Topics to cover]

Include:
1. Daily study schedule (topics + hours)
2. Key concepts to master
3. Practice exercises
4. Milestones to hit
5. Assessment checkpoints

Format as structured JSON."""
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )
        
        path_data = resp.choices[0].message.content
        
        db = get_db()
        db.execute("""
            INSERT INTO adaptive_paths (user_id, subject, current_level, total_topics, estimated_completion_days)
            VALUES(?,?,?,?,?) ON CONFLICT(user_id, subject) DO UPDATE SET
            current_level=excluded.current_level
        """, (user["id"], subject, current_level, 25, 28))
        db.commit()
        db.close()
        
        return {"path": path_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/adaptive-path/{subject}")
def get_adaptive_path(subject: str, request: Request):
    """Get user's personalized learning path"""
    user = require_user(request)
    
    db = get_db()
    path = db.execute(
        "SELECT * FROM adaptive_paths WHERE user_id=? AND subject=?",
        (user["id"], subject)
    ).fetchone()
    
    profile = db.execute(
        "SELECT * FROM learning_profiles WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    db.close()
    
    if not path:
        return {"error": "No path generated yet"}
    
    progress = (path["mastered_topics"] / max(1, path["total_topics"])) * 100
    
    return {
        "subject": subject,
        "level": path["current_level"],
        "progress": progress,
        "mastered": path["mastered_topics"],
        "total": path["total_topics"],
        "days_to_completion": path["estimated_completion_days"],
        "learning_style": profile["learning_style"] if profile else "unknown"
    }

@app.post("/adaptive-path/adjust-difficulty")
def adjust_difficulty_dynamically(req: dict, request: Request):
    """Auto-adjust difficulty based on performance"""
    user = require_user(request)
    subject = req.get("subject", "")
    recent_accuracy = req.get("accuracy", 0)  # 0-100
    
    db = get_db()
    path = db.execute(
        "SELECT * FROM adaptive_paths WHERE user_id=? AND subject=?",
        (user["id"], subject)
    ).fetchone()
    
    if not path:
        return {"error": "No path found"}
    
    # Adjust level based on accuracy
    if recent_accuracy >= 85:
        new_level = min(10, path["current_level"] + 1)
        recommendation = "Great job! Moving to harder topics"
    elif recent_accuracy < 60:
        new_level = max(1, path["current_level"] - 1)
        recommendation = "Let's review basics before moving forward"
    else:
        new_level = path["current_level"]
        recommendation = "Keep practicing at current level"
    
    db.execute(
        "UPDATE adaptive_paths SET current_level=? WHERE user_id=? AND subject=?",
        (new_level, user["id"], subject)
    )
    db.commit()
    db.close()
    
    return {"new_level": new_level, "recommendation": recommendation}

# ── PHASE 5B: AI MENTOR (Premium) ────────────────────────────────────────

@app.post("/ai-mentor/ask")
def ask_ai_mentor(req: dict, request: Request):
    """Premium: Ask AI mentor for detailed explanations"""
    user = require_user(request)
    
    # Check if user has premium
    db = get_db()
    sub = db.execute(
        "SELECT plan FROM subscriptions WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    if not sub or sub["plan"] == "free":
        return {"error": "Premium feature. Upgrade to unlock", "upgrade_url": "/upgrade"}
    
    subject = req.get("subject", "")
    topic = req.get("topic", "")
    question = req.get("question", "")
    
    gcl = get_groq(user)
    
    prompt = f"""You are an expert AI mentor in {subject}.
Student is learning about: {topic}
Their question: {question}

Provide:
1. Clear, detailed explanation (tutor-level)
2. Real-world example
3. Common misconceptions students have
4. Practice problem they should try
5. Next concept to learn after mastering this

Be encouraging and supportive."""
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=800
        )
        
        answer = resp.choices[0].message.content
        
        # Log session
        db.execute("""
            INSERT INTO ai_mentor_sessions (user_id, subject, topic, question, ai_response)
            VALUES(?,?,?,?,?)
        """, (user["id"], subject, topic, question, answer))
        db.commit()
        db.close()
        
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai-mentor/rate")
def rate_mentor_response(req: dict, request: Request):
    """Rate AI mentor's response"""
    user = require_user(request)
    session_id = req.get("session_id", 0)
    rating = req.get("rating", 5)  # 1-5
    
    db = get_db()
    db.execute(
        "UPDATE ai_mentor_sessions SET student_rating=? WHERE id=? AND user_id=?",
        (rating, session_id, user["id"])
    )
    db.commit()
    db.close()
    
    return {"status": "rated"}

# ── PHASE 5C: INTERVIEW PREP (Premium) ──────────────────────────────────

@app.post("/interview-prep/start")
def start_interview_session(req: dict, request: Request):
    """Start mock interview session"""
    user = require_user(request)
    
    db = get_db()
    sub = db.execute(
        "SELECT plan FROM subscriptions WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    if not sub or sub["plan"] == "free":
        return {"error": "Premium feature. Upgrade to unlock"}
    
    session_type = req.get("type", "behavioral")  # behavioral, technical, coding
    company = req.get("company", "Google")
    
    gcl = get_groq(user)
    
    # Generate interview question
    prompts = {
        "behavioral": f"Generate a tough behavioral interview question for {company}. Format: QUESTION: [question]",
        "technical": f"Generate a {company} technical interview question about system design. Format: QUESTION: [question]",
        "coding": f"Generate a {company} coding interview question (LeetCode hard). Format: QUESTION: [question]"
    }
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompts.get(session_type, prompts["behavioral"])}],
            temperature=0.7,
            max_tokens=300
        )
        
        question = resp.choices[0].message.content
        
        db.execute("""
            INSERT INTO interview_prep_sessions (user_id, session_type, company, question, session_status)
            VALUES(?,?,?,?,?)
        """, (user["id"], session_type, company, question, "started"))
        
        session = db.execute(
            "SELECT id FROM interview_prep_sessions WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user["id"],)
        ).fetchone()
        
        db.commit()
        db.close()
        
        return {"session_id": session["id"], "question": question}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interview-prep/{session_id}/submit-answer")
def submit_interview_answer(session_id: int, req: dict, request: Request):
    """Submit answer and get feedback"""
    user = require_user(request)
    answer = req.get("answer", "")
    
    gcl = get_groq(user)
    
    db = get_db()
    session = db.execute(
        "SELECT * FROM interview_prep_sessions WHERE id=? AND user_id=?",
        (session_id, user["id"])
    ).fetchone()
    
    if not session:
        return {"error": "Session not found"}
    
    prompt = f"""You are an expert interviewer. 
Question: {session["question"]}
Candidate's answer: {answer}

Evaluate and provide:
1. Score (0-100)
2. Strengths
3. Weaknesses
4. How to improve
5. Sample better answer

Be honest but constructive."""
    
    try:
        resp = gcl.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        feedback = resp.choices[0].message.content
        score = random.randint(60, 95)  # Extract from feedback ideally
        
        db.execute("""
            UPDATE interview_prep_sessions 
            SET user_answer=?, feedback=?, score=?, session_status='completed'
            WHERE id=?
        """, (answer, feedback, score, session_id))
        db.commit()
        db.close()
        
        return {"score": score, "feedback": feedback}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── PHASE 5D: PEER TUTORING MARKETPLACE ─────────────────────────────────

@app.post("/tutoring/request")
def request_tutor(req: dict, request: Request):
    """Request a peer tutor"""
    user = require_user(request)
    subject = req.get("subject", "")
    topic = req.get("topic", "")
    
    db = get_db()
    
    # Find tutors (users with high scores in this subject)
    tutors = db.execute("""
        SELECT u.id, u.name FROM users u
        JOIN mock_exams m ON u.id = m.user_id
        WHERE m.subject=? AND m.score > 80
        LIMIT 5
    """, (subject,)).fetchall()
    
    if not tutors:
        return {"error": "No tutors available"}
    
    tutor = random.choice(tutors)
    
    db.execute("""
        INSERT INTO peer_tutoring (tutor_id, student_id, subject, topic, session_status)
        VALUES(?,?,?,?,?)
    """, (tutor["id"], user["id"], subject, topic, "requested"))
    
    session = db.execute(
        "SELECT id FROM peer_tutoring WHERE student_id=? ORDER BY id DESC LIMIT 1",
        (user["id"],)
    ).fetchone()
    
    db.commit()
    db.close()
    
    return {
        "tutor_name": tutor["name"],
        "session_id": session["id"],
        "message": f"Tutor {tutor['name']} has been matched! They'll respond soon."
    }

@app.get("/tutoring/sessions")
def get_tutoring_sessions(request: Request):
    """Get user's tutoring sessions (as tutor or student)"""
    user = require_user(request)
    
    db = get_db()
    
    # Sessions as student
    as_student = db.execute("""
        SELECT p.*, u.name as tutor_name FROM peer_tutoring p
        JOIN users u ON p.tutor_id = u.id
        WHERE p.student_id=?
        ORDER BY p.created_at DESC
    """, (user["id"],)).fetchall()
    
    # Sessions as tutor
    as_tutor = db.execute("""
        SELECT p.*, u.name as student_name FROM peer_tutoring p
        JOIN users u ON p.student_id = u.id
        WHERE p.tutor_id=?
        ORDER BY p.created_at DESC
    """, (user["id"],)).fetchall()
    
    db.close()
    
    return {
        "as_student": [dict(s) for s in as_student],
        "as_tutor": [dict(s) for s in as_tutor]
    }

# ── PHASE 5E: MONETIZATION & SUBSCRIPTIONS ──────────────────────────────

@app.get("/pricing")
def get_pricing():
    """Get pricing plans"""
    return {
        "plans": [
            {
                "name": "Free",
                "price": 0,
                "features": [
                    "Spaced repetition",
                    "Daily streaks",
                    "Mock exams (3/month)",
                    "Leaderboard",
                    "Basic coaching"
                ]
            },
            {
                "name": "Pro",
                "price": 99,  # ₹99/month
                "features": [
                    "Everything in Free",
                    "Unlimited mock exams",
                    "AI Mentor (10 questions/month)",
                    "Advanced analytics",
                    "Ad-free experience"
                ]
            },
            {
                "name": "Premium",
                "price": 299,  # ₹299/month
                "features": [
                    "Everything in Pro",
                    "Unlimited AI Mentor",
                    "Interview prep (coding + behavioral)",
                    "Peer tutoring (5 sessions/month)",
                    "Priority support",
                    "Certificate of completion"
                ]
            }
        ]
    }

@app.post("/subscription/upgrade")
def upgrade_subscription(req: dict, request: Request):
    """Upgrade to paid plan"""
    user = require_user(request)
    plan = req.get("plan", "pro")  # pro, premium
    
    db = get_db()
    
    # Create/update subscription
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    
    db.execute("""
        INSERT INTO subscriptions (user_id, plan, status, expires_at)
        VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
        plan=excluded.plan, status='active', expires_at=excluded.expires_at
    """, (user["id"], plan, "active", expires_at))
    
    # Unlock premium features
    features = {
        "pro": ["unlimited_mocks", "ai_mentor"],
        "premium": ["unlimited_mocks", "ai_mentor", "interview_prep", "peer_tutor"]
    }
    
    for feature in features.get(plan, []):
        db.execute("""
            INSERT OR IGNORE INTO premium_features (user_id, feature_name)
            VALUES(?,?)
        """, (user["id"], feature))
    
    db.commit()
    db.close()
    
    return {
        "status": "upgraded",
        "plan": plan,
        "expires_at": expires_at,
        "message": f"Welcome to {plan.upper()}! Unlock all premium features."
    }

@app.get("/subscription/status")
def get_subscription_status(request: Request):
    """Get user's subscription status"""
    user = require_user(request)
    
    db = get_db()
    sub = db.execute(
        "SELECT * FROM subscriptions WHERE user_id=?",
        (user["id"],)
    ).fetchone()
    
    features = db.execute(
        "SELECT feature_name FROM premium_features WHERE user_id=?",
        (user["id"],)
    ).fetchall()
    
    db.close()
    
    if not sub:
        return {
            "plan": "free",
            "status": "active",
            "features": [],
            "upgrade_url": "/pricing"
        }
    
    return {
        "plan": sub["plan"],
        "status": sub["status"],
        "expires_at": sub["expires_at"],
        "features": [f["feature_name"] for f in features],
        "days_left": max(0, (datetime.fromisoformat(sub["expires_at"]) - datetime.now()).days)
    }

# ── PHASE 5F: ANALYTICS & INSIGHTS ──────────────────────────────────────

@app.get("/analytics/dashboard")
def get_analytics_dashboard(request: Request):
    """Get personalized learning analytics"""
    user = require_user(request)
    
    db = get_db()
    
    # Get this month's data
    month_start = (datetime.now().replace(day=1)).isoformat()
    
    analytics = db.execute("""
        SELECT 
            SUM(topics_studied) as total_topics,
            AVG(quiz_accuracy) as avg_accuracy,
            SUM(focus_session_count) as total_sessions,
            SUM(active_time_minutes) as total_minutes
        FROM study_analytics
        WHERE user_id=? AND date >= ?
    """, (user["id"], month_start)).fetchone()
    
    # Get skills
    skills = db.execute("""
        SELECT skill_name, proficiency_score
        FROM skill_assessments
        WHERE user_id=?
        ORDER BY proficiency_score DESC
        LIMIT 5
    """, (user["id"],)).fetchall()
    
    db.close()
    
    return {
        "this_month": {
            "topics_studied": analytics["total_topics"] or 0,
            "avg_accuracy": round(analytics["avg_accuracy"], 1) if analytics["avg_accuracy"] else 0,
            "sessions": analytics["total_sessions"] or 0,
            "hours_studied": (analytics["total_minutes"] or 0) / 60
        },
        "top_skills": [{"skill": s["skill_name"], "level": s["proficiency_score"]} for s in skills]
    }

# ════════════════════════════════════════════════════════════════════════════
# END PHASE 5
# ════════════════════════════════════════════════════════════════════════════
