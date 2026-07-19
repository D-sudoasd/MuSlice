<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="MuSlice: design transmission SXRD/SAXS sample thickness from X-ray attenuation.">
</p>

# MuSlice

**Design the sample thickness that lets the beam through.**

Beginner-friendly desktop tool for **transmission SXRD / SAXS** thickness design. Beer–Lambert law + elemental \((\mu/\rho)\) from [xraydb](https://xraypy.github.io/XrayDB/) → thickness from energy, composition, density, and target \(T\) or \(\mu t\). Optional window/air stacks, detector Q/d coverage, relative exposure scaling.

中文：透射式 SXRD/SAXS 样品厚度快速设计器。

<p align="center">
  <img src="assets/readme/section-01-physics.svg" width="100%" alt="01 Physics: Beer-Lambert thickness from attenuation.">
</p>

## Quick start

```bash
git clone https://github.com/D-sudoasd/MuSlice.git
cd MuSlice
pip install -r requirements.txt
python -m muslice          # Windows: run.bat
```

Optional theme: `pip install sv-ttk` · Example: `examples/session_83keV_Ti2448.json` · Physics: `docs/PHYSICS.md`

<p align="center">
  <img src="assets/readme/section-02-workflow.svg" width="100%" alt="02 Workflow: beam, sample, target, compute.">
</p>

1. **Beam** — energy or wavelength  
2. **Sample** — alloy preset or composition; prefer **measured density**  
3. **Target** — \(T\) or \(\mu t\)  
4. **Layers** — Kapton / Be / quartz stacks  
5. **Compute** — thickness + \(T\)–\(t\) curve · **Save session** JSON  

`Ctrl+Enter` compute · `Ctrl+S` export · `Ctrl+O` load · `F1` help  

### Features (v1.0.0)

Mass/atomic composition · density models · multi-layer transmission budget · detector Q/d · relative exposure · presets · session I/O · `.txt`/`.md` reports  

### Limits

Density quality dominates accuracy · exposure tool is a ratio guide · simple formulas only · flat orthogonal detector model  

## License

MIT · Cite **xraydb** (Elam/Chantler) when publishing derived results.
