"""Environment detection (Blender build, Python, render devices, exporters)."""
from __future__ import annotations

import importlib
import json
import os
import platform
import sys

import bpy

from . import config
from .log import check


def detect() -> dict:
    info = dict(
        blender_version=bpy.app.version_string,
        blender_version_tuple=list(bpy.app.version),
        blender_build_hash=bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else str(bpy.app.build_hash),
        blender_binary=bpy.app.binary_path or "(bpy Python module)",
        running_as_module=not bool(bpy.app.binary_path) or "python" in os.path.basename(bpy.app.binary_path or "python"),
        background=bpy.app.background,
        python_version=sys.version.split()[0],
        python_executable=sys.executable,
        platform=platform.platform(),
        cpu_count=os.cpu_count(),
        quality=config.QUALITY,
        total_length_m=config.TOTAL_LENGTH_M,
    )
    libs = {}
    for mod in ("numpy", "PIL"):
        try:
            m = importlib.import_module(mod)
            libs[mod] = getattr(m, "__version__", "present")
        except ImportError:
            libs[mod] = None
    info["python_libraries"] = libs
    # render devices / features
    try:
        import _cycles
        info["cycles_available"] = True
        info["cycles_oidn"] = bool(getattr(_cycles, "with_openimagedenoise", False))
    except ImportError:
        info["cycles_available"] = False
        info["cycles_oidn"] = False
    # exporters
    import addon_utils
    mods = {m.__name__ for m in addon_utils.modules()}
    info["exporters"] = dict(
        fbx="io_scene_fbx" in mods,
        gltf_glb="io_scene_gltf2" in mods,
        obj=hasattr(bpy.ops.wm, "obj_export"),
    )
    return info


def environment_checks(info: dict) -> list[dict]:
    v = tuple(info["blender_version_tuple"])
    out = [
        check("Blender version detected", "PASS" if v >= (4, 2, 0) else "WARNING",
              f"{info['blender_version']} ({info['blender_binary']})", info["blender_version"], "4.2+"),
        check("Python environment detected", "PASS", f"Python {info['python_version']} – {info['python_executable']}"),
        check("numpy available", "PASS" if info["python_libraries"]["numpy"] else "FAIL",
              str(info["python_libraries"]["numpy"])),
        check("Pillow available", "PASS" if info["python_libraries"]["PIL"] else "FAIL",
              str(info["python_libraries"]["PIL"])),
        check("Cycles available", "PASS" if info["cycles_available"] else "FAIL",
              f"OpenImageDenoise: {info['cycles_oidn']}"),
    ]
    for k, ok in info["exporters"].items():
        out.append(check(f"Exporter available: {k}", "PASS" if ok else "FAIL", str(ok)))
    return out


def ensure_dirs() -> list[dict]:
    out = []
    for name, path in config.DIRS.items():
        path.mkdir(parents=True, exist_ok=True)
        out.append(check(f"Directory {name}/", "PASS" if path.is_dir() else "FAIL", str(path)))
    for extra in (config.REGIONS_DIR, config.ANALYSIS_DIR, config.DIRS["reports"] / "milestones"):
        extra.mkdir(parents=True, exist_ok=True)
    return out


def write_environment_json(info: dict):
    p = config.DIRS["reports"] / "environment.json"
    p.write_text(json.dumps(info, indent=2))
    return p


def probe_gpu_raster(timeout=90) -> dict:
    """Try a tiny Workbench render in a subprocess (EGL failure can abort the process)."""
    import subprocess
    import tempfile
    out = os.path.join(tempfile.gettempdir(), "fsd_wb_probe.png")
    code = ("import bpy;bpy.ops.wm.read_factory_settings(use_empty=False);s=bpy.context.scene;"
            "s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=64;s.render.resolution_y=64;"
            f"s.render.filepath=r'{out}';bpy.ops.render.render(write_still=True);print('WB_PROBE_OK')")
    if bpy.app.binary_path and "python" not in os.path.basename(bpy.app.binary_path):
        cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python-expr", code]
    else:
        cmd = [sys.executable, "-c", code]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        ok = "WB_PROBE_OK" in r.stdout and os.path.exists(out)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        return dict(ok=ok, detail=tail[0][:200], returncode=r.returncode)
    except subprocess.TimeoutExpired:
        return dict(ok=False, detail="timeout", returncode=None)
