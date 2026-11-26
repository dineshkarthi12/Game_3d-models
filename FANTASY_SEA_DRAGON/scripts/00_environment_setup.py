"""00 – Environment setup (part of M01).

Detects the Blender build and Python environment, verifies required libraries,
render devices and exporters, and creates the project directory tree.

Run:
    python 00_environment_setup.py                     # Python with the `bpy` module
    blender -b --python-exit-code 1 -P 00_environment_setup.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dragon_lib import env                       # noqa: E402
from dragon_lib.log import MilestoneRun, check    # noqa: E402


def main():
    with MilestoneRun("M01a", "Environment detection & directories", ["00_environment_setup.py"]) as run:
        run.add_checks(env.ensure_dirs())
        info = env.detect()
        run.output("report", env.write_environment_json(info))
        run.metrics["blender"] = info["blender_version"]
        run.metrics["python"] = info["python_version"]
        run.metrics["cpu_count"] = info["cpu_count"]
        run.add_checks(env.environment_checks(info))
        probe = env.probe_gpu_raster()
        info["gpu_raster_probe"] = probe
        env.write_environment_json(info)
        if probe["ok"]:
            run.add_checks([check("GPU rasteriser (Workbench probe)", "PASS", "Workbench render succeeded")])
        else:
            run.add_checks([check("GPU rasteriser (Workbench probe)", "WARNING",
                                  f"unavailable ({probe['detail']}); all renders use Cycles on CPU")])
            run.note("No OpenGL/EGL context: Workbench and EEVEE cannot render here, "
                     "so every preview and final render uses Cycles (CPU + OpenImageDenoise).")


if __name__ == "__main__":
    main()
