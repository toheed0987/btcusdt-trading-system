"""
APScheduler jobs:
  - Daily new-data ingestion (every day at 00:15 UTC)
  - Weekly automatic retraining (configurable via RETRAIN_CRON, default Monday 03:00 UTC)
  - Live signal generation loop (every minute, publishes to WS + persists signal)
  - Nightly monitoring snapshot (recomputes accuracy/calibration for the dashboard)
"""
import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import RetrainJob, Model, Signal, AdminSettings
from app.tasks.retrain_job import run_daily_ingestion_job, run_retrain_pipeline
from app.services.data_ingestion import get_recent_ohlcv_df
from app.ml.features import FEATURE_COLUMNS, latest_feature_row, build_features
from app.ml.train import load_model
from app.ml.explain import explain_prediction
from app.ml.signal_engine import generate_signal
from app.services import redis_cache
from app.tasks.monitoring_job import compute_daily_monitoring_snapshot

logger = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler(timezone="UTC")


async def _weekly_retrain_wrapper():
    async with AsyncSessionLocal() as session:
        job = RetrainJob(job_type="retrain", status="pending", triggered_by="scheduler")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = str(job.id)
    await run_retrain_pipeline(job_id)


async def generate_live_signal():
    """Runs every minute: scores the latest candle with the active model and
    persists + broadcasts a fresh probabilistic signal."""
    async with AsyncSessionLocal() as session:
        active_result = await session.execute(select(Model).where(Model.is_active == True))  # noqa: E712
        active_model = active_result.scalars().first()
        settings_result = await session.execute(select(AdminSettings).where(AdminSettings.id == 1))
        admin = settings_result.scalars().first()

    if not active_model:
        logger.debug("No active model yet; skipping live signal generation.")
        return

    df = await get_recent_ohlcv_df(limit=500)
    if len(df) < 60:
        return

    model, feature_columns = load_model(active_model.artifact_path)
    feat_row = latest_feature_row(df)
    prob_up = float(model.predict_proba(feat_row)[:, 1][0])

    background = build_features(df).fillna(0)[FEATURE_COLUMNS].iloc[-200:]
    try:
        explanation = explain_prediction(model, active_model.version, feat_row, background)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SHAP explanation failed, continuing without it: %s", exc)
        explanation = {}

    thresholds = {
        "buy_prob_threshold": float(admin.buy_prob_threshold) if admin else 0.6,
        "sell_prob_threshold": float(admin.sell_prob_threshold) if admin else 0.6,
        "min_confidence": float(admin.min_confidence) if admin else 0.2,
    }
    sig = generate_signal(prob_up, thresholds["buy_prob_threshold"], thresholds["sell_prob_threshold"],
                           thresholds["min_confidence"], explanation=explanation)

    price = float(df.iloc[-1]["close"])

    async with AsyncSessionLocal() as session:
        db_signal = Signal(
            model_id=active_model.id, action=sig.action, prob_up=sig.prob_up,
            prob_down=sig.prob_down, confidence=sig.confidence, price_at_signal=price,
            explanation=sig.explanation, threshold_used=thresholds,
        )
        session.add(db_signal)
        await session.commit()
        await session.refresh(db_signal)

    payload = {
        "type": "signal", "id": str(db_signal.id), "action": sig.action,
        "prob_up": sig.prob_up, "prob_down": sig.prob_down, "confidence": sig.confidence,
        "price": price, "explanation": sig.explanation, "reasons": sig.reasons,
        "disclaimer": sig.disclaimer, "generated_at": db_signal.generated_at.isoformat(),
    }
    await redis_cache.set_json(redis_cache.LATEST_SIGNAL_KEY, payload, ex_seconds=300)
    await redis_cache.publish(redis_cache.SIGNAL_CHANNEL, payload)


def start_scheduler():
    scheduler.add_job(run_daily_ingestion_job, CronTrigger(hour=0, minute=15), id="daily_ingestion",
                       replace_existing=True)
    scheduler.add_job(_weekly_retrain_wrapper, CronTrigger.from_crontab(settings.RETRAIN_CRON),
                       id="weekly_retrain", replace_existing=True)
    scheduler.add_job(generate_live_signal, "interval", minutes=1, id="live_signal", replace_existing=True)
    scheduler.add_job(compute_daily_monitoring_snapshot, CronTrigger(hour=0, minute=30),
                       id="daily_monitoring", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started: daily ingestion 00:15 UTC, retrain '%s', live signal every 1m, "
                "monitoring snapshot 00:30 UTC", settings.RETRAIN_CRON)
