"""
The full retraining pipeline, runnable either from the APScheduler (weekly)
or via the manual "Retrain now" button in the Admin/Retraining UI.

Steps:
  1. Ingest latest data (daily ingestion also runs independently, but a
     retrain always refreshes first to avoid training on stale data).
  2. Generate features (handled inline via app.ml.features at train time).
  3. Train a new model version.
  4. Evaluate against the current champion on a held-out validation slice.
  5. Promote the new model to champion + active only if it's better
     (higher validation accuracy AND lower Brier score), otherwise keep
     the existing champion and simply register the new version for audit.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.db_models import RetrainJob, Model
from app.ml.train import train_model
from app.services.data_ingestion import backfill_history, get_recent_ohlcv_df

logger = logging.getLogger("retrain_job")


async def run_retrain_pipeline(job_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(RetrainJob).where(RetrainJob.id == job_id))
        job = result.scalars().first()
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        # 1. Refresh data
        await backfill_history(limit=1000)

        # 2 + 3. Build features & train (train_model builds features internally)
        df = await get_recent_ohlcv_df(limit=5000)
        if len(df) < 300:
            raise ValueError("Insufficient historical data to retrain (need >= 300 candles).")

        meta = train_model(df)

        async with AsyncSessionLocal() as session:
            new_model = Model(
                version=meta["version"], algorithm=meta["algorithm"],
                training_rows=meta["training_rows"], feature_list=meta["feature_list"],
                hyperparameters=meta["hyperparameters"], artifact_path=meta["artifact_path"],
                metrics=meta["metrics"], is_active=False, is_champion=False,
            )
            session.add(new_model)
            await session.commit()
            await session.refresh(new_model)

            # 4. Compare against current champion
            champ_result = await session.execute(select(Model).where(Model.is_champion == True))  # noqa: E712
            champion = champ_result.scalars().first()

            promote = False
            if champion is None:
                promote = True
            else:
                champ_metrics = champion.metrics or {}
                new_acc = meta["metrics"]["val_accuracy"]
                champ_acc = champ_metrics.get("val_accuracy", 0)
                new_brier = meta["metrics"]["val_brier_score"]
                champ_brier = champ_metrics.get("val_brier_score", 1)
                promote = (new_acc >= champ_acc) and (new_brier <= champ_brier)

            if promote:
                all_models = await session.execute(select(Model))
                for m in all_models.scalars().all():
                    m.is_champion = (m.id == new_model.id)
                    m.is_active = (m.id == new_model.id)
                new_model.notes = "Promoted: outperformed or matched previous champion."
            else:
                new_model.notes = "Trained but not promoted: did not beat current champion."

            await session.commit()

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(RetrainJob).where(RetrainJob.id == job_id))
            job = result.scalars().first()
            job.status = "success"
            job.finished_at = datetime.now(timezone.utc)
            job.result = {**(job.result or {}), "new_model_version": meta["version"],
                          "promoted": promote, "metrics": meta["metrics"]}
            await session.commit()

        logger.info("Retrain job %s finished: promoted=%s version=%s", job_id, promote, meta["version"])

    except Exception as exc:  # noqa: BLE001
        logger.exception("Retrain job %s failed", job_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(RetrainJob).where(RetrainJob.id == job_id))
            job = result.scalars().first()
            if job:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = str(exc)
                await session.commit()


async def run_daily_ingestion_job():
    """Standalone daily data-ingestion job (separate from weekly retrain)."""
    async with AsyncSessionLocal() as session:
        job = RetrainJob(job_type="ingestion", status="running", triggered_by="scheduler",
                          started_at=datetime.now(timezone.utc))
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = str(job.id)

    try:
        n = await backfill_history(limit=1500)
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(RetrainJob).where(RetrainJob.id == job_id))
            job = result.scalars().first()
            job.status = "success"
            job.finished_at = datetime.now(timezone.utc)
            job.result = {"candles_ingested": n}
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Daily ingestion job failed")
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(RetrainJob).where(RetrainJob.id == job_id))
            job = result.scalars().first()
            if job:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = str(exc)
                await session.commit()
