-- ============================================================
-- BTC/USDT Probabilistic Trading System — PostgreSQL schema
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------
-- Raw OHLCV market data (1-minute candles ingested continuously)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ohlcv (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(20) NOT NULL DEFAULT 'BTCUSDT',
    open_time   TIMESTAMPTZ NOT NULL,
    open        NUMERIC(20,8) NOT NULL,
    high        NUMERIC(20,8) NOT NULL,
    low         NUMERIC(20,8) NOT NULL,
    close       NUMERIC(20,8) NOT NULL,
    volume      NUMERIC(28,8) NOT NULL,
    interval    VARCHAR(5) NOT NULL DEFAULT '1m',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, interval, open_time)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv (symbol, interval, open_time DESC);

-- ---------------------------------------------------------------
-- Engineered features per candle (generated automatically)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS features (
    id            BIGSERIAL PRIMARY KEY,
    ohlcv_id      BIGINT REFERENCES ohlcv(id) ON DELETE CASCADE,
    symbol        VARCHAR(20) NOT NULL,
    open_time     TIMESTAMPTZ NOT NULL,
    feature_set   JSONB NOT NULL,        -- {"rsi_14": 55.2, "ema_9": ..., ...}
    label_up      SMALLINT,              -- 1 if price rose over horizon, 0 if fell, NULL if unknown yet
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, open_time)
);
CREATE INDEX IF NOT EXISTS idx_features_symbol_time ON features (symbol, open_time DESC);

-- ---------------------------------------------------------------
-- Model registry / versioning
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS models (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version         VARCHAR(50) NOT NULL UNIQUE,
    algorithm       VARCHAR(50) NOT NULL,          -- e.g. 'gradient_boosting'
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    training_rows   INTEGER,
    feature_list    JSONB,
    hyperparameters JSONB,
    artifact_path   TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE, -- currently serving live signals
    is_champion     BOOLEAN NOT NULL DEFAULT FALSE, -- best model selected by monitoring
    metrics         JSONB,                          -- accuracy, sharpe, etc at training time
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_models_active ON models (is_active);

-- ---------------------------------------------------------------
-- Retraining job runs (daily ingestion + weekly retrain)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retrain_jobs (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type      VARCHAR(20) NOT NULL,   -- 'ingestion' | 'feature_gen' | 'retrain'
    status        VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|running|success|failed
    triggered_by  VARCHAR(20) NOT NULL DEFAULT 'scheduler', -- 'scheduler' | 'manual'
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    result        JSONB,
    error_message TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------
-- Live trading signals produced by the active model
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID REFERENCES models(id),
    symbol          VARCHAR(20) NOT NULL DEFAULT 'BTCUSDT',
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    action          VARCHAR(10) NOT NULL,    -- BUY | SELL | HOLD
    prob_up         NUMERIC(6,5) NOT NULL,   -- 0..1, NEVER exactly 0 or 1 (clamped)
    prob_down       NUMERIC(6,5) NOT NULL,
    confidence      NUMERIC(6,5) NOT NULL,   -- 0..1, distance-from-uncertainty measure
    price_at_signal NUMERIC(20,8) NOT NULL,
    explanation     JSONB,                   -- top SHAP features {feature: contribution}
    threshold_used  JSONB                    -- thresholds active at generation time
);
CREATE INDEX IF NOT EXISTS idx_signals_time ON signals (generated_at DESC);

-- ---------------------------------------------------------------
-- Positions (paper or live) opened from signals
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    signal_id       UUID REFERENCES signals(id),
    symbol          VARCHAR(20) NOT NULL DEFAULT 'BTCUSDT',
    side            VARCHAR(10) NOT NULL,        -- LONG | SHORT
    status          VARCHAR(10) NOT NULL DEFAULT 'OPEN', -- OPEN | CLOSED
    entry_price     NUMERIC(20,8) NOT NULL,
    exit_price      NUMERIC(20,8),
    quantity        NUMERIC(20,8) NOT NULL,
    stop_loss       NUMERIC(20,8),
    take_profit     NUMERIC(20,8),
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,
    pnl             NUMERIC(20,8),
    pnl_pct         NUMERIC(10,5),
    close_reason    VARCHAR(30)                 -- signal_flip | stop_loss | take_profit | manual
);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);

-- ---------------------------------------------------------------
-- Backtest runs and their resulting trade log / equity curve
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID REFERENCES models(id),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    initial_capital NUMERIC(20,8) NOT NULL DEFAULT 10000,
    params          JSONB,
    metrics         JSONB,      -- sharpe, profit_factor, max_dd, win_rate, cagr, etc
    equity_curve    JSONB,      -- [{t, equity}, ...]
    monthly_returns JSONB,      -- [{month, return_pct}, ...]
    status          VARCHAR(20) NOT NULL DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id            BIGSERIAL PRIMARY KEY,
    backtest_id   UUID REFERENCES backtests(id) ON DELETE CASCADE,
    entry_time    TIMESTAMPTZ NOT NULL,
    exit_time     TIMESTAMPTZ NOT NULL,
    side          VARCHAR(10) NOT NULL,
    entry_price   NUMERIC(20,8) NOT NULL,
    exit_price    NUMERIC(20,8) NOT NULL,
    quantity      NUMERIC(20,8) NOT NULL,
    pnl           NUMERIC(20,8) NOT NULL,
    pnl_pct       NUMERIC(10,5) NOT NULL,
    exit_reason   VARCHAR(30)
);
CREATE INDEX IF NOT EXISTS idx_bt_trades_backtest ON backtest_trades (backtest_id);

-- ---------------------------------------------------------------
-- Rolling model-monitoring snapshots (for accuracy/calibration charts)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monitoring_snapshots (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id          UUID REFERENCES models(id),
    snapshot_date     DATE NOT NULL,
    daily_accuracy    NUMERIC(6,5),
    weekly_accuracy   NUMERIC(6,5),
    win_rate          NUMERIC(6,5),
    sharpe_ratio      NUMERIC(10,5),
    profit_factor     NUMERIC(10,5),
    max_drawdown      NUMERIC(6,5),
    calibration_curve JSONB,   -- [{bucket_mid, predicted, observed, n}]
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_id, snapshot_date)
);

-- ---------------------------------------------------------------
-- Admin-configurable settings (single-row config table)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_settings (
    id                      INTEGER PRIMARY KEY DEFAULT 1,
    trading_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    buy_prob_threshold      NUMERIC(4,3) NOT NULL DEFAULT 0.60,
    sell_prob_threshold     NUMERIC(4,3) NOT NULL DEFAULT 0.60,
    min_confidence          NUMERIC(4,3) NOT NULL DEFAULT 0.20,
    max_position_size_pct   NUMERIC(5,3) NOT NULL DEFAULT 0.10,  -- % of capital per trade
    max_open_positions      INTEGER NOT NULL DEFAULT 1,
    stop_loss_pct           NUMERIC(5,3) NOT NULL DEFAULT 0.02,
    take_profit_pct         NUMERIC(5,3) NOT NULL DEFAULT 0.04,
    daily_loss_limit_pct    NUMERIC(5,3) NOT NULL DEFAULT 0.05,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by              VARCHAR(50),
    CONSTRAINT single_row CHECK (id = 1)
);
INSERT INTO admin_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------
-- Audit log for admin changes (never-silent-changes principle)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id          BIGSERIAL PRIMARY KEY,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    changed_by  VARCHAR(50),
    field       VARCHAR(50) NOT NULL,
    old_value   TEXT,
    new_value   TEXT
);
