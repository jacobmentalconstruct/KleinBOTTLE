"""
kleinos/room_assist.py

Task 4 — Conversational Room Assistant for the World Builder.

A side panel that lets the user chat with a local Ollama model (qwen2.5:3b)
while editing a room.  The model receives the current form state as context
and can propose changes to name, description, environment, and objects.

Callbacks wired by KleinBuilderPane:
  get_snapshot()      -> dict   read current form values (not saved yet)
  apply_updates(d)              write partial updates back to form widgets
  area_rooms()        -> list   rooms in the same area, for context

UI contract:
  reset_chat()   call when the user switches to a different room
"""
from __future__ import annotations

import http.client
import json
import re
import sys
import threading
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from typing import Callable, Optional

_KB_ROOT = Path(__file__).resolve().parent.parent
if str(_KB_ROOT) not in sys.path:
    sys.path.insert(0, str(_KB_ROOT))

_BG     = "#010a01"
_BORDER = "#003300"
_FG     = "#00cc33"
_DIM    = "#005500"
_HDR_BG = "#001a00"
_WARN   = "#cc6600"
_BRIGHT = "#00ff66"

_OLLAMA_HOST  = "127.0.0.1"
_OLLAMA_PORT  = 11434
_ASSIST_MODEL = "qwen2.5:3b"
_MAX_TOKENS   = 512
_WINDOW_SIZE  = 6   # exchange pairs before summarising

_ALLOWED_UPDATES = {"name", "description", "environment", "objects"}

_SYSTEM_PROMPT = """You are a room design assistant for a text adventure game.
The user is editing a room and may ask you to describe, improve, or change it.

ROOM STATE (live form values, unsaved):
{room_state}

NEARBY ROOMS IN THIS AREA:
{nearby}

You may suggest changes to these fields only: name, description, environment (weather/light/sound), objects.
Do NOT modify: id, area, exits.

{summary_block}
Respond ONLY with valid JSON in exactly this format — no markdown, no code fences:
{{"reply": "your conversational message", "updates": {{}}}}

If you want to change fields, include them in updates.  Examples:
  "updates": {{"name": "The Den", "description": "A cosy reading room."}}
  "updates": {{"environment": {{"light": "dim", "sound": "silence"}}}}
If you are just chatting, use an empty object: "updates": {{}}
"""


# ── Ollama call (independent of ollama_phone.py — needs higher token limit) ──

def _ollama_chat(messages: list[dict], max_tokens: int = _MAX_TOKENS) -> str:
    body = json.dumps({
        "model": _ASSIST_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }).encode("utf-8")
    conn = http.client.HTTPConnection(_OLLAMA_HOST, _OLLAMA_PORT, timeout=90)
    try:
        conn.request("POST", "/api/chat", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = resp.read(4_000_001)
        if resp.status != 200:
            if resp.status == 404:
                raise RuntimeError(f"Model '{_ASSIST_MODEL}' not found. Run: ollama pull {_ASSIST_MODEL}")
            raise RuntimeError(f"Ollama returned HTTP {resp.status}")
        result = json.loads(data.decode("utf-8"))
        content = result.get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response.")
        return content
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise RuntimeError("Cannot reach Ollama (127.0.0.1:11434). Is it running?") from exc
    finally:
        conn.close()


def _summarise(exchanges: list[dict]) -> str:
    """Ask the model to summarise old exchanges into one sentence."""
    text = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in exchanges)
    prompt = f"Summarise the following conversation in one sentence:\n{text}"
    try:
        return _ollama_chat([{"role": "user", "content": prompt}], max_tokens=80)
    except Exception:
        return "(earlier context omitted)"


def _parse_response(raw: str) -> tuple[str, dict]:
    """Return (reply, updates) from the model's JSON output."""
    # Strip markdown code fences if the model adds them
    text = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    # Find the outermost {...}
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return raw, {}
    try:
        obj = json.loads(text[start:end])
    except json.JSONDecodeError:
        return raw, {}
    reply   = str(obj.get("reply", raw))
    updates = obj.get("updates", {})
    if not isinstance(updates, dict):
        updates = {}
    # Strip disallowed keys
    updates = {k: v for k, v in updates.items() if k in _ALLOWED_UPDATES}
    return reply, updates


# ── RoomAssistPane ────────────────────────────────────────────────────

class RoomAssistPane(tk.Frame):
    """
    Chat panel mounted beside the Room Editor.

    Caller wires:
        get_snapshot  -> callable() -> dict  (current form values)
        apply_updates -> callable(dict)      (write updates back to form)
        area_rooms    -> callable() -> list  (rooms in same area for context)
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        get_snapshot: Callable[[], dict],
        apply_updates: Callable[[dict], None],
        area_rooms: Callable[[], list],
    ):
        super().__init__(parent, bg=_BG, highlightthickness=1,
                         highlightbackground=_BORDER)
        self._get_snapshot   = get_snapshot
        self._apply_updates  = apply_updates
        self._area_rooms     = area_rooms

        # Conversation state
        self._messages: list[dict] = []   # Ollama message dicts (user/assistant)
        self._summary: str = ""
        self._undo_snapshot: Optional[dict] = None  # form state before last AI apply
        self._busy = False

        self._build()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" ASSIST ROOM ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 9, "bold")).pack(side="left", padx=8, pady=5)
        tk.Button(hdr, text="Reset Chat", bg=_HDR_BG, fg=_DIM,
                  activebackground=_BG, activeforeground=_FG,
                  relief="flat", font=("Consolas", 8), cursor="hand2",
                  command=self.reset_chat).pack(side="right", padx=6)

        # History
        self._history = tk.Text(
            self, bg="#000a00", fg=_FG,
            font=("Consolas", 8), relief="flat",
            state="disabled", wrap="word",
            highlightthickness=1, highlightbackground=_BORDER,
            padx=6, pady=6,
        )
        self._history.pack(fill="both", expand=True, padx=4, pady=(4, 0))
        self._history.tag_config("user",    foreground=_BRIGHT)
        self._history.tag_config("assist",  foreground=_FG)
        self._history.tag_config("system",  foreground=_DIM)
        self._history.tag_config("updated", foreground=_WARN)

        # Prompt entry
        entry_row = tk.Frame(self, bg=_BG)
        entry_row.pack(fill="x", padx=4, pady=4)
        self._prompt_var = tk.StringVar()
        entry = tk.Entry(
            entry_row, textvariable=self._prompt_var,
            bg=_BG, fg=_FG, insertbackground=_FG,
            font=("Consolas", 9), relief="flat",
            highlightthickness=1, highlightbackground=_BORDER,
            highlightcolor=_FG,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        entry.bind("<Return>", lambda _: self._send())
        self._send_btn = tk.Button(
            entry_row, text="Send", bg=_BG, fg=_FG,
            activebackground=_HDR_BG, activeforeground=_FG,
            relief="flat", font=("Consolas", 9, "bold"),
            cursor="hand2", command=self._send,
        )
        self._send_btn.pack(side="left")

        # Undo button
        self._undo_btn = tk.Button(
            self, text="Undo Last AI Update", bg=_BG, fg=_DIM,
            activebackground=_HDR_BG, activeforeground=_FG,
            relief="flat", font=("Consolas", 8), cursor="hand2",
            state="disabled", command=self._undo,
        )
        self._undo_btn.pack(fill="x", padx=4, pady=(0, 4))

        self._append("system", "Chat with the model to modify this room.\n"
                               "Changes apply to the form only — Save Room to persist.")

    # ── Chat state ────────────────────────────────────────────────────

    def reset_chat(self) -> None:
        """Clear conversation history. Does NOT clear form values."""
        self._messages = []
        self._summary  = ""
        self._undo_snapshot = None
        self._undo_btn.configure(state="disabled")
        self._history.configure(state="normal")
        self._history.delete("1.0", "end")
        self._history.configure(state="disabled")
        self._append("system", "Chat reset. Form values unchanged.")

    # ── Send / receive ────────────────────────────────────────────────

    def _send(self) -> None:
        prompt = self._prompt_var.get().strip()
        if not prompt or self._busy:
            return
        self._prompt_var.set("")
        self._busy = True
        self._send_btn.configure(state="disabled")
        self._append("user", prompt)
        threading.Thread(target=self._worker, args=(prompt,), daemon=True).start()

    def _worker(self, prompt: str) -> None:
        try:
            snapshot  = self._get_snapshot()
            area_list = self._area_rooms()

            # Build Ollama messages
            system_content = self._build_system(snapshot, area_list)
            messages = [{"role": "system", "content": system_content}]
            messages.extend(self._messages)
            messages.append({"role": "user", "content": prompt})

            raw = _ollama_chat(messages)
            reply, updates = _parse_response(raw)

            # Store exchange and roll window
            self._messages.append({"role": "user",      "content": prompt})
            self._messages.append({"role": "assistant",  "content": raw})
            self._roll_window()

            if updates:
                self.after(0, lambda u=updates, s=deepcopy(snapshot):
                           self._apply_safe(u, s))
            self.after(0, lambda r=reply: self._on_reply(r, bool(updates)))

        except Exception as exc:
            self.after(0, lambda: self._append("system", f"Error: {exc}"))
        finally:
            self._busy = False
            self.after(0, lambda: self._send_btn.configure(state="normal"))

    def _on_reply(self, reply: str, had_updates: bool) -> None:
        self._append("assist", reply)
        if had_updates:
            self._append("updated", "↑ Applied to form. Click Save Room to keep.")

    def _apply_safe(self, updates: dict, prev_snapshot: dict) -> None:
        self._undo_snapshot = prev_snapshot
        self._apply_updates(updates)
        self._undo_btn.configure(state="normal")

    def _undo(self) -> None:
        if self._undo_snapshot is None:
            return
        self._apply_updates(self._undo_snapshot)
        self._append("system", "Reverted to form state before last AI update.")
        self._undo_snapshot = None
        self._undo_btn.configure(state="disabled")

    # ── Rolling window ────────────────────────────────────────────────

    def _roll_window(self) -> None:
        """Summarise the two oldest exchanges when window overflows."""
        if len(self._messages) > _WINDOW_SIZE * 2:
            oldest = self._messages[:4]  # 2 exchanges = 4 messages
            self._messages = self._messages[4:]
            try:
                new_summary = _summarise(oldest)
                self._summary = (self._summary + " " + new_summary).strip()
            except Exception:
                pass

    # ── Context building ──────────────────────────────────────────────

    def _build_system(self, snapshot: dict, area_rooms: list) -> str:
        room_state = json.dumps({
            k: snapshot[k] for k in
            ("id", "name", "area", "description", "environment", "objects")
            if k in snapshot
        }, ensure_ascii=False, indent=2)

        nearby_parts = []
        for r in area_rooms[:6]:
            rid = r.get("id", "")
            if rid == snapshot.get("id"):
                continue
            nearby_parts.append(f"  {rid}: {r.get('name', '')} — {r.get('description', '')[:80]}")
        nearby = "\n".join(nearby_parts) or "  (none)"

        summary_block = (f"SUMMARY OF EARLIER CONVERSATION:\n{self._summary}\n\n"
                         if self._summary else "")

        return _SYSTEM_PROMPT.format(
            room_state=room_state,
            nearby=nearby,
            summary_block=summary_block,
        )

    # ── History display ───────────────────────────────────────────────

    def _append(self, role: str, text: str) -> None:
        prefix = {"user": "You: ", "assist": "AI:  ", "system": "",
                  "updated": ""}.get(role, "")
        self._history.configure(state="normal")
        self._history.insert("end", prefix + text + "\n\n", role)
        self._history.see("end")
        self._history.configure(state="disabled")
