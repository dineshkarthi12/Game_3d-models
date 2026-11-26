# Fantasy Sea Dragon – automated Blender pipeline

Procedural, reference-driven 3D creature pipeline (Python + Blender 4.5 LTS).
Every milestone is a script that opens the previous milestone's `.blend`,
generates real geometry, validates it, renders previews, and saves a new
versioned project file.

## Status

| Milestone | Script | Status |
|---|---|---|
| M01 Project initialization | `00_environment_setup.py`, `01_project_setup.py` | ✅ complete |
| M02 Reference system | `01_project_setup.py` | ✅ complete |
| M03 Serpentine body + neck | `02_body_generator.py`, `03_neck_generator.py` | ✅ complete – **awaiting visual approval** |
| M04–M18 | `04_…` – `18_export.py` | planned |

Live status: `python scripts/run_pipeline.py --list` · per-milestone records in
`reports/milestones/*.json` · human-readable log in `reports/milestone_log.md`.

## Setup

```bash
# Blender as a Python module (headless, no GUI needed)
uv venv -p python3.11 ~/.venv-blender
uv pip install -p ~/.venv-blender/bin/python bpy==4.5.4 numpy pillow
~/.venv-blender/bin/python scripts/run_pipeline.py
```

Or with a full Blender install:
`FSD_BLENDER=/path/to/blender python3 scripts/run_pipeline.py`
(steps then run as `blender -b -P script.py -- args`).

Options: `FSD_QUALITY=preview|standard|high` (geometry density + render samples),
`FSD_LENGTH=<metres>` (default 12 m). `run_pipeline.py --from M03a` resumes,
`--only M03` re-runs a single step.

## Layout

```
references/   source sheet, regions/ (23 cropped panels), analysis/ (measured profiles + overlays)
scripts/      milestone scripts + dragon_lib/ (shared library)
project/      versioned .blend saves  FSD_<milestone>_<tag>_v###.blend
renders/      per-milestone previews, contact sheets, reference comparisons
reports/      environment, calibration, comparison JSON; milestone log; pipeline.log
assets/ textures/ exports/   (later milestones)
```

`scripts/dragon_lib/`: `config` (all parameters, quality levels) · `reference`
(crops, landmarks, profile extraction) · `anatomy` (spine + cross-section model) ·
`geometry` (frames, tube builder) · `compare` (calibration, reference planes,
sheet-aligned silhouette comparison) · `validate` (PASS/WARNING/FAIL checks) ·
`render` (camera rig, Cycles, contact sheets) · `bl_utils` · `log` · `env`.

## Conventions

Metres, Z up, dragon faces **−Y**, its left side is **+X**. Arc parameter
`s` runs 0 (snout tip) → 1 (tail-fin tip); world `Y = (s − 0.5)·L`. Z = 0 is the
lowest limb-fin tip. The body mesh carries per-vertex attributes `fsd_s`,
`fsd_theta` (0 dorsal, π/2 left, π ventral) and `fsd_cap`, vertex groups
`VG_Neck/Torso/Tail`, and socket empties for head, limbs and tail fin.

## How the reference is used

The sheet is a design reference, not a calibrated scan. Each orthographic view
is calibrated separately from landmarks (snout tip, tail tip, ground line), and
calibration is verified by rendering a known box (≤ 0.7 px error). Trunk
depth comes from the side view and width from the ventral view, both by colour
segmentation, normalised to L. The comparison system renders the model
through cameras aligned pixel-for-pixel with the sheet and reports
per-column errors. It only covers what is modelled so far, so it makes no
whole-creature accuracy claim. Assumptions are listed in `reports/milestone_log.md`.
