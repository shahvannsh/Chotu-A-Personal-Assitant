# Chotu — Personal AI Assistant

> A brutally honest, Hinglish-speaking productivity AI that runs locally on your laptop.  
> Built with FastAPI + Groq + browser-native voice. No cloud. No subscription. Just open and work.

---

## What is this

Chotu is a personal AI assistant built for daily focus and productivity. It's not a general-purpose chatbot — it's opinionated, knows who you are, holds you accountable, and talks like a real dost.

Built by a student, for students. Runs entirely on your machine.

**Core features:**
- 💬 Chat with personality — Hinglish, direct, no corporate fluff
- 🎤 Voice input — continuous, no mid-sentence cutoff
- 🔊 Text-to-speech — Chotu speaks back
- 🔍 Smart web search — auto-detects when current info is needed
- ⏱️ Focus sessions — lock in a task, live timer, Chotu holds you to it
- 🧠 Persistent memory — knows your name, goals, projects across restarts
- 📝 Quick notes — sidebar notes saved to disk
- 🚀 Auto-launches on Windows startup

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.10+ / FastAPI |
| AI | Groq API (llama-3.3-70b-versatile) |
| Voice Input | Web Speech API (browser-native, free) |
| Voice Output | Web Speech Synthesis API (browser-native, free) |
| Web Search | Tavily API (free tier — 1000 searches/month) |
| Frontend | Vanilla HTML/CSS/JS (single file, no framework) |
| Storage | JSON files (local disk) |

---

## Requirements

- Python 3.10 or higher (3.13 works with pinned dependencies)
- Google Chrome (voice features require Chrome)
- A [Groq API key](https://console.groq.com) — free
- A [Tavily API key](https://app.tavily.com) — free tier available

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/chotu.git
cd chotu
```

### 2. Install dependencies

```bash
pip install fastapi uvicorn groq httpx==0.27.0 python-dotenv
```

> **Python 3.13 users** — pin these exact versions to avoid httpx/groq conflicts:
> ```bash
> pip uninstall groq httpx anyio -y
> pip install anyio==4.4.0 httpx==0.27.0 groq==0.11.0
> pip install fastapi uvicorn
> ```

### 3. Add your API keys

Open `server.py` and replace lines 14–15:

```python
GROQ_API_KEY  = "your-groq-key-here"
TAVILY_KEY    = "your-tavily-key-here"
```

Get your keys:
- Groq → [console.groq.com](https://console.groq.com) → API Keys
- Tavily → [app.tavily.com](https://app.tavily.com) → API Keys

### 4. Run

```bash
python server.py
```

Open `http://localhost:8000` in **Chrome**.

---

## Windows — auto-launch on startup

1. Create `launch_chotu.bat` in the project folder:
```bat
@echo off
cd /d "C:\path\to\chotu"
start http://localhost:8000
python server.py
```

2. Press `Win + R`, type `shell:startup`, hit Enter

3. Copy a shortcut of `launch_chotu.bat` into that folder

Chotu will now launch automatically every time Windows starts.

---

## First time setup

1. Open Chotu in Chrome
2. Click **👤 PROFILE** in the top bar
3. Fill in your name, goals, current projects, daily routine
4. Click **SAVE PROFILE**

Chotu now knows who you are across every session.

---

## Usage

### Chat
Type normally or use the 🎤 mic button. Press **Space** (when not typing) to toggle mic hands-free.

### Voice
Click 🎤 to start — speak as long as you want — click ⏹ to stop and send.  
Uses `en-IN` language model — handles Hinglish well.

### Focus sessions
Click **START SESSION** → type what you're working on → **LOCK IN**.  
Timer starts. Chotu knows your task and will call you out if you drift.

### Web search
Chotu auto-searches when it detects current info is needed (news, scores, weather, prices).  
You can also trigger manually: `search pune weather`, `find best laptop 2025`, `look up RCB score`

### TTS
Click **🔊 TTS: OFF** in the top bar to toggle voice output on.  
Every message also has a `🔊 speak` button for on-demand playback.

---

## Project structure

```
chotu/
├── server.py              # FastAPI backend — all routes and logic
├── index.html             # Frontend — entire UI in one file
├── chotu_memory.json      # Auto-created — focus sessions, notes, history
├── chotu_profile.json     # Auto-created — your persistent profile
└── launch_chotu.bat       # Windows startup launcher
```

---

## API keys safety

**Never commit your API keys to GitHub.**

Before pushing, replace your keys in `server.py` with placeholders, or use a `.env` file:

```python
# server.py
from dotenv import load_dotenv
import os
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY   = os.getenv("TAVILY_KEY")
```

```env
# .env  ← add this to .gitignore
GROQ_API_KEY=your-key-here
TAVILY_KEY=your-key-here
```

Add to `.gitignore`:
```
.env
chotu_memory.json
chotu_profile.json
```

---

## Roadmap

- [ ] Morning briefing — daily goal check-in on first open
- [ ] Session history log — total focus time per day
- [ ] Spotify integration — auto-start focus playlist on session start
- [ ] Mobile PWA — install on Android homescreen

---

## Built with

- [FastAPI](https://fastapi.tiangolo.com)
- [Groq](https://groq.com) — llama-3.3-70b
- [Tavily](https://tavily.com) — web search API
- Web Speech API — no external dependency

---

## License

MIT — do whatever you want with it.

---

*Built by Vannsh — a student project that actually gets used.*
