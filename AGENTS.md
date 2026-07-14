# AGENTS.md — MuSlice

Scientific **tool** workspace (tkinter GUI), not an experimental raw-data tree.  
**Language:** Chinese notes OK; paths exact.

## 1. What this is

| Item | Value |
|------|--------|
| Product | **MuSlice** v1.0.0 |
| Purpose | Transmission thickness design for SXRD/SAXS (Beer–Lambert) |
| CURRENT entry | `python -m muslice` → `src/muslice/app.py` |
| Do not treat as CURRENT | `99_archive/`, `__pycache__`, `01_source/` (legacy copy), `tmp/` |
| User UI config | `%APPDATA%\muslice\config.json` |

## 2. Read order

1. This file  
2. `README.md`  
3. `src/muslice/app.py` (+ `presets.py`, `session_io.py`)  
4. `data/presets/*.json`

## 3. Directory roles

```text
src/muslice/     package (GUI + physics helpers)
data/presets/    alloy & stack libraries
examples/        session JSON samples
docs/            physics notes / maps
tests/           smoke tests (no GUI)
```

## 4. Hard boundaries

- Do not invent experimental frame counts or beamline runs  
- Prefer measured density language in user-facing notes  
- Keep package importable: `python -m muslice`  
- Session schema major version is in `session_io.SESSION_SCHEMA`  

## 5. Run / test

```text
set PYTHONPATH=src
python -m muslice
python -m pytest tests -q
```
