"""
SQLAlchemy ORM models mirroring db/init.sql.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class OHLCV(Base):
    __tablename__ = "ohlcv"

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20), nullable=False, default="BTCUSDT")
    open_time = Column(DateTime(timezone=True), nullable=False)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(28, 8), nullable=False)
    interval = Column(String(5), nullable=False, default="1m")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("symbol", "interval", "open_time"),)


class Feature(Base):
    __tablename__ = "features"

    id = Column(BigInteger, primary_key=True)
    ohlcv_id = Column(BigInteger, ForeignKey("ohlcv.id", ondelete="CASCADE"))
    symbol = Column(String(20), nullable=False)
    open_time = Column(DateTime(timezone=True), nullable=False)
    feature_set = Column(JSONB, nullable=False)
    label_up = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("symbol", "open_time"),)


class Model(Base):
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String(50), nullable=False, unique=True)
    algorithm = Column(String(50), nullable=False)
    trained_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    training_rows = Column(Integer)
    feature_list = Column(JSONB)
    hyperparameters = Column(JSONB)
    artifact_path = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False)
    is_champion = Column(Boolean, default=False)
    metrics = Column(JSONB)
    notes = Column(Text)


class RetrainJob(Base):
    __tablename__ = "retrain_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(20), nullable=False)  # ingestion | feature_gen | retrain
    status = Column(String(20), default="pending")
    triggered_by = Column(String(20), default="scheduler")
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONB)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"))
    symbol = Column(String(20), default="BTCUSDT")
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    action = Column(String(10), nullable=False)  # BUY | SELL | HOLD
    prob_up = Column(Numeric(6, 5), nullable=False)
    prob_down = Column(Numeric(6, 5), nullable=False)
    confidence = Column(Numeric(6, 5), nullable=False)
    price_at_signal = Column(Numeric(20, 8), nullable=False)
    explanation = Column(JSONB)
    threshold_used = Column(JSONB)


class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"))
    symbol = Column(String(20), default="BTCUSDT")
    side = Column(String(10), nullable=False)  # LONG | SHORT
    status = Column(String(10), default="OPEN")
    entry_price = Column(Numeric(20, 8), nullable=False)
    exit_price = Column(Numeric(20, 8))
    quantity = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8))
    take_profit = Column(Numeric(20, 8))
    opened_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    closed_at = Column(DateTime(timezone=True))
    pnl = Column(Numeric(20, 8))
    pnl_pct = Column(Numeric(10, 5))
    close_reason = Column(String(30))


class Backtest(Base):
    __tablename__ = "backtests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"))
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    initial_capital = Column(Numeric(20, 8), default=10000)
    params = Column(JSONB)
    metrics = Column(JSONB)
    equity_curve = Column(JSONB)
    monthly_returns = Column(JSONB)
    status = Column(String(20), default="completed")

    trades = relationship("BacktestTrade", backref="backtest", cascade="all, delete-orphan")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id = Column(BigInteger, primary_key=True)
    backtest_id = Column(UUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"))
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=False)
    side = Column(String(10), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    exit_price = Column(Numeric(20, 8), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    pnl = Column(Numeric(20, 8), nullable=False)
    pnl_pct = Column(Numeric(10, 5), nullable=False)
    exit_reason = Column(String(30))


class MonitoringSnapshot(Base):
    __tablename__ = "monitoring_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"))
    snapshot_date = Column(Date, nullable=False)
    daily_accuracy = Column(Numeric(6, 5))
    weekly_accuracy = Column(Numeric(6, 5))
    win_rate = Column(Numeric(6, 5))
    sharpe_ratio = Column(Numeric(10, 5))
    profit_factor = Column(Numeric(10, 5))
    max_drawdown = Column(Numeric(6, 5))
    calibration_curve = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("model_id", "snapshot_date"),)


class AdminSettings(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, default=1)
    trading_enabled = Column(Boolean, default=False)
    buy_prob_threshold = Column(Numeric(4, 3), default=0.60)
    sell_prob_threshold = Column(Numeric(4, 3), default=0.60)
    min_confidence = Column(Numeric(4, 3), default=0.20)
    max_position_size_pct = Column(Numeric(5, 3), default=0.10)
    max_open_positions = Column(Integer, default=1)
    stop_loss_pct = Column(Numeric(5, 3), default=0.02)
    take_profit_pct = Column(Numeric(5, 3), default=0.04)
    daily_loss_limit_pct = Column(Numeric(5, 3), default=0.05)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_by = Column(String(50))


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id = Column(BigInteger, primary_key=True)
    changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    changed_by = Column(String(50))
    field = Column(String(50), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
