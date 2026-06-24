# THEO — Options Pricing Terminal

A live web dashboard for Black–Scholes pricing, Greeks, and market-maker quotes,
built on the options market maker engine. React frontend + FastAPI backend.

**Live demo:** _add your Vercel URL here_

![dashboard](screenshot.png)

## What it does
- Drag the contract inputs (spot, strike, expiry, rate, vol; call/put) and watch
  the theoretical value, all five Greeks, and a two-sided quote update live.
- Click any Greek to plot it across spot — an interactive curve with the current
  spot marked, redrawn on every change.
- All numbers come from a FastAPI service wrapping the Black–Scholes engine
  (auto-generated API docs at `/docs`).

## Run locally
Backend (from the repo root, where `api.py` and the engine live):
```bash
pip install fastapi "uvicorn[standard]"
uvicorn api:app --reload          # http://localhost:8000
```
Frontend (this folder):
```bash
npm install
npm run dev                        # http://localhost:5173
```

## Deploy (free tiers)
- **Backend → Render:** new Web Service, start command
  `uvicorn api:app --host 0.0.0.0 --port $PORT`.
- **Frontend → Vercel:** import the repo, set env var
  `VITE_API_URL=https://your-render-url`, deploy.

## Stack
React (Vite) · custom SVG charts (no chart lib) · FastAPI · NumPy/SciPy engine.
