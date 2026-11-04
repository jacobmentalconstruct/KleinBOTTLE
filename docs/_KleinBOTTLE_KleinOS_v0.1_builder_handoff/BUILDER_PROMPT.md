# Builder handoff — KleinBOTTLE / KleinOS v0.1

**Goal:** Implement **one in-game computer** with a simple Windows-like Tkinter desktop (Files, Terminal, Editor) backed by **one real, persistent, restricted Linux Docker sandbox**.

**Start from the user's current local KleinBOTTLE source**. The reference snapshot in this chat is not the current working tree. Telephone patches previously damaged indentation; do not use a blind project-wide patch. Back up and compile before editing.

## Workflow

**Baseline → Container → Backend → Desktop → Integrate → Verify → Park**

Read `TASK_PLAN.json`. Execute **one task at a time**, in order (K0–K6). Each task has start conditions, steps, end state, verification and forbidden scope. Do not proceed until the previous end state is verified; report blockers rather than guessing.

## Exact implementation boundaries

- **New files (target 4):** `Dockerfile.kleinos`, `src/computer_backend.py`, `src/surfaces/computer.py`, `tests/test_computer.py`.
- **Modify:** `src/game.py`, `src/surfaces/game.py`; `src/app.py` only if genuinely necessary; existing `README.md` for usage.
- **Do not touch:** saved worlds, `_spine/`, `.project-mapper/`, `.microservice-library/`, telephone implementation. No file rename in this tranche.
- **One sandbox:** fixed container and named volume, mounted at `/workspace`. Non-root user; no network, no host bind mounts, no Docker socket, read-only container root filesystem, restricted capabilities and resources. Docker is not absolute isolation; use a dedicated VM if a stronger adversarial security boundary is needed.
- **Backend:** all commands and file operations happen **inside** the container, never on host. Use `subprocess` argv (`shell=False`), bounded output, timeouts and proper termination, canonical path checks, and Docker-unavailable errors. No host execution fallback.
- **Desktop:** one `Toplevel` window with Files, Terminal and Editor. No full OS, no browser, no persistent PTY. UI must not block on Docker calls.
- **Gameplay:** recognize a visible room object with `kind: "terminal"`; `use computer` opens Toplevel. Preserve current GameSession (the Play notebook tab reloads on tab switches, so do not use a new notebook tab). The existing World Builder preserves arbitrary object fields; avoid changes to its schema/form.
- **Do not add world publishing yet**. Future tranche: sandbox writes proposed room JSON; trusted WorldBuilder validates and explicitly asks permission before import. No direct sandbox writes to `data/world.json`.

## Patch safety (mandatory)

1. Use exact current files. Stage each change in a temporary working copy.
2. For ProjectMapper Python replacements, use literal, correctly verified indentation (`use_patch_indent: true`), not inferred indentation.
3. Validate resulting files **before applying**: `python -m compileall -q src tests` and `python -m unittest discover -s tests -v` (plus task-specific Docker smoke checks).
4. Reject/repair any change breaking the existing phone, world editor or gameplay.
5. At completion report: files created/modified, actual test results, exact sandbox restrictions, limitations, and verified stop conditions.

## Acceptance path

`look → use computer → Files → Editor → Terminal → Close → use computer → confirm files persisted`

**Stop and park after that path and tests work.** Don't expand to multi-computer, a full virtual OS, agent, package manager, or world publishing.
