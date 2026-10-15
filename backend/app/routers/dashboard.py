"""
Dashboard endpoints: live chart data, current signal, probabilities,
confidence, open positions, and PnL.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import OHLCV, Signal, Position, AdminSettings
from app.schemas.schemas import CandleOut, SignalOut, PositionOut, DashboardSummary
from app.services import redis_cache
from app.config import settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/candles", response_model=list[CandleOut])
async def get_candles(
    symbol: str = Query(default=settings.SYMBOL),
    limit: int = Query(default=200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OHLCV).where(OHLCV.symbol == symbol, OHLCV.interval == "1m")
        .order_by(OHLCV.open_time.desc()).limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [CandleOut(open_time=r.open_time, open=float(r.open), high=float(r.high),
                       low=float(r.low), close=float(r.close), volume=float(r.volume))
            for r in rows]


@router.get("/latest-signal", response_model=SignalOut | None)
async def get_latest_signal(symbol: str = Query(default=settings.SYMBOL), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Signal).where(Signal.symbol == symbol).order_by(Signal.generated_at.desc()).limit(1)
    )
    sig = result.scalars().first()
    if not sig:
        return None
    return SignalOut(
        id=sig.id, generated_at=sig.generated_at, action=sig.action,
        prob_up=float(sig.prob_up), prob_down=float(sig.prob_down),
        confidence=float(sig.confidence), price_at_signal=float(sig.price_at_signal),
        explanation=sig.explanation,
    )


@router.get("/positions", response_model=list[PositionOut])
async def get_open_positions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Position).where(Position.status == "OPEN"))
    return list(result.scalars().all())


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(symbol: str = Query(default=settings.SYMBOL), db: AsyncSession = Depends(get_db)):
    price_data = await redis_cache.get_json(redis_cache.LATEST_PRICE_KEY)
    latest_price = price_data["price"] if price_data else 0.0

    sig_result = await db.execute(
        select(Signal).where(Signal.symbol == symbol).order_by(Signal.generated_at.desc()).limit(1)
    )
    sig = sig_result.scalars().first()
    latest_signal = None
    if sig:
        latest_signal = SignalOut(
            id=sig.id, generated_at=sig.generated_at, action=sig.action,
            prob_up=float(sig.prob_up), prob_down=float(sig.prob_down),
            confidence=float(sig.confidence), price_at_signal=float(sig.price_at_signal),
            explanation=sig.explanation,
        )

    open_result = await db.execute(select(Position).where(Position.status == "OPEN"))
    open_positions = list(open_result.scalars().all())

    unrealized = 0.0
    for p in open_positions:
        if latest_price:
            diff = (latest_price - float(p.entry_price)) if p.side == "LONG" else (float(p.entry_price) - latest_price)
            unrealized += diff * float(p.quantity)

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    realized_result = await db.execute(
        select(func.coalesce(func.sum(Position.pnl), 0)).where(
            Position.status == "CLOSED", Position.closed_at >= today_start
        )
    )
    realized_today = float(realized_result.scalar() or 0)

    settings_result = await db.execute(select(AdminSettings).where(AdminSettings.id == 1))
    admin = settings_result.scalars().first()

    return DashboardSummary(
        symbol=symbol, latest_price=latest_price, latest_signal=latest_signal,
        open_positions=open_positions, realized_pnl_today=realized_today,
        unrealized_pnl=round(unrealized, 2),
        trading_enabled=bool(admin.trading_enabled) if admin else False,
    )
