"""Tests for workspace creation, path validation, and store persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import kleinos.workspace_manager.workspace as wm_mod
from kleinos.workspace_manager.workspace import (
    WorkspaceDef,
    log_event,
    new_workspace,
    validate_name,
    validate_new_workspace,
)


# ── Name validation ────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["MyProject", "my_project", "proj-1", "A", "z9"])
def test_validate_name_ok(name):
    assert validate_name(name) is None


@pytest.mark.parametrize("name", ["", "bad name", "../evil", "has/slash", "-startswithdash"])
def test_validate_name_bad(name):
    assert validate_name(name) is not None


# ── Workspace path validation ──────────────────────────────────────────

def test_validate_new_workspace_nonexistent(tmp_path):
    assert validate_new_workspace("Alpha", tmp_path) is None


def test_validate_new_workspace_exists_empty(tmp_path):
    (tmp_path / "Alpha").mkdir()
    assert validate_new_workspace("Alpha", tmp_path) is None


def test_validate_new_workspace_exists_nonempty(tmp_path):
    d = tmp_path / "Alpha"
    d.mkdir()
    (d / "file.txt").write_text("x")
    assert validate_new_workspace("Alpha", tmp_path) is not None


# ── Workspace creation ─────────────────────────────────────────────────

def test_new_workspace_creates_dir(tmp_path):
    ws = new_workspace("Beta", tmp_path)
    assert Path(ws.root).is_dir()
    assert ws.name == "Beta"
    assert ws.workspace_id
    assert ws.installed is False


# ── Store persistence ──────────────────────────────────────────────────

@pytest.fixture()
def patched_store(tmp_path, monkeypatch):
    monkeypatch.setattr(wm_mod, "_MANAGED_ROOT", tmp_path)
    monkeypatch.setattr(wm_mod, "_STORE_FILE", tmp_path / "workspaces.json")
    monkeypatch.setattr(wm_mod, "_EVENT_LOG",  tmp_path / "events.jsonl")
    return wm_mod.WorkspaceStore()


def test_store_round_trip(patched_store, tmp_path):
    ws = WorkspaceDef(workspace_id="abc123", name="Gamma", root=str(tmp_path / "Gamma"))
    patched_store.add(ws)
    loaded = patched_store.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "Gamma"
    assert loaded[0].workspace_id == "abc123"


def test_store_update_installed(patched_store, tmp_path):
    ws = WorkspaceDef(workspace_id="xyz", name="Delta", root=str(tmp_path / "Delta"))
    patched_store.add(ws)
    ws.installed = True
    ws.sidecar_rev = "abc1234"
    patched_store.update(ws)
    loaded = patched_store.load_all()
    assert loaded[0].installed is True
    assert loaded[0].sidecar_rev == "abc1234"


def test_store_multiple(patched_store, tmp_path):
    for n in ("W1", "W2", "W3"):
        patched_store.add(
            WorkspaceDef(workspace_id=n.lower(), name=n, root=str(tmp_path / n))
        )
    assert len(patched_store.load_all()) == 3


def test_store_empty_on_missing_file(patched_store):
    assert patched_store.load_all() == []


# ── Event log ─────────────────────────────────────────────────────────

def test_log_event(tmp_path, monkeypatch):
    monkeypatch.setattr(wm_mod, "_MANAGED_ROOT", tmp_path)
    monkeypatch.setattr(wm_mod, "_EVENT_LOG",  tmp_path / "events.jsonl")

    log_event("workspace.created", workspace_id="id1", name="Epsilon", root="/tmp/Epsilon")
    log_event("app.installed",     workspace_id="id1", rev="deadbeef")

    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(lines) == 2
    r1 = json.loads(lines[0])
    assert r1["event"] == "workspace.created"
    assert r1["name"] == "Epsilon"
    r2 = json.loads(lines[1])
    assert r2["event"] == "app.installed"
    assert r2["rev"] == "deadbeef"
