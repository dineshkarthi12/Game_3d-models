"""Pipeline runner – executes milestone scripts in order, each in a fresh process.

Usage
-----
    python run_pipeline.py                 # run every implemented step
    python run_pipeline.py --from M03a     # resume from a step
    python run_pipeline.py --only M03      # single step
    python run_pipeline.py --list          # show steps and recorded status

Interpreter
-----------
By default each step runs with the current interpreter, which must provide the
``bpy`` module (pip install bpy==4.5.4 in a Python 3.11 venv).  To use a full
Blender install instead set ``FSD_BLENDER=/path/to/blender``; steps then run as
``blender -b --factory-startup --python-exit-code 1 -P <script> -- <args>``.

Quality: FSD_QUALITY=preview|standard|high (default standard).
The runner stops at the first failing step (non-zero exit code).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = [
    ("M01a", "00_environment_setup.py", []),
    ("M01", "01_project_setup.py", ["--milestone", "M01"]),
    ("M02", "01_project_setup.py", ["--milestone", "M02"]),
    ("M03a", "02_body_generator.py", []),
    ("M03", "03_neck_generator.py", []),
    ("M04", "04_head_generator.py", []),
    ("M05", "05_facial_details.py", []),
    ("M06", "06_scale_generator.py", []),
    ("M07", "07_belly_armour.py", []),
    ("M08", "08_spine_generator.py", []),
    ("M09", "09_fin_generator.py", []),
]
PLANNED = [

    ("M10", "10_limb_generator.py"), ("M11", "11_claw_generator.py"), ("M12", "12_tail_generator.py"),
    ("M13", "13_material_generator.py"), ("M14", "14_uv_generator.py"), ("M15", "15_rigging.py"),
    ("M16", "16_lighting_render.py"), ("M17", "17_quality_validation.py"), ("M18", "18_export.py"),
]


def command(script, args):
    blender = os.environ.get("FSD_BLENDER")
    if blender:
        return [blender, "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(HERE / script), "--", *args]
    return [sys.executable, str(HERE / script), *args]


def status():
    p = HERE.parent / "reports" / "pipeline_state.json"
    return json.loads(p.read_text())["milestones"] if p.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start")
    ap.add_argument("--only")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    st = status()
    if a.list:
        for mid, script, _ in STEPS:
            s = st.get(mid, {})
            print(f"{mid:5s} {script:28s} {s.get('status', 'not run'):24s} {s.get('blend') or ''}")
        for mid, script in PLANNED:
            print(f"{mid:5s} {script:28s} {'planned (not implemented)'}")
        return 0
    ids = [s[0] for s in STEPS]
    steps = STEPS
    if a.only:
        steps = [s for s in STEPS if s[0] == a.only]
    elif a.start:
        steps = STEPS[ids.index(a.start):]
    for mid, script, args in steps:
        t0 = time.time()
        print(f"\n>>> {mid}: {script} {' '.join(args)}", flush=True)
        r = subprocess.run(command(script, args), cwd=HERE)
        print(f"<<< {mid}: exit {r.returncode} ({time.time() - t0:.1f}s)", flush=True)
        if r.returncode != 0:
            print(f"Pipeline stopped: {mid} failed. See reports/milestones/{mid}.json and reports/pipeline.log")
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
