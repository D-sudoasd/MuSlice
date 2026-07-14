# -*- coding: utf-8 -*-
"""Load alloy and stack presets from JSON data files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def data_root() -> Path:
    """Resolve the repository/package data directory."""
    env = os.environ.get("MUSLICE_DATA")
    if env:
        p = Path(env)
        if p.is_dir():
            return p

    here = Path(__file__).resolve().parent
    candidates = [
        here / "data",  # src/muslice/data
        here.parents[1] / "data",  # src/data (unlikely)
        here.parents[2] / "data",  # repo/data when layout is repo/src/muslice
        Path.cwd() / "data",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # default preferred layout
    return here.parents[2] / "data"


def presets_dir() -> Path:
    return data_root() / "presets"


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Preset file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_alloys() -> List[Dict[str, Any]]:
    path = presets_dir() / "alloys.json"
    data = _load_json(path)
    alloys = data.get("alloys", data if isinstance(data, list) else [])
    if not isinstance(alloys, list):
        raise ValueError("alloys.json must contain an 'alloys' list.")
    return alloys


def load_stacks() -> List[Dict[str, Any]]:
    path = presets_dir() / "stacks.json"
    data = _load_json(path)
    stacks = data.get("stacks", data if isinstance(data, list) else [])
    if not isinstance(stacks, list):
        raise ValueError("stacks.json must contain a 'stacks' list.")
    return stacks


def alloy_by_id(alloy_id: str) -> Optional[Dict[str, Any]]:
    for a in load_alloys():
        if str(a.get("id", "")) == alloy_id:
            return a
    return None


def stack_by_id(stack_id: str) -> Optional[Dict[str, Any]]:
    for s in load_stacks():
        if str(s.get("id", "")) == stack_id:
            return s
    return None


def alloy_choices() -> List[tuple[str, str]]:
    """Return list of (id, display_name)."""
    out = []
    for a in load_alloys():
        aid = str(a.get("id", ""))
        name = str(a.get("name", aid))
        if aid:
            out.append((aid, name))
    return out


def stack_choices() -> List[tuple[str, str]]:
    out = []
    for s in load_stacks():
        sid = str(s.get("id", ""))
        name = str(s.get("name", sid))
        if sid:
            out.append((sid, name))
    return out
