"""
Admin panel endpoints: read/update probability thresholds, trading
enable/disable toggle, risk settings, stop-loss/take-profit config.
Every change is written to admin_audit_log for traceability.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import AdminSettings, AdminAuditLog
from app.schemas.schemas import AdminSettingsOut, AdminSettingsUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminSettings).where(AdminSettings.id == 1))
    return result.scalars().first()


@router.put("/settings", response_model=AdminSettingsOut)
async def update_settings(payload: AdminSettingsUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminSettings).where(AdminSettings.id == 1))
    settings_row = result.scalars().first()

    updates = payload.model_dump(exclude_unset=True, exclude={"updated_by"})
    for field, new_value in updates.items():
        old_value = getattr(settings_row, field)
        if str(old_value) != str(new_value):
            db.add(AdminAuditLog(
                changed_by=payload.updated_by or "admin", field=field,
                old_value=str(old_value), new_value=str(new_value),
            ))
        setattr(settings_row, field, new_value)

    settings_row.updated_by = payload.updated_by or "admin"
    await db.commit()
    await db.refresh(settings_row)
    return settings_row


@router.get("/audit-log")
async def get_audit_log(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminAuditLog).order_by(AdminAuditLog.changed_at.desc()).limit(limit))
    rows = result.scalars().all()
    return [{"changed_at": r.changed_at, "changed_by": r.changed_by, "field": r.field,
             "old_value": r.old_value, "new_value": r.new_value} for r in rows]
