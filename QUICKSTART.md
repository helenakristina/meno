# Quickstart Guide for Meno Developers

Get the Meno backend and frontend running locally in ~10 minutes.

## Prerequisites

- **Git** — for cloning/managing the repo
- **Node.js 20+** — for the frontend
- **Python 3.11+** — for the backend (already installed on most Macs)

## 1. Install `uv` (Python Package Manager)

`uv` is a fast Python package manager. If you don't have it, install it first:

```bash
# On macOS or Linux with Homebrew
brew install uv

# Or with pip (if you have Python already)
pip install uv

# Or with the standalone installer (no Python required)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify installation:

```bash
uv --version
```

## 2. Clone the Repo

```bash
git clone https://github.com/menoapp/meno.git
cd meno
```

## 3. Backend Setup (FastAPI + uv)

### Install Dependencies

```bash
cd backend
uv sync
```

This command:

- Creates a virtual environment (`.venv`)
- Installs all dependencies from `pyproject.toml`
- Takes ~1-2 minutes on first run

### Set Up Environment Variables

Copy the example env file and add your secrets:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

- `SUPABASE_URL` — your Supabase project URL
- `SUPABASE_SERVICE_KEY` — Supabase service role key (from Settings → API)
- `OPENAI_API_KEY` — your OpenAI API key (for LLM features)
- `ANTHROPIC_API_KEY` — optional, for future Claude integration

**⚠️ Never commit `.env` — it's gitignored for a reason.**

### Run the Backend

```bash
uv run uvicorn app.main:app --reload
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**API Docs:** Visit http://localhost:8000/docs to explore endpoints

The backend is now listening for requests.

## 4. Frontend Setup (SvelteKit + npm)

In a **new terminal window**, keep the backend running in the first one.

### Install Dependencies

```bash
cd frontend
npm install
```

Takes ~2-3 minutes.

### Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your Supabase credentials:

- `PUBLIC_SUPABASE_URL` — your Supabase project URL
- `PUBLIC_SUPABASE_ANON_KEY` — Supabase anon key (safe to expose in browser)
- `VITE_API_BASE_URL` — backend URL (default: `http://localhost:8000`)

### Run the Frontend

```bash
npm run dev
```

You should see:

```
  VITE v... ready in ... ms

  ➜  Local:   http://localhost:5173/
```

Open http://localhost:5173 in your browser.

## 5. Verify Everything Works

- **Frontend loads:** http://localhost:5173
- **Backend docs:** http://localhost:8000/docs
- **API is accessible from frontend:** Check browser console for any CORS errors

If you see auth errors, verify your Supabase credentials in both `.env` files.

## Common Commands

### Backend (from `backend/` directory)

```bash
# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Install a new package
uv add package-name
```

### Frontend (from `frontend/` directory)

```bash
# Run dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Install a new package
npm install package-name
```

## Troubleshooting

**"uv: command not found"**

- Make sure uv is installed: `uv --version`
- If installed via script, restart your terminal or run `source $HOME/.cargo/env`

**"ModuleNotFoundError" on `uv run uvicorn`**

- Run `uv sync` in the `backend/` directory to install dependencies

**Backend running but frontend can't reach it**

- Check `VITE_API_BASE_URL` in `frontend/.env` (should be `http://localhost:8000`)
- Check browser console for CORS errors
- Ensure backend is actually running: http://localhost:8000/docs

**Port already in use**

- Backend: `uv run uvicorn app.main:app --reload --port 8001`
- Frontend: `npm run dev -- --port 5174`

## Next Steps

- Read **CLAUDE.md** for architecture and code patterns
- Check **docs/dev/DESIGN.md** for the complete database schema
- Run the test suites: `uv run pytest` (backend) and `npm test` (frontend)

## Still Stuck?

- Check the full **CLAUDE.md** in the repo root for detailed setup and architecture
- Backend issues? Check `backend/.env` exists with valid Supabase keys
- Frontend issues? Check `frontend/.env` exists with valid Supabase keys
- Ask in the team Slack or open an issue on GitHub
