"""
GestureMouse 2.0 — Backend (Flask + Win32 cursor control)
=========================================================
All hand detection runs in the browser via MediaPipe.js.
Python only:
  - Receives landmark data from browser via POST /api/landmarks
  - Moves / clicks the Windows cursor via ctypes Win32 API
  - Serves the HTML pages
  - Exposes status API

Usage:
  py -3.11 gesture_mouse.py
  Then open http://localhost:5000 in Chrome / Edge
"""

import time
import json
import math
import threading
import os
from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Win32 cursor control ───────────────────────────────────────────────────────
try:
    import ctypes
    _u32 = ctypes.windll.user32

    def win_move(x: int, y: int):
        _u32.SetCursorPos(int(x), int(y))

    def win_click(btn: str = "left"):
        if btn == "left":
            _u32.mouse_event(0x0002, 0, 0, 0, 0)
            _u32.mouse_event(0x0004, 0, 0, 0, 0)
        elif btn == "right":
            _u32.mouse_event(0x0008, 0, 0, 0, 0)
            _u32.mouse_event(0x0010, 0, 0, 0, 0)

    def win_scroll(delta: int):
        _u32.mouse_event(0x0800, 0, 0, int(delta) * 120, 0)

    def screen_size():
        return _u32.GetSystemMetrics(0), _u32.GetSystemMetrics(1)

    WIN32 = True

except Exception:
    WIN32 = False
    def win_move(x, y): pass
    def win_click(btn="left"): pass
    def win_scroll(d): pass
    def screen_size(): return 1920, 1080

SCREEN_W, SCREEN_H = screen_size()

# ── EMA smoother ───────────────────────────────────────────────────────────────
class EMA:
    def __init__(self, alpha=0.50):
        self.alpha = alpha
        self.x = self.y = None

    def update(self, x, y):
        if self.x is None:
            self.x, self.y = float(x), float(y)
        else:
            a = self.alpha
            self.x = a * x + (1 - a) * self.x
            self.y = a * y + (1 - a) * self.y
        return int(self.x), int(self.y)

    def reset(self):
        self.x = self.y = None

# ── Shared state ───────────────────────────────────────────────────────────────
class State:
    def __init__(self):
        self._lock        = threading.Lock()
        self.running      = False
        self.gesture      = "none"
        self.hand_visible = False
        self.cursor_x     = 0
        self.cursor_y     = 0
        self.fps          = 0.0

    def get(self, k):
        with self._lock:
            return getattr(self, k)

    def set(self, **kw):
        with self._lock:
            for k, v in kw.items():
                setattr(self, k, v)

state = State()

# ── Landmark processor ─────────────────────────────────────────────────────────
_ema           = EMA(alpha=0.50)
_last_lclick   = 0.0
_last_rclick   = 0.0
_prev_scroll_y = None
CLICK_CD       = 0.45   # seconds between clicks

def _pinch(lm, a, b):
    return math.hypot(lm[a]["x"] - lm[b]["x"], lm[a]["y"] - lm[b]["y"])

def _up(lm, tip, pip):
    """True when finger tip is above its PIP joint (extended)."""
    return lm[tip]["y"] < lm[pip]["y"]

def classify(lm):
    """
    Gestures (landmarks are un-mirrored normalized coords):
      left_click   pinch thumb(4) + index(8)
      right_click  pinch thumb(4) + middle(12), index still up
      scroll       index + middle up, ring + pinky down
      open_palm    all four fingers up
      point        index only up
      fist         all four down
      idle         anything else
    """
    i_up = _up(lm, 8,  6)
    m_up = _up(lm, 12, 10)
    r_up = _up(lm, 16, 14)
    p_up = _up(lm, 20, 18)

    pl = _pinch(lm, 4, 8)   # thumb ↔ index
    pr = _pinch(lm, 4, 12)  # thumb ↔ middle
    TH = 0.055

    if pl < TH:                                    return "left_click"
    if pr < TH and i_up:                           return "right_click"
    if i_up and m_up and not r_up and not p_up:   return "scroll"
    if i_up and m_up and r_up and p_up:           return "open_palm"
    if i_up and not m_up and not r_up and not p_up: return "point"
    if not i_up and not m_up and not r_up and not p_up: return "fist"
    return "idle"

def process(lm: list):
    global _last_lclick, _last_rclick, _prev_scroll_y

    if not lm or len(lm) < 21:
        state.set(hand_visible=False, gesture="none")
        _ema.reset()
        return

    state.set(hand_visible=True)
    g = classify(lm)
    state.set(gesture=g)

    # Index fingertip → screen, clamped to centre 80% of frame
    raw_x = lm[8]["x"]
    raw_y = lm[8]["y"]
    sx = int((raw_x - 0.10) / 0.80 * SCREEN_W)
    sy = int((raw_y - 0.10) / 0.80 * SCREEN_H)
    sx = max(0, min(SCREEN_W - 1, sx))
    sy = max(0, min(SCREEN_H - 1, sy))
    sx, sy = _ema.update(sx, sy)
    state.set(cursor_x=sx, cursor_y=sy)

    now = time.monotonic()

    if g in ("open_palm", "point", "idle"):
        win_move(sx, sy)
        _prev_scroll_y = None

    elif g == "left_click":
        win_move(sx, sy)
        if now - _last_lclick > CLICK_CD:
            win_click("left")
            _last_lclick = now
        _prev_scroll_y = None

    elif g == "right_click":
        win_move(sx, sy)
        if now - _last_rclick > CLICK_CD:
            win_click("right")
            _last_rclick = now
        _prev_scroll_y = None

    elif g == "scroll":
        win_move(sx, sy)
        if _prev_scroll_y is not None:
            delta = _prev_scroll_y - raw_y
            if abs(delta) > 0.008:
                win_scroll(int(delta * 30))
        _prev_scroll_y = raw_y

    else:
        _prev_scroll_y = None

# ── Flask ──────────────────────────────────────────────────────────────────────
app  = Flask(__name__)
CORS(app)
BASE = os.path.dirname(os.path.abspath(__file__))

def _serve(filename):
    path = os.path.join(BASE, filename)
    if not os.path.exists(path):
        return f"<h2>{filename} not found</h2><p>Place it next to gesture_mouse.py</p>", 404
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/")
@app.route("/launcher")
def page_launcher():
    return _serve("launcher.html")

@app.route("/draw")
def page_draw():
    return _serve("drawing_board.html")

@app.route("/api/status")
def api_status():
    return jsonify({
        "running":      state.get("running"),
        "gesture":      state.get("gesture"),
        "hand_visible": state.get("hand_visible"),
        "fps":          state.get("fps"),
        "cursor":       {"x": state.get("cursor_x"), "y": state.get("cursor_y")},
        "screen":       {"w": SCREEN_W, "h": SCREEN_H},
        "win32":        WIN32,
    })

@app.route("/api/start", methods=["POST"])
def api_start():
    state.set(running=True)
    _ema.reset()
    return jsonify({"ok": True})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    state.set(running=False, hand_visible=False, gesture="none")
    return jsonify({"ok": True})

@app.route("/api/landmarks", methods=["POST"])
def api_landmarks():
    """Browser posts {landmarks:[...21 pts...], fps:float} every frame."""
    if not state.get("running"):
        return jsonify({"ok": True, "skipped": True})
    data = request.get_json(force=True, silent=True) or {}
    state.set(fps=round(float(data.get("fps", 0)), 1))
    process(data.get("landmarks", []))
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("=" * 52)
    print("  GestureMouse 2.0")
    print("=" * 52)
    print(f"  Screen : {SCREEN_W} x {SCREEN_H}")
    print(f"  Win32  : {WIN32}")
    print()
    print("  Launcher    → http://localhost:5000")
    print("  Draw Board  → http://localhost:5000/draw")
    print()
    print("  Open via URL — never double-click the HTML")
    print("=" * 52)
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
