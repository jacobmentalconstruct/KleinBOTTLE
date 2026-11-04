# KleinOS v0.1 — builder handoff

This bundle is a **plan/prompt only**, not an installation patch. It does not change working KleinBOTTLE files.

- `BUILDER_PROMPT.md`: paste into the builder agent; include the bundled `TASK_PLAN.json`.
- `TASK_PLAN.json`: task-by-task start/steps/end/verification/constraints.
- `EXAMPLE_TERMINAL_OBJECT.json`: illustrative object to add to a room using existing World Builder.

Implementation target: 4 new files, 2 modified code files, possibly app wiring, plus README update. Preserve telephone, saved worlds and development sidecars. Run one task at a time; verify before proceeding.

First action: **K0 — back up current local source and validate its working baseline.**
