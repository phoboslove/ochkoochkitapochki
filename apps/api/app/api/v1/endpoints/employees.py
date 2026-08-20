from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.audit.logger import AuditLogger
from app.services.reference_data import service as ref_service

router = APIRouter()
audit = AuditLogger()


class EmployeeIn(BaseModel):
    full_name: str
    iin: str | None = None
    position: str | None = None
    department: str | None = None
    hire_date: datetime | None = None
    salary: float | None = None
    allowances: float | None = None
    probation_period: str | None = None
    work_schedule: str | None = None
    vacation_days: int = 24
    address: str | None = None
    id_doc_number: str | None = None
    id_doc_issued_by: str | None = None
    id_doc_date: str | None = None


class EmployeePatch(BaseModel):
    full_name: str | None = None
    iin: str | None = None
    position: str | None = None
    department: str | None = None
    hire_date: datetime | None = None
    salary: float | None = None
    allowances: float | None = None
    probation_period: str | None = None
    work_schedule: str | None = None
    vacation_days: int | None = None
    address: str | None = None
    id_doc_number: str | None = None
    id_doc_issued_by: str | None = None
    id_doc_date: str | None = None


def _serialize(e) -> dict:
    return {
        "id": e.id, "full_name": e.full_name, "iin": e.iin, "position": e.position,
        "department": e.department,
        "hire_date": e.hire_date.isoformat() if e.hire_date else None,
        "salary": float(e.salary) if e.salary is not None else None,
        "allowances": float(e.allowances) if e.allowances is not None else None,
        "probation_period": e.probation_period, "work_schedule": e.work_schedule,
        "vacation_days": e.vacation_days, "address": e.address,
        "id_doc_number": e.id_doc_number, "id_doc_issued_by": e.id_doc_issued_by,
        "id_doc_date": e.id_doc_date, "created_at": e.created_at.isoformat(),
    }


@router.get("")
async def list_employees(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await ref_service.list_employees(session, user.company_id)
    return [_serialize(e) for e in rows]


@router.get("/{employee_id}")
async def get_employee(
    employee_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await ref_service.get_employee(session, user.company_id, employee_id)
    if not row:
        raise HTTPException(404, "employee not found")
    return _serialize(row)


@router.post("")
async def create_employee(
    body: EmployeeIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        row = await ref_service.create_employee(session, user.company_id, **body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                        action="employee.created", resource=row.id, meta={"full_name": row.full_name})
    await session.commit()
    return _serialize(row)


@router.patch("/{employee_id}")
async def update_employee(
    employee_id: str, body: EmployeePatch,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await ref_service.update_employee(
        session, user.company_id, employee_id,
        **{k: v for k, v in body.model_dump().items() if v is not None},
    )
    if not row:
        raise HTTPException(404, "employee not found")
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                        action="employee.updated", resource=row.id)
    await session.commit()
    return _serialize(row)


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ok = await ref_service.delete_employee(session, user.company_id, employee_id)
    if not ok:
        raise HTTPException(404, "employee not found")
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                        action="employee.deleted", resource=employee_id)
    await session.commit()
    return {"deleted": True}
