# -*- coding: utf-8 -*-
r"""Minimal ConfigManager for thickness_designer_gui_v5.py

Stores small persistent settings (theme, window size) in a JSON file.

Cross-platform location:
  - Windows: %APPDATA%\<app_name>\config.json
  - Linux/macOS: ~/.config/<app_name>/config.json  (or $XDG_CONFIG_HOME)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def _default_config_dir(app_name: str) -> Path:
    if os.name == "nt" and os.getenv("APPDATA"):
        return Path(os.getenv("APPDATA")) / app_name
    if os.getenv("XDG_CONFIG_HOME"):
        return Path(os.getenv("XDG_CONFIG_HOME")) / app_name
    return Path.home() / ".config" / app_name


class ConfigManager:
    def __init__(self, app_name: str = "muslice"):
        self.app_name = app_name
        self.config_path = _default_config_dir(app_name) / "config.json"
        self._cfg: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self.config_path.exists():
                self._cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            else:
                self._cfg = {}
        except Exception:
            # corrupted JSON or permission issue -> fall back safely
            self._cfg = {}

    def _save(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(self._cfg, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            # don't crash the GUI for config I/O problems
            pass

    def get(self, key: str, default=None):
        return self._cfg.get(key, default)

    def set(self, key: str, value) -> None:
        self._cfg[key] = value
        self._save()

    def load_window_state(self) -> Dict[str, Any]:
        """Return window state dict: {'width': int, 'height': int, 'maximized': bool}."""
        ws = self._cfg.get("window_state", {})
        if not isinstance(ws, dict):
            ws = {}

        def _safe_dim(value: Any, default: int) -> int:
            try:
                out = int(value)
            except Exception:
                return default
            # Guard against corrupted/extreme values from edited config.
            if out < 200 or out > 20000:
                return default
            return out

        def _safe_bool(value: Any) -> bool:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        width = _safe_dim(ws.get("width", 1120), 1120)
        height = _safe_dim(ws.get("height", 720), 720)
        maximized = _safe_bool(ws.get("maximized", False))
        return {"width": width, "height": height, "maximized": maximized}

    def save_window_state(self, width: int, height: int, maximized: bool) -> None:
        self._cfg["window_state"] = {
            "width": int(width),
            "height": int(height),
            "maximized": bool(maximized),
        }
        self._save()
