# Fundament — Investor Education Platform

A complete, zero-dependency mutual fund education app.
**No npm. No pip install. Just Python 3.6+ and a browser.**

---

## Quick Start

### Windows
Double-click `start.bat`
— or —
```
python server.py
```

### macOS / Linux
```bash
chmod +x start.sh
./start.sh
```
— or —
```bash
python3 server.py
```

Then open: **http://localhost:8080**

The app opens in your browser automatically.

---

## What's Inside

```
fundament/
├── server.py          ← Python backend (zero dependencies)
├── start.bat          ← Windows launcher
├── start.sh           ← macOS/Linux launcher
├── README.md          ← This file
└── static/
    └── index.html     ← Complete frontend
```

---

## Features

| Tool | Description |
|------|-------------|
| SIP Calculator | Monthly investment with step-up, inflation-adjusted |
| Lump Sum Calculator | Compound vs simple, Rule of 72, real value |
| Goal Planner | Reverse-calculate SIP/lump sum for any target |
| Fund Comparator | 8 fund types side-by-side, risk/return scatter |
| Scenario Comparison | Compare 2 strategies head-to-head |
| Key Concepts | 12 illustrated explainers |
| Quiz | 8 questions with detailed explanations |

---

## API Endpoints

The Python backend exposes a REST API:

```
GET  /api/health
GET  /api/sip?monthly=5000&rate=12&years=15&inflation=6&stepup=5
GET  /api/lumpsum?principal=100000&rate=12&years=10&inflation=6&freq=4
GET  /api/goal?target=5000000&years=15&rate=12&inflation=6&existing=0
GET  /api/funds
GET  /api/compare?a=largecap&b=midcap
GET  /api/fund?id=elss
GET  /api/quiz
GET  /api/quiz/check?id=1&chosen=0
POST /api/quiz/submit   (body: {"answers": {"1": 0, "2": 1, ...}})
POST /api/sip/batch     (body: {"scenarios": [...]})
```

---

## Custom Port

```bash
PORT=3000 python3 server.py
```

---

## Requirements

- Python 3.6 or higher
- A modern web browser (Chrome, Firefox, Safari, Edge)
- No internet connection required after first font load

---

## Offline Mode

If the Python server is not running, the frontend automatically
falls back to local JavaScript calculations — all tools remain
fully functional. The server adds API access and more advanced
features like batch scenario comparison.

---

## Disclaimer

**Educational purpose only.** All projections are illustrative.
Mutual fund investments are subject to market risks. Past
performance does not guarantee future results. This is not
financial advice. Please consult a SEBI-registered advisor
before making investment decisions.

---

*Fundament — Investor Education & Awareness Initiative*
