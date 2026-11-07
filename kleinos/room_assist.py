"""
kleinos/room_assist.py

Task 4 — Conversational Room Assistant for the World Builder.

Mention system:  type <room name or id> in the chat and the assistant
automatically receives that room's full data plus its direct neighbors
(rooms it exits to + rooms that exit into it).  The model can then
suggest connections using real room IDs rather than invented ones.

Callbacks wired by KleinBuilderPane:
  get_snapshot()   -> dict   current form values (unsaved)
  apply_updates(d)           write partial updates back to form widgets
  area_rooms()     -> list   rooms in the same area (for nearby context)
  all_rooms()      -> list   every room in the world (for mention resolution)

UI:
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
_MENTION = "#00aaff"   # resolved mention highlight

_OLLAMA_HOST  = "127.0.0.1"
_OLLAMA_PORT  = 11434
_ASSIST_MODEL = "qwen2.5:3b"
_MAX_TOKENS   = 600
_WINDOW_SIZE  = 6

_ALLOWED_UPDATES = {"name", "description", "environment", "objects"}

# ─── mention syntax: <anything here> ─────────────────────────────────
_MENTION_RE = re.compile(r"<([^>]+)>")

_SYSTEM_PROMPT = """\
You are a room design assistant for a text adventure game.
The user is editing a room and can ask you to modify it.

CURRENT ROOM (live form, unsaved):
{room_state}

NEARBY ROOMS IN THIS AREA:
{nearby}
{mention_block}\
{summary_block}\
You may ONLY suggest changes to: name, description, environment (weather/light/sound), objects.
Never change id, area, or exits directly — exits are handled by the user.
If the user asks to connect rooms, suggest the direction and the target room id from the referenced data.

Respond ONLY with valid JSON, no markdown, no code fences:
{{"reply": "conversational message", "updates": {{}}}}

Include changed fields in updates if appropriate. Use empty {{}} if just chatting.
"""


# ── Ollama ────────────────────────────────────────────────────────────

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
                raise RuntimeError(
                    f"Model '{_ASSIST_MODEL}' not found — run: ollama pull {_ASSIST_MODEL}"
                )
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
    text = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in exchanges)
    prompt = f"Summarise this conversation in one sentence:\n{text}"
    try:
        return _ollama_chat([{"role": "user", "content": prompt}], max_tokens=80)
    except Exception:
        return "(earlier context omitted)"


def _parse_response(raw: str) -> tuple[str, dict]:
    text = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
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
    return reply, {k: v for k, v in updates.items() if k in _ALLOWED_UPDATES}


# ── Mention resolution ────────────────────────────────────────────────

def _resolve_mention(query: str, rooms: list[dict]) -> Optional[dict]:
    """Fuzzy-resolve a mention string to a room dict (or None)."""
    q = query.strip().casefold()
    # 1. exact ID
    for r in rooms:
        if r.get("id", "").casefold() == q:
            return r
    # 2. exact name
    for r in rooms:
        if r.get("name", "").casefold() == q:
            return r
    # 3. name starts with query
    for r in rooms:
        if r.get("name", "").casefold().startswith(q):
            return r
    # 4. name contains query
    for r in rooms:
        if q in r.get("name", "").casefold() or q in r.get("id", "").casefold():
            return r
    return None


def _room_neighbors(room: dict, all_rooms: list[dict]) -> dict[str, dict]:
    """
    Return a dict of {room_id: room_dict} for direct neighbors:
    rooms this room exits to + rooms that exit into this room.
    """
    rid = room.get("id", "")
    room_index = {r["id"]: r for r in all_rooms}
    neighbors: dict[str, dict] = {}

    # Forward: rooms this room exits to
    for target_id in room.get("exits", {}).values():
        if target_id in room_index and target_id != rid:
            neighbors[target_id] = room_index[target_id]

    # Backward: rooms that have an exit pointing here
    for r in all_rooms:
        if r["id"] != rid and rid in r.get("exits", {}).values():
            neighbors[r["id"]] = r

    return neighbors


def _format_mention_block(mentions: list[tuple[str, dict]], all_rooms: list[dict]) -> str:
    """Build the REFERENCED ROOMS section for the system prompt."""
    if not mentions:
        return ""
    lines = ["REFERENCED ROOMS (resolved from your <mentions>):"]
    for query, room in mentions:
        rid   = room.get("id", "?")
        name  = room.get("name", rid)
        desc  = room.get("description", "")[:120]
        area  = room.get("area", "")
        exits = room.get("exits", {})

        lines.append(f"\n  <{query}> → \"{name}\" (id: {rid}, area: {area})")
        if desc:
            lines.append(f"    Description: {desc}{'…' if len(room.get('description','')) > 120 else ''}")
        if exits:
            exit_summary = ", ".join(f"{d}→{t}" for d, t in exits.items())
            lines.append(f"    Exits: {exit_summary}")

        neighbors = _room_neighbors(room, all_rooms)
        if neighbors:
            lines.append("    Neighbors:")
            for nb in list(neighbors.values())[:4]:
                nb_desc = nb.get("description", "")[:60]
                lines.append(f"      {nb['id']}: \"{nb.get('name','')}\" — {nb_desc}")

        # Back-links
        back = [r for r in all_rooms if rid in r.get("exits", {}).values()
                and r.get("id") != rid]
        if back:
            back_ids = ", ".join(r["id"] for r in back[:4])
            lines.append(f"    Linked from: {back_ids}")

    lines.append("")
    return "\n".join(lines) + "\n"


# ── RoomAssistPane ────────────────────────────────────────────────────

class RoomAssistPane(tk.Frame):
    """
    Chat panel mounted beside the Room Editor.

    Type <room name> in a message to pull that room's data and neighbors
    into the model's context for that exchange.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        get_snapshot: Callable[[], dict],
        apply_updates: Callable[[dict], None],
        area_rooms: Callable[[], list],
        all_rooms: Callable[[], list],
    ):
        super().__init__(parent, bg=_BG, highlightthickness=1,
                         highlightbackground=_BORDER)
        self._get_snapshot  = get_snapshot
        self._apply_updates = apply_updates
        self._area_rooms    = area_rooms
        self._all_rooms     = all_rooms

        self._messages: list[dict] = []
        self._summary: str = ""
        self._undo_snapshot: Optional[dict] = None
        self._busy = False

        self._build()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self) -> None:
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" ASSIST ROOM ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 9, "bold")).pack(side="left", padx=8, pady=5)
        tk.Button(hdr, text="Reset Chat", bg=_HDR_BG, fg=_DIM,
                  activebackground=_BG, activeforeground=_FG,
                  relief="flat", font=("Consolas", 8), cursor="hand2",
                  command=self.reset_chat).pack(side="right", padx=6)

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
        self._history.tag_config("mention", foreground=_MENTION)

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

        self._undo_btn = tk.Button(
            self, text="Undo Last AI Update", bg=_BG, fg=_DIM,
            activebackground=_HDR_BG, activeforeground=_FG,
            relief="flat", font=("Consolas", 8), cursor="hand2",
            state="disabled", command=self._undo,
        )
        self._undo_btn.pack(fill="x", padx=4, pady=(0, 4))

        self._append("system",
                     "Chat to modify this room.  Mention other rooms with <name>.\n"
                     "Changes apply to the form only — Save Room to persist.")

    # ── Chat state ────────────────────────────────────────────────────

    def reset_chat(self) -> None:
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
        self._append_user_with_mentions(prompt)
        threading.Thread(target=self._worker, args=(prompt,), daemon=True).start()

    def _worker(self, prompt: str) -> None:
        try:
            snapshot   = self._get_snapshot()
            area_list  = self._area_rooms()
            all_rooms  = self._all_rooms()

            # Resolve mentions in the user's message
            mentions   = self._extract_mentions(prompt, all_rooms)

            system_msg = self._build_system(snapshot, area_list, all_rooms, mentions)
            messages   = [{"role": "system", "content": system_msg}]
            messages.extend(self._messages)
            messages.append({"role": "user", "content": prompt})

            raw = _ollama_chat(messages)
            reply, updates = _parse_response(raw)

            self._messages.append({"role": "user",     "content": prompt})
            self._messages.append({"role": "assistant","content": raw})
            self._roll_window()

            if updates:
                self.after(0, lambda u=updates, s=deepcopy(snapshot):
                           self._apply_safe(u, s))
            self.after(0, lambda r=reply, m=mentions: self._on_reply(r, bool(updates), m))

        except Exception as exc:
            self.after(0, lambda: self._append("system", f"Error: {exc}"))
        finally:
            self._busy = False
            self.after(0, lambda: self._send_btn.configure(state="normal"))

    def _on_reply(self, reply: str, had_updates: bool,
                  mentions: list[tuple[str, dict]]) -> None:
        self._append("assist", reply)
        if mentions:
            names = ", ".join(f"<{q}>" for q, _ in mentions)
            self._append("mention", f"↳ context pulled: {names}")
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

    # ── Mention helpers ───────────────────────────────────────────────

    def _extract_mentions(self, text: str,
                          all_rooms: list[dict]) -> list[tuple[str, dict]]:
        """Return [(query, room_dict)] for each resolved <mention> in text."""
        seen: set[str] = set()
        result = []
        for m in _MENTION_RE.finditer(text):
            query = m.group(1).strip()
            if query.casefold() in seen:
                continue
            seen.add(query.casefold())
            room = _resolve_mention(query, all_rooms)
            if room:
                result.append((query, room))
        return result

    # ── Rolling window ────────────────────────────────────────────────

    def _roll_window(self) -> None:
        if len(self._messages) > _WINDOW_SIZE * 2:
            oldest = self._messages[:4]
            self._messages = self._messages[4:]
            try:
                new_summary = _summarise(oldest)
                self._summary = (self._summary + " " + new_summary).strip()
            except Exception:
                pass

    # ── Context building ──────────────────────────────────────────────

    def _build_system(self, snapshot: dict, area_rooms: list,
                      all_rooms: list, mentions: list[tuple[str, dict]]) -> str:
        room_state = json.dumps({
            k: snapshot[k]
            for k in ("id", "name", "area", "description", "environment", "objects")
            if k in snapshot
        }, ensure_ascii=False, indent=2)

        nearby_parts = []
        for r in area_rooms[:6]:
            if r.get("id") == snapshot.get("id"):
                continue
            nearby_parts.append(
                f"  {r['id']}: {r.get('name','')} — {r.get('description','')[:80]}"
            )
        nearby = "\n".join(nearby_parts) or "  (none)"

        mention_block = _format_mention_block(mentions, all_rooms)
        summary_block = (f"EARLIER CONVERSATION SUMMARY:\n{self._summary}\n\n"
                         if self._summary else "")

        return _SYSTEM_PROMPT.format(
            room_state=room_state,
            nearby=nearby,
            mention_block=mention_block,
            summary_block=summary_block,
        )

    # ── History display ───────────────────────────────────────────────

    def _append(self, role: str, text: str) -> None:
        prefix = {"user": "You: ", "assist": "AI:  ",
                  "system": "", "updated": "", "mention": "  "}.get(role, "")
        self._history.configure(state="normal")
        self._history.insert("end", prefix + text + "\n\n", role)
        self._history.see("end")
        self._history.configure(state="disabled")

    def _append_user_with_mentions(self, text: str) -> None:
        """Display user message with <mentions> highlighted in a distinct colour."""
        self._history.configure(state="normal")
        self._history.insert("end", "You: ", "user")
        last = 0
        for m in _MENTION_RE.finditer(text):
            if m.start() > last:
                self._history.insert("end", text[last:m.start()], "user")
            self._history.insert("end", m.group(0), "mention")
            last = m.end()
        if last < len(text):
            self._history.insert("end", text[last:], "user")
        self._history.insert("end", "\n\n")
        self._history.see("end")
        self._history.configure(state="disabled")
