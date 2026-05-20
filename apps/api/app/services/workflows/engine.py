"""Workflow engine.

Workflows are DAGs persisted as JSON: {nodes: [{key, type, config}], edges}.
`WorkflowEngine` triggers a run, the `Runner` walks the graph and dispatches
each step to the appropriate executor. Designed so the execution backend can
be swapped (LangGraph, Temporal) without changing the persistence model.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.services.workflows.runner import Runner

_DEMO_WORKFLOWS = [
    {
        "id": "wf_whatsapp_invoice",
        "name": "WhatsApp → Invoice",
        "trigger": "whatsapp.message",
        "enabled": True,
        "graph": {
            "nodes": [
                {"key": "parse", "type": "ai.parse_intent"},
                {"key": "lead", "type": "crm.upsert_client"},
                {"key": "invoice", "type": "invoice.create_draft"},
                {"key": "approve", "type": "approval.request"},
                {"key": "send", "type": "whatsapp.send_pdf"},
            ],
            "edges": [
                ["parse", "lead"], ["lead", "invoice"],
                ["invoice", "approve"], ["approve", "send"],
            ],
        },
    },
    {
        "id": "wf_monthly_report",
        "name": "Monthly accounting report",
        "trigger": "schedule:monthly",
        "enabled": True,
        "graph": {
            "nodes": [
                {"key": "collect", "type": "accounting.collect"},
                {"key": "report", "type": "report.render"},
                {"key": "email", "type": "email.send"},
            ],
            "edges": [["collect", "report"], ["report", "email"]],
        },
    },
]


class WorkflowEngine:
    def __init__(self) -> None:
        self.runner = Runner()
        self._runs: dict[str, list[dict]] = {}

    def list_demo(self) -> list[dict]:
        return _DEMO_WORKFLOWS

    async def trigger(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        wf = next((w for w in _DEMO_WORKFLOWS if w["id"] == workflow_id), None)
        if not wf:
            return {"error": "workflow not found"}
        run = await self.runner.execute(wf, payload)
        self._runs.setdefault(workflow_id, []).append(run)
        return run

    def list_runs(self, workflow_id: str) -> list[dict]:
        return self._runs.get(workflow_id, [])
