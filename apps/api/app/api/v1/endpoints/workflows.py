"""Workflow endpoints — list, trigger, and inspect demo workflows.

SECURITY: every route requires a logged-in user and operates within that
user's company. Anonymous workflow triggering was the original release
blocker (CRITICAL #1 of the beta audit).
"""
from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, get_current_user, require_admin
from app.services.workflows.engine import WorkflowEngine

router = APIRouter()
engine = WorkflowEngine()


@router.get("")
async def list_workflows(
    _user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Return the demo workflow catalogue. Authenticated only."""
    return engine.list_demo()


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    payload: dict,
    # Triggering a workflow is a write-side action — require an admin so
    # an ordinary MEMBER can't fire AI/billing-touching graphs.
    _user: CurrentUser = Depends(require_admin),
) -> dict:
    return await engine.trigger(workflow_id, payload)


@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    return engine.list_runs(workflow_id)
