"""Minimal process registry for launched projectmapper instances."""
from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ProcessRecord:
    run_id: str
    workspace_id: str
    app_id: str
    pid: int
    started_at: str
    status: str = "running"      # "running" | "stopped" | "failed"
    exit_code: Optional[int] = None
    _proc: Optional[subprocess.Popen] = field(
        default=None, repr=False, compare=False,
    )


class ProcessRegistry:
    def __init__(self) -> None:
        self._records: dict[str, ProcessRecord] = {}

    def register(self, workspace_id: str, proc: subprocess.Popen) -> ProcessRecord:
        record = ProcessRecord(
            run_id=uuid.uuid4().hex,
            workspace_id=workspace_id,
            app_id="projectmapper",
            pid=proc.pid,
            started_at=datetime.now(timezone.utc).isoformat(),
            _proc=proc,
        )
        self._records[record.run_id] = record
        return record

    def poll_all(self) -> list[ProcessRecord]:
        """Check exit status of all running records. Return newly-finished ones."""
        changed: list[ProcessRecord] = []
        for record in self._records.values():
            if record.status != "running" or record._proc is None:
                continue
            rc = record._proc.poll()
            if rc is not None:
                record.exit_code = rc
                record.status = "stopped" if rc == 0 else "failed"
                changed.append(record)
        return changed

    def for_workspace(self, workspace_id: str) -> list[ProcessRecord]:
        return [r for r in self._records.values() if r.workspace_id == workspace_id]

    def running_for_workspace(self, workspace_id: str) -> list[ProcessRecord]:
        return [r for r in self.for_workspace(workspace_id) if r.status == "running"]

    def all_records(self) -> list[ProcessRecord]:
        return list(self._records.values())
