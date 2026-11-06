"""
klein_monitors/terminal_pane.py

TerminalPane — a minimal interactive terminal widget.

The pane owns its UI; the caller supplies a command executor:

    def my_executor(text: str) -> str:
        ...

    pane = TerminalPane(parent, executor=my_executor)

When the player presses Enter the executor is called in a background
thread; its return value is appended to the output area.

Pass executor=None to get a simple local shell (help / echo / clear).
"""

from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable, Optional

from kleinos.palette import (
    BG as _BG, FG_ON as _FG, FG as _DIM, FG_PROMPT as _PROMPT,
    CHROME as _CHROME, BORDER as _BORDER,
)
_FONT    = ("Consolas", 9)
_FONT_SB = ("Consolas", 9, "bold")


class TerminalPane(tk.Frame):
    """
    Green-phosphor terminal widget.

    executor(text) -> str   called in a background thread for each command.
    If executor is None a built-in mini-shell handles help/echo/clear.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        executor: Optional[Callable[[str], str]] = None,
        prompt: str = "C:\\> ",
        header: str = "KleinOS Terminal  [type 'help' for commands]",
    ):
        super().__init__(parent, bg=_BG, bd=0, highlightthickness=0)
        self._executor = executor or self._builtin
        self._prompt = prompt
        self._header = header
        self._busy = False
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Chrome bar
        bar = tk.Frame(self, bg=_CHROME, bd=0)
        bar.pack(fill="x")
        tk.Label(bar, text="KleinOS Terminal", bg=_CHROME, fg=_FG,
                 font=_FONT_SB, padx=6, pady=3).pack(side="left")

        tk.Frame(self, bg=_BORDER, height=1).pack(fill="x")

        # Output
        self._text = tk.Text(
            self,
            bg=_BG,
            fg=_FG,
            font=_FONT,
            relief="flat",
            bd=0,
            wrap="word",
            state="disabled",
            cursor="arrow",
            highlightthickness=0,
            insertbackground=_FG,
        )
        scroll = tk.Scrollbar(self, command=self._text.yview, bg=_BG, troughcolor=_BG)
        self._text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._text.pack(fill="both", expand=True)

        self._text.tag_config("prompt", foreground=_PROMPT)
        self._text.tag_config("output", foreground=_FG)
        self._text.tag_config("error",  foreground="#ff4444")
        self._text.tag_config("dim",    foreground=_DIM)

        # Input row
        input_row = tk.Frame(self, bg=_CHROME, bd=0)
        input_row.pack(fill="x")
        tk.Label(input_row, text=self._prompt, bg=_CHROME, fg=_PROMPT,
                 font=_FONT).pack(side="left", padx=(4, 0))
        self._entry = tk.Entry(
            input_row,
            bg=_BG,
            fg=_PROMPT,
            font=_FONT,
            relief="flat",
            bd=0,
            insertbackground=_PROMPT,
            highlightthickness=0,
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=4, pady=3)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Up>",     self._history_up)
        self._entry.bind("<Down>",   self._history_down)
        self._entry.focus_set()

        self._history: list[str] = []
        self._hist_pos: int = -1

        if self._header:
            self._append(self._header + "\n", "dim")

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _on_enter(self, _event=None) -> None:
        if self._busy:
            return
        text = self._entry.get().strip()
        self._entry.delete(0, "end")
        if not text:
            return
        self._history.append(text)
        self._hist_pos = -1
        self._append(f"{self._prompt}{text}\n", "prompt")
        self._busy = True
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text: str) -> None:
        try:
            result = self._executor(text)
        except Exception as exc:
            result = f"[Error] {exc}"
        self.after(0, self._finish, result)

    def _finish(self, result: str) -> None:
        self._busy = False
        self._append(result.rstrip("\n") + "\n", "output")

    def _history_up(self, _event=None) -> None:
        if not self._history:
            return
        self._hist_pos = max(0, self._hist_pos - 1
                             if self._hist_pos >= 0
                             else len(self._history) - 1)
        self._entry.delete(0, "end")
        self._entry.insert(0, self._history[self._hist_pos])

    def _history_down(self, _event=None) -> None:
        if self._hist_pos < 0:
            return
        self._hist_pos += 1
        self._entry.delete(0, "end")
        if self._hist_pos < len(self._history):
            self._entry.insert(0, self._history[self._hist_pos])
        else:
            self._hist_pos = -1

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _append(self, text: str, tag: str = "output") -> None:
        self._text.config(state="normal")
        self._text.insert("end", text, tag)
        self._text.see("end")
        self._text.config(state="disabled")

    def write(self, text: str) -> None:
        """External callers can push text in (from the main thread)."""
        self._append(text, "output")

    # ------------------------------------------------------------------
    # Built-in mini-shell (used when no executor is provided)
    # ------------------------------------------------------------------

    def _builtin(self, text: str) -> str:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            return (
                "Built-in commands:\n"
                "  help          — this list\n"
                "  echo <text>   — repeat text\n"
                "  clear         — clear screen\n"
                "  about         — version info\n"
            )
        elif cmd == "echo":
            return arg or ""
        elif cmd == "clear":
            self.after(0, self._clear)
            return ""
        elif cmd == "about":
            return "KleinOS Terminal  v1.0  — KleinBOTTLE"
        else:
            return f"'{cmd}' is not recognised.  Type 'help' for commands."

    def _clear(self) -> None:
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.config(state="disabled")
