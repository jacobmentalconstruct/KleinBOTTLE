"""Tests for process registry lifecycle transitions."""
from __future__ import annotations

import subprocess
import sys

from kleinos.workspace_manager.process_registry import ProcessRegistry


def test_register_initial_state():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    reg = ProcessRegistry()
    record = reg.register("ws1", proc)
    try:
        assert record.workspace_id == "ws1"
        assert record.app_id == "projectmapper"
        assert record.pid == proc.pid
        assert record.status == "running"
        assert record.exit_code is None
    finally:
        proc.kill()
        proc.wait()


def test_poll_detects_exit():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    reg = ProcessRegistry()
    record = reg.register("ws2", proc)
    proc.wait()
    changed = reg.poll_all()
    assert len(changed) == 1
    assert changed[0].run_id == record.run_id
    assert changed[0].status == "stopped"
    assert changed[0].exit_code == 0


def test_poll_detects_nonzero_exit():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(2)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    reg = ProcessRegistry()
    reg.register("ws3", proc)
    proc.wait()
    changed = reg.poll_all()
    assert changed[0].status == "failed"
    assert changed[0].exit_code == 2


def test_poll_does_not_re_report_stopped():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    reg = ProcessRegistry()
    reg.register("ws4", proc)
    proc.wait()
    reg.poll_all()
    second = reg.poll_all()
    assert second == []


def test_running_for_workspace():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    reg = ProcessRegistry()
    reg.register("ws5", proc)
    running = reg.running_for_workspace("ws5")
    assert len(running) == 1
    assert running[0].status == "running"
    proc.kill()
    proc.wait()


def test_running_for_workspace_after_exit():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    reg = ProcessRegistry()
    reg.register("ws6", proc)
    proc.wait()
    reg.poll_all()
    assert reg.running_for_workspace("ws6") == []


def test_all_records():
    reg = ProcessRegistry()
    for _ in range(3):
        p = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        reg.register("wsN", p)
        p.wait()
    assert len(reg.all_records()) == 3
