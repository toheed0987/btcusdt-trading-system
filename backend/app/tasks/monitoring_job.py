"""
Nightly job that evaluates the active model's recent real-world performance:
compares each past signal's prob_up against what actually happened
`PREDICTION_HORIZON_MINUTES` later, then derives accuracy, win rate, Sharpe,
profit factor, max drawdown, and a calibration curve for the Monitoring page.
"""
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import Model, Signal, Position, MonitoringSnapshot, OHLCV

logger = logging.getLogger("monitoring_job")


async def compute_daily_monitoring_snapshot():
    async with AsyncSessionLocal() as session:
        active_result = await session.execute(select(Model).where(Model.is_active == True))  # noqa: E712
        active_model = active_result.scalars().first()
        if not active_model:
            logger.info("No active model; skipping monitoring snapshot.")
            return

        now = datetime.now(timezone.utc)
        horizon = timedelta(minutes=settings.PREDICTION_HORIZON_MINUTES)

        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        sig_result = await session.execute(
            select(Signal).where(Signal.model_id == active_model.id, Signal.generated_at >= week_ago)
            .order_by(Signal.generated_at.asc())
        )
        signals = sig_result.scalars().all()

        price_result = await session.execute(
            select(OHLCV).where(OHLCV.symbol == settings.SYMBOL, OHLCV.interval == "1m",
                                 OHLCV.open_time >= week_ago - horizon)
            .order_by(OHLCV.open_time.asc())
        )
        candles = price_result.scalars().all()
        price_series = pd.Series(
            {c.open_time: float(c.close) for c in candles}
        ).sort_index()

        def outcome_for(sig_time, ref_price):
            future_time_target = sig_time + horizon
            idx = price_series.index.searchsorted(future_time_target)
            if idx >= len(price_series):
                return None
            future_price = price_series.iloc[idx]
            return 1 if future_price > ref_price else 0

        daily_correct, daily_total = 0, 0
        weekly_correct, weekly_total = 0, 0
        calibration_buckets = {b: {"correct": 0, "total": 0, "prob_sum": 0.0} for b in np.arange(0.0, 1.0, 0.1)}

        for sig in signals:
            actual = outcome_for(sig.generated_at, float(sig.price_at_signal))
            if actual is None:
                continue
            predicted_up = float(sig.prob_up) >= 0.5
            correct = int(predicted_up == bool(actual))

            weekly_total += 1
            weekly_correct += correct
            if sig.generated_at >= day_ago:
                daily_total += 1
                daily_correct += correct

            bucket = min(0.9, np.floor(float(sig.prob_up) * 10) / 10)
            calibration_buckets[bucket]["total"] += 1
            calibration_buckets[bucket]["correct"] += actual
            calibration_buckets[bucket]["prob_sum"] += float(sig.prob_up)

        calibration_curve = []
        for bucket_mid, stats in sorted(calibration_buckets.items()):
            if stats["total"] == 0:
                continue
            calibration_curve.append({
                "bucket_mid": round(bucket_mid + 0.05, 3),
                "predicted": round(stats["prob_sum"] / stats["total"], 4),
                "observed": round(stats["correct"] / stats["total"], 4),
                "n": stats["total"],
            })

        pos_result = await session.execute(
            select(Position).where(Position.status == "CLOSED", Position.closed_at >= week_ago)
        )
        closed_positions = pos_result.scalars().all()
        pnls = [float(p.pnl) for p in closed_positions if p.pnl is not None]

        win_rate = (sum(1 for p in pnls if p > 0) / len(pnls)) if pnls else None
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p <= 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        sharpe_ratio = None
        max_drawdown = None
        if pnls:
            returns = np.array(pnls)
            if returns.std() > 0:
                sharpe_ratio = float(returns.mean() / returns.std() * np.sqrt(len(returns)))
            cumulative = np.cumsum(pnls)
            running_max = np.maximum.accumulate(cumulative) if len(cumulative) else np.array([0])
            drawdowns = cumulative - running_max
            max_drawdown = float(drawdowns.min()) if len(drawdowns) else 0.0

        snapshot = MonitoringSnapshot(
            model_id=active_model.id,
            snapshot_date=now.date(),
            daily_accuracy=(daily_correct / daily_total) if daily_total else None,
            weekly_accuracy=(weekly_correct / weekly_total) if weekly_total else None,
            win_rate=win_rate,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            calibration_curve=calibration_curve,
        )
        session.add(snapshot)
        await session.commit()
        logger.info("Monitoring snapshot computed for model %s", active_model.version)
