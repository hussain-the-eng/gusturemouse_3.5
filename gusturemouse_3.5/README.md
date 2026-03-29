# GestureMouse 2.0
### Real-time Hand Tracking · Drawing Board · Anime Visual Effects
> 3rd Year CE Portfolio Project — Computer Vision / Real-Time Systems

---

## 📁 Project Structure

```
GestureMouse-2.0/
├── gesture_mouse.py     ← Python backend (tracking + cursor control + Flask API)
├── launcher.html        ← Web control panel (open in browser)
├── visual_effects.html  ← Anime effects page (fireball, magic, lightning, sakura)
├── requirements.txt     ← Python dependencies
└── README.md
```

---

## ⚙️ Setup (Windows)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the backend
```bash
python gesture_mouse.py
```
You'll see:
```
  GestureMouse 2.0  —  Backend Starting
  Screen   : 1920 x 1080
  API      : http://localhost:5000
```

### 3. Open the launcher
Open `launcher.html` in your browser (double-click or drag into Chrome/Edge).
- Click **START TRACKING**
- Switch between **CURSOR / DRAW / EFFECTS** modes

### 4. Visual Effects (separate page)
Click **"🔥 Visual Effects"** in the launcher, or open `visual_effects.html` directly.
- Uses **MediaPipe.js** in the browser — runs at full GPU-accelerated speed
- Falls back to the backend API if MediaPipe.js fails to load

---

## ✋ Gesture Reference

| Gesture | Action |
|---|---|
| ✋ Open palm | Move cursor |
| 👌 Pinch (index + thumb) | Left click |
| 🤏 Pinch (index + middle + thumb) | Right click |
| ✌️ Index + middle up | Scroll |
| ✊ Fist | Drag mode |
| ☝️ Index only (Draw mode) | Draw stroke |
| ✌️ Two fingers (Draw mode) | Lift pen |

---

## 🎨 Visual Effects

| Effect | Description |
|---|---|
| 🔥 Fireball | Animated fire particles follow your finger |
| 🔮 Magic Hand | Purple/cyan sparkles + 4-pointed stars from all fingertips |
| ⚡ Lightning | Branching procedural lightning bolts |
| 🌸 Sakura | Physics-based cherry blossom petals |

All effects run in **HTML5 Canvas** with WebGL-accelerated compositing.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (launcher.html / visual_effects.html)          │
│  - Mode control via fetch() → Flask API                 │
│  - MJPEG stream from /video_feed                        │
│  - MediaPipe.js runs hand detection natively in browser │
└───────────────────┬─────────────────────────────────────┘
                    │ HTTP (localhost:5000)
┌───────────────────▼─────────────────────────────────────┐
│  gesture_mouse.py  (Python backend)                     │
│                                                         │
│  Thread 1: Webcam capture (cv2.VideoCapture)            │
│  Thread 2: MediaPipe detection (model_complexity=0)     │
│  Thread 3: EMA cursor smoother + Windows ctypes calls   │
│  Thread 4: Flask API server (start/stop/mode/stream)    │
└─────────────────────────────────────────────────────────┘
```

### Performance Optimizations
- **Downscaled detection**: 320×240 for MediaPipe, full 640×480 for display
- **model_complexity=0**: 3× faster than complexity 1 with minimal accuracy loss
- **EMA smoothing**: α=0.55, eliminates jitter without adding lag
- **ctypes SetCursorPos**: direct Win32 API — zero overhead vs pyautogui
- **CAP_DSHOW**: Windows-native camera backend, reduces capture latency by ~15ms
- **JPEG quality 75**: fast encode for MJPEG stream

---

## 🛠 Extending

**Add a new gesture**: Edit `classify_gesture()` in `gesture_mouse.py`

**Add a new visual effect**: Add a particle class in `visual_effects.html` and register it in `switchEffect()`

**Change draw color**: Edit `DRAW_COLOR` in `gesture_mouse.py`

**Tune smoothing**: Adjust `SMOOTHING_ALPHA` (0=laggy, 1=raw/jittery)

---

## 📚 Tech Stack

- **MediaPipe Hands** (Python + JS) — hand landmark detection
- **OpenCV** — camera capture, frame processing, drawing overlay
- **Flask** — lightweight REST API + MJPEG streaming
- **ctypes Win32** — zero-overhead cursor/mouse control
- **HTML5 Canvas** — GPU-composited particle effects
- **MediaPipe.js** — browser-native hand tracking for effects page

---

*Built for CE3 portfolio — demonstrates real-time CV pipeline, multi-threaded architecture, cross-layer system design (Python ↔ Browser), and production ML library usage.*
