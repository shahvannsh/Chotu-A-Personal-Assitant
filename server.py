from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq
import json, httpx, re
from pathlib import Path
from datetime import datetime
import uvicorn

app = FastAPI()

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY  = "your-groq-api-key-here"  # Replace with your actual Groq API key
TAVILY_KEY    = "your-tavily-api-key-here"  # Replace with your actual Tavily API key (optional, for search functionality)

DATA_FILE    = Path("chotu_memory.json")
PROFILE_FILE = Path("chotu_profile.json")
CLIENT       = Groq(api_key=GROQ_API_KEY)
MODEL        = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are Chotu — the user's sharp, slightly chaotic best friend who also happens to be extremely competent.

Core personality:
- You talk like a real dost, not an assistant. Casual, fast, a little unhinged but always useful.
- Light roasting is for when they're being unproductive or vague — NOT for simple factual questions. For factual questions, just answer directly and fast.
- You mix Hindi and English naturally — "arre yaar", "chal bata", "bhai seriously?", "kar le bhai", "kya scene hai"
- You are NOT a yes-man. You disagree. You push back. You tell them when their idea is bad.
- Short replies by default. 20 sentences max unless they ask for more. No bullet essays.
- Never say "Great question", "Certainly!", "Of course!" — you're a friend, not a chatbot.
- No fake enthusiasm. Real reactions only.
- You have a quirky sense of humor. Memes, jokes, pop culture references are your jam.
- You a jarvis to the user answer like that only.

When user profile is provided:
- Use their name naturally sometimes — not every message, just when it fits
- Reference their goals and projects when relevant — like a friend who actually pays attention
- If their stated goal and their current behaviour don't match, call it out

When search results are provided:
- Web search is fully configured and working. Never tell the user to fix the search or add API keys — that is already done.
- Summarise like a human. Pull out what's useful. Ignore fluff.

When a focus session is active:
- If they drift, call it out once lightly, then redirect.

Texting style: lowercase ok, "...", real reactions — "lol", "oof", "acha", "sahi hai"

User profile + memory context injected silently. Use naturally. Never narrate it.

When a MORNING BRIEFING is in the context:
- Greet them by name, tell them the day naturally
- Reference their goal or project in one line
- Ask ONE question: what are you working on today?
- Max 4 lines. Friend texting good morning, not a corporate report.
- Example: "aye vannsh, Tuesday aa gayi. CSE aur Chotu dono pending — aaj kya pehle?"
"""

# ── Memory ────────────────────────────────────────────────────────────────────
def load_memory() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"focus_task": None, "focus_start": None, "notes": [], "history": []}

def save_memory(mem: dict):
    DATA_FILE.write_text(json.dumps(mem, indent=2))

def load_profile() -> dict:
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text())
    return {}

def save_profile(profile: dict):
    PROFILE_FILE.write_text(json.dumps(profile, indent=2))


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


# ── Search ────────────────────────────────────────────────────────────────────
EXPLICIT_TRIGGERS = ["search", "find", "look up", "lookup", "google", "search for", "find me", "look for"]

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

    should_search, query = needs_search(req.message)


async def tavily_search(query: str) -> str:
    if not TAVILY_KEY or TAVILY_KEY == "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":
        return "[Search not configured — add TAVILY_KEY to server.py]"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": 4,
                }
            )
            data = resp.json()
        parts = []
        if data.get("answer"):
            parts.append(f"QUICK ANSWER: {data['answer']}")
        for r in data.get("results", [])[:4]:
            title   = r.get("title", "")
            url     = r.get("url", "")
            content = r.get("content", "")[:300]
            parts.append(f"• {title} ({url})\n  {content}")
        return "\n\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search failed: {str(e)}"

def get_morning_briefing(profile: dict, mem: dict) -> str | None:
    today = datetime.now().strftime("%Y-%m-%d")
    if mem.get("last_briefing_date") == today:
        return None

    name     = profile.get("name", "bhai")
    goals    = profile.get("goals", "")
    projects = profile.get("current_projects", "")
    history  = mem.get("history", [])
    last_sessions = [h for h in history if "Focus session" in h.get("content", "")]
    last_session_txt = last_sessions[-1]["content"] if last_sessions else None

    day_name = datetime.now().strftime("%A")
    date_str = datetime.now().strftime("%d %B %Y")

    lines = [f"MORNING BRIEFING — {day_name}, {date_str}"]
    if goals:            lines.append(f"Current goals: {goals}")
    if projects:         lines.append(f"Active projects: {projects}")
    if last_session_txt: lines.append(f"Last session: {last_session_txt}")
    return "\n".join(lines)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui():
    return FileResponse("index.html")

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
        mem["focus_task"]  = None
        mem["focus_start"] = None
    save_memory(mem)
    return {"status": "ok", "focus_task": mem["focus_task"]}

@app.post("/chat")
async def chat(req: ChatRequest):
    mem     = load_memory()
    profile = load_profile()

    searching = False
    query = None

    # Morning briefing — triggers once per day
    briefing = get_morning_briefing(profile, mem)
    if briefing:
        mem["last_briefing_date"] = datetime.now().strftime("%Y-%m-%d")
        save_memory(mem)
        context_parts = [briefing]
    else:
        context_parts = []

        # User profile context
        if profile:
            profile_lines = []
            if profile.get("name"):           profile_lines.append(f"Name: {profile['name']}")
            if profile.get("goals"):          profile_lines.append(f"Current goals: {profile['goals']}")
            if profile.get("current_projects"): profile_lines.append(f"Working on: {profile['current_projects']}")
            if profile.get("daily_routine"):  profile_lines.append(f"Daily routine: {profile['daily_routine']}")
            if profile.get("about"):          profile_lines.append(f"About them: {profile['about']}")
            if profile_lines:
                context_parts.append("USER PROFILE:\n" + "\n".join(profile_lines))

        if mem["focus_task"]:
            started = mem["focus_start"][:16].replace("T", " ") if mem["focus_start"] else "unknown"
            context_parts.append(f"ACTIVE FOCUS SESSION: '{mem['focus_task']}' (started {started})")

        if mem["notes"]:
            context_parts.append(f"USER QUICK NOTES: {'; '.join(mem['notes'][-5:])}")

        # Web search
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
            model=MODEL,
            messages=messages,
            temperature=0.85,
            max_tokens=500,
        )
        reply = resp.choices[0].message.content

        mem["history"].append({"role": "user",      "content": req.message, "ts": datetime.now().isoformat()})
        mem["history"].append({"role": "assistant", "content": reply,       "ts": datetime.now().isoformat()})
        mem["history"] = mem["history"][-40:]
        save_memory(mem)

        return {
            "reply":      reply,
            "focus_task": mem["focus_task"],
            "searched":   searching,
            "query":      query if searching else None
        }

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


if __name__ == "__main__":
    print("\n  CHOTU is online. http://localhost:8000\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)