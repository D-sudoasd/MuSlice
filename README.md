<p align="center">
  <img src="assets/readme/hero.png" width="100%" alt="MuSlice — Estimate sample thickness from X-ray attenuation / 根据 X 射线衰减估算样品厚度. Conceptual illustration / 概念插图。">
</p>

# MuSlice

**用能量、组成、密度与目标透射率，估算透射式 SXRD / SAXS 样品厚度。**

A desktop thickness-design tool based on Beer–Lambert attenuation and elemental mass attenuation coefficients from xraydb. Intended for planning sample thickness before a transmission experiment.

[安装与启动](#install--quick-start) · [操作顺序](#usage) · [83 keV Ti2448 示例](examples/session_83keV_Ti2448.json) · [物理定义](docs/PHYSICS.md)

[![MIT](https://img.shields.io/badge/License-MIT-455A64)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](pyproject.toml)

<picture>
  <source media="(max-width: 600px)" srcset="assets/readme/diagrams/workflow-readme-md-1-mobile.svg">
  <img src="assets/readme/diagrams/workflow-readme-md-1.svg" width="100%" alt="MuSlice — workflow schematic / 流程示意图">
</picture>

<sub>[Editable diagram source / 可编辑图源](assets/readme/diagrams/workflow-readme-md-1.mmd)</sub>

仓库会话示例使用 **83 keV、Ti–24Nb–4Zr–8Sn 质量组成、手动密度 5.5 g/cm³ 和目标透射率 0.5**。这些是示例输入，不是对实测密度或实验结果的认证。可另计窗口与空气层的透射预算、探测器覆盖范围和相对曝光比例。优先输入实测密度。

## 原理示意 / Principle schematic

<p align="center">
  <img src="assets/readme/principle.png" width="100%" alt="Beer–Lambert 衰减、多层透射预算与有效厚度 — conceptual schematic / 概念示意图">
</p>

*概念示意：组成、密度和能量决定衰减系数，样品与窗口等层共同影响透射率；倾斜入射增加有效路径长度。图中 T–t 曲线为模型示意，不是实测透射数据。*

*Conceptual schematic: composition, density and energy determine attenuation, while sample and window layers contribute to the transmission budget; tilt increases effective path length. The T–t curve is a model illustration, not measured transmission.*

[查看完整示意图 / View full-size schematic](assets/readme/principle.png)

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
