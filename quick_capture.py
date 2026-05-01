"""
Chotu Quick Capture
-------------------
Press Alt+N anywhere on Windows → tiny popup appears →
type your note → press Enter to save, Escape to cancel.
Saves directly to chotu_memory.json (no server needed).

Install dependencies:
    pip install keyboard pillow

Run in background:
    pythonw quick_capture.py       (silent, no terminal window)
OR  python quick_capture.py        (with terminal for debugging)

Add to Windows startup:
    Copy a shortcut of this file into shell:startup
    Change target to: pythonw.exe "C:\\path\\to\\quick_capture.py"
"""

import keyboard
import json
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path
from datetime import datetime
import threading
import sys
import os

# ── Config ────────────────────────────────────────────────────────────────────
# Path to your Chotu memory file — update if your jarvis folder is elsewhere
MEMORY_FILE = Path(r"C:\Users\itsva\Desktop\my_jarvis\chotu_memory.json")
HOTKEY      = "alt+n"

# ── Colours ───────────────────────────────────────────────────────────────────
BG       = "#080c10"
SURFACE  = "#0d1117"
ACCENT   = "#00c8ff"
TEXT_HI  = "#e6edf3"
TEXT_DIM = "#4a5568"
BORDER   = "#1a2332"
GREEN    = "#22c55e"
WARN     = "#ff6b35"


# ── Memory helpers ────────────────────────────────────────────────────────────
def load_memory():
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"focus_task": None, "focus_start": None, "notes": [], "history": []}

def save_note(text: str) -> bool:
    try:
        mem = load_memory()
        date_str = datetime.now().strftime("%b %d")
        note = f"[{date_str}] {text.strip()}"
        if "notes" not in mem:
            mem["notes"] = []
        mem["notes"].append(note)
        mem["notes"] = mem["notes"][-20:]  # keep last 20
        MEMORY_FILE.write_text(json.dumps(mem, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False


# ── Popup window ──────────────────────────────────────────────────────────────
class QuickCapture:
    def __init__(self):
        self.root = None
        self.visible = False
        self._lock = threading.Lock()

    def show(self):
        with self._lock:
            if self.visible:
                # already open — bring to front
                if self.root:
                    self.root.lift()
                    self.root.focus_force()
                return
            self.visible = True

        # Must run on main thread — schedule via after
        threading.Thread(target=self._create_window, daemon=True).start()

    def _create_window(self):
        root = tk.Tk()
        self.root = root

        root.title("")
        root.overrideredirect(True)   # no title bar
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.97)
        root.configure(bg=SURFACE)
        root.resizable(False, False)

        # ── Size and position — centre of screen ──
        w, h = 480, 130
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x  = (sw - w) // 2
        y  = int(sh * 0.35)   # slightly above centre
        root.geometry(f"{w}x{h}+{x}+{y}")

        # ── Border frame ──
        frame = tk.Frame(root, bg=ACCENT, padx=1, pady=1)
        frame.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(frame, bg=SURFACE, padx=16, pady=14)
        inner.pack(fill=tk.BOTH, expand=True)

        # ── Header ──
        header = tk.Frame(inner, bg=SURFACE)
        header.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            header, text="⚡ CHOTU", bg=SURFACE, fg=ACCENT,
            font=("Share Tech Mono", 11, "bold")
        ).pack(side=tk.LEFT)

        tk.Label(
            header, text="Quick Note  |  Enter to save  ·  Esc to cancel",
            bg=SURFACE, fg=TEXT_DIM,
            font=("Share Tech Mono", 9)
        ).pack(side=tk.LEFT, padx=(10, 0))

        # ── Input ──
        entry_var = tk.StringVar()
        entry = tk.Entry(
            inner,
            textvariable=entry_var,
            bg="#111d2e", fg=TEXT_HI,
            insertbackground=ACCENT,
            relief=tk.FLAT,
            font=("Rajdhani", 14, "bold"),
            bd=0,
        )
        entry.pack(fill=tk.X, ipady=8, pady=(0, 6))

        # Bottom hint
        hint_var = tk.StringVar(value=f"saves to chotu_memory.json")
        hint = tk.Label(inner, textvariable=hint_var, bg=SURFACE, fg=TEXT_DIM,
                        font=("Share Tech Mono", 9), anchor="w")
        hint.pack(fill=tk.X)

        # ── Focus ──
        entry.focus_set()
        entry.focus_force()

        # ── Bindings ──
        def on_enter(e=None):
            text = entry_var.get().strip()
            if not text:
                self._close()
                return
            ok = save_note(text)
            if ok:
                hint_var.set(f"✓ saved: \"{text[:40]}{'...' if len(text)>40 else ''}\"")
                hint.config(fg=GREEN)
                root.after(800, self._close)
            else:
                hint_var.set("✗ save failed — is chotu_memory.json path correct?")
                hint.config(fg=WARN)
                root.after(2000, self._close)

        def on_escape(e=None):
            self._close()

        entry.bind("<Return>", on_enter)
        entry.bind("<Escape>", on_escape)
        root.bind("<Escape>", on_escape)

        # Close if clicks outside
        def on_focus_out(e=None):
            if root.focus_displayof() is None:
                self._close()
        root.bind("<FocusOut>", on_focus_out)

        # Drag window
        def start_drag(e):
            root._drag_x = e.x_root - root.winfo_x()
            root._drag_y = e.y_root - root.winfo_y()
        def do_drag(e):
            root.geometry(f"+{e.x_root - root._drag_x}+{e.y_root - root._drag_y}")
        inner.bind("<Button-1>", start_drag)
        inner.bind("<B1-Motion>", do_drag)
        header.bind("<Button-1>", start_drag)
        header.bind("<B1-Motion>", do_drag)

        root.mainloop()
        with self._lock:
            self.visible = False
            self.root = None

    def _close(self):
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass


# ── Main ──────────────────────────────────────────────────────────────────────
capture = QuickCapture()

def trigger_capture():
    capture.show()

print(f"Chotu Quick Capture running.")
print(f"Press Alt+N anywhere to capture a note.")
print(f"Saving to: {MEMORY_FILE}")
print(f"Press Ctrl+C to stop.\n")

keyboard.add_hotkey(HOTKEY, trigger_capture, suppress=False)

# Keep alive
try:
    keyboard.wait()
except KeyboardInterrupt:
    print("Stopped.")
    sys.exit(0)
