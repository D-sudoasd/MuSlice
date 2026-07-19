<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="MuSlice: design transmission SXRD/SAXS sample thickness from X-ray attenuation.">
</p>

# MuSlice

**Design the sample thickness that lets the beam through.**

MuSlice is a beginner-friendly desktop tool for **transmission SXRD / SAXS** sample thickness design. It uses the Beer–Lambert law and elemental \((\mu/\rho)\) from [xraydb](https://xraypy.github.io/XrayDB/) to recommend thickness from energy, composition, density, and target transmission (\(T\) or \(\mu t\)). Optional tools cover **window/air stacks**, **detector Q/d coverage**, and **relative exposure scaling**.

中文：透射式 SXRD/SAXS **样品厚度快速设计器**——从能量、成分、密度与目标透过率估算厚度，并可预算窗片/空气束路。

## Quick start

```bash
git clone https://github.com/D-sudoasd/MuSlice.git
cd MuSlice
pip install -r requirements.txt
# or: pip install -e .
python -m muslice
# Windows: double-click run.bat
```

Optional modern theme: `pip install sv-ttk`

| Need | Path |
|------|------|
| **Run the app** | `python -m muslice` or `run.bat` |
| Alloy / stack presets | `data/presets/` |
| Example session | `examples/session_83keV_Ti2448.json` |
| Physics notes | `docs/PHYSICS.md` |

## Typical workflow

1. **Beam** — energy (e.g. 83 keV) or wavelength  
2. **Sample** — alloy preset or typed composition; prefer **measured density**  
3. **Target** — \(T\) (e.g. 0.5) or \(\mu t\) (e.g. 0.7); optional total-stack target  
4. **Layers** — stack preset (Kapton / Be / quartz), edit real thicknesses  
5. **Compute** — recommended thickness + \(T\)–\(t\) curve  
6. **Save session** — JSON for full reproducibility  

Keyboard: `Ctrl+Enter` compute · `Ctrl+S` export · `Ctrl+O` load session · `F1` quick start  

## Features (v1.0.0)

- Mass- or atomic-fraction composition with convert / normalize  
- Density: manual (recommended) or rough estimate models  
- Multi-layer transmission budget (windows, air, capillary, sample)  
- Detector orthogonal-geometry Q / d coverage  
- Relative exposure-time estimator (ratio guide, not absolute SNR)  
- Alloy & stack JSON presets  
- Full **session save/load** (JSON)  
- Export report as `.txt` / `.md` (mm + μm, warnings)  

## Project layout

```text
MuSlice/
  src/muslice/          # application package
  data/presets/         # alloys.json, stacks.json
  examples/             # example session files
  docs/                 # PHYSICS, maps
  tests/
  run.bat
  requirements.txt
  pyproject.toml
```

Legacy folder `01_source/` (if present) is superseded by `src/muslice/`.

## Limitations

- Absolute thickness accuracy tracks **density quality** (use measured \(\rho\)).  
- Exposure tool is a **ratio guide**, not absolute SNR.  
- Chemical formulas: simple only (no parentheses).  
- Detector model: flat orthogonal detector.  

## License

MIT — see [LICENSE](LICENSE).

## Cite / credit

Attenuation data via **xraydb** (Elam / Chantler tables). Please cite xraydb and the original tabulations when publishing results derived from this tool.
