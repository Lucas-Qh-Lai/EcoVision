# 🌿 EcoVision

> **AI-Powered Real-Time Garbage Classification System**
>
> Version 2.0 · 2025-2026 · Quanzhou No.5 Middle School Science Fair Project

[中文文档](README.md)

---

## 📋 Overview

EcoVision is an AI-powered garbage classification system that identifies **265 types** of household waste through a browser camera or image upload. Built on a **ConvNeXt-Base** deep neural network (ImageNet-22K pretrained, fine-tuned on a custom waste dataset), it delivers real-time classification with on-device GPU acceleration (Apple MPS / CPU fallback).

The server is built with **FastAPI** + **PyTorch** + **SQLite**, featuring a responsive web interface with both light and dark themes.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📷 Real-time Camera Capture | Browser WebRTC → Canvas → JPEG (0.93 quality, max 800px) |
| 🤖 AI Classification | ConvNeXt-Base, 265 categories, 0.5% confidence filter |
| 📋 Disposal Guides | 8 tips per category, 25+ item-specific tips |
| 📊 Statistics Dashboard | Charts: category distribution (doughnut) + daily trend (bar) |
| 🌓 Dual Theme | Light/dark mode via CSS custom properties, localStorage persistence |
| 📱 Responsive Design | 3 breakpoints: desktop → tablet → mobile |
| 🔄 Auto Capture | 3s interval loop with drift-corrected scheduling |
| 🚀 MPS Acceleration | Metal Performance Shaders on Apple Silicon (M1–M4) |
| 🔒 Input Validation | Base64 10MB limit, Pydantic validation, SQL parameterized queries |

---

## 🧠 Tech Stack

```
┌─────────────────────┐     POST /api/predict      ┌──────────────────────────┐
│    Browser Client    │ ◄───── (base64 JPEG) ─────► │   FastAPI Server         │
│  ┌─────────────────┐ │     JSON Response           │   Python 3.10+           │
│  │  index.html     │ │ ◄────── (PredictResponse) ──│                          │
│  │  app.js         │ │     GET /api/stats          │  ├─ /api/predict  POST   │
│  │  style.css      │ │ ◄────── (stats JSON) ──────►│  ├─ /api/health   GET    │
│  └─────────────────┘ │     GET /api/health         │  ├─ /api/labels   GET    │
│  ┌─────────────────┐ │ ◄────── (status) ──────────►│  ├─ /api/stats    GET    │
│  │  stats.html     │ │                             │  ├─ /api/stats/export    │
│  │  Chart.js 4.4.7 │ │                             │  └──/  /stats  (static)  │
│  └─────────────────┘ │                             │                          │
└─────────────────────┘                             │  asyncio.to_thread()     │
                                                    │         │                │
                                                    │         ▼                │
                                                    │  ┌──────────────┐        │
                                                    │  │ classifier   │        │
                                                    │  │ .py          │        │
                                                    │  │ ConvNeXt-Base│        │
                                                    │  │ MPS / CPU    │        │
                                                    │  └──────┬───────┘        │
                                                    │         │                │
                                                    │  ┌──────▼───────┐        │
                                                    │  │ guides_db.py │        │
                                                    │  │ guides.json  │        │
                                                    │  └──────┬───────┘        │
                                                    │         │                │
                                                    │  ┌──────▼───────┐        │
                                                    │  │ ecovision_   │        │
                                                    │  │ stats.db     │        │
                                                    │  │ (SQLite WAL) │        │
                                                    │  └──────────────┘        │
                                                    └──────────────────────────┘
```

### Components

| Layer | Technology | Detail |
|-------|-----------|--------|
| **HTTP Server** | FastAPI (uvicorn) | Async ASGI, lifespan context manager |
| **ML Model** | ConvNeXt-Base via ModelScope | `iic/cv_convnext-base_image-classification_garbage` rev `v1.0.2` |
| **Inference** | PyTorch 2.0+ | Manual pipeline bypass: CPU pre → GPU forward → CPU post |
| **Backend** | Python 3.10+ | `threading.Lock` classifier singleton, `asyncio` |
| **Database** | SQLite 3 | WAL + `synchronous=NORMAL`, 7 columns |
| **Frontend** | Vanilla JS (ES6) | fetch, Canvas 2D, getUserMedia WebRTC |
| **Charts** | Chart.js 4.4.7 | Doughnut + Bar charts |
| **Validation** | Pydantic v2 | @field_validator for base64 size limit |

---

## 📊 Database Schema

`ecovision_stats.db` — `recognition_log` table:

```sql
CREATE TABLE recognition_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT    NOT NULL,       -- e.g. "可回收物-饮料瓶"
    display_name TEXT    NOT NULL,       -- e.g. "饮料瓶"
    category     TEXT    NOT NULL,       -- e.g. "可回收物"
    confidence   REAL    NOT NULL,       -- 0.00–1.00
    inference_ms REAL    NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_log_created ON recognition_log(created_at);
```

---

## 📖 API Reference

### `POST /api/predict` — Image Classification

**Request**:
```json
{ "image": "data:image/jpeg;base64,..." }
```

**Response** (200):
```json
{
  "success": true,
  "label": "可回收物-饮料瓶",
  "display_name": "饮料瓶",
  "category": "可回收物",
  "category_info": {"color": "#3B82F6", "icon": "♻️", "label": "可回收垃圾"},
  "confidence": 95.3,
  "top_predictions": [
    {"label": "可回收物-饮料瓶", "display_name": "饮料瓶", "score": 95.3}
  ],
  "guide": {
    "display_name": "饮料瓶",
    "category": "可回收垃圾",
    "color": "#3B82F6",
    "icon": "♻️",
    "tips": [
      "Clean and place in blue recycling bin",
      "Crush plastic bottles before disposal",
      ...
    ]
  },
  "inference_ms": 72.5
}
```

**Error** (400 — invalid image):
```json
{ "detail": "图片解码失败: Invalid base64 string" }
```

### `GET /api/health`

```json
{
  "status": "ok",
  "classifier_loaded": true,
  "device": "mps",
  "mps_active": true,
  "guide_count": 265,
  "stats_db_size": 237568
}
```

### `GET /api/labels`
Returns `{"count": 265, "labels": ["可回收物-饮料瓶", ...]}`

### `GET /api/stats?days=7`
Recognition statistics: total, avg_confidence, categories, daily trend, top-20 items.

### `GET /api/stats/export?days=7`
Export records as JSON array (max 10,000 rows).

### Static Routes

| Path | File |
|------|------|
| `/` | `static/index.html` |
| `/stats` | `static/stats.html` |
| `/static/app.js` | Frontend logic |
| `/static/style.css` | Theme + layout |

---

## 🚀 Quick Start

### Requirements

- Python ≥ 3.10
- pip
- Modern browser (Chrome/Safari/Firefox)
- (Optional) Apple Silicon Mac for MPS acceleration
- (Optional) Camera (upload mode works without it)

### Install & Run

```bash
cd EcoVision
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# (Optional) pip install modelscope datasets mmcv
# (One-time) python build_guides.py
uvicorn server:app --host 0.0.0.0 --port 8765
```

Then open **http://localhost:8765** in a browser.

### Scripts

```bash
./start.sh   # Start in background
./stop.sh    # Stop all processes
```

**First run**: The model downloads from ModelScope (~500MB, ~25s). Subsequent starts load from cache instantly.

---

## 📁 Project Structure

```
EcoVision/
├── server.py            # FastAPI: routes, DB, lifecycle
├── classifier.py        # AI: ConvNeXt inference, MPS, model loading
├── guides_db.py         # Guide data: categories, tips, icons
├── guides.json          # Pre-built 265 guide entries
├── build_guides.py      # Guide builder from model labels
├── model_labels.json    # Model label cache (265 items)
├── requirements.txt     # Python dependencies
├── start.sh / stop.sh   # Start/stop scripts
├── static/
│   ├── index.html       # Main page
│   ├── app.js           # Frontend logic
│   ├── style.css        # Theme + responsive layout
│   └── stats.html       # Statistics dashboard
├── .gitignore
├── LICENSE
└── README.*.md          # This documentation
```

---

## ⚙️ Configuration

| Parameter | Default | Location |
|-----------|---------|----------|
| Port | 8765 | `start.sh` |
| Image limit | 10MB (base64) | `server.py:PredictRequest` |
| Canvas max | 800px | `app.js` |
| Auto interval | 3000ms | `app.js` |
| Log threshold | ≥0.50 (50%) | `server.py` |
| Export limit | 10,000 rows | `server.py` |
| Model revision | `v1.0.2` | `classifier.py` |

---

## 🔒 Security

- ✅ SQL parameterized queries (no injection)
- ✅ Base64 size validation (Pydantic, 10MB max)
- ✅ PyTorch `weights_only=True` with safe globals
- ✅ Thread-safe classifier (double-checked locking)
- ✅ XSS protection (textContent + escapeHtml)

---



---

## 🍎 Apple Silicon Optimization

This system is optimized for **Apple Silicon (M1–M4)** chips:

- **MPS backend**: Auto-detects and uses Metal Performance Shaders for GPU-accelerated inference
- **Unified memory**: CPU and GPU share memory, eliminating data copy overhead
- **Auto fallback**: Falls back to CPU inference when MPS is unavailable
- **Memory management**: Calls `torch.mps.empty_cache()` after inference to release GPU tensors

> Other platforms (Intel Mac, Windows, Linux) default to CPU inference, approximately 1/3–1/5 the performance of MPS. Users with NVIDIA GPUs can configure CUDA acceleration.

---

## 🪟 Windows Support

The system also runs on Windows:

- **Backend**: Python standard library is cross-platform; FastAPI + uvicorn work on Windows without issues
- **Frontend**: Supports Chrome / Edge / Firefox; camera access via WebRTC
- **GPU**: CUDA detection built-in. If NVIDIA GPU + CUDA PyTorch, inference auto-uses GPU (untested, no stability guarantee)
- **Installation**: Same steps as macOS; PowerShell or Git Bash recommended

```bash
# Windows PowerShell example:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8765
```

## ⚡ Performance

> **Note**: Benchmarks measured on MacBook Pro M1 Pro + Safari. Actual performance varies by device, network, and browser.
> Apple Silicon optimization targets M1–M4 series. Other platforms are not performance-guaranteed.

| Stage | Reference | Notes |
|-------|-----------|-------|
| Capture → Canvas | < 20ms | Browser Canvas 2D rendering |
| Image transfer | ~30–80ms | Local LAN, JPEG compressed ~100KB |
| Model inference (MPS, Apple Silicon) | 60–120ms | M1 Pro + Safari, MPS acceleration |
| Model inference (CUDA, NVIDIA GPU) | 50–100ms | Windows/Linux, requires CUDA PyTorch (untested, no guarantee) |
| Model inference (CPU, other platforms) | 200–500ms | CPU fallback mode |
| Total response (MPS) | 100–250ms | Transfer + inference + post-processing |
| SQLite INSERT | < 5ms | WAL mode, < 10k rows |

---

## 🤖 Model Credit

This project uses a **ConvNeXt-Base** model sourced from **ModelScope**:

| Attribute | Value |
|-----------|-------|
| **Source** | [ModelScope](https://modelscope.cn/models/iic/cv_convnext-base_image-classification_garbage/summary) |
| **Model ID** | `iic/cv_convnext-base_image-classification_garbage` |
| **Revision** | `v1.0.2` |
| **Architecture** | ConvNeXt-Base (ImageNet-22K → garbage classification) |
| **Framework** | PyTorch 2.0+ via ModelScope pipeline |
| **License** | ModelScope License (research & educational use) |

---

## ©️ Credits

This project was built with assistance from **OpenAI Codex** © 2025-2026

---

## 📝 Open Source License

This project is licensed under the **MIT License** — fully open software.

- ✅ **Commercial use** — free for any project
- ✅ **Modification** — freely modify and create derivatives
- ✅ **Distribution** — redistribute with original copyright notice
- ❌ **No warranty** — no liability for any use



See [LICENSE](LICENSE) for details.

---

<p align="center"><em>Built for environmental awareness</em></p>
