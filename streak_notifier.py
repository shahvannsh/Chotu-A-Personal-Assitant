"""
Chotu Daily Streak Notifier
----------------------------
Runs silently in the background.
Checks at 10:00 AM and 11:00 AM if you've started a focus session today.
If not → fires a Windows toast notification.
Once you start a session, no more notifications for that day.

Install:
    pip install plyer

Run silently (no terminal window):
    pythonw streak_notifier.py

Add to Windows startup:
    Win+R → shell:startup → create shortcut
    Target: pythonw.exe "C:\\Users\\itsva\\Desktop\\my_jarvis\\streak_notifier.py"
"""

import time
import json
import sys
from pathlib import Path
from datetime import datetime, date

# ── Config ────────────────────────────────────────────────────────────────────
SESSIONS_FILE = Path(r"C:\Users\itsva\Desktop\my_jarvis\chotu_sessions.json")
MEMORY_FILE   = Path(r"C:\Users\itsva\Desktop\my_jarvis\chotu_memory.json")

# Times to check (24h format)
NOTIFY_TIMES = [
    (10, 0),   # 10:00 AM
    (11, 0),   # 11:00 AM
]

APP_NAME = "Chotu"

# ── Helpers ───────────────────────────────────────────────────────────────────
def load_sessions():
    try:
        if SESSIONS_FILE.exists():
            return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def load_memory():
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def has_session_today() -> bool:
    today = date.today().isoformat()

    # Check completed sessions
    sessions = load_sessions()
    for s in sessions:
        if s.get("date") == today:
            return True

    # Also check if a session is currently active
    mem = load_memory()
    if mem.get("focus_task") and mem.get("focus_start"):
        try:
            start = datetime.fromisoformat(mem["focus_start"])
            if start.date().isoformat() == today:
                return True
        except Exception:
            pass

    return False

def get_streak() -> int:
    sessions = load_sessions()
    if not sessions:
        return 0
    daily = {}
    for s in sessions:
        d = s.get("date", "")
        daily[d] = daily.get(d, 0) + 1

    from datetime import timedelta
    streak = 0
    check = date.today()
    while True:
        if check.isoformat() in daily:
            streak += 1
            check = check - timedelta(days=1)
        else:
            break
    return streak

def send_notification(title: str, message: str):
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name=APP_NAME,
            timeout=10,   # seconds before auto-dismiss
        )
    except Exception as e:
        # Fallback: try win10toast if plyer fails
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=8, threaded=True)
        except Exception:
            print(f"Notification failed: {e}")

def build_message(attempt: int) -> tuple[str, str]:
    streak = get_streak()
    streak_text = f"🔥 {streak} day streak" if streak > 0 else "Start your streak today"

    if attempt == 1:
        title = "Chotu — Kahan hai bhai? 👀"
        msg   = f"10 AM ho gayi. Aaj koi session nahi. {streak_text} — lag ja kaam pe."
    else:
        title = "Chotu — Last chance ⚠️"
        msg   = f"11 AM. Abhi bhi koi session nahi. {streak_text} at risk. Open Chotu now."

    return title, msg

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    print(f"Chotu Streak Notifier running.")
    print(f"Will notify at 10:00 AM and 11:00 AM if no session started.")
    print(f"Sessions file: {SESSIONS_FILE}")
    print(f"Press Ctrl+C to stop.\n")

    notified = set()  # track which times have fired today
    last_date = date.today().isoformat()

    while True:
        now       = datetime.now()
        today_str = date.today().isoformat()

        # Reset at midnight for new day
        if today_str != last_date:
            notified.clear()
            last_date = today_str

        # Check each notification time
        for i, (h, m) in enumerate(NOTIFY_TIMES):
            key = f"{today_str}-{h}-{m}"
            if key in notified:
                continue

            # Is it time? (within the current minute)
            if now.hour == h and now.minute == m:
                if not has_session_today():
                    title, msg = build_message(i + 1)
                    send_notification(title, msg)
                    print(f"[{now.strftime('%H:%M')}] Notification sent: {title}")
                else:
                    print(f"[{now.strftime('%H:%M')}] Session already started — skipping notification")
                notified.add(key)  # mark as done regardless

        # Sleep 30 seconds between checks (catches the right minute reliably)
        time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped.")
        sys.exit(0)
