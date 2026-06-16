# Setup Guide — HTML → Elementor JSON Converter
**Stack:** FastAPI (Python) + React (Vite) + Tailwind CSS  
**Claude AI:** Optional server-side fallback via Anthropic API

---

## Project Structure

```
html-to-elementor/
├── SETUP.md                      ← this file
├── SKILL-html-to-elementor.md    ← conversion algorithm reference
├── backend/
│   ├── main.py                   ← FastAPI app (routes)
│   ├── converter.py              ← deterministic HTML parser
│   ├── claude_fallback.py        ← Claude API integration
│   ├── requirements.txt
│   └── .env.example              ← copy to .env and fill in
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── index.css
        └── App.jsx               ← main UI
```

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.11+ | `python3 --version` |
| pip | latest | `pip --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

Install Python 3.11+ on Ubuntu/Debian:
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip
```

Install Node.js 20 (LTS) via NodeSource:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## Step 1 — Clone / Enter the project

```bash
cd /home/cuncis/Downloads/PROJECTS/html-to-elementor
```

---

## Step 2 — Backend Setup

### 2a. Create a virtual environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### 2b. Install Python dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `fastapi` — web framework
- `uvicorn` — ASGI server
- `beautifulsoup4` + `lxml` — HTML parser (most fault-tolerant available)
- `cssutils` — inline CSS → Elementor settings translator
- `httpx` — async HTTP client for Claude API calls
- `python-dotenv` — loads `.env` file

### 2c. Create your `.env` file
```bash
cp .env.example .env
```

Open `.env` and edit:
```
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
USE_CLAUDE_FALLBACK=true
CLAUDE_MODEL=claude-sonnet-4-5
CORS_ORIGINS=http://localhost:5173
```

> **Where to get a Claude API key:** https://console.anthropic.com/  
> If you don't want AI fallback, set `USE_CLAUDE_FALLBACK=false` and leave the key as-is.

### 2d. Start the backend
```bash
uvicorn main:app --reload --port 8000
```

Verify it's running:
```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

Auto-generated API docs: http://localhost:8000/docs

---

## Step 3 — Frontend Setup

Open a **new terminal tab**, keeping the backend running.

### 3a. Install Node dependencies
```bash
cd /home/cuncis/Downloads/PROJECTS/html-to-elementor/frontend
npm install
```

### 3b. Start the dev server
```bash
npm run dev
```

The app will be available at: **http://localhost:5173**

Vite proxies `/convert` and `/health` to `http://localhost:8000` automatically — no CORS issues in development.

---

## Step 4 — Using the App

1. Open **http://localhost:5173**
2. Paste your HTML into the left panel (or click **Load example HTML**)
3. Toggle options in the toolbar:
   - **Claude AI fallback** — enable to use Claude when the parser produces empty output
   - **Template envelope** — wraps output in Elementor import format (`version`, `title`, `type`, `content`)
4. Click **Convert**
5. The JSON appears on the right panel
6. Use **Copy** to paste into Elementor, or **Download** to get a `.json` file

---

## Step 5 — Import into WordPress / Elementor

### Option A — Direct paste (raw `_elementor_data`)
1. Disable Template envelope toggle
2. Copy the JSON
3. In WP Admin → **Elementor → Tools → Replace URL** (or use WP-CLI below)

### Option B — Template import (GUI, easiest)
1. Enable **Template envelope** toggle
2. Download the JSON file
3. WP Admin → **Templates → Saved Templates → Import Templates** → upload file

### Option C — WP-CLI (fastest for developers)
```bash
wp post meta update <POST_ID> _elementor_data '<paste json here>' --format=json
wp post meta update <POST_ID> _elementor_edit_mode builder
```

### Option D — WordPress REST API
```js
await fetch(`/wp-json/wp/v2/pages/${postId}`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Basic " + btoa("user:app-password")
  },
  body: JSON.stringify({
    meta: { _elementor_data: jsonString, _elementor_edit_mode: "builder" }
  })
});
```

---

## Step 6 — Test the API Directly (curl)

### Basic conversion
```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"html": "<h1>Hello World</h1><p>This is a test.</p>", "use_claude": false}'
```

### With template envelope
```bash
curl -X POST http://localhost:8000/convert/template \
  -H "Content-Type: application/json" \
  -d '{"html": "<h1>Hello</h1>", "use_claude": false}'
```

### With Claude fallback
```bash
curl -X POST http://localhost:8000/convert \
  -H "Content-Type: application/json" \
  -d '{"html": "<section>...</section>", "use_claude": true}'
```

---

## Step 7 — Production Build

### Backend (production with Gunicorn)
```bash
pip install gunicorn
cd backend
source venv/bin/activate
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend (static build)
```bash
cd frontend
npm run build
# Output in frontend/dist/
```

Serve `dist/` with Nginx or any static host. Point the API base URL to your production backend.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'lxml'`
```bash
source backend/venv/bin/activate
pip install lxml
```

### `CORS error` in browser console
Make sure `CORS_ORIGINS` in `backend/.env` matches your frontend URL exactly (no trailing slash).

### `Claude API error 401`
Your `ANTHROPIC_API_KEY` in `.env` is invalid. Get a fresh key from https://console.anthropic.com/

### Backend returns empty `data: []`
The HTML may consist entirely of elements that `node_to_widget()` returns `None` for (e.g., empty divs, `<head>` content). Try pasting only the `<body>` content, or enable Claude fallback.

### Port already in use
```bash
# Kill whatever is on port 8000
lsof -ti:8000 | xargs kill -9
# Kill whatever is on port 5173
lsof -ti:5173 | xargs kill -9
```

---

## How the Conversion Works (Summary)

```
Raw HTML
   │
   ▼
BeautifulSoup (lxml parser) — fault-tolerant HTML normalization
   │
   ▼
Complexity Classifier — each block element checked for:
   ├── complex CSS (@keyframes, display:grid, CSS vars, clip-path…)
   └── complex JS (addEventListener, querySelector, Swiper, gsap…)
         │
         ├── Complex → html snippet widget (bundled <style>+markup+<script>)
         └── Simple  → native widget (heading / text-editor / image / button…)
   │
   ▼
Section → Column → Widget tree assembly
   │
   ▼
JSON serialisation → _elementor_data array
   │
   ▼ (optional Claude fallback if output is empty)
Claude API (server-side, key never exposed to browser)
```

---

## Dependencies Reference

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework, request validation, OpenAPI docs |
| `uvicorn` | ASGI server to run FastAPI |
| `beautifulsoup4` | HTML parsing and tree walking |
| `lxml` | Fast, fault-tolerant HTML parser backend for bs4 |
| `cssutils` | Parse inline CSS → Elementor settings keys |
| `httpx` | Async HTTP client for Claude API calls |
| `python-dotenv` | Load `.env` environment variables |
| `react` + `vite` | Frontend UI framework + build tool |
| `tailwindcss` | Utility-first CSS framework |
| `lucide-react` | Icon set |
