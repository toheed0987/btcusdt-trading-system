# Setup Guide

## Prerequisites

- Docker + Docker Compose (recommended path), **or**
- Python 3.11+, Node.js 20+, PostgreSQL 16, Redis 7 for a manual/local setup

## Option A — Docker (recommended)

```bash
cd btc-trading-system
cp .env.example .env
docker compose up --build
```

This starts, in dependency order: `postgres` → `redis` → `backend` →
`frontend`. Postgres runs `db/init.sql` automatically on first boot via
the `docker-entrypoint-initdb.d` mount — no separate migration step is
needed for a fresh database.

Verify everything is up:
```bash
curl http://localhost:8000/api/health
# {"status":"ok","environment":"development","symbol":"BTCUSDT"}
```

Open:
- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

### First-run checklist

1. Wait ~1–2 minutes for the initial candle backfill to complete (check
   backend logs: `docker compose logs -f backend`).
2. Go to **Retraining** (http://localhost:3000/retraining) and click
   **"Retrain Now"** — a fresh install has no model until the first
   training run completes.
3. Once a champion model exists, the **Dashboard** will start showing
   live BUY/SELL/HOLD signals (generated every minute), and **Backtesting**
   becomes available.
4. Trading is **disabled by default**. Enable it (and review thresholds)
   on the **Admin Panel** if you want the system to open simulated
   positions based on its own signals.

## Option B — Manual / local development

### 1. Database
```bash
createdb btc_trading
psql -d btc_trading -f db/init.sql
```

### 2. Redis
```bash
redis-server
```

### 3. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL="postgresql+asyncpg://<user>:<pass>@localhost:5432/btc_trading"
export REDIS_URL="redis://localhost:6379/0"

uvicorn app.main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
npm install
export NEXT_PUBLIC_API_URL=http://localhost:8000
export NEXT_PUBLIC_WS_URL=ws://localhost:8000
npm run dev
```

## Running tests

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

The included test suite (`tests/test_signal_engine.py`) specifically
verifies the "never claims certainty" guarantee: probabilities are always
strictly between 0 and 1, even when the model's raw output is arbitrarily
close to 0 or 1.

## Configuration reference (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `btc_user` / `btc_password` / `btc_trading` | Change for anything beyond local dev |
| `DATABASE_URL` | derived from above | Full async SQLAlchemy URL |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `SECRET_KEY` | placeholder | Set a long random value in production |
| `BINANCE_WS_URL` / `BINANCE_REST_URL` | Binance public endpoints | No API key required for market data |
| `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` | empty | Only needed if you extend the system with real order execution; **do not commit real keys** |
| `RETRAIN_CRON` | `0 3 * * 1` (Mon 03:00 UTC) | Standard cron syntax |
| `MODEL_ARTIFACT_DIR` | `/app/artifacts` | Where trained `.joblib` model files are stored |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` | `http://localhost:8000` / `ws://localhost:8000` | Frontend → backend endpoints |

## Troubleshooting

- **"No champion model available yet" on Backtesting** → train a model
  first via the Retraining page (needs ≥ 300 historical candles; the
  initial backfill pulls up to 1000).
- **Dashboard chart is empty** → check `docker compose logs backend` for
  ingestion errors (e.g. outbound network restrictions blocking Binance
  endpoints). The system needs outbound HTTPS/WSS access to
  `api.binance.com` and `stream.binance.com`.
- **WebSocket shows "reconnecting…" indefinitely** → confirm
  `NEXT_PUBLIC_WS_URL` matches how your browser can reach the backend
  (e.g. `ws://localhost:8000`, not the internal Docker service name).
- **Calibration curve is empty** → it populates after the nightly
  monitoring snapshot job has run at least once with live signals in
  the database (needs signals older than the prediction horizon so
  outcomes are known).
