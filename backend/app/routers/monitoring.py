"""
Model monitoring endpoints: daily/weekly accuracy, win rate, Sharpe,
profit factor, max drawdown, and calibration curve for the active model.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import Model, MonitoringSnapshot
from app.schemas.schemas import MonitoringOut, CalibrationPoint

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/current", response_model=MonitoringOut)
async def get_current_monitoring(db: AsyncSession = Depends(get_db)):
    active_result = await db.execute(select(Model).where(Model.is_active == True))  # noqa: E712
    active_model = active_result.scalars().first()

    if not active_model:
        return MonitoringOut(
            model_version=None, daily_accuracy=None, weekly_accuracy=None,
            win_rate=None, sharpe_ratio=None, profit_factor=None, max_drawdown=None,
            calibration_curve=[], snapshot_date=None,
        )

    snap_result = await db.execute(
        select(MonitoringSnapshot)
        .where(MonitoringSnapshot.model_id == active_model.id)
        .order_by(MonitoringSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = snap_result.scalars().first()

    if not snap:
        return MonitoringOut(
            model_version=active_model.version, daily_accuracy=None, weekly_accuracy=None,
            win_rate=None, sharpe_ratio=None, profit_factor=None, max_drawdown=None,
            calibration_curve=[], snapshot_date=None,
        )

    calibration = [CalibrationPoint(**pt) for pt in (snap.calibration_curve or [])]

    return MonitoringOut(
        model_version=active_model.version,
        daily_accuracy=float(snap.daily_accuracy) if snap.daily_accuracy is not None else None,
        weekly_accuracy=float(snap.weekly_accuracy) if snap.weekly_accuracy is not None else None,
        win_rate=float(snap.win_rate) if snap.win_rate is not None else None,
        sharpe_ratio=float(snap.sharpe_ratio) if snap.sharpe_ratio is not None else None,
        profit_factor=float(snap.profit_factor) if snap.profit_factor is not None else None,
        max_drawdown=float(snap.max_drawdown) if snap.max_drawdown is not None else None,
        calibration_curve=calibration,
        snapshot_date=snap.snapshot_date.isoformat() if snap.snapshot_date else None,
    )


@router.get("/history")
async def get_monitoring_history(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Time series of daily snapshots for trend charts."""
    result = await db.execute(
        select(MonitoringSnapshot).order_by(MonitoringSnapshot.snapshot_date.desc()).limit(days)
    )
    rows = list(reversed(result.scalars().all()))
    return [
        {
            "date": r.snapshot_date.isoformat(),
            "daily_accuracy": float(r.daily_accuracy) if r.daily_accuracy is not None else None,
            "weekly_accuracy": float(r.weekly_accuracy) if r.weekly_accuracy is not None else None,
            "win_rate": float(r.win_rate) if r.win_rate is not None else None,
            "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio is not None else None,
            "profit_factor": float(r.profit_factor) if r.profit_factor is not None else None,
            "max_drawdown": float(r.max_drawdown) if r.max_drawdown is not None else None,
        }
        for r in rows
    ]
