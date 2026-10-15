"""
Pydantic schemas for API request/response validation.
Note: all model outputs are probabilities in (0, 1) — the system never
emits a bare 0, 1, or a "certain" claim. See app.ml.signal_engine.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------- Dashboard
class CandleOut(BaseModel):
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class SignalOut(BaseModel):
    id: UUID
    generated_at: datetime
    action: str = Field(description="BUY | SELL | HOLD")
    prob_up: float = Field(ge=0, le=1)
    prob_down: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    price_at_signal: float
    explanation: Optional[Dict[str, Any]] = None
    disclaimer: str = "Probabilistic estimate only. Not a guarantee of future price movement."

    model_config = ConfigDict(from_attributes=True)


class PositionOut(BaseModel):
    id: UUID
    side: str
    status: str
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    opened_at: datetime
    closed_at: Optional[datetime]
    pnl: Optional[float]
    pnl_pct: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    symbol: str
    latest_price: float
    latest_signal: Optional[SignalOut]
    open_positions: List[PositionOut]
    realized_pnl_today: float
    unrealized_pnl: float
    trading_enabled: bool


# ---------------------------------------------------------------- Monitoring
class CalibrationPoint(BaseModel):
    bucket_mid: float
    predicted: float
    observed: float
    n: int


class MonitoringOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: Optional[str]
    daily_accuracy: Optional[float]
    weekly_accuracy: Optional[float]
    win_rate: Optional[float]
    sharpe_ratio: Optional[float]
    profit_factor: Optional[float]
    max_drawdown: Optional[float]
    calibration_curve: List[CalibrationPoint] = []
    snapshot_date: Optional[str]


# ---------------------------------------------------------------- Retraining
class RetrainJobOut(BaseModel):
    id: UUID
    job_type: str
    status: str
    triggered_by: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ModelOut(BaseModel):
    id: UUID
    version: str
    algorithm: str
    trained_at: datetime
    training_rows: Optional[int]
    is_active: bool
    is_champion: bool
    metrics: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class ManualRetrainRequest(BaseModel):
    reason: Optional[str] = "manual_trigger"


# ---------------------------------------------------------------- Backtest
class BacktestRequest(BaseModel):
    period_start: datetime
    period_end: datetime
    initial_capital: float = 10000
    buy_prob_threshold: float = 0.60
    sell_prob_threshold: float = 0.60
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    position_size_pct: float = 0.10


class TradeOut(BaseModel):
    entry_time: datetime
    exit_time: datetime
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    exit_reason: Optional[str]


class BacktestOut(BaseModel):
    id: UUID
    period_start: datetime
    period_end: datetime
    initial_capital: float
    metrics: Dict[str, Any]
    equity_curve: List[Dict[str, Any]]
    monthly_returns: List[Dict[str, Any]]
    trades: List[TradeOut] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- Admin
class AdminSettingsOut(BaseModel):
    trading_enabled: bool
    buy_prob_threshold: float
    sell_prob_threshold: float
    min_confidence: float
    max_position_size_pct: float
    max_open_positions: int
    stop_loss_pct: float
    take_profit_pct: float
    daily_loss_limit_pct: float
    updated_at: datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AdminSettingsUpdate(BaseModel):
    trading_enabled: Optional[bool] = None
    buy_prob_threshold: Optional[float] = Field(None, ge=0.5, le=0.99)
    sell_prob_threshold: Optional[float] = Field(None, ge=0.5, le=0.99)
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    max_position_size_pct: Optional[float] = Field(None, gt=0, le=1)
    max_open_positions: Optional[int] = Field(None, ge=1, le=20)
    stop_loss_pct: Optional[float] = Field(None, gt=0, le=0.5)
    take_profit_pct: Optional[float] = Field(None, gt=0, le=1)
    daily_loss_limit_pct: Optional[float] = Field(None, gt=0, le=1)
    updated_by: Optional[str] = "admin"
