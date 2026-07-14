#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SXRD Transmission Thickness Designer (GUI) — v5 (Detector + Layers + Exposure)

面向新手的“透射式 SXRD / SAXS 样品厚度”快速设计器。

核心物理：
    T = I/I0 = exp(-μ t_eff)
    μ = (μ/ρ)_mix · ρ
    (μ/ρ)_mix = Σ w_i (μ/ρ)_i   (质量分数加权)
    t_eff = t / cos(tilt)      (若存在入射倾角)

你需要输入：
    1) X-ray 能量 E (keV) 或波长 λ (Å)
    2) 样品成分（wt.% 或 at.%），可一键互换
    3) 样品密度 ρ（强烈推荐实测值；估算仅用于“粗略”）
    4) 目标透过率 T 或目标 μt

程序会自动：
    - 从 xraydb 获取元素 (μ/ρ)(E) 并做合金加权
    - 计算 μ、1/μ、推荐厚度 t（以及常用 T 列表）
    - 绘制 T–t 曲线（若安装 numpy/matplotlib）

依赖（建议）：
    pip install xraydb numpy matplotlib

可选（更“高级感”的主题，Windows 上很漂亮）：
    pip install sv-ttk

运行：
    python thickness_designer_gui_v4.py
"""

from __future__ import annotations

import math
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# UI/UX improvements
from config_manager import ConfigManager
from help_panel import HelpPanel

# --- Optional scientific deps
try:
    import numpy as np
except Exception:
    np = None

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    Figure = None
    FigureCanvasTkAgg = None

try:
    import xraydb  # https://xraypy.github.io/XrayDB/
except Exception:
    xraydb = None

# --- Optional modern theme
try:
    import sv_ttk  # pip install sv-ttk
except Exception:
    sv_ttk = None


APP_TITLE = "SXRD Transmission Thickness Designer"
APP_SUBTITLE = "Transmission thickness design for SXRD/SAXS (Beer–Lambert attenuation)"

# conversions
HC_KEV_A = 12.398419843320026  # keV·Å
CM_PER_MM = 0.1

# Interstitial-like in metallic alloys: mass contributes but volume contribution is not "bulk density".
INTERSTITIAL_LIKE = {"H", "B", "C", "N", "O"}




# ------------------------- material / stack helpers -------------------------
def parse_formula_simple(formula: str) -> dict[str, int]:
    """
    Parse a simple chemical formula without parentheses, e.g. 'C22H10N2O5', 'SiO2', 'Be', 'C'.
    Returns {element_symbol: count}.
    """
    s = (formula or "").strip()
    if not s:
        raise ValueError("Empty formula.")
    if re.fullmatch(r"(?:[A-Z][a-z]?\d*)+", s) is None:
        raise ValueError(
            f"Invalid formula syntax: '{formula}'. "
            "Only simple formulas without parentheses are supported."
        )
    # Basic token: Element symbol + optional integer
    tokens = re.findall(r"([A-Z][a-z]?)(\d*)", s)
    if not tokens:
        raise ValueError(f"Invalid formula: '{formula}'")
    out: dict[str, int] = {}
    for sym, n in tokens:
        sym = normalize_symbol(sym)
        validate_symbol(sym)
        cnt = int(n) if n else 1
        if cnt <= 0:
            raise ValueError(f"Invalid stoichiometry in formula: '{formula}'")
        out[sym] = out.get(sym, 0) + cnt
    return out


def mass_fractions_from_formula(formula: str) -> dict[str, float]:
    """Convert formula -> mass fractions using atomic masses (requires xraydb)."""
    if xraydb is None:
        raise RuntimeError("Formula conversion requires xraydb (pip install xraydb).")
    atoms = parse_formula_simple(formula)
    mass_terms = {sym: cnt * float(xraydb.atomic_mass(sym)) for sym, cnt in atoms.items()}
    denom = sum(mass_terms.values())
    if denom <= 0:
        raise ValueError("Invalid formula mass conversion.")
    return {sym: mt / denom for sym, mt in mass_terms.items()}


def mass_fractions_dry_air() -> dict[str, float]:
    """
    Approximate dry air mass fractions at ~1 atm, ~20–25°C.
    Uses a simple mole-fraction model: N2 0.78084, O2 0.20946, Ar 0.00934, CO2 0.00040.
    """
    if xraydb is None:
        raise RuntimeError("Air composition requires xraydb (pip install xraydb).")

    # molecule mole fractions
    x_N2 = 0.78084
    x_O2 = 0.20946
    x_Ar = 0.00934
    x_CO2 = 0.00040

    # convert to elemental "moles"
    nN = 2.0 * x_N2
    nO = 2.0 * x_O2 + 2.0 * x_CO2
    nAr = 1.0 * x_Ar
    nC = 1.0 * x_CO2

    mass = {
        "N": nN * float(xraydb.atomic_mass("N")),
        "O": nO * float(xraydb.atomic_mass("O")),
        "Ar": nAr * float(xraydb.atomic_mass("Ar")),
        "C": nC * float(xraydb.atomic_mass("C")),
    }
    denom = sum(mass.values())
    return {k: v / denom for k, v in mass.items() if v > 0}


# ------------------------- tiny UI helpers -------------------------
class ToolTip:
    """Simple hover tooltip for Tk/ttk widgets (pure tkinter, no extra deps)."""

    def __init__(self, widget, text: str, wrap=360):
        self.widget = widget
        self.text = text
        self.wrap = wrap
        self._tip = None
        self._id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, _event=None):
        self._unschedule()
        self._id = self.widget.after(250, self._show)

    def _unschedule(self):
        if self._id is not None:
            try:
                self.widget.after_cancel(self._id)
            except Exception:
                pass
            self._id = None

    def _show(self):
        if self._tip is not None:
            return
        if not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10

        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")

        frm = ttk.Frame(self._tip, style="Tip.TFrame", padding=(10, 8))
        frm.pack(fill="both", expand=True)

        lbl = ttk.Label(frm, text=self.text, style="Tip.TLabel", justify="left", wraplength=self.wrap)
        lbl.pack(anchor="w")

    def _hide(self, _event=None):
        self._unschedule()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def energy_keV_from_wavelength_A(wavelength_A: float) -> float:
    if wavelength_A <= 0:
        raise ValueError("Wavelength must be > 0.")
    return HC_KEV_A / wavelength_A


def wavelength_A_from_energy_keV(energy_keV: float) -> float:
    if energy_keV <= 0:
        raise ValueError("Energy must be > 0.")
    return HC_KEV_A / energy_keV


def safe_float(s: str, default=None):
    try:
        v = float(str(s).strip())
        if math.isfinite(v):
            return v
        return default
    except Exception:
        return default


def normalize_symbol(sym: str) -> str:
    """Normalize element symbol case: 'ti'->'Ti', 'NB'->'Nb'."""
    s = str(sym).strip()
    if not s:
        return s
    s = s.replace(" ", "")
    return s[:1].upper() + s[1:].lower()


def validate_symbol(sym: str) -> None:
    """Validate element symbol against xraydb if available."""
    if not sym:
        raise ValueError("Empty element symbol.")
    if xraydb is None:
        return
    try:
        _ = xraydb.atomic_number(sym)
    except Exception:
        raise ValueError(f"Unknown element symbol: '{sym}'")


def norm_mass_fractions_from_percent(pairs):
    total = sum(v for _, v in pairs)
    if total <= 0:
        raise ValueError("Total % must be > 0.")
    out = {}
    for sym, v in pairs:
        out[sym] = out.get(sym, 0.0) + v / total
    return out


def wt_from_at_percent(pairs):
    """Convert at.% to mass fractions (w_i) using atomic masses."""
    if xraydb is None:
        raise RuntimeError("Atomic% conversion requires xraydb (pip install xraydb).")
    total = sum(v for _, v in pairs)
    if total <= 0:
        raise ValueError("Total at% must be > 0.")
    x = {}
    for sym, v in pairs:
        x[sym] = x.get(sym, 0.0) + v / total

    mass_terms = {}
    for sym, xi in x.items():
        mass_terms[sym] = xi * float(xraydb.atomic_mass(sym))
    denom = sum(mass_terms.values())
    if denom <= 0:
        raise ValueError("Invalid atomic mass conversion.")
    return {sym: mt / denom for sym, mt in mass_terms.items()}


def at_from_wt_percent(pairs):
    """Convert wt.% to at.% using atomic masses."""
    if xraydb is None:
        raise RuntimeError("wt% -> at% conversion requires xraydb (pip install xraydb).")
    total = sum(v for _, v in pairs)
    if total <= 0:
        raise ValueError("Total wt% must be > 0.")
    w = {sym: v / total for sym, v in pairs}
    n_terms = {}
    for sym, wi in w.items():
        n_terms[sym] = wi / float(xraydb.atomic_mass(sym))
    denom = sum(n_terms.values())
    if denom <= 0:
        raise ValueError("Invalid atomic mass conversion.")
    return {sym: ni / denom for sym, ni in n_terms.items()}  # atomic fractions


def estimate_density_rule_of_mixtures(w_mass, model: str = "alloy_interstitial"):
    """
    Estimate alloy density.

    model:
      - alloy_interstitial (default): ignore H/B/C/N/O in volume sum (recommended for metallic alloys)
      - volume_additive: naive 1/rho = Σ w_i/rho_i (for physical mixtures)
      - block_if_interstitial: refuse when interstitial-like elements exist (forces Manual)
    """
    if xraydb is None:
        raise RuntimeError("Density estimate requires xraydb (pip install xraydb).")

    rho_elem = {sym: float(xraydb.atomic_density(sym)) for sym in w_mass.keys()}
    has_interstitial = any(sym in INTERSTITIAL_LIKE for sym in w_mass.keys())

    if model == "block_if_interstitial" and has_interstitial:
        raise ValueError(
            "Density estimate blocked: interstitial-like element detected (H/B/C/N/O). "
            "For alloys, please input measured density (Manual)."
        )

    if model == "volume_additive":
        inv_rho = 0.0
        for sym, wi in w_mass.items():
            ri = rho_elem[sym]
            if ri <= 0:
                raise ValueError(f"Invalid density for element '{sym}'.")
            inv_rho += wi / ri
        if inv_rho <= 0:
            raise ValueError("Invalid mixture density calculation.")
        return 1.0 / inv_rho, {"model": model, "interstitial_detected": has_interstitial, "ignored": []}

    # alloy_interstitial
    ignored = []
    inv_rho = 0.0
    used_any = False
    for sym, wi in w_mass.items():
        if sym in INTERSTITIAL_LIKE:
            ignored.append(sym)
            continue
        ri = rho_elem[sym]
        if ri <= 0:
            raise ValueError(f"Invalid density for element '{sym}'.")
        inv_rho += wi / ri
        used_any = True

    if not used_any:
        raise ValueError("Cannot estimate density: only interstitial-like elements were provided. Use Manual density.")
    rho = 1.0 / inv_rho
    return rho, {"model": model, "interstitial_detected": has_interstitial, "ignored": ignored}


def mu_over_rho_element_cm2_g(sym: str, energy_keV: float, kind="total", source="elam") -> float:
    """Elemental μ/ρ in cm^2/g. xraydb expects energy in eV."""
    if xraydb is None:
        raise RuntimeError("Attenuation lookup requires xraydb (pip install xraydb).")
    e_eV = energy_keV * 1000.0
    if e_eV <= 0:
        raise ValueError("Energy must be > 0.")
    if source.lower() == "chantler":
        return float(xraydb.mu_chantler(sym, e_eV))
    return float(xraydb.mu_elam(sym, e_eV, kind=kind))


def mu_over_rho_mix_cm2_g(w_mass, energy_keV: float, kind="total", source="elam") -> float:
    return sum(wi * mu_over_rho_element_cm2_g(sym, energy_keV, kind=kind, source=source)
               for sym, wi in w_mass.items())


def linear_mu_per_mm(mu_over_rho_cm2_g: float, density_g_cm3: float) -> float:
    mu_per_cm = mu_over_rho_cm2_g * density_g_cm3  # 1/cm
    return mu_per_cm * CM_PER_MM  # 1/mm


def thickness_for_transmission(mu_per_mm: float, transmission: float) -> float:
    if mu_per_mm <= 0:
        raise ValueError("mu must be > 0.")
    if not (0 < transmission < 1):
        raise ValueError("Transmission must be between 0 and 1.")
    return -math.log(transmission) / mu_per_mm


# ------------------------- detector geometry (orthogonal model) -------------------------
def q_from_r_mm(r_mm: float, L_mm: float, wavelength_A: float) -> tuple[float, float]:
    """
    Compute Q (Å^-1) and 2θ (radians) from detector radius r and sample-detector distance L.
    Orthogonal model: detector plane perpendicular to incident beam, small-angle/large-angle supported.
        2θ = arctan(r/L)
        Q = (4π/λ) sin(θ), θ = 0.5·2θ
    """
    if L_mm <= 0:
        raise ValueError("Detector distance L must be > 0.")
    if r_mm < 0:
        raise ValueError("Detector radius r must be >= 0.")
    if wavelength_A <= 0:
        raise ValueError("Wavelength must be > 0.")
    two_theta = math.atan2(r_mm, L_mm)
    theta = 0.5 * two_theta
    Q = (4.0 * math.pi / wavelength_A) * math.sin(theta)
    return Q, two_theta


def detector_rmax_corner_mm(nx: int, ny: int, pixel_mm: float, x0_px: float, y0_px: float) -> float:
    """
    Max radius (mm) from beam center to detector CORNERS (diagonal / geometric extreme).

    Pixel coordinate convention:
      - x0_px, y0_px are pixel-center coordinates in 0-index (e.g., center ~ (Nx/2, Ny/2)).
      - The physical detector edges are at x = -0.5 and x = Nx - 0.5 (same for y).
    """
    if nx <= 1 or ny <= 1:
        raise ValueError("Detector Nx, Ny must be > 1.")
    if pixel_mm <= 0:
        raise ValueError("Pixel size must be > 0.")

    # Use physical edges (±0.5 px) for slightly more accurate geometry.
    corners = [(-0.5, -0.5), (nx - 0.5, -0.5), (-0.5, ny - 0.5), (nx - 0.5, ny - 0.5)]
    rmax_px = 0.0
    for x, y in corners:
        r = math.hypot(x - x0_px, y - y0_px)
        if r > rmax_px:
            rmax_px = r
    return rmax_px * pixel_mm


def detector_rmax_edge_mm(nx: int, ny: int, pixel_mm: float, x0_px: float, y0_px: float) -> float:
    """
    Max radius (mm) for FULL-RING azimuthal coverage (conservative / edge-limited).

    This is the radius of the largest circle centered at (x0, y0) fully contained in the detector,
    i.e., limited by the nearest detector edge.

    If the beam center is outside the detector, this function raises ValueError.
    """
    if nx <= 1 or ny <= 1:
        raise ValueError("Detector Nx, Ny must be > 1.")
    if pixel_mm <= 0:
        raise ValueError("Pixel size must be > 0.")

    # Physical edges at -0.5 and Nx-0.5 (pixel-center convention).
    dx_left = x0_px + 0.5
    dx_right = (nx - 0.5) - x0_px
    dy_top = y0_px + 0.5
    dy_bottom = (ny - 0.5) - y0_px

    if min(dx_left, dx_right, dy_top, dy_bottom) < 0:
        raise ValueError("Beam center (x0,y0) is outside detector bounds. Please check Nx/Ny and x0/y0.")

    rmax_px = min(dx_left, dx_right, dy_top, dy_bottom)
    return rmax_px * pixel_mm


# Backward-compatible alias (older code used detector_rmax_mm as corner-limit)
def detector_rmax_mm(nx: int, ny: int, pixel_mm: float, x0_px: float, y0_px: float) -> float:
    """Alias of detector_rmax_corner_mm (corner-limit)."""
    return detector_rmax_corner_mm(nx, ny, pixel_mm, x0_px, y0_px)


# ------------------------- Composition table -------------------------
class CompositionTable(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.rows = []
        self._build()

    def _available_elements(self):
        if xraydb is None:
            return ["Ti", "Nb", "Zr", "Sn", "Fe", "Ni", "Cr", "Al", "V", "Mo", "W", "Co", "Cu", "Mn", "Si", "C", "O", "N", "H", "B"]
        try:
            return [xraydb.atomic_symbol(z) for z in range(1, 93)]
        except Exception:
            return ["Ti", "Nb", "Zr", "Sn", "Fe", "Ni", "Cr", "Al", "V", "Mo", "W", "Co", "Cu", "Mn", "Si", "C", "O", "N", "H", "B"]

    def _build(self):
        hdr = ttk.Frame(self)
        hdr.grid(row=0, column=0, sticky="ew")
        ttk.Label(hdr, text="Element").grid(row=0, column=0, padx=(0, 6))
        ttk.Label(hdr, text="Fraction (%)").grid(row=0, column=1, padx=(0, 6))
        add_btn = ttk.Button(hdr, text="Add row", command=self.add_row)
        add_btn.grid(row=0, column=2)

        ToolTip(add_btn, "添加一行元素成分输入（元素 + 百分比）。\n\n建议：先输入主要合金元素，再输入微量元素。")

        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.body.columnconfigure(1, weight=1)

        # Default example (Ti2448, wt.%)
        for sym, val in [("Ti", "64"), ("Nb", "24"), ("Zr", "4"), ("Sn", "8")]:
            self.add_row(sym, val)

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        norm_btn = ttk.Button(btns, text="Normalize", command=self.normalize)
        clr_btn = ttk.Button(btns, text="Clear", command=self.clear)
        rm_btn = ttk.Button(btns, text="Remove last", command=self.remove_last)

        norm_btn.pack(side="left")
        clr_btn.pack(side="left", padx=(6, 0))
        rm_btn.pack(side="left", padx=(6, 0))

        ToolTip(norm_btn, "把当前输入的百分比归一化到总和=100%。\n\n例如你输入 Ti=63.8, Nb=24.1 ...，点击后会自动缩放到 100%。")
        ToolTip(clr_btn, "清空所有行（会删掉所有成分输入）。")
        ToolTip(rm_btn, "删除最后一行成分。")

    def add_row(self, sym="Ti", val=""):
        r = len(self.rows)
        el = ttk.Combobox(self.body, values=self._available_elements(), width=6)
        el.set(sym)
        frac = ttk.Entry(self.body)
        frac.insert(0, val)
        el.grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
        frac.grid(row=r, column=1, sticky="ew", padx=(0, 8), pady=3)

        ToolTip(el, "选择或输入元素符号（如 Ti, Nb, Zr）。\n程序会自动纠正大小写：ti -> Ti。")
        ToolTip(frac, "输入该元素的百分比（wt.% 或 at.%，由上方选择决定）。\n不需要你手动归一化，可点击 Normalize。")

        self.rows.append((el, frac))

    def remove_last(self):
        if not self.rows:
            return
        el, frac = self.rows.pop()
        el.destroy()
        frac.destroy()

    def clear(self):
        while self.rows:
            self.remove_last()

    def normalize(self):
        pairs = self.get_pairs(allow_empty=False, normalize_symbols=True)
        total = sum(v for _, v in pairs)
        if total <= 0:
            messagebox.showerror(APP_TITLE, "Total fraction must be > 0.")
            return
        for (el, frac), (_, v) in zip(self.rows, pairs):
            frac.delete(0, tk.END)
            frac.insert(0, f"{v/total*100:.6g}")

    def set_values_from_dict_percent(self, d_percent):
        d = {normalize_symbol(k): float(v) for k, v in d_percent.items()}

        current_syms = []
        for el, _ in self.rows:
            s = normalize_symbol(el.get())
            if s and s not in current_syms:
                current_syms.append(s)

        ordered = []
        for s in current_syms:
            if s in d:
                ordered.append((s, d[s]))
        for s in sorted(d.keys()):
            if s not in current_syms:
                ordered.append((s, d[s]))

        while len(self.rows) < len(ordered):
            self.add_row()

        for i, (sym, val) in enumerate(ordered):
            el, frac = self.rows[i]
            el.set(sym)
            frac.delete(0, tk.END)
            frac.insert(0, f"{val:.6g}")

        for j in range(len(ordered), len(self.rows)):
            _, frac = self.rows[j]
            frac.delete(0, tk.END)

    def get_pairs(self, allow_empty=True, normalize_symbols=False):
        pairs = []
        for el, frac in self.rows:
            sym_raw = el.get()
            sym = normalize_symbol(sym_raw) if normalize_symbols else str(sym_raw).strip()
            v = safe_float(frac.get(), None)
            if v is None:
                if allow_empty:
                    continue
                raise ValueError(f"Invalid fraction for element '{sym}'.")
            if v < 0:
                raise ValueError(f"Negative fraction for element '{sym}'.")
            if normalize_symbols:
                validate_symbol(sym)
            pairs.append((sym, v))
        if not pairs:
            raise ValueError("No valid composition entries.")
        return pairs




# ------------------------- Layer (stack) table -------------------------
class LayerTable(ttk.Frame):
    """
    A small, beginner-friendly layer stack editor for transmission budgeting.
    Each layer contributes: T_i = exp(-μ_i * t_i)
    Total: T_total = Π T_i = exp(-Σ μ_i t_i)
    """
    MATERIALS = [
        "Kapton (C22H10N2O5)",
        "Air (dry)",
        "Vacuum",
        "Sample (current)",
        "Quartz (SiO2)",
        "Graphite (C)",
        "Beryllium (Be)",
        "Custom formula",
    ]

    DEFAULTS = {
        "Kapton (C22H10N2O5)": {"formula": "C22H10N2O5", "rho": 1.42},
        "Air (dry)": {"formula": "", "rho": 0.0012},
        "Vacuum": {"formula": "", "rho": 0.0},
        "Sample (current)": {"formula": "", "rho": None},
        "Quartz (SiO2)": {"formula": "SiO2", "rho": 2.65},
        "Graphite (C)": {"formula": "C", "rho": 2.26},
        "Beryllium (Be)": {"formula": "Be", "rho": 1.85},
        "Custom formula": {"formula": "", "rho": None},
    }

    def __init__(self, master):
        super().__init__(master)
        self.rows = []
        self._build()

    def _build(self):
        # header
        hdr = ttk.Frame(self)
        hdr.grid(row=0, column=0, sticky="ew")
        for c,w in enumerate([5, 20, 10, 10, 18, 12, 3]):
            hdr.columnconfigure(c, weight=0 if c!=1 else 1)

        ttk.Label(hdr, text="Use").grid(row=0, column=0, sticky="w")
        ttk.Label(hdr, text="Material").grid(row=0, column=1, sticky="w", padx=(6,0))
        ttk.Label(hdr, text="t (mm)").grid(row=0, column=2, sticky="w", padx=(6,0))
        ttk.Label(hdr, text="ρ (g/cm³)").grid(row=0, column=3, sticky="w", padx=(6,0))
        ttk.Label(hdr, text="Formula (if needed)").grid(row=0, column=4, sticky="w", padx=(6,0))
        ttk.Label(hdr, text="Auto t").grid(row=0, column=5, sticky="w", padx=(6,0))

        ToolTip(hdr, "这里用于预算“整套实验路径”的总透过率：窗片/毛细管/空气/样品……\\n"
                     "总透过率 T_total = Π exp(-μ_i t_i)。\\n"
                     "提示：做方位积分需要“全环(full-ring)”数据时，windows/air 的吸收往往是隐藏杀手。")

        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="ew")
        self.body.columnconfigure(1, weight=1)

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, sticky="ew", pady=(8,0))
        ttk.Button(btns, text="+ Add layer", command=self.add_row).pack(side="left")
        ttk.Button(btns, text="Load common stack", command=self.load_common_stack).pack(side="left", padx=(8,0))
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="left", padx=(8,0))

        ToolTip(btns, "Load common stack 会自动生成：Kapton + Air + Sample + Air + Kapton。\\n"
                      "Sample 层默认使用主计算得到的厚度（Auto t）。")

        # start with a common stack
        self.load_common_stack()

    def clear(self):
        for r in self.rows:
            r["frame"].destroy()
        self.rows.clear()

    def load_common_stack(self):
        self.clear()
        # Kapton window
        self.add_row(material="Kapton (C22H10N2O5)", t_mm="0.10", auto=False, enabled=True)
        # Air gap
        self.add_row(material="Air (dry)", t_mm="50", auto=False, enabled=True)
        # Sample
        self.add_row(material="Sample (current)", t_mm="", auto=True, enabled=True)
        # Air gap
        self.add_row(material="Air (dry)", t_mm="50", auto=False, enabled=True)
        # Kapton window
        self.add_row(material="Kapton (C22H10N2O5)", t_mm="0.10", auto=False, enabled=True)

    def add_row(self, material=None, t_mm="", auto=False, enabled=True):
        idx = len(self.rows)
        fr = ttk.Frame(self.body)
        fr.grid(row=idx, column=0, sticky="ew", pady=2)
        fr.columnconfigure(1, weight=1)

        v_use = tk.BooleanVar(value=bool(enabled))
        v_mat = tk.StringVar(value=material or self.MATERIALS[0])
        v_t = tk.StringVar(value=str(t_mm))
        v_rho = tk.StringVar(value="")
        v_formula = tk.StringVar(value="")
        v_auto = tk.BooleanVar(value=bool(auto))

        # widgets
        cb = ttk.Checkbutton(fr, variable=v_use)
        cb.grid(row=0, column=0, sticky="w")

        combo = ttk.Combobox(fr, textvariable=v_mat, values=self.MATERIALS, width=24, state="readonly")
        combo.grid(row=0, column=1, sticky="ew", padx=(6,0))

        e_t = ttk.Entry(fr, textvariable=v_t, width=10)
        e_t.grid(row=0, column=2, sticky="w", padx=(6,0))

        e_rho = ttk.Entry(fr, textvariable=v_rho, width=10)
        e_rho.grid(row=0, column=3, sticky="w", padx=(6,0))

        e_form = ttk.Entry(fr, textvariable=v_formula, width=18)
        e_form.grid(row=0, column=4, sticky="w", padx=(6,0))

        cb_auto = ttk.Checkbutton(fr, variable=v_auto)
        cb_auto.grid(row=0, column=5, sticky="w", padx=(6,0))

        btn_del = ttk.Button(fr, text="×", width=3, command=lambda: self._delete_row(fr))
        btn_del.grid(row=0, column=6, sticky="e", padx=(6,0))

        ToolTip(combo, "选择层材料类型。\\n"
                       "Sample (current)：使用 ② Sample 页的成分与密度。\\n"
                       "Custom formula：可输入化学式（不支持括号）。")
        ToolTip(e_t, "层厚度（沿束路方向的几何厚度），单位 mm。\\n"
                     "Air gap 例如 50 mm。Kapton 窗片 0.05–0.25 mm 常见。")
        ToolTip(e_rho, "密度 ρ（g/cm³）。空着会用“典型值”（若该材料有内置）。\\n"
                       "强烈建议：对窗口材料用厂商规格，对空气用实际条件折算。")
        ToolTip(e_form, "当材料为 Custom formula 时，请输入如：C22H10N2O5、SiO2、Be。\\n"
                        "不支持括号/水合物等复杂式子。")
        ToolTip(cb_auto, "仅对 Sample (current) 有效：\\n"
                         "勾选表示该层厚度 = 主计算得到的样品厚度。\\n"
                         "不勾选则使用 t(mm) 输入框。")

        # init defaults
        self._apply_defaults(v_mat.get(), v_rho, v_formula)

        def on_mat_change(_evt=None):
            self._apply_defaults(v_mat.get(), v_rho, v_formula)
            # auto thickness only makes sense for Sample
            if v_mat.get() != "Sample (current)":
                v_auto.set(False)

        combo.bind("<<ComboboxSelected>>", on_mat_change)

        self.rows.append({
            "frame": fr,
            "use": v_use,
            "material": v_mat,
            "t_mm": v_t,
            "rho": v_rho,
            "formula": v_formula,
            "auto": v_auto,
        })

    def _apply_defaults(self, material: str, v_rho: tk.StringVar, v_formula: tk.StringVar):
        d = self.DEFAULTS.get(material, {})
        if v_formula.get().strip() == "" and d.get("formula"):
            v_formula.set(d["formula"])
        if v_rho.get().strip() == "" and d.get("rho") is not None:
            # keep a compact string
            v_rho.set(f"{d['rho']:.6g}")

    def _delete_row(self, fr):
        # remove row and re-pack grid
        idx = None
        for i, r in enumerate(self.rows):
            if r["frame"] is fr:
                idx = i
                break
        if idx is None:
            return
        self.rows[idx]["frame"].destroy()
        self.rows.pop(idx)
        # re-grid
        for i, r in enumerate(self.rows):
            r["frame"].grid_configure(row=i)

    def get_layers(self):
        """Return a list of layer dicts with raw user inputs."""
        out = []
        for r in self.rows:
            if not r["use"].get():
                continue
            out.append({
                "material": r["material"].get(),
                "t_mm": r["t_mm"].get(),
                "rho": r["rho"].get(),
                "formula": r["formula"].get(),
                "auto": bool(r["auto"].get()),
            })
        return out


# ------------------------- Main App -------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(1120, 720)

        # Config manager for persistent settings
        self.config_manager = ConfigManager()

        # Load window geometry from config
        window_state = self.config_manager.load_window_state()
        if window_state["maximized"]:
            self.state('zoomed')
        else:
            self.geometry(f"{window_state['width']}x{window_state['height']}")

        # state
        self.energy_mode = tk.StringVar(value="keV")
        self.energy_keV = tk.StringVar(value="83.0")
        self.wavelength_A = tk.StringVar(value=f"{wavelength_A_from_energy_keV(83.0):.6g}")
        self.source_db = tk.StringVar(value="elam")
        self.cross_kind = tk.StringVar(value="total")

        # Composition basis and conversion UX
        self.fraction_basis = tk.StringVar(value="wt")  # 'wt' or 'at'
        self.basis_warning = tk.StringVar(
            value="提示：切换 wt.%/at.% 只改变“解释方式”，不会自动换算数值。需要换算请点右侧 Convert。"
        )

        # Density
        self.density_mode = tk.StringVar(value="manual")
        self.density_g_cm3 = tk.StringVar(value="")
        self.density_est_model = tk.StringVar(value="alloy_interstitial")  # estimate model

        # Geometry
        self.incident_angle_deg = tk.StringVar(value="0")

        # Design targets
        self.target_mode = tk.StringVar(value="T")
        self.target_T = tk.StringVar(value="0.5")
        self.target_mut = tk.StringVar(value="0.7")
        self.reco_mut_min = tk.StringVar(value="0.5")
        self.reco_mut_max = tk.StringVar(value="1.2")



        # Target scope: sample-only vs total stack (layers)
        self.target_scope_total = tk.BooleanVar(value=False)

        # Last computed sample thickness (mm) for sharing across tabs (Layers / Exposure)
        self.last_sample_thickness_mm: float | None = None
        self.last_mu_eff_1_per_mm: float | None = None
        self.last_other_mut: float | None = None

        # Exposure estimator inputs (ratio / scaling)
        self.exp_ref_time_s = tk.StringVar(value="1.0")
        self.exp_ref_t_sample_mm = tk.StringVar(value="1.0")
        self.exp_ref_flux = tk.StringVar(value="")
        self.exp_ref_Ttotal = tk.StringVar(value="")  # optional

        self.exp_new_flux = tk.StringVar(value="")
        self.exp_eff_ratio = tk.StringVar(value="1.0")  # (eta_new / eta_ref)
        self.exp_snr_ratio = tk.StringVar(value="1.0")  # (SNR_new / SNR_ref)
        self.exp_model = tk.StringVar(value="linear")   # 'linear' or 'absorption'
        self.exp_use_computed_t = tk.BooleanVar(value=True)
        self.exp_new_t_sample_mm = tk.StringVar(value="")  # used if not computed

        # Detector / geometry (optional): compute Q & d coverage (orthogonal detector model)
        self.det_enable = tk.BooleanVar(value=True)
        # Sample-to-detector distance L (mm)
        self.det_L_mm = tk.StringVar(value="1500")
        # Pixel size (mm/pixel), e.g., 0.15 mm for 150 µm pixels
        self.det_pixel_mm = tk.StringVar(value="0.15")
        # Detector pixel dimensions (Nx, Ny)
        self.det_nx = tk.StringVar(value="2880")
        self.det_ny = tk.StringVar(value="2880")
        # Beam center (x0, y0) in pixels (0-index). Default set to detector center.
        self.det_x0 = tk.StringVar(value="1440")
        self.det_y0 = tk.StringVar(value="1440")
        # If Nx/Ny are changed, x0/y0 can become out-of-bounds and produce confusing Q ranges.
        # Heuristic: if x0/y0 currently equal the *previous* detector center, auto-update to the new center.
        self._det_last_nx = int(float(self.det_nx.get()))
        self._det_last_ny = int(float(self.det_ny.get()))
        try:
            self.det_nx.trace_add("write", lambda *_: self._on_detector_size_change())
            self.det_ny.trace_add("write", lambda *_: self._on_detector_size_change())
        except Exception:
            # trace_add may not exist in very old Tk builds; in that case we fall back to runtime checks.
            pass

        # Inner masked radius (beamstop / unusable region) in mm; determines Qmin
        self.det_rmin_mm = tk.StringVar(value="2.0")
        # Optional: manual outer radius rmax (mm). Leave blank to auto-compute from detector corners.
        self.det_rmax_mm = tk.StringVar(value="")

        # status & output
        self.status = tk.StringVar(value="Ready.")
        self._last_summary = ""

        # theme / style
        self._apply_theme()
        self._build()
        self._build_menu()

    # ---------- Theme ----------
    def _apply_theme(self, theme_name: str = None):
        """
        Apply theme to the application

        Args:
            theme_name: "light" or "dark" (if None, loads from config)
        """
        if theme_name is None:
            theme_name = self.config_manager.get("theme", "light")

        style = ttk.Style(self)

        # Prefer a modern theme if available
        if sv_ttk is not None:
            try:
                # sv_ttk supports light and dark themes
                sv_ttk.set_theme(theme_name)
                self._current_theme = theme_name
                self.config_manager.set("theme", theme_name)
            except Exception:
                pass
        else:
            # fallback to a clean built-in theme
            for candidate in ("clam", "vista", "xpnative", "alt", "default"):
                try:
                    style.theme_use(candidate)
                    break
                except Exception:
                    continue

        # Typography (Windows-friendly defaults)
        default_font = ("Segoe UI", 10)
        heading_font = ("Segoe UI", 12, "bold")
        small_font = ("Segoe UI", 9)

        self.option_add("*Font", default_font)

        # Card-like frames
        style.configure("Card.TLabelframe", padding=10)
        style.configure("Card.TLabelframe.Label", font=heading_font)

        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("SubTitle.TLabel", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", font=small_font, foreground="#555555")

        # Buttons
        style.configure("Primary.TButton", padding=(12, 6))
        style.configure("Secondary.TButton", padding=(10, 5))

        # Tooltip styles
        style.configure("Tip.TFrame", relief="solid", borderwidth=1)
        style.configure("Tip.TLabel", font=small_font)

    # ---------- Layout ----------
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        # Header
        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text=APP_TITLE, style="Title.TLabel")
        subtitle = ttk.Label(header, text=APP_SUBTITLE, style="SubTitle.TLabel")
        title.grid(row=0, column=0, sticky="w")
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Dependency banner
        dep = []
        if xraydb is None:
            dep.append("xraydb missing → attenuation lookup disabled")
        if np is None:
            dep.append("numpy missing → plotting disabled")
        if Figure is None or FigureCanvasTkAgg is None:
            dep.append("matplotlib missing → plotting disabled")
        if dep:
            dep_lbl = ttk.Label(header, text="⚠ " + " | ".join(dep), style="Muted.TLabel", foreground="#A00000")
            dep_lbl.grid(row=2, column=0, sticky="w", pady=(6, 0))
            ToolTip(dep_lbl, "建议安装：pip install xraydb numpy matplotlib\n\n可选更高级主题：pip install sv-ttk")

        # Main split
        paned = ttk.PanedWindow(root, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew")
        root.rowconfigure(1, weight=1)

        left = ttk.Frame(paned, padding=(0, 0, 8, 0))
        right = ttk.Frame(paned, padding=(8, 0, 0, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)  # Help panel weight=0

        paned.add(left, weight=2)
        paned.add(right, weight=3)

        # Notebook (Inputs)
        nb = ttk.Notebook(left)
        nb.grid(row=0, column=0, sticky="nsew")

        tab_beam = ttk.Frame(nb, padding=12)
        tab_sample = ttk.Frame(nb, padding=12)
        tab_target = ttk.Frame(nb, padding=12)
        tab_detector = ttk.Frame(nb, padding=12)
        tab_layers = ttk.Frame(nb, padding=12)
        tab_exposure = ttk.Frame(nb, padding=12)
        tab_help = ttk.Frame(nb, padding=12)

        nb.add(tab_beam, text="① Beam")
        nb.add(tab_sample, text="② Sample")
        nb.add(tab_target, text="③ Target")
        nb.add(tab_detector, text="④ Detector")
        nb.add(tab_layers, text="⑤ Layers")
        nb.add(tab_exposure, text="⑥ Exposure")
        nb.add(tab_help, text="⑦ Quick Start")

        self._build_beam_tab(tab_beam)
        self._build_sample_tab(tab_sample)
        self._build_target_tab(tab_target)
        self._build_detector_tab(tab_detector)
        self._build_layers_tab(tab_layers)
        self._build_exposure_tab(tab_exposure)
        self._build_help_tab(tab_help)

        # Action buttons
        actions = ttk.Frame(left)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)

        compute_btn = ttk.Button(actions, text="Compute thickness", style="Primary.TButton", command=self.compute)
        export_btn = ttk.Button(actions, text="Export report", style="Secondary.TButton", command=self.export_report)
        copy_btn = ttk.Button(actions, text="Copy summary", style="Secondary.TButton", command=self.copy_summary)

        compute_btn.grid(row=0, column=0, sticky="ew")
        export_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        copy_btn.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        ToolTip(compute_btn, "根据输入的能量/成分/密度/目标，计算推荐厚度。\n\n建议：第一次先用默认 μt=0.5–1.2 窗口评估范围。")
        ToolTip(export_btn, "把当前计算结果保存为 txt 文本，方便放进实验记录或邮件。")
        ToolTip(copy_btn, "把结果复制到剪贴板（可直接粘贴到实验记录表/笔记）。")

        # Results panel
        res_title = ttk.Label(right, text="Results", style="Title.TLabel")
        res_title.grid(row=0, column=0, sticky="w")

        self.result_text = tk.Text(right, height=14, wrap="word", bd=0)
        self.result_text.grid(row=1, column=0, sticky="nsew", pady=(8, 10))
        self.result_text.configure(state="disabled")

        ToolTip(res_title, "这里显示计算细节：μ/ρ、μ、1/μ、推荐厚度、常用 T 列表等。")

        # Plot area
        plot_card = ttk.LabelFrame(right, text="Transmission curve", style="Card.TLabelframe")
        plot_card.grid(row=2, column=0, sticky="nsew")
        plot_card.columnconfigure(0, weight=1)
        plot_card.rowconfigure(0, weight=1)

        self.plot_frame = ttk.Frame(plot_card)
        self.plot_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas = None

        # Help panel (new)
        self.help_panel = HelpPanel(right, title="💡 使用提示")
        self.help_panel.grid(row=3, column=0, sticky="nsew", pady=(10, 0))

        # Status bar
        status = ttk.Label(root, textvariable=self.status, style="Muted.TLabel")
        status.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ToolTip(status, "状态栏：提示缺少依赖、输入错误、或当前操作结果。")

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Export report...", command=self.export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.destroy)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Copy summary", command=self.copy_summary)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_radiobutton(
            label="Light theme ☀️",
            value="light",
            variable=self._get_theme_var(),
            command=lambda: self._apply_theme("light")
        )
        view_menu.add_radiobutton(
            label="Dark theme 🌙",
            value="dark",
            variable=self._get_theme_var(),
            command=lambda: self._apply_theme("dark")
        )
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="Show help panel",
            variable=self._get_help_panel_visible_var(),
            command=self._toggle_help_panel
        )

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Quick Start", command=self._show_quick_start)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._about)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        menubar.add_cascade(label="View", menu=view_menu)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

        # Keyboard shortcuts
        self.bind("<Control-Return>", lambda e: self.compute())
        self.bind("<Control-s>", lambda e: self.export_report())
        self.bind("<Control-c>", lambda e: self.copy_summary())
        self.bind("<F1>", lambda e: self._show_quick_start())
        self.bind("<Control-t>", lambda e: self._toggle_theme())
        self.bind("<Control-h>", lambda e: self._toggle_help_panel())

    def _get_theme_var(self):
        """Get theme variable for menu"""
        if not hasattr(self, "_theme_var"):
            self._theme_var = tk.StringVar(value=self.config_manager.get("theme", "light"))
        return self._theme_var

    def _toggle_theme(self):
        """Toggle between light and dark theme"""
        current = self.config_manager.get("theme", "light")
        new_theme = "dark" if current == "light" else "light"
        self._apply_theme(new_theme)
        self._get_theme_var().set(new_theme)

    def _get_help_panel_visible_var(self):
        """Get help panel visibility variable"""
        if not hasattr(self, "_help_panel_visible_var"):
            self._help_panel_visible_var = tk.BooleanVar(value=True)
        return self._help_panel_visible_var

    def _toggle_help_panel(self):
        """Toggle help panel visibility"""
        if self.help_panel.is_expanded():
            self.help_panel._toggle()
            self._get_help_panel_visible_var().set(False)
        else:
            self.help_panel._toggle()
            self._get_help_panel_visible_var().set(True)

    def _about(self):
        messagebox.showinfo(
            APP_TITLE,
            "SXRD Transmission Thickness Designer (v3)\n"
            "• Beer–Lambert attenuation model\n"
            "• Element μ/ρ from xraydb\n"
            "• Beginner-friendly tooltips + quick start\n\n"
            "Tip: Use measured density for best accuracy."
        )

    def _show_quick_start(self):
        # Just switch to the "Quick Start" tab.
        # Notebook is the first child in left panel.
        try:
            nb = self.nametowidget(self.winfo_children()[0].winfo_children()[0].winfo_children()[0])
            nb.select(6)
        except Exception:
            pass

    # ---------- Tabs ----------
    def _build_beam_tab(self, tab):
        tab.columnconfigure(1, weight=1)

        card = ttk.LabelFrame(tab, text="X-ray energy / wavelength", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        rb_e = ttk.Radiobutton(card, text="Energy (keV)", variable=self.energy_mode, value="keV",
                               command=self._sync_energy_inputs)
        rb_l = ttk.Radiobutton(card, text="Wavelength (Å)", variable=self.energy_mode, value="A",
                               command=self._sync_energy_inputs)
        rb_e.grid(row=0, column=0, sticky="w")
        rb_l.grid(row=0, column=1, sticky="w", padx=(12, 0))

        ToolTip(rb_e, "选择“以能量输入”。通常同步辐射线站给的是能量 (keV)。")
        ToolTip(rb_l, "选择“以波长输入”。若你手头是 λ(Å)，可以直接输入。")

        ttk.Label(card, text="E (keV):").grid(row=1, column=0, sticky="w", pady=(10, 0))
        e_entry = ttk.Entry(card, textvariable=self.energy_keV)
        e_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0))

        ttk.Label(card, text="λ (Å):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        l_entry = ttk.Entry(card, textvariable=self.wavelength_A)
        l_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0))

        ToolTip(e_entry, "输入 X-ray 能量（keV）。例：83 keV（高能 SXRD 常用）。\n程序会自动更新 λ。")
        ToolTip(l_entry, "输入 X-ray 波长（Å）。程序会自动更新 E。")

        ttk.Label(card, text="Incidence tilt (deg, optional):").grid(row=3, column=0, sticky="w", pady=(8, 0))
        tilt_entry = ttk.Entry(card, textvariable=self.incident_angle_deg)
        tilt_entry.grid(row=3, column=1, sticky="ew", pady=(8, 0))
        ToolTip(tilt_entry, "入射相对法向的倾角（度）。若是法向透射填 0。\n倾角会增加有效路径：t_eff = t / cos(tilt)。")

        db = ttk.LabelFrame(tab, text="Attenuation database (μ/ρ)", style="Card.TLabelframe")
        db.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(db, text="Source:").grid(row=0, column=0, sticky="w")
        src = ttk.Combobox(db, textvariable=self.source_db, values=["elam", "chantler"], state="readonly", width=14)
        src.grid(row=0, column=1, sticky="w", padx=(6, 0))
        ToolTip(src, "μ/ρ 数据来源。\n• elam：常用、速度快，可选 kind\n• chantler：另一套常用数据")

        ttk.Label(db, text="Kind (Elam only):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        kind = ttk.Combobox(db, textvariable=self.cross_kind, values=["total", "photo", "coh", "incoh"], state="readonly", width=14)
        kind.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0))
        ToolTip(kind, "Elam 数据的截面类型：\n• total：总衰减（推荐）\n• photo：光电吸收\n• coh/incoh：相干/非相干散射")

    def _build_sample_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        comp = ttk.LabelFrame(tab, text="Composition", style="Card.TLabelframe")
        comp.grid(row=0, column=0, sticky="ew")
        comp.columnconfigure(3, weight=1)

        ttk.Label(comp, text="Fractions are:").grid(row=0, column=0, sticky="w")

        rb_wt = ttk.Radiobutton(comp, text="wt.% (mass)", variable=self.fraction_basis, value="wt",
                                command=self._on_basis_switch)
        rb_at = ttk.Radiobutton(comp, text="at.% (atomic)", variable=self.fraction_basis, value="at",
                                command=self._on_basis_switch)
        rb_wt.grid(row=0, column=1, sticky="w", padx=(8, 0))
        rb_at.grid(row=0, column=2, sticky="w", padx=(8, 0))

        ToolTip(rb_wt, "wt.%：按质量百分比输入（最常见）。")
        ToolTip(rb_at, "at.%：按原子百分比输入。\n注意：切换按钮不会自动换算，需要点 Convert。")

        conv = ttk.Button(comp, text="Convert current values", command=self.convert_values)
        conv.grid(row=0, column=3, sticky="e")
        ToolTip(conv, "把当前表格里的数值在 wt.% ↔ at.% 之间一键换算，并自动切换选择。")

        warn = ttk.Label(comp, textvariable=self.basis_warning, style="Muted.TLabel", foreground="#A00000")
        warn.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # table
        self.comp_table = CompositionTable(tab)
        self.comp_table.grid(row=2, column=0, sticky="nsew", pady=(12, 0))

        # density
        dens = ttk.LabelFrame(tab, text="Density ρ", style="Card.TLabelframe")
        dens.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        dens.columnconfigure(2, weight=1)

        rb_m = ttk.Radiobutton(dens, text="Manual (recommended)", variable=self.density_mode, value="manual")
        rb_m.grid(row=0, column=0, sticky="w")
        rho_entry = ttk.Entry(dens, textvariable=self.density_g_cm3, width=12)
        rho_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(dens, text="g/cm³").grid(row=0, column=2, sticky="w", padx=(6, 0))

        ToolTip(rb_m, "强烈推荐：输入样品实测密度（阿基米德法等）。\n厚度设计对密度敏感。")
        ToolTip(rho_entry, "输入样品密度 ρ（g/cm³）。例如 Ti 合金常见 ~4.5–5.5。\n有氧/氮等间隙元素时更建议用实测值。")

        rb_e = ttk.Radiobutton(dens, text="Estimate (rough)", variable=self.density_mode, value="estimate")
        rb_e.grid(row=1, column=0, sticky="w", pady=(8, 0))

        model = ttk.Combobox(
            dens,
            textvariable=self.density_est_model,
            values=["alloy_interstitial", "volume_additive", "block_if_interstitial"],
            state="readonly",
            width=20
        )
        model.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ToolTip(model, "密度估算模型：\n"
                       "• alloy_interstitial：忽略 O/N/C/H/B 的体积项（合金推荐）\n"
                       "• volume_additive：简单混合定律（适合粉末/混合物）\n"
                       "• block_if_interstitial：检测到间隙元素就拒绝估算，强制 Manual")

        tip = ttk.Label(
            dens,
            text="Tip: If your alloy contains O/N/C/H/B, Manual density is the safest choice.",
            style="Muted.TLabel"
        )
        tip.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_target_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        primary = ttk.LabelFrame(tab, text="Primary design target", style="Card.TLabelframe")
        primary.grid(row=0, column=0, sticky="ew")
        primary.columnconfigure(2, weight=1)

        rb_T = ttk.Radiobutton(primary, text="Target transmission T = I/I0", variable=self.target_mode, value="T")
        rb_T.grid(row=0, column=0, sticky="w")
        t_entry = ttk.Entry(primary, textvariable=self.target_T, width=10)
        t_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))

        ToolTip(rb_T, "选择用“目标透过率 T”设计厚度。\nT=0.5 表示透过 50%。")
        ToolTip(t_entry, "输入目标透过率 T (0~1)。\n经验：T≈0.3–0.7 常用于兼顾强度与吸收校正。")

        rb_mut = ttk.Radiobutton(primary, text="Target μt (dimensionless)", variable=self.target_mode, value="mut")
        rb_mut.grid(row=1, column=0, sticky="w", pady=(10, 0))
        mut_entry = ttk.Entry(primary, textvariable=self.target_mut, width=10)
        mut_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ToolTip(rb_mut, "选择用“目标 μt”设计厚度。\nμt 是无量纲吸收厚度，T=exp(-μt)。")
        ToolTip(mut_entry, "输入目标 μt。\n经验：μt=0.7 对应 T≈0.50。")

        scope = ttk.Checkbutton(primary, text="Apply target to total stack (Layers)", variable=self.target_scope_total)
        scope.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ToolTip(scope, "勾选后：目标 T 或 μt 指的是“整套路径”的总透过率（包含 ⑤ Layers 里的窗片/空气/毛细管等）。\n"
                       "程序会先计算其它层的吸收 Σ(μt)_other，然后反推出样品厚度。\n"
                       "注意：若其它层已导致 T 很低，则可能无法达到目标。")

        window = ttk.LabelFrame(tab, text="Suggested μt window (optional)", style="Card.TLabelframe")
        window.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(window, text="Common window: μt ~ 0.5–1.2  (T ≈ 0.61–0.30)").grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Label(window, text="μt min:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        min_entry = ttk.Entry(window, textvariable=self.reco_mut_min, width=10)
        min_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(window, text="μt max:").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(10, 0))
        max_entry = ttk.Entry(window, textvariable=self.reco_mut_max, width=10)
        max_entry.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        ToolTip(min_entry, "建议窗口的下限 μt。\n用于给出一个厚度范围（不是强制）。")
        ToolTip(max_entry, "建议窗口的上限 μt。\n窗口越大，T 越低，吸收校正更难但信号更强。")



    def _build_detector_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(tab, text="Detector geometry (orthogonal model)", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        # Enable checkbox
        en = ttk.Checkbutton(card, text="Enable Q/d coverage calculation", variable=self.det_enable)
        en.grid(row=0, column=0, columnspan=2, sticky="w")
        ToolTip(
            en,
            """勾选后，程序会根据“探测器几何 + 波长”计算可覆盖的 Q 与 d 范围。

这是“正交简化版”（探测器平面 ⟂ 入射束），90% 场景够用。"""
        )

        # Distance L
        ttk.Label(card, text="Sample–detector distance L (mm):").grid(row=1, column=0, sticky="w", pady=(10, 0))
        L_entry = ttk.Entry(card, textvariable=self.det_L_mm)
        L_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        ToolTip(
            L_entry,
            """样品到探测器距离 L（mm）。

• L 越大：Qmin 更低（更小角），但同一探测器尺寸下 Qmax 通常降低。
• L 越小：Qmax 更高，但小角区更容易被 beamstop / 直通光影响。"""
        )

        # Pixel size
        ttk.Label(card, text="Pixel size p (mm/pixel):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        p_entry = ttk.Entry(card, textvariable=self.det_pixel_mm)
        p_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ToolTip(
            p_entry,
            """像素尺寸 p（mm/px）。

例如 150 µm 像素 -> p=0.15 mm。若未知，请查探测器规格或线站参数表。"""
        )

        # Detector size
        size_frm = ttk.Frame(card)
        size_frm.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        size_frm.columnconfigure(5, weight=1)

        ttk.Label(size_frm, text="Detector size (pixels):").grid(row=0, column=0, sticky="w")
        ttk.Label(size_frm, text="Nx:").grid(row=0, column=1, sticky="w", padx=(10, 0))
        nx_entry = ttk.Entry(size_frm, textvariable=self.det_nx, width=10)
        nx_entry.grid(row=0, column=2, sticky="w", padx=(6, 0))
        ttk.Label(size_frm, text="Ny:").grid(row=0, column=3, sticky="w", padx=(12, 0))
        ny_entry = ttk.Entry(size_frm, textvariable=self.det_ny, width=10)
        ny_entry.grid(row=0, column=4, sticky="w", padx=(6, 0))

        ToolTip(nx_entry, "探测器水平方向像素数 Nx（例如 2880）。")
        ToolTip(ny_entry, "探测器垂直方向像素数 Ny（例如 2880）。")

        # Beam center & masks
        bc = ttk.LabelFrame(tab, text="Beam center & masks", style="Card.TLabelframe")
        bc.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        bc.columnconfigure(3, weight=1)

        ttk.Label(bc, text="Beam center x0 (px):").grid(row=0, column=0, sticky="w")
        x0_entry = ttk.Entry(bc, textvariable=self.det_x0, width=12)
        x0_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(bc, text="y0 (px):").grid(row=0, column=2, sticky="w", padx=(12, 0))
        y0_entry = ttk.Entry(bc, textvariable=self.det_y0, width=12)
        y0_entry.grid(row=0, column=3, sticky="w", padx=(8, 0))

        ToolTip(
            x0_entry,
            """束心 x0（像素坐标，0-index）。

通常由标样/几何标定得到；若未知，可先用 Nx/2 作为近似。"""
        )
        ToolTip(y0_entry, "束心 y0（像素坐标，0-index）。若未知，可先用 Ny/2 作为近似。")

        ttk.Label(bc, text="Inner mask radius r_min (mm):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        rmin_entry = ttk.Entry(bc, textvariable=self.det_rmin_mm, width=12)
        rmin_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ToolTip(
            rmin_entry,
            """内圈不可用半径 r_min（mm）。

通常由 beamstop、直通光饱和、或 mask 决定；它决定 Qmin（最小可测 Q）。"""
        )

        ttk.Label(bc, text="Optional: analysis outer radius r_max (mm):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        rmax_entry = ttk.Entry(bc, textvariable=self.det_rmax_mm, width=12)
        rmax_entry.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ToolTip(
            rmax_entry,
            """可选：分析外圈可用半径 r_max（mm）。

• 用于表示你实际分析/积分时保留的最大半径（例如边缘裁剪、mask）。
• r_max 会同时作用于两种 Qmax 定义：
  - full-ring（edge-limited）：用于需要“完整德拜环”的保守范围
  - corner limit（diagonal）：对角线几何极限，可能只有部分覆盖

留空时，程序会同时输出：
  - full-ring 的 Qmax（建议默认采用）
  - corner limit 的 Qmax（仅作几何极限参考）"""
        )

        note = ttk.Label(
            tab,
            text=("Model assumption (simplified): detector plane ⟂ incident beam, no tilt/rotation. "
                  "If your detector is tilted/off-normal, use a full geometry model (pyFAI-like)."),
            style="Muted.TLabel"
        )
        note.grid(row=2, column=0, sticky="w", pady=(12, 0))
        ToolTip(note, "简化模型说明：未考虑探测器倾角/旋转/非正交。需要更高精度时可升级。")


    # ------------------------- Layers (stack) tab -------------------------
    def _build_layers_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(tab, text="Multi-layer stack (windows / air / capillary / sample)", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        intro = ttk.Label(
            card,
            text=(
                "Use this to budget TOTAL transmission through the full beam path.\n"
                "T_total = Π exp(-μ_i t_i). This prevents the classic failure mode: sample is fine, but windows/air kill the signal."
            ),
            justify="left",
        )
        intro.grid(row=0, column=0, sticky="w", pady=(0, 8))
        ToolTip(intro, "强烈建议：把你真实的窗片、空气路径、毛细管壁都加进去。\n"
                       "否则你可能只按样品算到了 T≈0.5，但最后总透过率只有 0.1，导致散射信号崩掉。")

        self.layers_table = LayerTable(card)
        self.layers_table.grid(row=1, column=0, sticky="ew")

        # buttons + output
        bot = ttk.Frame(card)
        bot.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bot, text="Compute stack transmission", command=self._compute_stack_only).pack(side="left")

        ToolTip(bot, "只计算层叠透过率，不改变主计算结果。\n"
                     "如果你想把结果一起写入主 Results，请点击左侧的 Compute thickness。")

        out = ttk.LabelFrame(tab, text="Stack results", style="Card.TLabelframe")
        out.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        out.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        self.stack_text = tk.Text(out, height=10, wrap="word")
        self.stack_text.grid(row=0, column=0, sticky="nsew")
        self.stack_text.insert("1.0", "Click 'Compute stack transmission' or run the main Compute to see results here.\n")
        self.stack_text.configure(state="disabled")

    def _compute_stack_only(self):
        try:
            if xraydb is None:
                raise RuntimeError("xraydb is required. Install with: pip install xraydb")

            e_keV = self._get_energy_keV()
            lam_A = wavelength_A_from_energy_keV(e_keV)
            tilt_factor = self._tilt_factor()

            w_mass = self._get_mass_fractions()
            rho, _ = self._get_density(w_mass)

            source = self.source_db.get()
            kind = self.cross_kind.get()

            mu_rho = mu_over_rho_mix_cm2_g(w_mass, e_keV, kind=kind, source=source)
            mu_mm = linear_mu_per_mm(mu_rho, rho)
            mu_eff = mu_mm * tilt_factor

            # Prefer computed thickness if available
            t_sample = self.last_sample_thickness_mm
            res = self._evaluate_layer_stack(e_keV, kind, source, w_mass, rho, mu_eff, t_sample)

            text = self._format_stack_report(e_keV, lam_A, res, mu_eff, t_sample)
            self._set_text(self.stack_text, text)
            self._set_status("Stack transmission computed.", ok=True)
        except Exception as exc:
            self._set_status(f"Stack compute failed: {exc}", ok=False)
            messagebox.showerror("Stack compute error", str(exc))

    # ------------------------- Exposure estimator tab -------------------------
    def _build_exposure_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(tab, text="Exposure time estimator (ratio / scaling)", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        # Reference
        ttk.Label(card, text="Reference exposure (your previous good dataset):").grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(card, text="t_ref (s)").grid(row=1, column=0, sticky="w", pady=(6, 0))
        e_tr = ttk.Entry(card, textvariable=self.exp_ref_time_s, width=12)
        e_tr.grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(card, text="sample thickness_ref (mm)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        e_ts = ttk.Entry(card, textvariable=self.exp_ref_t_sample_mm, width=12)
        e_ts.grid(row=2, column=1, sticky="w", pady=(6, 0))

        ttk.Label(card, text="flux_ref (ph/s, optional)").grid(row=3, column=0, sticky="w", pady=(6, 0))
        e_fr = ttk.Entry(card, textvariable=self.exp_ref_flux, width=18)
        e_fr.grid(row=3, column=1, sticky="w", pady=(6, 0))

        ttk.Label(card, text="T_total_ref (optional)").grid(row=4, column=0, sticky="w", pady=(6, 0))
        e_Tr = ttk.Entry(card, textvariable=self.exp_ref_Ttotal, width=12)
        e_Tr.grid(row=4, column=1, sticky="w", pady=(6, 0))

        ToolTip(e_tr, "参考曝光时间（秒）。例如你上次在某线站：1 mm 样品，曝光 1 s。")
        ToolTip(e_ts, "参考样品几何厚度（mm）。")
        ToolTip(e_fr, "参考通量（可选）。若留空，默认与当前相同（只做相对缩放）。")
        ToolTip(e_Tr, "参考条件下的总透过率（可选）。\n"
                      "如果你的参考实验也有窗片/空气吸收，请填入 T_total_ref；否则默认为 1。")

        sep = ttk.Separator(card)
        sep.grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

        # Current
        ttk.Label(card, text="Current setup:").grid(row=6, column=0, columnspan=2, sticky="w")

        cb = ttk.Checkbutton(card, text="Use computed sample thickness from main Compute", variable=self.exp_use_computed_t)
        cb.grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ToolTip(cb, "勾选后会使用主计算得到的样品厚度（last computed t）。\n"
                    "若你还没运行主 Compute，或想手动指定厚度，请取消勾选并在下方输入。")

        ttk.Label(card, text="sample thickness_new (mm)").grid(row=8, column=0, sticky="w", pady=(6, 0))
        e_tn = ttk.Entry(card, textvariable=self.exp_new_t_sample_mm, width=12)
        e_tn.grid(row=8, column=1, sticky="w", pady=(6, 0))
        ToolTip(e_tn, "当前样品几何厚度（mm）。仅在不使用 computed thickness 时生效。")

        ttk.Label(card, text="flux_new (ph/s, optional)").grid(row=9, column=0, sticky="w", pady=(6, 0))
        e_fn = ttk.Entry(card, textvariable=self.exp_new_flux, width=18)
        e_fn.grid(row=9, column=1, sticky="w", pady=(6, 0))
        ToolTip(e_fn, "当前通量（可选）。\n若留空，默认与参考相同。")

        ttk.Label(card, text="detector efficiency ratio (η_new/η_ref)").grid(row=10, column=0, sticky="w", pady=(6, 0))
        e_er = ttk.Entry(card, textvariable=self.exp_eff_ratio, width=12)
        e_er.grid(row=10, column=1, sticky="w", pady=(6, 0))
        ToolTip(e_er, "探测器效率/设置导致的有效计数比例（新/参考）。\n"
                      "例如换了探测器或换了阈值，导致效率变为 0.8，则填 0.8。")

        ttk.Label(card, text="SNR ratio (SNR_new/SNR_ref)").grid(row=11, column=0, sticky="w", pady=(6, 0))
        e_sr = ttk.Entry(card, textvariable=self.exp_snr_ratio, width=12)
        e_sr.grid(row=11, column=1, sticky="w", pady=(6, 0))
        ToolTip(e_sr, "目标信噪比倍率。SNR ∝ sqrt(counts) ⇒ time ∝ SNR^2。\n"
                      "例如想要 2× 更高 SNR，则填 2，时间会变为 4×。")

        ttk.Label(card, text="Intensity model").grid(row=12, column=0, sticky="w", pady=(6, 0))
        model = ttk.Combobox(card, textvariable=self.exp_model, values=["linear", "absorption"], width=14, state="readonly")
        model.grid(row=12, column=1, sticky="w", pady=(6, 0))
        ToolTip(model, "linear：计数 ~ 厚度（薄样品近似）\n"
                       "absorption：计数 ~ (1-exp(-μt))/μ（更稳健，但仍是粗略模型）。")

        btn = ttk.Button(card, text="Estimate exposure time", command=self._estimate_exposure)
        btn.grid(row=13, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # output box
        out = ttk.LabelFrame(tab, text="Exposure estimate", style="Card.TLabelframe")
        out.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        out.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        self.exp_text = tk.Text(out, height=10, wrap="word")
        self.exp_text.grid(row=0, column=0, sticky="nsew")
        self.exp_text.insert("1.0", "This estimator is intentionally conservative and should be used as a scaling guide.\n")
        self.exp_text.configure(state="disabled")

    def _estimate_exposure(self):
        try:
            if xraydb is None:
                raise RuntimeError("xraydb is required. Install with: pip install xraydb")

            # Current beam/sample state
            e_keV = self._get_energy_keV()
            lam_A = wavelength_A_from_energy_keV(e_keV)
            tilt_factor = self._tilt_factor()

            w_mass = self._get_mass_fractions()
            rho, _ = self._get_density(w_mass)

            source = self.source_db.get()
            kind = self.cross_kind.get()

            mu_rho = mu_over_rho_mix_cm2_g(w_mass, e_keV, kind=kind, source=source)
            mu_mm = linear_mu_per_mm(mu_rho, rho)
            mu_eff = mu_mm * tilt_factor

            # Thickness (new)
            if self.exp_use_computed_t.get():
                if self.last_sample_thickness_mm is None:
                    raise ValueError("No computed thickness available. Run main Compute once, or uncheck 'Use computed thickness' and enter t_new.")
                t_new = float(self.last_sample_thickness_mm)
            else:
                t_new = safe_float(self.exp_new_t_sample_mm.get(), None)
                if t_new is None or t_new <= 0:
                    raise ValueError("sample thickness_new must be > 0 mm.")

            # Stack transmission for NEW (if Layers exist), otherwise sample-only
            res_new = self._evaluate_layer_stack(e_keV, kind, source, w_mass, rho, mu_eff, t_new)
            T_new = res_new["T_total"] if res_new["has_any_layer"] else math.exp(-mu_eff * t_new)

            # Reference inputs
            t_ref_exp = safe_float(self.exp_ref_time_s.get(), None)
            if t_ref_exp is None or t_ref_exp <= 0:
                raise ValueError("t_ref must be > 0 s.")
            t_ref = safe_float(self.exp_ref_t_sample_mm.get(), None)
            if t_ref is None or t_ref <= 0:
                raise ValueError("sample thickness_ref must be > 0 mm.")

            # Reference transmission
            T_ref = safe_float(self.exp_ref_Ttotal.get(), None)
            if T_ref is None:
                # If user does not provide, assume 1 and state clearly.
                T_ref = 1.0
                T_ref_note = " (assumed 1.0; please set if windows/air differed)"
            else:
                if not (0 < T_ref <= 1):
                    raise ValueError("T_total_ref must be in (0, 1].")
                T_ref_note = ""

            # Flux (optional)
            F_ref = safe_float(self.exp_ref_flux.get(), None)
            F_new = safe_float(self.exp_new_flux.get(), None)
            if F_ref is None or F_new is None:
                flux_factor = 1.0
                flux_note = " (flux ignored; fill both to scale by flux)"
            else:
                if F_ref <= 0 or F_new <= 0:
                    raise ValueError("Flux must be > 0.")
                flux_factor = F_ref / F_new
                flux_note = ""

            # Detector efficiency ratio (eta_new/eta_ref)
            eff_ratio = safe_float(self.exp_eff_ratio.get(), None)
            if eff_ratio is None or eff_ratio <= 0:
                raise ValueError("Efficiency ratio must be > 0.")
            eff_factor = 1.0 / eff_ratio

            # SNR ratio
            snr_ratio = safe_float(self.exp_snr_ratio.get(), None)
            if snr_ratio is None or snr_ratio <= 0:
                raise ValueError("SNR ratio must be > 0.")
            snr_factor = snr_ratio ** 2

            # Intensity model: how scattering scales with thickness (very rough)
            def intensity_model(t_mm: float) -> float:
                if self.exp_model.get() == "absorption":
                    # I ~ ∫_0^t exp(-μx) dx = (1-exp(-μt))/μ
                    if mu_eff <= 0:
                        return t_mm
                    return (1.0 - math.exp(-mu_eff * t_mm)) / mu_eff
                # thin-sample approx: I ~ t
                return t_mm

            I_ref = intensity_model(t_ref)
            I_new = intensity_model(t_new)
            if I_new <= 0:
                raise ValueError("Invalid model intensity for current thickness.")

            intensity_factor = (I_ref * T_ref) / (I_new * T_new)

            t_new_exp = t_ref_exp * flux_factor * eff_factor * snr_factor * intensity_factor
            if not (t_new_exp > 0 and math.isfinite(t_new_exp)):
                raise ValueError("Exposure estimate is not finite. Check inputs.")

            lines = []
            lines.append(f"Energy: {e_keV:.6g} keV (λ={lam_A:.6g} Å)")
            lines.append(f"μ_eff(sample) = {mu_eff:.6g} 1/mm, model = {self.exp_model.get()}")
            lines.append("")
            lines.append("Reference:")
            lines.append(f"  t_ref_exp = {t_ref_exp:.6g} s")
            lines.append(f"  t_sample_ref = {t_ref:.6g} mm")
            lines.append(f"  T_total_ref = {T_ref:.6g}{T_ref_note}")
            lines.append("")
            lines.append("Current:")
            lines.append(f"  t_sample_new = {t_new:.6g} mm")
            lines.append(f"  T_total_new = {T_new:.6g} (from Layers)" if res_new["has_any_layer"] else f"  T_sample_only = {T_new:.6g}")
            lines.append("")
            lines.append("Scaling factors:")
            lines.append(f"  flux factor (F_ref/F_new) = {flux_factor:.6g}{flux_note}")
            lines.append(f"  efficiency factor (η_ref/η_new) = {eff_factor:.6g}  (η_new/η_ref={eff_ratio:.6g})")
            lines.append(f"  SNR factor (SNR_new/SNR_ref)^2 = {snr_factor:.6g}")
            lines.append(f"  intensity factor (I_ref*T_ref)/(I_new*T_new) = {intensity_factor:.6g}")
            lines.append("")
            lines.append(f"Estimated exposure time: {t_new_exp:.6g} s")
            lines.append("")
            lines.append("Note: this is a scaling guide; absolute accuracy depends on sample scattering power, background, and detector settings.")

            self._set_text(self.exp_text, "\n".join(lines))
            self._set_status("Exposure estimated.", ok=True)
        except Exception as exc:
            self._set_status(f"Exposure estimate failed: {exc}", ok=False)
            messagebox.showerror("Exposure estimate error", str(exc))

    # ------------------------- Stack evaluation helpers -------------------------
    def _evaluate_layer_stack(self, e_keV, kind, source, w_mass_sample, rho_sample, mu_eff_sample, sample_t_mm):
        """
        Evaluate enabled layers.
        Returns a dict with:
          - rows: list of per-layer metrics
          - mut_other: sum μt excluding sample
          - mut_total: sum μt including sample (if sample thickness available)
          - T_other, T_total
          - has_any_layer: whether any enabled non-sample layer exists
        """
        layers = []
        has_any = False
        mut_other = 0.0

        # Parse table (if present)
        raw = []
        if hasattr(self, "layers_table") and self.layers_table is not None:
            raw = self.layers_table.get_layers()

        # pick first sample layer thickness if present
        sample_t_for_stack = sample_t_mm
        for L in raw:
            if L["material"] == "Sample (current)":
                # resolve thickness
                if L.get("auto", False):
                    if sample_t_mm is None:
                        # cannot resolve now
                        continue
                    sample_t_for_stack = sample_t_mm
                else:
                    tman = safe_float(L.get("t_mm", ""), None)
                    if tman is not None and tman > 0:
                        sample_t_for_stack = tman
                break

        for L in raw:
            mat = L["material"]
            # resolve thickness
            if mat == "Sample (current)":
                # will be handled later as a single sample layer
                continue

            t = safe_float(L.get("t_mm", ""), None)
            if t is None or t <= 0:
                continue

            # resolve rho
            rho = safe_float(L.get("rho", ""), None)
            if rho is None:
                # try defaults
                rho = LayerTable.DEFAULTS.get(mat, {}).get("rho", None)
            if rho is None:
                # cannot compute absorption without density
                continue
            if rho <= 0:
                raise ValueError(f"Layer '{mat}' density must be > 0 g/cm^3.")

            # resolve w_mass for this layer
            if mat == "Vacuum":
                mu_mm = 0.0
                mu_t = 0.0
                T = 1.0
                layers.append({"material": mat, "t_mm": t, "rho": rho, "mu_mm": mu_mm, "mu_t": mu_t, "T": T})
                continue

            if mat == "Air (dry)":
                w = mass_fractions_dry_air()
            elif mat in ("Kapton (C22H10N2O5)", "Quartz (SiO2)", "Graphite (C)"):
                formula = LayerTable.DEFAULTS.get(mat, {}).get("formula", "")
                w = mass_fractions_from_formula(formula)
            elif mat == "Beryllium (Be)":
                w = {"Be": 1.0}
            elif mat == "Custom formula":
                formula = (L.get("formula", "") or "").strip()
                if not formula:
                    continue
                w = mass_fractions_from_formula(formula)
            else:
                # unknown layer type
                continue

            mu_rho = mu_over_rho_mix_cm2_g(w, e_keV, kind=kind, source=source)
            mu_mm = linear_mu_per_mm(mu_rho, rho)
            mu_t = mu_mm * t
            T = math.exp(-mu_t)

            layers.append({
                "material": mat,
                "t_mm": t,
                "rho": rho,
                "mu_mm": mu_mm,
                "mu_t": mu_t,
                "T": T,
            })
            mut_other += mu_t
            has_any = True

        # sample contribution
        mut_sample = None
        T_sample = None
        if sample_t_for_stack is not None and sample_t_for_stack > 0 and mu_eff_sample > 0:
            mut_sample = mu_eff_sample * float(sample_t_for_stack)
            T_sample = math.exp(-mut_sample)
            layers.append({
                "material": "Sample (current)",
                "t_mm": float(sample_t_for_stack),
                "rho": rho_sample,
                "mu_mm": float(mu_eff_sample),  # report μ_eff here
                "mu_t": mut_sample,
                "T": T_sample,
                "note": "μ_eff (includes tilt) used",
            })

        mut_total = mut_other + (mut_sample or 0.0)
        T_other = math.exp(-mut_other)
        T_total = math.exp(-mut_total)

        return {
            "rows": layers,
            "mut_other": mut_other,
            "mut_total": mut_total,
            "T_other": T_other,
            "T_total": T_total,
            "has_any_layer": has_any,
            "sample_t_for_stack": sample_t_for_stack,
        }

    def _format_stack_report(self, e_keV, lam_A, res, mu_eff_sample, sample_t_mm):
        lines = []
        lines.append(f"Energy: {e_keV:.6g} keV (λ={lam_A:.6g} Å)")
        lines.append("")
        if not res["rows"]:
            lines.append("No enabled layers with valid thickness/density were found.")
            return "\n".join(lines)

        lines.append("Per-layer transmission:")
        lines.append("  (μ in 1/mm, μt dimensionless, T=exp(-μt))")
        for row in res["rows"]:
            mat = row["material"]
            t = row["t_mm"]
            mu = row["mu_mm"]
            mut = row["mu_t"]
            T = row["T"]
            note = row.get("note", "")
            if note:
                note = f"  [{note}]"
            lines.append(f"  - {mat:20s}  t={t:.6g} mm, μ={mu:.6g}, μt={mut:.6g}, T={T:.6g}{note}")

        lines.append("")
        lines.append(f"Other layers:  Σ(μt)_other = {res['mut_other']:.6g}  ⇒  T_other = {res['T_other']:.6g}")
        if res["sample_t_for_stack"] is not None:
            lines.append(f"Total stack:  Σ(μt)_total = {res['mut_total']:.6g}  ⇒  T_total = {res['T_total']:.6g}")
        else:
            lines.append("Total stack:  (sample thickness not resolved; run main Compute or set sample thickness in Layers)")
        return "\n".join(lines)

    def _set_text(self, widget: tk.Text, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _build_help_tab(self, tab):
        tab.columnconfigure(0, weight=1)

        card = ttk.LabelFrame(tab, text="Quick Start (for beginners)", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        steps = (
            "① Beam: 输入线站能量 E(keV)。如果你只知道波长 λ(Å) 也可以输入。\\n"
            "② Sample: 输入合金成分（默认 Ti2448 示例）。选择 wt.% 或 at.%。\\n"
            "   • 如果你切换了 wt/at，想把数值也换算，请点 “Convert current values”。\\n"
            "③ Density: 强烈建议填实测密度 ρ（g/cm³）。\\n"
            "   • 含 O/N/C/H/B 的合金不要迷信估算值。\\n"
            "④ Target: 选 T 或 μt。\\n"
            "   • 新手推荐：先看 μt=0.5–1.2 给出的厚度窗口。\\n"
            "   • 如果你有窗片/空气路径：勾选 “Apply target to total stack (Layers)”。\\n"
            "⑤ Layers: 把 Kapton/石英窗片、空气路径、毛细管壁等加入层叠预算。\\n"
            "⑥ 点击 Compute thickness：得到样品厚度，并同步输出总透过率 T_total。\\n"
            "⑦ Exposure (可选): 用比例法估算曝光时间（可包含 T_total 的影响）。\\n\\n"
            "常用经验：\\n"
            "• T≈0.3–0.7：常见折中区间\\n"
            "• μt≈0.5–1.2：常用吸收厚度窗口\\n"
        )

        lbl = ttk.Label(card, text=steps, justify="left", wraplength=720)
        lbl.grid(row=0, column=0, sticky="w")
        ToolTip(lbl, "这是给新手的最短操作路径。\n\n你也可以把这段复制到实验记录作为 SOP。")

    # ---------- Small behaviors ----------
    def _on_basis_switch(self):
        self.basis_warning.set("提示：切换 wt.%/at.% 只改变“解释方式”，不会自动换算数值。需要换算请点右侧 Convert。")

    
    def _on_detector_size_change(self):
        """
        Keep the default beam center consistent when detector Nx/Ny changes.

        Common workflow:
            - User changes Nx/Ny to match a different detector/crop
            - Forgets to update x0/y0 (still old center), leading to out-of-bounds geometry and absurd Q ranges.

        Heuristic (safe):
            - If x0 equals the *previous* center (old_Nx/2), update it to new_Nx/2 (only when Nx changed).
            - If y0 equals the *previous* center (old_Ny/2), update it to new_Ny/2 (only when Ny changed).
            - Otherwise do nothing (assume user intentionally set an off-center beam).
        """
        try:
            new_nx = int(float(self.det_nx.get()))
            new_ny = int(float(self.det_ny.get()))
            x0 = safe_float(self.det_x0.get(), None)
            y0 = safe_float(self.det_y0.get(), None)
            if new_nx <= 1 or new_ny <= 1 or x0 is None or y0 is None:
                return
        except Exception:
            return

        old_nx = getattr(self, "_det_last_nx", new_nx)
        old_ny = getattr(self, "_det_last_ny", new_ny)

        tol = 1e-6

        if new_nx != old_nx:
            old_cx = old_nx / 2.0
            if abs(x0 - old_cx) < tol:
                self.det_x0.set(f"{new_nx/2.0:.6g}")

        if new_ny != old_ny:
            old_cy = old_ny / 2.0
            if abs(y0 - old_cy) < tol:
                self.det_y0.set(f"{new_ny/2.0:.6g}")

        self._det_last_nx = new_nx
        self._det_last_ny = new_ny

    def convert_values(self):
        """Convert current values in-place between wt.% and at.% and switch basis accordingly."""
        try:
            if xraydb is None:
                raise RuntimeError("Conversion requires xraydb (pip install xraydb).")

            pairs = self.comp_table.get_pairs(allow_empty=False, normalize_symbols=True)
            current = self.fraction_basis.get()

            if current == "wt":
                at_frac = at_from_wt_percent(pairs)
                d_percent = {sym: 100.0 * xi for sym, xi in at_frac.items()}
                self.comp_table.set_values_from_dict_percent(d_percent)
                self.fraction_basis.set("at")
            else:
                w_mass = wt_from_at_percent(pairs)
                d_percent = {sym: 100.0 * wi for sym, wi in w_mass.items()}
                self.comp_table.set_values_from_dict_percent(d_percent)
                self.fraction_basis.set("wt")

            self._on_basis_switch()
            self.status.set("Converted composition basis.")
        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror(APP_TITLE, str(e))

    def _sync_energy_inputs(self):
        try:
            if self.energy_mode.get() == "keV":
                e = safe_float(self.energy_keV.get(), None)
                if e is None or e <= 0:
                    return
                self.wavelength_A.set(f"{wavelength_A_from_energy_keV(e):.6g}")
            else:
                lam = safe_float(self.wavelength_A.get(), None)
                if lam is None or lam <= 0:
                    return
                self.energy_keV.set(f"{energy_keV_from_wavelength_A(lam):.6g}")
        except Exception:
            pass

    def _get_energy_keV(self) -> float:
        self._sync_energy_inputs()
        e = safe_float(self.energy_keV.get(), None)
        if e is None or e <= 0:
            raise ValueError("Please enter a valid energy (keV) or wavelength (Å).")
        return e

    def _tilt_factor(self) -> float:
        tilt = safe_float(self.incident_angle_deg.get(), 0.0) or 0.0
        c = math.cos(math.radians(tilt))
        if c <= 0:
            raise ValueError("Incidence tilt too large (cos <= 0).")
        return 1.0 / c

    def _get_mass_fractions(self):
        pairs = self.comp_table.get_pairs(allow_empty=True, normalize_symbols=True)
        if self.fraction_basis.get() == "wt":
            return norm_mass_fractions_from_percent(pairs)
        return wt_from_at_percent(pairs)

    def _get_density(self, w_mass):
        if self.density_mode.get() == "manual":
            rho = safe_float(self.density_g_cm3.get(), None)
            if rho is None or rho <= 0:
                raise ValueError("Please enter a valid density (g/cm³), or choose Estimate.")
            return rho, None
        return estimate_density_rule_of_mixtures(w_mass, model=self.density_est_model.get())

    # ---------- Output ----------
    def _set_results(self, s: str):
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, s)
        self.result_text.configure(state="disabled")

    def _plot(self, mu_eff: float):
        if np is None or Figure is None or FigureCanvasTkAgg is None:
            return
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None

        tmax = max(0.1, 5.0 / max(mu_eff, 1e-9))
        tmax = min(tmax, 20.0)
        t = np.linspace(0, tmax, 250)
        T = np.exp(-mu_eff * t)

        fig = Figure(figsize=(6.2, 3.4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(t, T)
        ax.set_xlabel("Thickness (mm)")
        ax.set_ylabel("Transmission T = I/I0")
        ax.set_ylim(0, 1.02)
        ax.grid(True, alpha=0.25)

        self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def compute(self):
        # Progress indicator
        progress = ttk.Progressbar(self, mode="determinate", length=300)
        progress.grid(row=1, column=0, columnspan=2, pady=(5, 15), sticky="ew")
        progress["value"] = 0

        try:
            if xraydb is None:
                raise RuntimeError("xraydb is required. Install with: pip install xraydb")

            progress["value"] = 10
            e_keV = self._get_energy_keV()
            lam_A = wavelength_A_from_energy_keV(e_keV)
            tilt_factor = self._tilt_factor()

            progress["value"] = 30
            w_mass = self._get_mass_fractions()
            rho, rho_meta = self._get_density(w_mass)

            source = self.source_db.get()
            kind = self.cross_kind.get()

            mu_rho = mu_over_rho_mix_cm2_g(w_mass, e_keV, kind=kind, source=source)
            mu_mm = linear_mu_per_mm(mu_rho, rho)
            mu_eff = mu_mm * tilt_factor

            progress["value"] = 50

            lines = []
            lines.append(f"Energy: {e_keV:.6g} keV   (λ = {lam_A:.6g} Å)")
            if abs(tilt_factor - 1.0) > 1e-6:
                lines.append(f"Tilt correction: path × {tilt_factor:.4g}  (μ_eff = μ × {tilt_factor:.4g})")
            lines.append("")
            lines.append("Composition (mass fractions):")
            for sym in sorted(w_mass.keys()):
                lines.append(f"  {sym:>2s}: {w_mass[sym]:.6f}")
            lines.append("")

            if rho_meta is None:
                lines.append(f"Density ρ: {rho:.6g} g/cm³  (manual)")
            else:
                lines.append(f"Density ρ: {rho:.6g} g/cm³  (estimated; model={rho_meta['model']})")
                if rho_meta.get("interstitial_detected", False):
                    ig = rho_meta.get("ignored", [])
                    if ig:
                        lines.append(f"  Interstitial-like ignored in volume sum: {', '.join(sorted(set(ig)))}")

            lines.append(f"(μ/ρ)_mix: {mu_rho:.6g} cm²/g   [source={source}, kind={kind}]")
            lines.append(f"μ: {mu_mm:.6g} 1/mm   (1/μ = {1.0/mu_mm:.6g} mm)")
            if abs(tilt_factor - 1.0) > 1e-6:
                lines.append(f"μ_eff: {mu_eff:.6g} 1/mm")
            lines.append("")

            
            # ---- Layer stack transmission (optional) ----
            # Note: Layer stack evaluated after thickness is computed
            pass

# ---- Detector Q/d coverage (optional, orthogonal geometry) ----
            if self.det_enable.get():
                try:
                    L_mm = safe_float(self.det_L_mm.get(), None)
                    p_mm = safe_float(self.det_pixel_mm.get(), None)
                    nx = int(float(self.det_nx.get()))
                    ny = int(float(self.det_ny.get()))
                    x0 = safe_float(self.det_x0.get(), None)
                    y0 = safe_float(self.det_y0.get(), None)
                    rmin_mm = safe_float(self.det_rmin_mm.get(), 0.0) or 0.0

                    if L_mm is None or L_mm <= 0:
                        raise ValueError("Detector L must be > 0.")
                    if p_mm is None or p_mm <= 0:
                        raise ValueError("Pixel size must be > 0.")
                    if x0 is None or y0 is None:
                        raise ValueError("Beam center x0/y0 must be numbers (px).")
                    if nx <= 1 or ny <= 1:
                        raise ValueError("Detector Nx/Ny must be > 1.")
                    if rmin_mm < 0:
                        raise ValueError("r_min must be >= 0.")                    # Beam center sanity check: must be within detector bounds.
                    # Pixel-center convention: valid region is [-0.5, Nx-0.5] × [-0.5, Ny-0.5]
                    if not (-0.5 <= x0 <= (nx - 0.5) and -0.5 <= y0 <= (ny - 0.5)):
                        raise ValueError(
                            f"Beam center (x0,y0)=({x0:.6g},{y0:.6g}) px is outside detector bounds "
                            f"[0..{nx-1}]×[0..{ny-1}]. If you changed Nx/Ny, update x0/y0 accordingly."
                        )

                    # Two outer-radius definitions:
                    #   (1) edge-limited full-ring radius (conservative, for azimuthal integration)
                    #   (2) corner (diagonal) geometric limit (may be partial coverage)
                    r_edge_mm = detector_rmax_edge_mm(nx, ny, p_mm, x0, y0)
                    r_corner_mm = detector_rmax_corner_mm(nx, ny, p_mm, x0, y0)

                    # User outer-radius mask (optional): applied to BOTH definitions.
                    rmax_user = safe_float(self.det_rmax_mm.get(), None)
                    rmax_user_note = None
                    if rmax_user is not None and rmax_user > 0:
                        if rmax_user > r_corner_mm:
                            rmax_user_note = "user r_max > corner limit; clamped"
                            rmax_user = r_corner_mm
                        else:
                            rmax_user_note = "user"
                        r_full_mm = min(r_edge_mm, rmax_user)
                        r_diag_mm = min(r_corner_mm, rmax_user)
                    else:
                        r_full_mm = r_edge_mm
                        r_diag_mm = r_corner_mm

                    if rmin_mm >= r_diag_mm:
                        raise ValueError("r_min must be < r_max (corner limit). Reduce r_min or check geometry.")

                    # Q from radii
                    Qmin, two_theta_min = q_from_r_mm(rmin_mm, L_mm, lam_A) if rmin_mm > 0 else (0.0, 0.0)
                    Qmax_full, two_theta_full = q_from_r_mm(r_full_mm, L_mm, lam_A)
                    Qmax_diag, two_theta_diag = q_from_r_mm(r_diag_mm, L_mm, lam_A)

                    # d from Q (Å)
                    dmax = (2.0 * math.pi / Qmin) if Qmin > 0 else float("inf")
                    dmin_full = (2.0 * math.pi / Qmax_full) if Qmax_full > 0 else float("inf")
                    dmin_diag = (2.0 * math.pi / Qmax_diag) if Qmax_diag > 0 else float("inf")

                    lines.append("Detector coverage (orthogonal model):")
                    lines.append(f"  L = {L_mm:.6g} mm, pixel = {p_mm:.6g} mm/px, size = {nx}×{ny} px")
                    lines.append(f"  beam center = ({x0:.3g}, {y0:.3g}) px")
                    if rmax_user_note is not None:
                        lines.append(f"  user r_max = {rmax_user:.6g} mm  [{rmax_user_note}]")
                    lines.append(f"  r_min = {rmin_mm:.6g} mm")
                    lines.append(f"  r_max(full-ring, edge) = {r_full_mm:.6g} mm")
                    lines.append(f"  r_max(corner limit)    = {r_diag_mm:.6g} mm")
                    lines.append(f"  2θ max (full/corner) ≈ {math.degrees(two_theta_full):.6g} / {math.degrees(two_theta_diag):.6g} deg")

                    # NOTE: Qmax differs by definition (edge vs corner). Report both to avoid ambiguity.
                    lines.append(f"  Q range (full-ring) ≈ {Qmin:.6g} – {Qmax_full:.6g} Å⁻¹  (edge-limited)")
                    lines.append(f"  Q range (corner)    ≈ {Qmin:.6g} – {Qmax_diag:.6g} Å⁻¹ (diagonal limit)")
                    if math.isfinite(dmax):
                        lines.append(f"  d_max (from r_min) ≈ {dmax:.6g} Å")
                        lines.append(f"  d_min (full/corner) ≈ {dmin_full:.6g} / {dmin_diag:.6g} Å")
                    else:
                        lines.append(f"  d_min (full/corner) ≈ {dmin_full:.6g} / {dmin_diag:.6g} Å ; d_max → ∞ (r_min=0)")
                    lines.append("")
                except Exception as ge:
                    lines.append("Detector coverage: skipped (invalid geometry inputs).")
                    lines.append(f"  Reason: {ge}")
                    lines.append("")
            if self.target_mode.get() == "T":
                Tt = safe_float(self.target_T.get(), None)
                if Tt is None or not (0 < Tt < 1):
                    raise ValueError("Target T must be between 0 and 1.")

                other_mut = 0.0
                if self.target_scope_total.get():
                    # compute absorption from enabled non-sample layers
                    try:
                        res_other = self._evaluate_layer_stack(e_keV, kind, source, w_mass, rho, mu_eff, sample_t_mm=None)
                        other_mut = float(res_other["mut_other"])
                    except Exception as _exc:
                        raise ValueError(f"Failed to evaluate layer stack for TOTAL target: {_exc}") from _exc
                    mut_total_target = -math.log(Tt)
                    mut_sample_needed = mut_total_target - other_mut
                    if mut_sample_needed <= 0:
                        raise ValueError("Other layers already absorb too much: cannot reach the requested TOTAL transmission. Reduce windows/air, or relax target T.")
                    t_req = mut_sample_needed / mu_eff
                    lines.append(f"Primary: target TOTAL T = {Tt:.6g}  (includes Layers)")
                    lines.append(f"  other layers: Σ(μt)_other = {other_mut:.6g}  ⇒  T_other = {math.exp(-other_mut):.6g}")
                    lines.append(f"  sample thickness t = {t_req:.6g} mm  (sample μt = {mu_eff*t_req:.6g})")
                    lines.append(f"  check: T_total = exp(-(μt_other+μt_sample)) = {math.exp(-(other_mut+mu_eff*t_req)):.6g}")
                else:
                    t_req = thickness_for_transmission(mu_eff, Tt)
                    lines.append(f"Primary: target sample-only T = {Tt:.6g}")
                    lines.append(f"  thickness t = {t_req:.6g} mm  (μt = {mu_eff*t_req:.6g})")
            else:
                mut = safe_float(self.target_mut.get(), None)
                if mut is None or mut <= 0:
                    raise ValueError("Target μt must be > 0.")

                other_mut = 0.0
                if self.target_scope_total.get():
                    try:
                        res_other = self._evaluate_layer_stack(e_keV, kind, source, w_mass, rho, mu_eff, sample_t_mm=None)
                        other_mut = float(res_other["mut_other"])
                    except Exception as _exc:
                        raise ValueError(f"Failed to evaluate layer stack for TOTAL target: {_exc}") from _exc
                    mut_sample_needed = mut - other_mut
                    if mut_sample_needed <= 0:
                        raise ValueError("Other layers already exceed the requested TOTAL μt. Reduce windows/air, or increase target μt.")
                    t_req = mut_sample_needed / mu_eff
                    lines.append(f"Primary: target TOTAL μt = {mut:.6g}  (includes Layers)")
                    lines.append(f"  other layers: Σ(μt)_other = {other_mut:.6g}")
                    lines.append(f"  sample thickness t = {t_req:.6g} mm  (sample μt = {mu_eff*t_req:.6g})")
                    lines.append(f"  check: T_total = exp(-μt_total) = {math.exp(-(other_mut+mu_eff*t_req)):.6g}")
                else:
                    t_req = mut / mu_eff
                    lines.append(f"Primary: target μt = {mut:.6g}")
                    lines.append(f"  thickness t = {t_req:.6g} mm  (T = exp(-μt) = {math.exp(-mut):.6g})")

            # store last computed thickness for Layers / Exposure
            self.last_sample_thickness_mm = float(t_req)
            self.last_mu_eff_1_per_mm = float(mu_eff)

            lines.append("")
            mut_min = safe_float(self.reco_mut_min.get(), None)
            mut_max = safe_float(self.reco_mut_max.get(), None)
            if mut_min and mut_max and mut_min > 0 and mut_max > mut_min:
                tmin = mut_min / mu_eff
                tmax = mut_max / mu_eff
                lines.append(f"Suggested window (μt = {mut_min:g}–{mut_max:g}):")
                lines.append(f"  thickness ~ {tmin:.6g} – {tmax:.6g} mm")
                lines.append(f"  transmission ~ {math.exp(-mut_max):.3g} – {math.exp(-mut_min):.3g}")
                lines.append("")

            lines.append("Common transmission targets (thickness in mm):")
            for T in [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]:
                lines.append(f"  T={T:.1f} -> t={thickness_for_transmission(mu_eff, T):.6g} mm   (μt={-math.log(T):.3g})")
            lines.append("")
            lines.append("Notes:")
            lines.append("  • This is a first-pass design. Verify by a quick transmission test if possible.")
            lines.append("  • Avoid placing E right on an absorption edge unless intentional.")
            if rho_meta is not None and rho_meta.get("interstitial_detected", False):
                lines.append("  • For alloys with O/N/C/H/B, measured density is preferred for absolute thickness.")

            summary = "\n".join(lines) + "\n"
            self._last_summary = summary
            self._set_results(summary)

            progress["value"] = 80
            self._plot(mu_eff)

            progress["value"] = 100
            self.status.set("Computed successfully.")

        except Exception as e:
            self.status.set(f"Error: {e}")
            messagebox.showerror(APP_TITLE, str(e))
        finally:
            # Ensure progress bar is removed
            try:
                progress.grid_forget()
            except Exception:
                pass

    def export_report(self):
        if not self._last_summary.strip():
            messagebox.showinfo(APP_TITLE, "Nothing to export. Click Compute first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save report",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._last_summary)
            self.status.set(f"Saved report: {path}")
            messagebox.showinfo(APP_TITLE, f"Saved: {path}")
        except Exception as e:
            self.status.set(f"Save failed: {e}")
            messagebox.showerror(APP_TITLE, f"Failed to save: {e}")

    def copy_summary(self):
        if not self._last_summary.strip():
            messagebox.showinfo(APP_TITLE, "Nothing to copy. Click Compute first.")
            return
        self.clipboard_clear()
        self.clipboard_append(self._last_summary)
        self.status.set("Summary copied to clipboard.")
        messagebox.showinfo(APP_TITLE, "Summary copied to clipboard.")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
