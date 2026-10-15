"""
Backtesting endpoints: run a new backtest over a historical window using
the current champion model, and fetch past backtest results (equity curve,
trade log, monthly returns, performance metrics).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.db_models import Backtest, BacktestTrade, Model, OHLCV
from app.schemas.schemas import BacktestRequest, BacktestOut, TradeOut
from app.ml.train import load_model
from app.services.backtest_engine import run_backtest

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestOut)
async def run_new_backtest(req: BacktestRequest, db: AsyncSession = Depends(get_db)):
    champ_result = await db.execute(select(Model).where(Model.is_champion == True))  # noqa: E712
    champion = champ_result.scalars().first()
    if not champion:
        raise HTTPException(400, "No champion model available yet. Train a model first.")

    price_result = await db.execute(
        select(OHLCV).where(OHLCV.open_time >= req.period_start, OHLCV.open_time <= req.period_end)
        .order_by(OHLCV.open_time.asc())
    )
    rows = price_result.scalars().all()
    if len(rows) < 100:
        raise HTTPException(400, "Not enough historical candles in the requested window (need >= 100).")

    import pandas as pd
    df = pd.DataFrame([{
        "open_time": r.open_time, "open": float(r.open), "high": float(r.high),
        "low": float(r.low), "close": float(r.close), "volume": float(r.volume),
    } for r in rows])

    model, _ = load_model(champion.artifact_path)

    result = run_backtest(
        df, model, initial_capital=req.initial_capital,
        buy_prob_threshold=req.buy_prob_threshold, sell_prob_threshold=req.sell_prob_threshold,
        stop_loss_pct=req.stop_loss_pct, take_profit_pct=req.take_profit_pct,
        position_size_pct=req.position_size_pct,
    )

    bt = Backtest(
        model_id=champion.id, period_start=req.period_start, period_end=req.period_end,
        initial_capital=req.initial_capital,
        params=req.model_dump(mode="json"),
        metrics=result["metrics"], equity_curve=result["equity_curve"],
        monthly_returns=result["monthly_returns"],
    )
    db.add(bt)
    await db.commit()
    await db.refresh(bt)

    trade_rows = [
        BacktestTrade(backtest_id=bt.id, **{k: v for k, v in t.items()})
        for t in result["trades"]
    ]
    if trade_rows:
        db.add_all(trade_rows)
        await db.commit()

    return BacktestOut(
        id=bt.id, period_start=bt.period_start, period_end=bt.period_end,
        initial_capital=float(bt.initial_capital), metrics=bt.metrics,
        equity_curve=bt.equity_curve, monthly_returns=bt.monthly_returns,
        trades=[TradeOut(**t) for t in result["trades"]],
    )


@router.get("/{backtest_id}", response_model=BacktestOut)
async def get_backtest(backtest_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Backtest).where(Backtest.id == backtest_id))
    bt = result.scalars().first()
    if not bt:
        raise HTTPException(404, "Backtest not found")

    trades_result = await db.execute(select(BacktestTrade).where(BacktestTrade.backtest_id == bt.id))
    trades = trades_result.scalars().all()

    return BacktestOut(
        id=bt.id, period_start=bt.period_start, period_end=bt.period_end,
        initial_capital=float(bt.initial_capital), metrics=bt.metrics or {},
        equity_curve=bt.equity_curve or [], monthly_returns=bt.monthly_returns or [],
        trades=[TradeOut(
            entry_time=t.entry_time, exit_time=t.exit_time, side=t.side,
            entry_price=float(t.entry_price), exit_price=float(t.exit_price),
            quantity=float(t.quantity), pnl=float(t.pnl), pnl_pct=float(t.pnl_pct),
            exit_reason=t.exit_reason,
        ) for t in trades],
    )


@router.get("", response_model=list[BacktestOut])
async def list_backtests(limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Backtest).order_by(Backtest.started_at.desc()).limit(limit))
    backtests = result.scalars().all()
    out = []
    for bt in backtests:
        out.append(BacktestOut(
            id=bt.id, period_start=bt.period_start, period_end=bt.period_end,
            initial_capital=float(bt.initial_capital), metrics=bt.metrics or {},
            equity_curve=bt.equity_curve or [], monthly_returns=bt.monthly_returns or [], trades=[],
        ))
    return out
