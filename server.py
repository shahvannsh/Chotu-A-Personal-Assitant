from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import json, httpx, os, re
from pathlib import Path
from datetime import datetime, date
import uvicorn

app = FastAPI()
load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_KEY   = os.getenv("TAVILY_KEY", "")

DATA_FILE     = Path("chotu_memory.json")
PROFILE_FILE  = Path("chotu_profile.json")
SESSIONS_FILE = Path("chotu_sessions.json")
CLIENT        = Groq(api_key=GROQ_API_KEY)
MODEL         = "llama-3.3-70b-versatile"

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
Memory context injected silently. Use naturally. Never narrate it."""

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

Subject context will be injected. Use it to anchor all explanations."""

STUDY_QUIZ_PROMPT = """You are generating quiz questions for a CSE student exam preparation.

Given the provided text/notes, generate exactly 5 questions.

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

STUDY_CHECK_PROMPT = """You are checking a student's quiz answer.

Given the question, correct answer, and student's answer:
1. Determine if the student's answer is correct (accept partial credit if the core concept is right)
2. Give brief feedback — 1-2 sentences max
3. If wrong, explain why briefly

Respond ONLY with valid JSON:
{"correct": true/false, "feedback": "..."}"""


# ── Memory ────────────────────────────────────────────────────────────────────
def load_memory() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"focus_task": None, "focus_start": None, "notes": [], "history": [], "last_briefing_date": None}

def save_memory(mem: dict):
    DATA_FILE.write_text(json.dumps(mem, indent=2))

def load_profile() -> dict:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text())
    return {}

def save_profile(profile: dict):
    PROFILE_FILE.write_text(json.dumps(profile, indent=2))

def load_sessions() -> list:
    if SESSIONS_FILE.exists():
        return json.loads(SESSIONS_FILE.read_text())
    return []

def save_sessions(sessions: list):
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2))


# ── Models ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    history: list[dict]

class FocusRequest(BaseModel):
    task: str | None

class ProfileRequest(BaseModel):
    name: str = ""
    goals: str = ""
    current_projects: str = ""
    daily_routine: str = ""
    about: str = ""

class StudyChatRequest(BaseModel):
    message: str
    subject: str = ""
    history: list[dict] = []

class QuizRequest(BaseModel):
    notes: str
    subject: str = ""

class CheckRequest(BaseModel):
    question: str
    correct_answer: str
    user_answer: str
    subject: str = ""



# ── Search ────────────────────────────────────────────────────────────────────
EXPLICIT_TRIGGERS = [
    # English
    "search", "find", "look up", "lookup", "google", "search for", "find me", "look for", "can you find", "can you search", "can you look up", "can you google", "what is", "what's", "who is", "who's", "tell me about", "give me info on", "show me info on", "do you know", "find out", "check", "check on", "look into", "investigate", "research", "get info on", "fetch info on","see if you can find", "see if you can search", "see if you can look up", "see if you can google",
    # Hindi/Hinglish
    "dhundh", "dhundo", "khoj", "khojo", "bata", "batao", "dekh", "dekho", "batao na", "suna hai", "maine suna hai", "pta kar", "pata kar", "pata karo", "nikal", "nikalo","kya chal raha hai", "kya kar raha hai", "kya plan hai", "bata kya karna hai", "batao na bro", "sun yaar", "suno na", "sun toh sahi", "bhai ek baat bolu?", "ek baat bolu?", "suna hai...", "maine suna hai..."
]

RECENCY_PATTERNS = [
    r"\b(today|tonight|yesterday|this week|this month|this year|right now|currently|latest|recent|now)\b",
    r"\b(20(2[4-9]|[3-9]\d))\b",
    r"\b(news|update|announce|release|launch|drop)\b",
    r"\b(score|result|winner|standing|ranking|match|game|ipl|cricket|football|nba|fifa)\b",
    r"\b(price|cost|rate|stock|crypto|bitcoin|market)\b",
    r"\b(weather|temperature|forecast)\b",
    r"\b(who is|who's|who are).{0,30}(now|current|president|pm|ceo|head|chief|minister)\b",
    r"\b(what is|what's).{0,30}(happening|going on|situation|status)\b",
    r"\b(best|top|recommended).{0,20}(2024|2025|2026|right now|currently)\b",
]

def needs_search(message: str) -> tuple[bool, str]:
    msg_lower = message.lower().strip()
    for trigger in EXPLICIT_TRIGGERS:
        if msg_lower.startswith(trigger):
            query = message[len(trigger):].strip().lstrip("for").strip()
            return True, query or message
        if f" {trigger} " in f" {msg_lower} ":
            idx = msg_lower.find(trigger)
            query = message[idx + len(trigger):].strip()
            return True, query or message
    for pattern in RECENCY_PATTERNS:
        if re.search(pattern, msg_lower):
            return True, message
    return False, message

async def tavily_search(query: str) -> str:
    if not TAVILY_KEY:
        return "[Search not configured — add TAVILY_KEY to server.py]"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_KEY, "query": query, "search_depth": "basic",
                    "include_answer": True, "include_raw_content": False, "max_results": 4}
            )
            data = resp.json()
        parts = []
        if data.get("answer"):
            parts.append(f"QUICK ANSWER: {data['answer']}")
        for r in data.get("results", [])[:4]:
            parts.append(f"• {r.get('title','')} ({r.get('url','')})\n  {r.get('content','')[:300]}")
        return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search failed: {str(e)}"


# ── Morning briefing ──────────────────────────────────────────────────────────
def get_morning_briefing(profile: dict, mem: dict) -> str | None:
    today = datetime.now().strftime("%Y-%m-%d")
    if mem.get("last_briefing_date") == today:
        return None
    day_name = datetime.now().strftime("%A")
    date_str  = datetime.now().strftime("%d %B %Y")
    lines = [f"MORNING BRIEFING — {day_name}, {date_str}"]
    if profile.get("goals"):            lines.append(f"Current goals: {profile['goals']}")
    if profile.get("current_projects"): lines.append(f"Working on: {profile['current_projects']}")
    return "\n".join(lines)


# ── Session helpers ───────────────────────────────────────────────────────────
def log_session(task: str, start_iso: str, end_iso: str):
    """Save a completed focus session to the sessions log."""
    sessions = load_sessions()
    start_dt  = datetime.fromisoformat(start_iso)
    end_dt    = datetime.fromisoformat(end_iso)
    duration  = int((end_dt - start_dt).total_seconds())
    sessions.append({
        "task":       task,
        "date":       start_dt.strftime("%Y-%m-%d"),
        "start":      start_iso,
        "end":        end_iso,
        "duration":   duration,   # seconds
    })
    save_sessions(sessions)


def compute_stats(sessions: list) -> dict:
    """Compute daily totals, weekly total, and streak."""
    if not sessions:
        return {"today": 0, "week": 0, "streak": 0, "daily": {}}

    today_str = date.today().isoformat()

    # daily totals
    daily: dict[str, int] = {}
    for s in sessions:
        d = s.get("date", "")
        daily[d] = daily.get(d, 0) + s.get("duration", 0)

    # today
    today_secs = daily.get(today_str, 0)

    # this week (last 7 days)
    from datetime import timedelta
    week_secs = sum(
        daily.get((date.today() - timedelta(days=i)).isoformat(), 0)
        for i in range(7)
    )

    # streak — consecutive days ending today with at least 1 session
    streak = 0
    check = date.today()
    while True:
        if check.isoformat() in daily:
            streak += 1
            check = check - timedelta(days=1)
        else:
            break

    return {"today": today_secs, "week": week_secs, "streak": streak, "daily": daily}


def fmt_duration(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui():
    return FileResponse("index.html")

@app.get("/history")
def serve_history():
    return FileResponse("history.html")

@app.get("/memory")
def get_memory():
    return load_memory()

@app.get("/profile")
def get_profile():
    return load_profile()

@app.post("/profile")
def update_profile(req: ProfileRequest):
    profile = req.model_dump()
    profile["updated_at"] = datetime.now().isoformat()
    save_profile(profile)
    return {"status": "ok"}

@app.get("/onenote/status")
def onenote_status():
    return {"connected": False}

@app.post("/focus")
def set_focus(req: FocusRequest):
    mem = load_memory()
    if req.task:
        mem["focus_task"]  = req.task
        mem["focus_start"] = datetime.now().isoformat()
    else:
        # Session ending — log it
        if mem.get("focus_task") and mem.get("focus_start"):
            log_session(mem["focus_task"], mem["focus_start"], datetime.now().isoformat())
        mem["focus_task"]  = None
        mem["focus_start"] = None
    save_memory(mem)
    return {"status": "ok", "focus_task": mem["focus_task"]}

@app.get("/sessions")
def get_sessions():
    sessions  = load_sessions()
    stats     = compute_stats(sessions)
    # Return last 50 sessions newest first
    recent = list(reversed(sessions[-50:]))
    return {
        "sessions": recent,
        "stats":    stats,
        "fmt": {
            "today": fmt_duration(stats["today"]),
            "week":  fmt_duration(stats["week"]),
            "streak": stats["streak"],
        }
    }

@app.post("/chat")
async def chat(req: ChatRequest):
    mem     = load_memory()
    profile = load_profile()
    context_parts = []

    # Morning briefing
    briefing = get_morning_briefing(profile, mem)
    if briefing:
        mem["last_briefing_date"] = datetime.now().strftime("%Y-%m-%d")
        save_memory(mem)
        context_parts.append(briefing)

    if profile:
        lines = []
        if profile.get("name"):             lines.append(f"Name: {profile['name']}")
        if profile.get("goals"):            lines.append(f"Goals: {profile['goals']}")
        if profile.get("current_projects"): lines.append(f"Working on: {profile['current_projects']}")
        if profile.get("daily_routine"):    lines.append(f"Routine: {profile['daily_routine']}")
        if profile.get("about"):            lines.append(f"About: {profile['about']}")
        if lines: context_parts.append("USER PROFILE:\n" + "\n".join(lines))

    if mem["focus_task"]:
        started = mem["focus_start"][:16].replace("T", " ") if mem["focus_start"] else "unknown"
        context_parts.append(f"ACTIVE FOCUS SESSION: '{mem['focus_task']}' (started {started})")

    if mem["notes"]:
        context_parts.append(f"USER QUICK NOTES: {'; '.join(mem['notes'][-5:])}")

    searching = False
    should_search, query = needs_search(req.message)
    if should_search:
        searching = True
        search_results = await tavily_search(query)
        context_parts.append(f"WEB SEARCH RESULTS for '{query}':\n{search_results}")

    user_content = req.message
    if context_parts:
        user_content += f"\n\n[CONTEXT:\n" + "\n---\n".join(context_parts) + "\n]"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in req.history[-12:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_content})

    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.85, max_tokens=500
        )
        reply = resp.choices[0].message.content
        mem["history"].append({"role": "user",      "content": req.message, "ts": datetime.now().isoformat()})
        mem["history"].append({"role": "assistant", "content": reply,       "ts": datetime.now().isoformat()})
        mem["history"] = mem["history"][-40:]
        save_memory(mem)
        return {"reply": reply, "focus_task": mem["focus_task"], "searched": searching, "query": query if searching else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/note")
def add_note(payload: dict):
    mem = load_memory()
    note = payload.get("note", "").strip()
    if note:
        mem["notes"].append(f"[{datetime.now().strftime('%b %d')}] {note}")
        mem["notes"] = mem["notes"][-20:]
        save_memory(mem)
    return {"status": "ok"}

@app.post("/update-notes")
def update_notes(payload: dict):
    mem = load_memory()
    mem["notes"] = payload.get("notes", [])
    save_memory(mem)
    return {"status": "ok"}

@app.post("/update-profile")
def update_profile(payload: dict):
    profile = load_profile()
    profile.update(payload)
    save_profile(profile)
    return {"status": "ok"}

@app.post("/update-memory")
def update_memory(payload: dict):
    mem = load_memory()
    mem.update(payload)
    save_memory(mem)
    return {"status": "ok"}

@app.post("/study/chat")
async def study_chat(req: StudyChatRequest):
    subject_ctx = f"Current subject: {req.subject}" if req.subject else "No subject set — answer generally for CSE."

    messages = [{"role": "system", "content": STUDY_TUTOR_PROMPT + f"\n\n{subject_ctx}"}]
    for h in req.history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message})

    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.5, max_tokens=700
        )
        return {"reply": resp.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/study/quiz")
async def generate_quiz(req: QuizRequest):
    subject_hint = f"Subject: {req.subject}. " if req.subject else ""
    prompt = f"{subject_hint}Generate 5 quiz questions from this text:\n\n{req.notes[:3000]}"

    messages = [
        {"role": "system", "content": STUDY_QUIZ_PROMPT},
        {"role": "user",   "content": prompt}
    ]
    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.4, max_tokens=800
        )
        raw = resp.choices[0].message.content
        # strip markdown fences if present
        clean = raw.replace("```json","").replace("```","").strip()
        data  = json.loads(clean)
        return {"questions": data["questions"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")


@app.post("/study/check")
async def check_answer(req: CheckRequest):
    prompt = f"Question: {req.question}\nCorrect answer: {req.correct_answer}\nStudent's answer: {req.user_answer}"

    messages = [
        {"role": "system", "content": STUDY_CHECK_PROMPT},
        {"role": "user",   "content": prompt}
    ]
    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.3, max_tokens=200
        )
        raw   = resp.choices[0].message.content
        clean = raw.replace("```json","").replace("```","").strip()
        data  = json.loads(clean)
        return {"correct": data["correct"], "feedback": data["feedback"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/study")
def serve_study():
    return FileResponse("study.html")


if __name__ == "__main__":
    print("\n  CHOTU is online.")
    print("  Chat  → http://localhost:8000")
    print("  Stats → http://localhost:8000/history\n")
    print("  Study → http://localhost:8000/study\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)