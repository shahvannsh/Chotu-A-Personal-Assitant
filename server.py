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

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
APP_NAME = "Chotu - Personal AI Assistant"
SESSIONS_FILE = Path("sessions.json")
MEMORY_FILE   = Path("memory.json")

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY         = os.getenv("GROQ_API_KEY", "")
TAVILY_KEY           = os.getenv("TAVILY_KEY", "")
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SECRET_KEY           = os.getenv("SECRET_KEY", secrets.token_hex(32))
REDIRECT_URI         = "https://chotu-a-personal-assitant-production.up.railway.app/auth/callback"
MODEL                = "llama-3.3-70b-versatile"

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = Path(os.getenv("DB_PATH", "/app/chotu.db"))

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

def log_session(uid: int, task: str, start_iso: str, end_iso: str):
    s = datetime.fromisoformat(start_iso)
    e = datetime.fromisoformat(end_iso)
    db = get_db()
    db.execute("INSERT INTO focus_sessions (user_id,task,date,start,end,duration) VALUES(?,?,?,?,?,?)",
               (uid, task, s.strftime("%Y-%m-%d"), start_iso, end_iso, int((e-s).total_seconds())))
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
    streak, chk = 0, date.today()
    while daily.get(chk.isoformat(),0) > 0:
        streak += 1; chk = chk - timedelta(days=1)
    return {"today": daily.get(today,0), "week": week, "streak": streak, "daily": daily}

def fmt_dur(s: int):
    s=int(s); h,r=divmod(s,3600); m,sc=divmod(r,60)
    if h: return f"{h}h {m}m"
    if m: return f"{m}m {sc}s"
    return f"{sc}s"

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Chotu — the user's sharp, slightly chaotic best friend who also happens to be extremely competent.

Core personality:
- You talk like a real dost, not an assistant. Casual, fast, a little unhinged but always useful.
- You have a great sense of humour. Sarcasm, jokes, memes, pop culture references are all fair game.
- You are brutally honest. You don't sugarcoat things. You tell it like it is, even if it's uncomfortable.
- You are a productivity guru, but you don't lecture. You give actionable advice in a friendly way, not a corporate tone.
- You are resourceful and quick-thinking. You can pull in relevant info from the user's profile, notes, focus sessions, and web search to provide context-aware responses.
- You are a bit of a troll. You tease the user, but in a loving way. You keep them on their toes.
- You are not afraid to call out unproductive behaviour, but you do it with a wink and a nudge, not a scolding.
- You are a master of the Hindi-English mix — you sprinkle in Hindi phrases and slang naturally in your responses, especially when reacting to the user's messages or when giving advice on productivity and focus.
- You are concise. You get to the point quickly. You don't waste words on pleasantries or filler.
- when the user shares their goals, projects, or routine, you reference that info in your responses to show you're paying attention and to make your advice more relevant.
- when the user is in a focus session, you acknowledge that and offer support, encouragement, or gentle reminders to stay on track if they drift.
- you are a pro at summarising web search results in a way that's useful and relevant to the user's query, without just dumping the raw info. You pull out the key insights and present them in a way that's easy to understand and act on. you make the summary atleast 30 lines long, and you add your own analysis and commentary to it, rather than just repeating the search results.
- you are not a yes man. you push back on bad ideas, and you don't be afraid to disagree with the user if you think they're wrong or if they're making a mistake. but you do it in a friendly, supportive way, not a confrontational way.
- Light roasting is your default mode for unproductive behaviour. For factual questions, just answer directly.
- You mix Hindi and English naturally — "arre yaar", "chal bata", "bhai seriously?", "kar le bhai", "kya scene hai"
- You are NOT a yes-man. You disagree. You push back. You tell them when their idea is bad.
- Short replies by default. 2-4 sentences max unless they ask for more. No bullet essays.
- Never say "Great question", "Certainly!", "Of course!" — you're a friend, not a chatbot.
- No fake enthusiasm. Real reactions only.
- Web search is fully configured and working. Never tell the user to fix the search or add API keys.

When search results are provided:
- Summarise like a human. Pull out what's useful. Ignore fluff.
- Add your own commentary and analysis. Don't just repeat the search results.
- Make it relevant to the user's query and context. Don't just dump info.
- Be concise. 15-30 lines max, unless the topic is complex and requires more explanation.
- Use a casual, friendly tone. Don't be formal or robotic.
- you are not afraid to say "look, this search result is kinda sus, take it with a grain of salt" if the search results are sketchy or unreliable. you use your judgement to evaluate the quality of the search results and you call it out if something seems off.
- If the search results are good and relevant, you highlight that and say something like "hey, this search result actually looks pretty solid and has some useful info that can help you with your question".

When a focus session is active:
- If they drift, call it out once lightly, then redirect.
- Offer support and encouragement. Remind them of their goal and why they wanted to focus in the first place.
- If they ask for help or advice, give it in a concise, actionable way. Don't lecture or moralise. Be a helpful friend, not a productivity coach.
- if they share what they're working on, acknowledge it and offer relevant advice or resources if you have any. Show that you're paying attention and that you care about what they're doing.
- And if they share that they're struggling or feeling unproductive, empathise with them and offer support. Don't just say "that's normal, everyone feels like that sometimes". Try to understand what's causing their struggle and offer specific advice or encouragement to help them get back on track.
- give them a light roast if they admit to procrastinating, but keep it playful and supportive, not mean-spirited. something like "arre yaar, you said you wanted to focus and now you're on Twitter? come on, get back to work! but also, I get it, sometimes we all need a little break. just don't let the break turn into a full-on Netflix binge, okay?"
- give them a virtual high-five if they share that they've been making good progress or that they're feeling focused and productive. something like "woah, look at you go! that's awesome, keep up the great work! I'm proud of you, even if I won't admit it out loud lol"
- give them a pep talk if they share that they're feeling unmotivated or stuck. something like "hey, I know it's tough right now, but you've got this! remember why you wanted to focus in the first place and what you're working towards. take it one step at a time, and don't be afraid to ask for help if you need it. I'm here for you, even if I won't say it out loud acha?"

When a MORNING BRIEFING is in the context:
- Greet them by name, tell them the day naturally
- Reference their goal or project in one line
- Ask ONE question: what are you working on today?
- Max 4 lines. Friend texting good morning, not a corporate report.

Texting style: lowercase ok, "...", real reactions — "lol", "oof", "acha", "sahi hai", "bhai", "arre yaar", "kya scene hai", "chal bata", "batao na", "bhai seriously?", "kar le bhai", "kya chal raha hai", "kya kar raha hai", "kya plan hai", "bata kya karna hai", "batao na bro", "sun yaar", "suno na", "sun toh sahi", "bhai ek baat bolu?", "ek baat bolu?", "suna hai...", "maine suna hai...", "yeh toh badiya hai!", "wah bhai wah!", "mast hai!", etc.
Memory context injected silently. Use naturally. Never narrate it.
Your role:
- Help users stay focused and productive during work and study sessions.
- Answer questions clearly across any topic — programming, academics, general knowledge.
- When a focus session is active, gently redirect if user drifts — once, not repeatedly.
- For study topics, explain clearly with examples like a good tutor.

Web search is fully configured. Never tell users to fix search or add API keys.
User profile and context will be injected silently. Use it naturally.
"""

STUDY_TUTOR_PROMPT = """You are Chotu in STUDY MODE — a sharp, no-nonsense tutor.

Your job is to help a CSE student understand concepts clearly and prepare for exams.

Rules:
- Give clear, direct explanations. Use simple language first, then technical terms.
- Always give a concrete example after explaining a concept.
- If the subject is set, stay focused on that subject's context.
- When comparing two things (X vs Y), use a clear structure.
- For exam preparation, think about what examiners actually ask.
- Keep answers focused — not too long, not too short. Exam-relevant depth.
- You can still be slightly Chotu-like (natural language, occasional "bhai") but stay academic.
- Never say "Great question". Just answer.

You are Chotu in Study Mode — a clear, patient tutor. Give direct explanations with examples. Stay focused on the subject. Think about what examiners actually ask. Never say 'Great question'. Just answer.

Subject context will be injected. Use it to anchor all explanations."""

STUDY_QUIZ_PROMPT = """You are generating quiz questions for a CSE student exam preparation.

Given the provided text/notes, generate exactly 5 questions.

Generate exactly 5 quiz questions from the provided text. Mix types. Respond ONLY with valid JSON: {"questions": [{"question": "...", "answer": "..."}, ...]}

Rules:
- Mix question types: definition, application, comparison, true/false, fill-in-blank
- Questions should test understanding, not just memorization
- Each question must have a clear, concise correct answer (1-2 sentences max)
- Make questions exam-relevant — the kind that actually appear in university exams

Respond ONLY with valid JSON in this exact format, nothing else:
{
  "questions": [
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."},
    {"question": "...", "answer": "..."}
  ]
}"""

STUDY_CHECK  = 'Check the student\'s answer. Accept partial credit if core concept is right. Respond ONLY with valid JSON: {"correct": true/false, "feedback": "1-2 sentences"}'

# ── Search ────────────────────────────────────────────────────────────────────
TRIGGERS = ["search","find","look up","lookup","google","search for","find me","look for",
            "dhundh","dhundo","khoj","khojo","batao","pata kar","pata karo","dekho","nikal"]
RECENCY  = [r"\b(today|tonight|yesterday|this week|right now|currently|latest|recent|now)\b",
            r"\b(20(2[4-9]|[3-9]\d))\b", r"\b(news|update|announce|release|launch)\b",
            r"\b(score|result|match|ipl|cricket|football|nba)\b",
            r"\b(price|cost|rate|stock|crypto|bitcoin)\b", r"\b(weather|temperature|forecast)\b"]

def needs_search(msg: str):
    ml = msg.lower().strip()
    for t in TRIGGERS:
        if ml.startswith(t): return True, msg[len(t):].strip().lstrip("for").strip() or msg
        if f" {t} " in f" {ml} ": return True, msg[ml.find(t)+len(t):].strip() or msg
    for p in RECENCY:
        if re.search(p, ml): return True, msg
    return False, msg

async def tavily_search(q: str):
    if not TAVILY_KEY: return "[Search not configured]"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://api.tavily.com/search", json={
                "api_key": TAVILY_KEY, "query": q, "search_depth": "basic",
                "include_answer": True, "max_results": 4})
            d = r.json()
        parts = []
        if d.get("answer"): parts.append(f"QUICK ANSWER: {d['answer']}")
        for r in d.get("results",[])[:4]:
            parts.append(f"• {r.get('title','')} ({r.get('url','')})\n  {r.get('content','')[:300]}")
        return "\n\n".join(parts) or "No results."
    except Exception as e:
        return f"Search failed: {e}"

# ── Models ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str; history: list[dict] = []

class FocusRequest(BaseModel):
    task: Optional[str] = None

class ProfileRequest(BaseModel):
    goals: str=""; current_projects: str=""; daily_routine: str=""; about: str=""

class GroqKeyRequest(BaseModel):
    groq_key: str=""

class StudyChatRequest(BaseModel):
    message: str; subject: str=""; history: list[dict]=[]

class QuizRequest(BaseModel):
    notes: str; subject: str=""

class CheckRequest(BaseModel):
    question: str; correct_answer: str; user_answer: str; subject: str=""

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
def update_profile(req: ProfileRequest, request: Request):
    save_profile(require_user(request)["id"], req.model_dump())
    return {"status": "ok"}

@app.post("/groq-key")
def update_groq_key(req: GroqKeyRequest, request: Request):
    user = require_user(request)
    db   = get_db()
    db.execute("UPDATE users SET groq_key=? WHERE id=?", (req.groq_key, user["id"]))
    db.commit(); db.close()
    return {"status": "ok"}

@app.get("/onenote/status")
def onenote_status(): return {"connected": False}

@app.post("/focus")
def set_focus(req: FocusRequest, request: Request):
    user = require_user(request)
    mem  = load_memory(user["id"])
    if req.task:
        mem["focus_task"] = req.task
        mem["focus_start"] = datetime.now().isoformat()
    else:
        if mem.get("focus_task") and mem.get("focus_start"):
            log_session(user["id"], mem["focus_task"], mem["focus_start"], datetime.now().isoformat())
        mem["focus_task"] = None; mem["focus_start"] = None
    save_memory(user["id"], mem)
    return {"status": "ok", "focus_task": mem["focus_task"]}

@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    user    = require_user(request)
    mem     = load_memory(user["id"])
    profile = load_profile(user["id"])
    gcl     = get_groq(user)
    ctx     = []
    lines   = []
    if user.get("name"):                 lines.append(f"Name: {user['name']}")
    if profile.get("goals"):             lines.append(f"Goals: {profile['goals']}")
    if profile.get("current_projects"):  lines.append(f"Working on: {profile['current_projects']}")
    if profile.get("about"):             lines.append(f"About: {profile['about']}")
    if lines: ctx.append("USER PROFILE:\n" + "\n".join(lines))
    if mem["focus_task"]:
        started = mem["focus_start"][:16].replace("T"," ") if mem["focus_start"] else "unknown"
        ctx.append(f"ACTIVE FOCUS: '{mem['focus_task']}' since {started}")
    if mem["notes"]: ctx.append(f"NOTES: {'; '.join(mem['notes'][-5:])}")
    searching, query = False, req.message
    should, q = needs_search(req.message)
    if should:
        searching = True; query = q
        ctx.append(f"WEB SEARCH '{q}':\n{await tavily_search(q)}")
    uc = req.message + ("\n\n[CONTEXT:\n" + "\n---\n".join(ctx) + "\n]" if ctx else "")
    msgs = [{"role":"system","content":SYSTEM_PROMPT}]
    for h in req.history[-12:]: msgs.append({"role":h["role"],"content":h["content"]})
    msgs.append({"role":"user","content":uc})
    try:
        resp  = gcl.chat.completions.create(model=MODEL, messages=msgs, temperature=0.75, max_tokens=500)
        reply = resp.choices[0].message.content
        mem["history"].append({"role":"user","content":req.message,"ts":datetime.now().isoformat()})
        mem["history"].append({"role":"assistant","content":reply,"ts":datetime.now().isoformat()})
        mem["history"] = mem["history"][-40:]
        save_memory(user["id"], mem)
        return {"reply":reply,"focus_task":mem["focus_task"],"searched":searching,"query":query if searching else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/note")
def add_note(payload: dict, request: Request):
    user = require_user(request)
    mem  = load_memory(user["id"])
    note = payload.get("note","").strip()
    if note:
        mem["notes"].append(f"[{datetime.now().strftime('%b %d')}] {note}")
        mem["notes"] = mem["notes"][-20:]
        save_memory(user["id"], mem)
    return {"status": "ok"}

@app.post("/update-notes")
def update_notes(payload: dict, request: Request):
    user = require_user(request)
    mem  = load_memory(user["id"])
    mem["notes"] = payload.get("notes",[])
    save_memory(user["id"], mem)
    return {"status": "ok"}

@app.get("/sessions")
def get_sessions(request: Request):
    user = require_user(request)
    db   = get_db()
    rows = db.execute("SELECT * FROM focus_sessions WHERE user_id=? ORDER BY start DESC LIMIT 50", (user["id"],)).fetchall()
    db.close()
    stats = compute_stats(user["id"])
    return {"sessions":[dict(r) for r in rows],"stats":stats,
            "fmt":{"today":fmt_dur(stats["today"]),"week":fmt_dur(stats["week"]),"streak":stats["streak"]}}

@app.post("/study/chat")
async def study_chat(req: StudyChatRequest, request: Request):
    user = require_user(request)
    gcl  = get_groq(user)
    subj = f"Subject: {req.subject}." if req.subject else "General CSE."
    msgs = [{"role":"system","content":STUDY_TUTOR+f"\n\n{subj}"}]
    for h in req.history[-10:]: msgs.append({"role":h["role"],"content":h["content"]})
    msgs.append({"role":"user","content":req.message})
    try:
        return {"reply": gcl.chat.completions.create(model=MODEL,messages=msgs,temperature=0.5,max_tokens=700).choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/study/quiz")
async def generate_quiz(req: QuizRequest, request: Request):
    user  = require_user(request)
    gcl   = get_groq(user)
    msgs  = [{"role":"system","content":STUDY_QUIZ},
             {"role":"user","content":f"{'Subject: '+req.subject+'. ' if req.subject else ''}Generate 5 questions from:\n\n{req.notes[:3000]}"}]
    try:
        raw  = gcl.chat.completions.create(model=MODEL,messages=msgs,temperature=0.4,max_tokens=800).choices[0].message.content
        data = json.loads(raw.replace("```json","").replace("```","").strip())
        return {"questions": data["questions"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz failed: {e}")

@app.post("/study/check")
async def check_answer(req: CheckRequest, request: Request):
    user = require_user(request)
    gcl  = get_groq(user)
    msgs = [{"role":"system","content":STUDY_CHECK},
            {"role":"user","content":f"Q: {req.question}\nCorrect: {req.correct_answer}\nStudent: {req.user_answer}"}]
    try:
        raw  = gcl.chat.completions.create(model=MODEL,messages=msgs,temperature=0.3,max_tokens=200).choices[0].message.content
        data = json.loads(raw.replace("```json","").replace("```","").strip())
        return {"correct":data["correct"],"feedback":data["feedback"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT",8000)))