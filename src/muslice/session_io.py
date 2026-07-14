# -*- coding: utf-8 -*-
"""Save / load full MuSlice GUI sessions as JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from muslice import __app_name__, __version__

SESSION_SCHEMA = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def save_session(path: Path | str, session: Dict[str, Any]) -> None:
    path = Path(path)
    payload = {
        "schema": SESSION_SCHEMA,
        "app": "muslice",
        "version": __version__,
        "saved_at_utc": utc_now_iso(),
        **session,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_session(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Session file must be a JSON object.")
    schema = int(data.get("schema", 0))
    if schema != SESSION_SCHEMA:
        raise ValueError(
            f"Unsupported session schema {schema} (this app supports schema {SESSION_SCHEMA})."
        )
    app = str(data.get("app", "")).lower()
    if app and app not in {"muslice", ""}:
        raise ValueError(f"Session app field is '{app}', expected 'muslice'.")
    return data


def composition_from_pairs(pairs: List[tuple[str, float]], basis: str) -> Dict[str, Any]:
    return {
        "basis": basis,
        "elements": [{"symbol": s, "percent": float(v)} for s, v in pairs],
    }


def pairs_from_composition(comp: Dict[str, Any]) -> tuple[str, List[tuple[str, float]]]:
    basis = str(comp.get("basis", "wt"))
    elements = comp.get("elements", [])
    pairs: List[tuple[str, float]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        sym = str(el.get("symbol", "")).strip()
        try:
            pct = float(el.get("percent"))
        except (TypeError, ValueError):
            continue
        if sym:
            pairs.append((sym, pct))
    return basis, pairs
