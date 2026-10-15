# Architecture

## Overview

The system is split into two deployable services plus two data stores, all
orchestrated by `docker-compose.yml`:

| Component | Tech | Responsibility |
|---|---|---|
| `frontend` | Next.js 14 (App Router) + Tailwind + Recharts | 5 pages, REST calls via axios, live updates via WebSocket |
| `backend` | FastAPI + SQLAlchemy (async) + APScheduler | REST/WS API, ML pipeline, scheduler, risk engine |
| `postgres` | PostgreSQL 16 | System of record: candles, features, models, signals, positions, backtests, settings, audit log |
| `redis` | Redis 7 | Latest-price/signal cache + pub/sub fan-out to WebSocket clients |

## Data flow

### Live signal generation (every 1 minute)

1. `stream_live_prices()` (backend, runs continuously) receives 1-minute
   kline ticks from Binance's public WebSocket, publishes every tick to
   Redis (`btc:price_channel`), and persists **closed** candles to
   `ohlcv`.
2. Every minute, the scheduler's `generate_live_signal()` job:
   - Loads the current `is_active` model from `models`.
   - Pulls the most recent ~500 candles, builds the feature row
     (`app/ml/features.py`).
   - Calls `model.predict_proba()` → raw probability of price being higher
     `PREDICTION_HORIZON_MINUTES` ahead.
   - Runs SHAP `TreeExplainer` against the calibrated model's base
     estimator to get the top contributing features for *this specific*
     prediction (`app/ml/explain.py`).
   - Passes the raw probability through `generate_signal()`
     (`app/ml/signal_engine.py`), which:
     - Clamps probability into `(epsilon, 1-epsilon)` — **never exactly 0
       or 1**.
     - Derives a `confidence` score (distance from 50/50 uncertainty).
     - Applies the Admin Panel's `buy_prob_threshold` /
       `sell_prob_threshold` / `min_confidence` to decide BUY / SELL /
       HOLD.
   - Persists the signal to `signals` and publishes it to Redis
     (`btc:signal_channel`) with the SHAP explanation and disclaimer
     attached.
3. `ConnectionManager` (backend) subscribes to both Redis channels and
   fans every message out to all connected `/ws/live` WebSocket clients.
4. The frontend's `useLiveSocket()` hook keeps the latest price and signal
   in React state, updating the Dashboard in real time without polling.

### Retraining pipeline

Triggered either by the weekly cron (`RETRAIN_CRON`, default Monday 03:00
UTC) or the **"Retrain Now"** button on the Retraining page
(`POST /api/retraining/retrain`):

1. Refresh data: `backfill_history()` pulls the latest candles from
   Binance REST.
2. Feature generation + label construction happen inline in
   `train_model()` (`app/ml/train.py`) — no separate feature-store step is
   required since features are deterministic functions of OHLCV history.
3. A `GradientBoostingClassifier` wrapped in `CalibratedClassifierCV`
   (isotonic calibration, 3-fold CV) is trained on a time-ordered 85/15
   train/validation split (no shuffling — avoids lookahead leakage).
4. Validation accuracy and Brier score are computed and stored as the new
   model version's `metrics`.
5. **Champion selection**: the new model is compared against the current
   champion. It's promoted (`is_champion = is_active = True`) only if it
   matches or beats the champion on *both* validation accuracy and Brier
   score (lower is better for Brier). Otherwise it's kept in the registry
   (for audit/rollback) but not promoted.
6. The job's status/result is recorded in `retrain_jobs` and visible on
   the Retraining page.

### Monitoring snapshots

A nightly job (`compute_daily_monitoring_snapshot`, 00:30 UTC) walks back
through the last 7 days of persisted `signals`, looks up what BTC/USDT
actually did `PREDICTION_HORIZON_MINUTES` after each signal, and computes:

- Daily / weekly directional accuracy (predicted-up vs. actual-up)
- Win rate, Sharpe ratio, profit factor, max drawdown from *closed
  positions* in the same window
- A calibration curve: signals are bucketed by predicted probability
  (0.0–0.1, 0.1–0.2, …) and each bucket's *observed* up-frequency is
  compared to its *average predicted* probability. A well-calibrated model
  produces buckets that sit near the diagonal on the Monitoring page's
  scatter chart.

### Backtesting

`POST /api/backtest/run` loads the current champion model and walks
`app/services/backtest_engine.py::run_backtest()` candle-by-candle over the
requested historical window, applying the *exact same* `generate_signal()`
and risk-manager logic used live — so backtest results reflect what the
live system would actually have done, not an idealized approximation. It
returns an equity curve, trade log, monthly returns, and metrics (Sharpe,
profit factor, max drawdown, win rate), all persisted to `backtests` /
`backtest_trades` for later retrieval.

### Risk management

`app/services/risk_manager.py` is the single gate through which every new
position (live or backtested) must pass:

- Trading must be enabled (Admin Panel toggle).
- Open position count must be under `max_open_positions`.
- Today's realized PnL must not have breached `daily_loss_limit_pct`.
- Position size is computed as `capital * max_position_size_pct / price`.
- Stop-loss / take-profit levels are computed from `stop_loss_pct` /
  `take_profit_pct` relative to entry price and side.

All of these are configurable at runtime from the Admin Panel and take
effect on the *next* signal cycle — no redeploy needed.

## Why these design choices

- **Isotonic calibration** rather than raw `predict_proba` output:
  gradient boosting classifiers are known to produce overconfident
  probability estimates; calibration is what makes "70% probability up"
  actually mean roughly 70% of such signals resolve up historically (see
  the calibration curve on the Monitoring page).
- **Probability clamping in `signal_engine.py`** is a deliberate,
  code-level guarantee — not just a UI convention — that the system cannot
  emit a claim of certainty, satisfying the "never claim certainty"
  requirement at the architecture level rather than relying on prompt/UI
  discipline alone.
- **SHAP TreeExplainer** on the underlying tree ensemble gives per-signal,
  per-feature attributions cheaply (no retraining or surrogate model
  needed), which is what powers the "why was this signal generated"
  explanation on the Dashboard.
- **Redis pub/sub** decouples "who computed this tick/signal" from "who
  needs to know about it," so the WebSocket layer scales independently of
  the ingestion/scheduler processes and multiple backend workers could
  share one Redis instance in a horizontally-scaled deployment.
