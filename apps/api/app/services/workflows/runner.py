"""Workflow runner — topological walk + step executors."""
from __future__ import annotations

import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


StepFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


class Runner:
    def __init__(self) -> None:
        self._executors: dict[str, StepFn] = _default_executors()

    async def execute(self, workflow: dict, payload: dict[str, Any]) -> dict[str, Any]:
        nodes = {n["key"]: n for n in workflow["graph"]["nodes"]}
        edges = workflow["graph"]["edges"]
        indeg: dict[str, int] = defaultdict(int)
        out: dict[str, list[str]] = defaultdict(list)
        for a, b in edges:
            indeg[b] += 1
            out[a].append(b)
        queue = deque([k for k in nodes if indeg[k] == 0])

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        steps: list[dict] = []
        ctx: dict[str, Any] = {"payload": payload, "results": {}}

        while queue:
            key = queue.popleft()
            node = nodes[key]
            executor = self._executors.get(node["type"], _noop)
            try:
                result = await executor(node, ctx)
                ctx["results"][key] = result
                steps.append({"key": key, "status": "ok", "output": result})
            except Exception as exc:  # noqa: BLE001
                steps.append({"key": key, "status": "error", "error": str(exc)})
                return {
                    "run_id": run_id,
                    "status": "FAILED",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "steps": steps,
                }
            for nxt in out[key]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)

        return {
            "run_id": run_id,
            "status": "SUCCEEDED",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
        }


async def _noop(node: dict, ctx: dict) -> dict:
    return {"note": f"noop for {node['type']}"}


def _default_executors() -> dict[str, StepFn]:
    # Real executors call the corresponding service. For the scaffold,
    # all step types fall through to _noop unless registered here.
    return {}
