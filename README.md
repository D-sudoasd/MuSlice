<p align="center">
  <img src="assets/readme/hero.png" width="100%" alt="MuSlice — Estimate sample thickness from X-ray attenuation / 根据 X 射线衰减估算样品厚度. Conceptual illustration / 概念插图。">
</p>

# MuSlice

**Estimate sample thickness from X-ray attenuation**

**根据 X 射线衰减估算样品厚度**

[Overview / 项目概览](#overview--项目概览) · [Start / 开始使用](#start--开始使用) · [Reference / 详细说明](#reference--详细说明)

## Overview / 项目概览

Combine beam energy, composition, density and a target transmission to design transmission-SXRD or SAXS samples. Compare optional window layers and save the calculation context.

结合能量、成分、密度与目标透射率，设计透射 SXRD 或 SAXS 样品厚度，比较可选窗口层并保存计算条件。

- **Beer–Lambert calculation** — 使用 xraydb 元素衰减系数与明确输入条件。
- **Layer budgets** — 计入窗口和空气等附加层。
- **Session export** — 保存工程与文本或 Markdown 报告。

## Start / 开始使用

```powershell
py -m pip install -e .
py -m muslice
```

Prefer measured density where available. Relative exposure estimates are ratios, not an absolute beam-flux calibration.

有实测密度时优先采用；相对曝光估计表示比例，不是绝对束流标定。

*Cover: AI-generated conceptual illustration. 封面为 AI 生成的概念插图。*

## Reference / 详细说明

# MuSlice

**Design the sample thickness that lets the beam through.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/downloads/)
[![version](https://img.shields.io/badge/version-1.0.0-lightgrey.svg)](pyproject.toml)

Beginner-friendly desktop tool for **transmission SXRD / SAXS** thickness design. Beer–Lambert law + elemental \((\mu/\rho)\) from [xraydb](https://xraypy.github.io/XrayDB/) → thickness from energy, composition, density, and target transmittance \(T\) or optical depth \(\mu t\).

Optional window/air stacks, detector *Q*/*d* coverage, and relative exposure scaling.

中文：透射式 SXRD/SAXS 样品厚度快速设计器（基于 Beer–Lambert 与 xraydb 元素衰减系数）。

<p align="center">
  <img src="assets/readme/section-01-physics.svg" width="100%" alt="01 Physics: Beer-Lambert thickness from attenuation.">
</p>

## Features (v1.0.0)

- Mass or atomic composition; alloy presets
- Density models — prefer **measured density** when available
- Multi-layer transmission budget (Kapton / Be / quartz / air)
- Detector *Q*/*d* coverage helper
- Relative exposure scaling (ratio guide, not absolute flux)
- Session JSON I/O and `.txt` / `.md` reports

## Install / Quick start

```bash
git clone https://github.com/D-sudoasd/MuSlice.git
cd MuSlice
python -m pip install -e .
python -m muslice          # Windows: run.bat
```

The editable install includes the runtime dependencies and makes the `src/muslice` package importable. Installing only `requirements.txt` does not install the package; for that source-only route, use `run.bat` on Windows or set `PYTHONPATH=src` before running the module. Python must include `tkinter`.

Optional theme: `pip install sv-ttk`  
Example session: `examples/session_83keV_Ti2448.json`  
Physics notes: `docs/PHYSICS.md`

## Usage

<p align="center">
  <img src="assets/readme/section-02-workflow.svg" width="100%" alt="02 Workflow: beam, sample, target, compute.">
</p>

1. **Beam** — energy or wavelength  
2. **Sample** — alloy preset or composition; prefer measured density  
3. **Target** — \(T\) or \(\mu t\)  
4. **Layers** — Kapton / Be / quartz stacks  
5. **Compute** — thickness + \(T\)–\(t\) curve · **Save session** JSON  

Shortcuts: `Ctrl+Enter` compute · `Ctrl+S` export · `Ctrl+O` load · `F1` help

## Scientific boundary — what it is NOT

- Density quality **dominates** accuracy — wrong ρ → wrong thickness
- Exposure tool is a **relative ratio guide**, not absolute beamtime prediction
- Uses simple Beer–Lambert formulas only (no full Monte-Carlo ray tracing)
- Flat orthogonal detector model for *Q*/*d* coverage
- Not a scattering simulator, sample changer planner, or safety interlock

## License

MIT · Cite **xraydb** (Elam / Chantler tables) when publishing derived thicknesses or attenuation results.
