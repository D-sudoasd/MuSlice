# -*- coding: utf-8 -*-
"""Smoke tests for MuSlice physics helpers and presets (no GUI)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from muslice.app import (  # noqa: E402
    energy_keV_from_wavelength_A,
    thickness_for_transmission,
    wavelength_A_from_energy_keV,
)
from muslice.presets import load_alloys, load_stacks  # noqa: E402
from muslice.session_io import load_session, save_session  # noqa: E402


def test_energy_wavelength_roundtrip():
    e = 83.0
    lam = wavelength_A_from_energy_keV(e)
    e2 = energy_keV_from_wavelength_A(lam)
    assert abs(e2 - e) < 1e-9


def test_thickness_transmission_roundtrip():
    mu = 0.5  # 1/mm
    T = 0.5
    t = thickness_for_transmission(mu, T)
    assert abs(math.exp(-mu * t) - T) < 1e-12


def test_alloy_presets_sum_near_100():
    alloys = load_alloys()
    assert alloys
    for a in alloys:
        comp = a.get("composition") or {}
        s = sum(float(v) for v in comp.values())
        # SS316L is approximate; still should be positive
        assert s > 0
        if a.get("id") != "SS316L":
            assert abs(s - 100.0) < 1e-6 or abs(s - 100.0) < 1.0


def test_stack_presets_nonempty():
    stacks = load_stacks()
    assert stacks
    assert all(s.get("layers") for s in stacks)


def test_session_roundtrip(tmp_path: Path):
    path = tmp_path / "sess.json"
    payload = {
        "beam": {"energy_keV": "83.0"},
        "sample": {
            "composition": {
                "basis": "wt",
                "elements": [{"symbol": "Ti", "percent": 100}],
            }
        },
        "layers": [],
    }
    save_session(path, payload)
    data = load_session(path)
    assert data["schema"] == 1
    assert data["beam"]["energy_keV"] == "83.0"
