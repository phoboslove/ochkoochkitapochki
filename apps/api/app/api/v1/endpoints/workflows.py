from fastapi import APIRouter

from app.services.workflows.engine import WorkflowEngine

router = APIRouter()
engine = WorkflowEngine()


@router.get("")
async def list_workflows() -> list[dict]:
    return engine.list_demo()


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, payload: dict) -> dict:
    return await engine.trigger(workflow_id, payload)


@router.get("/{workflow_id}/runs")
async def list_runs(workflow_id: str) -> list[dict]:
    return engine.list_runs(workflow_id)
