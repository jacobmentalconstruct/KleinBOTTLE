"""
kleinos/room_assist.py

Narrative conversation panel + per-field AI generation for the World Builder.

The chat panel is a free-form narrative space: the user builds up creative
context about the room (story, mood, purpose).  Small "✦" buttons next to
each form field use that narrative as a filter to generate the field value.

Callbacks wired by KleinBuilderPane:
  get_snapshot()   -> dict   current form values (unsaved)
  apply_updates(d)           write partial updates back to form widgets
  area_rooms()     -> list   rooms in the same area (for nearby context)
  all_rooms()      -> list   every room in the world (for mention resolution)

Public interface:
  reset_chat()           clear narrative; call when user switches room
  generate_field(name)   run per-field inference from narrative context
  generate_all_fields()  chain all per-field inferences in sequence
"""
from __future__ import annotations

import http.client
import json
import re
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable

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

_OLLAMA_HOST = "127.0.0.1"
_OLLAMA_PORT = 11434
_NARR_MODEL  = "qwen2.5:7b"   # narrative conversation
_FIELD_MODEL = "qwen2.5:3b"   # per-field generation (fast)
_WINDOW_SIZE = 6               # rolling window in exchanges


def _load_ollama_defaults() -> None:
    global _OLLAMA_HOST, _OLLAMA_PORT, _NARR_MODEL, _FIELD_MODEL
    try:
        from kleinos import config as _kconfig
        ocfg = _kconfig.load().get("ollama", {})
        _OLLAMA_HOST = str(ocfg.get("host", _OLLAMA_HOST))
        _OLLAMA_PORT = int(ocfg.get("port", _OLLAMA_PORT))
        _NARR_MODEL  = str(ocfg.get("narr_model", _NARR_MODEL))
        _FIELD_MODEL = str(ocfg.get("field_model", _FIELD_MODEL))
    except Exception:  # SAFE: config absent on first run
        pass


_load_ollama_defaults()

_NARRATIVE_SYSTEM = """\
You are a creative story collaborator helping a game designer conceive a room \
for a text adventure game.
Your job is to understand the narrative IDENTITY of this room through conversation.

AREA: {area}
NEARBY ROOMS IN THIS AREA:
{nearby}

Help the user explore: What story does this room tell? What mood or atmosphere?
What happened here? What purpose does it serve? Who uses it?

Keep responses to 2-3 sentences. Ask ONE focused creative question per reply.
Do NOT generate form fields or JSON — this is pure creative exploration.
{summary_block}"""

_FIELD_PROMPTS: dict[str, str] = {
    "name":        "Generate ONLY the room name (2–4 evocative words). No explanation.",
    "description": (
        "Generate ONLY the room description (2–3 evocative sentences "
        "for a text adventure player). No explanation."
    ),
    "weather":     (
        "Generate ONLY a short weather/atmosphere phrase "
        "(e.g. 'bitter cold', 'humid and still'). "
        "One phrase, no explanation. Empty string if irrelevant."
    ),
    "light":       (
        "Generate ONLY a short lighting phrase "
        "(e.g. 'dim candlelight', 'harsh fluorescent glow'). "
        "One phrase, no explanation. Empty string if irrelevant."
    ),
    "sound":       (
        "Generate ONLY a short ambient sound phrase "
        "(e.g. 'distant dripping water', 'eerie silence'). "
        "One phrase, no explanation. Empty string if irrelevant."
    ),
    "objects":     (
        "Generate ONLY a JSON array of objects in this room. "
        "Each object: {\"id\": \"snake_case\", \"name\": \"Name\", "
        "\"kind\": \"item\", \"description\": \"...\"}. "
        "Reply with valid JSON array only, no explanation. Can be []."
    ),
}


# ── Ollama ────────────────────────────────────────────────────────────

def _ollama_chat(messages: list[dict], model: str, max_tokens: int = 600) -> str:
    body = json.dumps({
        "model": model,
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
                    f"Model '{model}' not found — run: ollama pull {model}"
                )
            raise RuntimeError(f"Ollama returned HTTP {resp.status}")
        result = json.loads(data.decode("utf-8"))
        content = result.get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response.")
        return content
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise RuntimeError(
            "Cannot reach Ollama (127.0.0.1:11434). Is it running?"
        ) from exc
    finally:
        conn.close()


def _summarise(exchanges: list[dict]) -> str:
    text = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in exchanges
    )
    prompt = f"Summarise this conversation in one sentence:\n{text}"
    try:
        return _ollama_chat(
            [{"role": "user", "content": prompt}],
            model=_NARR_MODEL, max_tokens=80,
        )
    except Exception:
        return "(earlier context omitted)"


# ── RoomAssistPane ────────────────────────────────────────────────────

class RoomAssistPane(tk.Frame):
    """
    Narrative conversation panel.  Chat builds creative context; ✦ buttons
    on the form use that context to generate individual field values.
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
        self._busy     = False
        self._gen_busy = False

        self._build()

    # ── Layout ────────────────────────────────────────────────────────

    def _build(self) -> None:
        hdr = tk.Frame(self, bg=_HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" NARRATIVE ", bg=_HDR_BG, fg=_FG,
                 font=("Consolas", 9, "bold")).pack(side="left", padx=8, pady=5)
        tk.Button(hdr, text="Reset", bg=_HDR_BG, fg=_DIM,
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
        self._history.bind("<MouseWheel>", lambda e: self._history.yview_scroll(int(-e.delta / 120), "units"))
        self._history.tag_config("user",   foreground=_BRIGHT)
        self._history.tag_config("assist", foreground=_FG)
        self._history.tag_config("system", foreground=_DIM)
        self._history.tag_config("gen",    foreground=_WARN)

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

        self._append("system",
                     "Build the room's narrative here.\n"
                     "Use the ✦ buttons on the form to generate each field.")

    # ── Chat state ────────────────────────────────────────────────────

    def reset_chat(self) -> None:
        self._messages = []
        self._summary  = ""
        self._history.configure(state="normal")
        self._history.delete("1.0", "end")
        self._history.configure(state="disabled")
        self._append("system", "Narrative cleared.")

    # ── Narrative context (exposed for field generation) ──────────────

    def get_narrative(self) -> str:
        """Return the full conversation history as a formatted string."""
        if not self._messages:
            return "(no narrative yet)"
        lines = []
        if self._summary:
            lines.append(f"[Earlier context: {self._summary}]")
        for m in self._messages:
            role = "User" if m["role"] == "user" else "AI"
            lines.append(f"{role}: {m['content']}")
        return "\n".join(lines)

    # ── Narrative chat ────────────────────────────────────────────────

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

            nearby_parts = []
            for r in area_list[:5]:
                if r.get("id") == snapshot.get("id"):
                    continue
                nearby_parts.append(
                    f"  {r['id']}: {r.get('name','')} — "
                    f"{r.get('description','')[:60]}"
                )
            nearby = "\n".join(nearby_parts) or "  (none)"

            summary_block = (
                f"EARLIER CONTEXT:\n{self._summary}\n\n"
                if self._summary else ""
            )
            system = _NARRATIVE_SYSTEM.format(
                area=snapshot.get("area", "unknown"),
                nearby=nearby,
                summary_block=summary_block,
            )

            messages = [{"role": "system", "content": system}]
            messages.extend(self._messages)
            messages.append({"role": "user", "content": prompt})

            reply = _ollama_chat(messages, model=_NARR_MODEL)

            self._messages.append({"role": "user",      "content": prompt})
            self._messages.append({"role": "assistant", "content": reply})
            self._roll_window()

            self.after(0, lambda r=reply: self._append("assist", r))

        except Exception as exc:
            self.after(0, lambda: self._append("system", f"Error: {exc}"))
        finally:
            self._busy = False
            self.after(0, lambda: self._send_btn.configure(state="normal"))

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

    # ── Per-field generation ──────────────────────────────────────────

    def generate_field(self, field_name: str) -> None:
        """Generate a single field using the narrative as context."""
        if self._gen_busy:
            self._append("gen", "✦ busy — wait for current generation to finish.")
            return
        self._gen_busy = True
        threading.Thread(target=self._gen_worker,
                         args=(field_name,), daemon=True).start()

    def generate_all_fields(self) -> None:
        """Chain generation of all fields in sequence."""
        if self._gen_busy:
            self._append("gen", "✦ busy — wait for current generation to finish.")
            return
        self._gen_busy = True
        fields = ["name", "description", "weather", "light", "sound", "objects"]
        threading.Thread(target=self._gen_all_worker,
                         args=(fields,), daemon=True).start()

    def _build_field_messages(self, field_name: str) -> list[dict]:
        snapshot  = self._get_snapshot()
        area_list = self._area_rooms()
        nearby_parts = [
            f"  {r['id']}: {r.get('name','')}"
            for r in area_list[:5]
            if r.get("id") != snapshot.get("id")
        ]
        nearby    = "\n".join(nearby_parts) or "  (none)"
        narrative = self.get_narrative()
        instruction = _FIELD_PROMPTS.get(field_name, f"Generate only the {field_name}.")

        system = (
            f"You are generating room data for a text adventure game.\n"
            f"Area: {snapshot.get('area', 'unknown')}\n"
            f"Nearby rooms:\n{nearby}\n\n"
            f"NARRATIVE CONTEXT (creative conversation about this room):\n"
            f"{narrative}\n\n"
            f"{instruction}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user",   "content": f"Generate the {field_name}."},
        ]

    def _gen_worker(self, field_name: str) -> None:
        try:
            messages = self._build_field_messages(field_name)
            raw = _ollama_chat(messages, model=_FIELD_MODEL, max_tokens=300)
            self.after(0, lambda r=raw, f=field_name: self._apply_field(f, r))
        except Exception as exc:
            self.after(0, lambda: self._append(
                "gen", f"✦ {field_name}: error — {exc}"))
        finally:
            self._gen_busy = False

    def _gen_all_worker(self, fields: list[str]) -> None:
        try:
            for field in fields:
                self.after(0, lambda f=field:
                           self._append("gen", f"✦ generating {f}…"))
                try:
                    messages = self._build_field_messages(field)
                    raw = _ollama_chat(messages, model=_FIELD_MODEL, max_tokens=300)
                    self.after(0, lambda r=raw, f=field: self._apply_field(f, r))
                except Exception as exc:
                    self.after(0, lambda f=field, e=exc:
                               self._append("gen", f"✦ {f}: error — {e}"))
        finally:
            self._gen_busy = False

    def _apply_field(self, field_name: str, raw: str) -> None:
        if field_name == "objects":
            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
            start = cleaned.find("[")
            end   = cleaned.rfind("]") + 1
            if start != -1 and end > 0:
                try:
                    value: object = json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    self._append(
                        "gen",
                        f"✦ objects: could not parse JSON — {cleaned[:60]}"
                    )
                    return
            else:
                value = []
            self._apply_updates({"objects": value})
        elif field_name in ("weather", "light", "sound"):
            self._apply_updates({"environment": {field_name: raw.strip().strip('"')}})
        else:
            self._apply_updates({field_name: raw.strip().strip('"')})
        self._append("gen", f"✦ {field_name} written to form.")

    # ── History display ───────────────────────────────────────────────

    def _append(self, role: str, text: str) -> None:
        prefix = {
            "user": "You: ", "assist": "AI:  ", "system": "", "gen": "",
        }.get(role, "")
        self._history.configure(state="normal")
        self._history.insert("end", prefix + text + "\n\n", role)
        self._history.see("end")
        self._history.configure(state="disabled")
