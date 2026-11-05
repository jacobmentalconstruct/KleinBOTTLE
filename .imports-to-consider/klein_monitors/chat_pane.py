"""
klein_monitors/chat_pane.py

OllamaChatPane — green phosphor chat widget talking to a local Ollama instance.

Features:
  • Model dropdown populated from GET localhost:11434/api/tags
  • Scrolling transcript with alternating user / assistant styling
  • Rolling context window (last N message pairs; oldest fall off automatically)
  • New Chat button to clear context
  • Background thread for non-blocking Ollama calls
"""

from __future__ import annotations

import http.client
import json
import queue
import threading
import tkinter as tk
from typing import Callable, Optional

from klein_monitors.klein_app import KleinChat

# ── Palette (matches game_pane green monochrome) ─────────────────────
_BG      = "#010a01"
_CHROME  = "#003311"
_BORDER  = "#005522"
_BTN_BG  = "#0a2010"
_BTN_ACT = "#0d3a1a"
_FG      = "#00dd33"   # main green
_FG_DIM  = "#1a4a1a"
_FG_HI   = "#88ff88"   # bright green — user messages
_FG_SYS  = "#005522"   # very dim — system notices
_STATUS  = "#050e05"
_FONT    = ("Consolas", 9)
_FONT_B  = ("Consolas", 9, "bold")
_FONT_SM = ("Consolas", 8)

_OLLAMA_HOST    = "127.0.0.1"
_OLLAMA_PORT    = 11434
_DEFAULT_MODEL  = "qwen2.5:3b"
_MAX_CONTEXT    = 20   # message pairs kept in rolling window


# ── Ollama helpers (stdlib only, no KleinBOTTLE import) ──────────────

def _fetch_models() -> list[str]:
    """Return locally available Ollama model names, or [] on any error."""
    try:
        conn = http.client.HTTPConnection(_OLLAMA_HOST, _OLLAMA_PORT, timeout=4)
        conn.request("GET", "/api/tags")
        resp = conn.getresponse()
        if resp.status != 200:
            return []
        data = json.loads(resp.read(200_000).decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _chat(model: str, messages: list[dict]) -> str:
    """Non-streaming /api/chat call. Returns assistant content string."""
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": 300},
    }).encode("utf-8")
    conn = http.client.HTTPConnection(_OLLAMA_HOST, _OLLAMA_PORT, timeout=90)
    conn.request("POST", "/api/chat", body=body,
                 headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    raw = resp.read(2_000_001)
    if resp.status != 200:
        if resp.status == 404:
            raise RuntimeError(f"Model not found locally. Run: ollama pull {model}")
        raise RuntimeError(f"Ollama HTTP {resp.status}")
    result = json.loads(raw.decode("utf-8"))
    return result["message"]["content"].strip()


# ── Chat widget ───────────────────────────────────────────────────────

class OllamaChatPane(tk.Frame):
    """
    Full-height chat interface for a local Ollama model.

    Parameters
    ----------
    parent   : tk.Widget  — the content frame from KleinPC
    on_exit  : callable   — called when the user clicks Back / ESC
    """

    def __init__(self, parent: tk.Widget, *, on_exit: Optional[Callable] = None):
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._on_exit = on_exit
        self._context: list[dict] = []          # rolling message history
        self._reply_queue: queue.Queue = queue.Queue()
        self._busy = False
        self._available_models: list[str] = []
        self._model_var = tk.StringVar(value=_DEFAULT_MODEL)
        self._build()
        self._load_models_async()
        self.after(100, self._poll)

    # ── Layout ───────────────────────────────────────────────────────

    def _build(self) -> None:
        # Chrome bar: title + model picker + new-chat button
        bar = tk.Frame(self, bg=_CHROME, bd=0)
        bar.pack(fill="x")
        tk.Label(bar, text="OLLAMA CHAT", bg=_CHROME, fg=_FG,
                 font=_FONT_B, padx=8, pady=4).pack(side="left")

        # Model dropdown (populated after async fetch)
        self._model_menu = tk.OptionMenu(bar, self._model_var, _DEFAULT_MODEL)
        self._model_menu.configure(
            bg=_BTN_BG, fg=_FG, activebackground=_BTN_ACT,
            activeforeground=_FG_HI, highlightthickness=0,
            relief="flat", font=_FONT_SM, bd=0,
        )
        self._model_menu["menu"].configure(
            bg=_BTN_BG, fg=_FG, activebackground=_BTN_ACT,
            activeforeground=_FG_HI, font=_FONT_SM,
        )
        self._model_menu.pack(side="left", padx=4, pady=2)

        tk.Button(
            bar, text="New Chat", command=self._new_chat,
            bg=_BTN_BG, fg=_FG, activebackground=_BTN_ACT,
            activeforeground=_FG_HI, font=_FONT_SM,
            relief="flat", padx=8, pady=2, bd=0, cursor="hand2",
        ).pack(side="right", padx=6, pady=2)

        # Status bar — pack bottom items BEFORE the expanding transcript
        self._status_var = tk.StringVar(value="Ready — type a message and press Enter")
        tk.Label(
            self, textvariable=self._status_var,
            bg=_STATUS, fg=_FG_DIM, font=_FONT_SM,
            anchor="w", padx=8,
        ).pack(side="bottom", fill="x")

        # Input row
        tk.Frame(self, bg=_BORDER, height=1).pack(side="bottom", fill="x")
        input_row = tk.Frame(self, bg=_STATUS, bd=0)
        input_row.pack(side="bottom", fill="x")
        self._entry = tk.Entry(
            input_row, bg=_BG, fg=_FG, insertbackground=_FG,
            font=_FONT, relief="flat", bd=0, highlightthickness=0,
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=5)
        self._entry.bind("<Return>", lambda e: self._send())

        self._send_btn = tk.Button(
            input_row, text="SEND", command=self._send,
            bg=_BTN_BG, fg=_FG, activebackground=_BTN_ACT,
            activeforeground=_FG_HI, font=_FONT_B,
            relief="flat", padx=10, pady=3, bd=0, cursor="hand2",
        )
        self._send_btn.pack(side="right", padx=6, pady=4)

        # Transcript — fills remaining space after bottom items are reserved
        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")
        transcript_frame = tk.Frame(self, bg=_BG)
        transcript_frame.pack(fill="both", expand=True)

        self._transcript = tk.Text(
            transcript_frame, bg=_BG, fg=_FG, font=_FONT,
            relief="flat", bd=0, wrap="word", state="disabled",
            cursor="arrow", highlightthickness=0,
            padx=8, pady=6, spacing3=4,
        )
        scroll = tk.Scrollbar(transcript_frame, command=self._transcript.yview,
                              bg=_STATUS, troughcolor=_STATUS)
        self._transcript.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._transcript.pack(fill="both", expand=True)

        # Text tags
        self._transcript.tag_configure("user",      foreground=_FG_HI, font=_FONT_B)
        self._transcript.tag_configure("assistant", foreground=_FG,    font=_FONT)
        self._transcript.tag_configure("system",    foreground=_FG_SYS, font=_FONT_SM)
        self._transcript.tag_configure("thinking",  foreground=_FG_DIM, font=_FONT_SM)

        self._append("system",
                     f"Local Ollama chat  •  model: {self._model_var.get()}\n"
                     "Fetching available models…\n")
        self._entry.focus_set()

    # ── Model loading ────────────────────────────────────────────────

    def _load_models_async(self) -> None:
        def _worker():
            models = _fetch_models()
            self._reply_queue.put(("models", models))
        threading.Thread(target=_worker, daemon=True).start()

    def _apply_models(self, models: list[str]) -> None:
        self._available_models = models
        menu = self._model_menu["menu"]
        menu.delete(0, "end")
        if models:
            for m in models:
                menu.add_command(label=m, command=tk._setit(self._model_var, m))
            # pick best default: prefer the existing default if present
            if _DEFAULT_MODEL in models:
                self._model_var.set(_DEFAULT_MODEL)
            else:
                self._model_var.set(models[0])
            self._append("system", f"Models available: {', '.join(models)}\n")
        else:
            menu.add_command(label=_DEFAULT_MODEL,
                             command=tk._setit(self._model_var, _DEFAULT_MODEL))
            self._append("system",
                         "Ollama not reachable — is it running? (ollama serve)\n"
                         f"Defaulting to {_DEFAULT_MODEL}\n")
        self._status_var.set("Ready")

    # ── Send / receive ───────────────────────────────────────────────

    def _send(self) -> None:
        text = self._entry.get().strip()
        if not text or self._busy:
            return
        self._entry.delete(0, "end")
        self._append("user", f"You: {text}\n")
        self._context.append({"role": "user", "content": text})

        # Trim context to rolling window
        if len(self._context) > _MAX_CONTEXT * 2:
            self._context = self._context[-_MAX_CONTEXT * 2:]

        model = self._model_var.get()
        self._busy = True
        self._send_btn.configure(state="disabled", text="…")
        self._status_var.set(f"Waiting for {model}…")

        ctx_snapshot = list(self._context)

        def _worker():
            try:
                reply = _chat(model, ctx_snapshot)
                self._reply_queue.put(("reply", reply))
            except Exception as exc:
                self._reply_queue.put(("error", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._reply_queue.get_nowait()
                if kind == "models":
                    self._apply_models(payload)
                elif kind == "reply":
                    self._context.append({"role": "assistant", "content": payload})
                    self._append("assistant", f"AI: {payload}\n")
                    self._busy = False
                    self._send_btn.configure(state="normal", text="SEND")
                    self._status_var.set("Ready")
                elif kind == "error":
                    self._append("system", f"[Error] {payload}\n")
                    self._busy = False
                    self._send_btn.configure(state="normal", text="SEND")
                    self._status_var.set("Error — see transcript")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ── Helpers ──────────────────────────────────────────────────────

    def _append(self, tag: str, text: str) -> None:
        self._transcript.configure(state="normal")
        self._transcript.insert("end", text, tag)
        self._transcript.see("end")
        self._transcript.configure(state="disabled")

    def _new_chat(self) -> None:
        self._context.clear()
        self._transcript.configure(state="normal")
        self._transcript.delete("1.0", "end")
        self._transcript.configure(state="disabled")
        self._append("system", "New conversation started.\n")
        self._status_var.set("Ready")
        self._entry.focus_set()


# ── KleinChat registration ────────────────────────────────────────────

class OllamaChat(KleinChat):
    title = "KleinCHAT"

    def create(self, parent: tk.Widget, on_exit: Callable) -> tk.Widget:
        return OllamaChatPane(parent, on_exit=on_exit)
