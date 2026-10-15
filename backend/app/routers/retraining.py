"""
Retraining system endpoints: view ingestion/retrain job history, trigger a
manual retrain, list model versions, and see which model is the champion
(best model currently selected to serve live signals).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.db_models import RetrainJob, Model
from app.schemas.schemas import RetrainJobOut, ModelOut, ManualRetrainRequest
from app.tasks.retrain_job import run_retrain_pipeline

router = APIRouter(prefix="/api/retraining", tags=["retraining"])


@router.get("/jobs", response_model=list[RetrainJobOut])
async def list_jobs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RetrainJob).order_by(RetrainJob.created_at.desc()).limit(limit))
    return list(result.scalars().all())


@router.get("/models", response_model=list[ModelOut])
async def list_models(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).order_by(Model.trained_at.desc()).limit(limit))
    return list(result.scalars().all())


@router.get("/models/champion", response_model=ModelOut | None)
async def get_champion(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).where(Model.is_champion == True))  # noqa: E712
    return result.scalars().first()


@router.post("/retrain", response_model=RetrainJobOut)
async def trigger_manual_retrain(
    payload: ManualRetrainRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Kicks off an async retraining job (ingestion -> features -> train -> evaluate -> promote)."""
    job = RetrainJob(job_type="retrain", status="pending", triggered_by="manual",
                      result={"reason": payload.reason})
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(run_retrain_pipeline, str(job.id))
    return job


@router.post("/models/{model_id}/activate", response_model=ModelOut)
async def activate_model(model_id: str, db: AsyncSession = Depends(get_db)):
    """Manually promote a specific model version to be the active (serving) model."""
    result = await db.execute(select(Model).where(Model.id == model_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(404, "Model not found")

    all_models = await db.execute(select(Model))
    for m in all_models.scalars().all():
        m.is_active = (m.id == target.id)
    await db.commit()
    await db.refresh(target)
    return target
