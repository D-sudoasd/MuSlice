# -*- coding: utf-8 -*-
"""Minimal collapsible HelpPanel for thickness_designer_gui_v5.py

Required API:
  - is_expanded() -> bool
  - _toggle() -> None
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class HelpPanel(ttk.Frame):
    def __init__(self, master, title: str = "Help", text: str | None = None):
        super().__init__(master)

        self._expanded = True

        # Header
        hdr = ttk.Frame(self)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(0, weight=1)

        ttk.Label(hdr, text=title).grid(row=0, column=0, sticky="w")
        self._btn = ttk.Button(hdr, text="Hide", width=8, command=self._toggle)
        self._btn.grid(row=0, column=1, sticky="e")

        # Body
        self._body = ttk.Frame(self)
        self._body.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.columnconfigure(0, weight=1)

        default_text = (
            "• 建议先用 μt=0.5–1.2 评估范围，再根据计数率微调。\n"
            "• 优先用实测密度；估算密度只适合粗略预估。\n"
            "• 若要预算整套束路吸收（窗片/空气/毛细管），请在 ⑤ Layers 勾选 Total stack。\n"
            "• 83 keV 高能 SXRD：空气/窗口吸收常被低估，尤其是长空气程与厚 Kapton。\n"
        )

        self._txt = tk.Text(self._body, height=6, wrap="word", bd=0)
        self._txt.insert("1.0", text if text else default_text)
        self._txt.configure(state="disabled")
        self._txt.pack(fill="x", expand=False)

    def is_expanded(self) -> bool:
        return bool(self._expanded)

    def _toggle(self) -> None:
        # (kept as a private method because v5.py calls _toggle() directly)
        if self._expanded:
            self._body.grid_remove()
            self._btn.configure(text="Show")
            self._expanded = False
        else:
            self._body.grid()
            self._btn.configure(text="Hide")
            self._expanded = True
