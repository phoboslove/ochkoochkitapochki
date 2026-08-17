"""Tax reference + deterministic calculators — Block 3's dedicated-page path.

Same calculation functions the AI tools call
(``app/services/tax/calculators.py``) — this endpoint exists so users who'd
rather fill in a form than type into chat get identical, deterministic
numbers either way.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, get_current_user
from app.services.tax.calculators import calculate_salary, calculate_turnover_tax
from app.services.tax.rates import disclaimer, load_rates

router = APIRouter()


@router.get("/rates")
async def rates_summary(_user: CurrentUser = Depends(get_current_user)) -> dict:
    r = load_rates()
    return {
        "effective_date": r["effective_date"],
        "last_verified": r["last_verified"],
        "disclaimer": disclaimer(),
        "base_values": r["base_values"],
    }


class SalaryCalcRequest(BaseModel):
    gross: float = Field(..., gt=0, description="Monthly gross salary (оклад), KZT")


@router.post("/calculate/salary")
async def calculate_salary_endpoint(
    body: SalaryCalcRequest, _user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        return calculate_salary(body.gross).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class TurnoverCalcRequest(BaseModel):
    turnover: float = Field(..., gt=0, description="Period turnover/оборот, KZT")
    rate: float | None = Field(None, gt=0, lt=1, description="Override regional rate (0.02-0.06)")


@router.post("/calculate/turnover")
async def calculate_turnover_endpoint(
    body: TurnoverCalcRequest, _user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        return calculate_turnover_tax(body.turnover, rate=body.rate).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
