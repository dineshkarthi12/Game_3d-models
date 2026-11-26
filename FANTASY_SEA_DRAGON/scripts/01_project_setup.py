"""01 – Project setup (M01) and reference system (M02).

M01  metric scene, collection hierarchy, neutral clay material, world,
     orthographic + 3/4 camera rig, preview lights, scale gauges, first save.
M02  crops every panel of the reference sheet, measures trunk profiles,
     builds calibrated orthographic reference planes, and verifies the
     calibration with sheet-aligned test renders.

Run:
    python 01_project_setup.py [--milestone M01|M02|all]
    blender -b --python-exit-code 1 -P 01_project_setup.py -- --milestone all
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from dragon_lib import compare, config, reference as ref, render  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend, rel  # noqa: E402

L = config.TOTAL_LENGTH_M


# ==========================================================================
# M01
# ==========================================================================
def build_scale_gauges():
    """Length gauge (1 m ticks) and a 1.8 m human-scale proxy (viewport only)."""
    bu.remove_objects("REF_Gauge")
    bu.remove_objects("REF_Human")
    verts, faces = [], []

    def box(cx, cy, cz, sx, sy, sz):
        b = len(verts)
        for x in (-sx, sx):
            for y in (-sy, sy):
                for z in (-sz, sz):
                    verts.append((cx + x, cy + y, cz + z))
        faces.extend([(b, b + 1, b + 3, b + 2), (b + 4, b + 6, b + 7, b + 5), (b, b + 4, b + 5, b + 1),
                      (b + 2, b + 3, b + 7, b + 6), (b, b + 2, b + 6, b + 4), (b + 1, b + 5, b + 7, b + 3)])

    box(0, 0, 0.01, 0.02, L / 2, 0.01)
    for i in range(int(L) + 1):
        y = -L / 2 + i
        h = 0.15 if i % 5 else 0.3
        box(0, y, h / 2, 0.03, 0.015, h / 2)
    g = bu.mesh_object("REF_Gauge_Length", verts, faces, "01_REFERENCES", smooth=False)
    verts.clear(); faces.clear()
    box(2.0, -L / 2, 0.9, 0.25, 0.15, 0.9)
    h = bu.mesh_object("REF_Human_1p8m", verts, faces, "01_REFERENCES", smooth=False)
    for ob in (g, h):
        bu.assign_material(ob, bu.clay_material())
        ob.hide_render = True
    return g, h


def m01():
    with MilestoneRun("M01", "Project initialization", ["00_environment_setup.py", "01_project_setup.py"]) as run:
        bu.reset_scene()
        sc = bpy.context.scene
        sc.name = "FSD_Scene"
        sc.unit_settings.system = "METRIC"
        sc.unit_settings.scale_length = 1.0
        sc.unit_settings.length_unit = "METERS"
        sc.unit_settings.mass_unit = "KILOGRAMS"
        sc.render.fps = 30
        sc.frame_start, sc.frame_end = 1, 120
        bu.ensure_collections()
        clay = bu.clay_material()
        render.setup_world()
        render.configure_cycles(config.quality()["render_samples"])
        render.create_camera_rig(L)
        render.create_preview_lights(L)
        g, h = build_scale_gauges()
        sc["fsd_total_length_m"] = L
        sc["fsd_quality"] = config.QUALITY
        sc["fsd_conventions"] = "Z up, metres, dragon faces -Y, left side +X, s=0 snout -> s=1 tail tip"

        # ---- checks
        missing = [c for c in config.COLLECTIONS if c not in bpy.data.collections]
        run.add_checks([
            check("Collections created", "PASS" if not missing else "FAIL",
                  f"{len(config.COLLECTIONS) - len(missing)}/{len(config.COLLECTIONS)} "
                  f"(+ {config.CAMERA_COLLECTION}, {config.PREVIEW_LIGHT_COLLECTION})"),
            check("Metric units", "PASS" if sc.unit_settings.system == "METRIC" and sc.unit_settings.scale_length == 1.0
                  else "FAIL", f"{sc.unit_settings.system}, scale {sc.unit_settings.scale_length}, {sc.unit_settings.length_unit}"),
            check("Camera rig", "PASS" if len(bu.coll(config.CAMERA_COLLECTION).objects) == len(render.VIEWS) else "FAIL",
                  f"{len(bu.coll(config.CAMERA_COLLECTION).objects)} cameras: " + ", ".join(render.VIEWS)),
            check("Preview lights", "PASS" if len(bu.coll(config.PREVIEW_LIGHT_COLLECTION).objects) == 4 else "FAIL",
                  f"{len(bu.coll(config.PREVIEW_LIGHT_COLLECTION).objects)} area lights"),
            check("Neutral clay material", "PASS" if clay.use_fake_user else "FAIL", clay.name),
        ])
        gauge_len = g.dimensions.y
        run.add_checks([check("Scene scale (length gauge)", "PASS" if abs(gauge_len - (L + 0.03)) < 1e-3 else "FAIL",
                              f"gauge spans {gauge_len:.3f} m for a {L} m creature")])
        bu.save_milestone(run, "init")

        # ---- preview: verify cameras render the gauges at the right scale
        for ob in (g, h):
            ob.hide_render = False
        out = config.DIRS["renders"] / "M01"
        paths = render.render_views(["left", "three_quarter_front_left"], out, "M01_gauges",
                                    samples=16, objs=[g, h], res_scale=0.5)
        for ob in (g, h):
            ob.hide_render = True
        for p in paths.values():
            run.output("render", p)
        sheet = render.contact_sheet([[(paths["left"], "Left ortho – 12 m gauge, 1 m ticks"),
                                       (paths["three_quarter_front_left"], "3/4 front-left – 1.8 m human proxy")]],
                                     out / "M01_preview_sheet.png", "M01 – camera rig & scale check", width=1800)
        run.output("preview", sheet)
        run.add_checks([check("Preview renders written", "PASS" if all(p.exists() for p in paths.values()) else "FAIL",
                              ", ".join(p.name for p in paths.values()))])


# ==========================================================================
# M02
# ==========================================================================
def m02():
    with MilestoneRun("M02", "Reference system", ["01_project_setup.py"]) as run:
        bu.open_blend(latest_blend("M01"))
        # ---- 1. organise reference regions
        crops = ref.crop_regions()
        for p in crops.values():
            run.output("reference_region", p)
        run.add_checks([check("Reference regions cropped", "PASS" if len(crops) == len(ref.REGIONS) else "FAIL",
                              f"{len(crops)} panels -> references/regions/")])
        run.assume("The sheet is a design reference, not a calibrated scan: every orthographic view is "
                   "calibrated independently (snout tip / tail-fin tip landmarks) and normalised to the total length L.")
        run.assume("Side view length 1029 px vs top/bottom 1009–1011 px (1.8 % discrepancy) – resolved by per-view normalisation.")
        run.assume("Ground (Z = 0) = lowest limb-fin tip on the side view; the sheet shows a swimming pose with hanging webbed feet.")
        run.assume("Front/back views are scaled by matching the head's vertical extent to the side view (approximate, ±10 %).")
        run.assume("3/4 views and head/detail panels are perspective or close-up images: kept as review crops, not projected.")

        # ---- 2. measure trunk profiles
        prof = ref.extract_profiles(write=True)
        for name in ("reference_profiles.json", "side_profile_overlay.png", "bottom_width_overlay.png", "profile_chart.png"):
            run.output("analysis", config.ANALYSIS_DIR / name)
        sm = prof["summary"]
        n_valid_d = sum(v is not None for v in prof["half_depth_L"])
        n_valid_w = sum(v is not None for v in prof["half_width_L"])
        run.metrics["max trunk depth (m)"] = round(2 * sm["max_half_depth_L"] * L, 3)
        run.metrics["max trunk width (m)"] = round(2 * sm["max_half_width_L"] * L, 3)
        run.metrics["mean depth/width ratio"] = round(sm["mean_depth_to_width"], 2)
        run.add_checks([
            check("Side-view trunk profile measured", "PASS" if n_valid_d > 150 else "FAIL",
                  f"{n_valid_d} stations (s {ref.VALID_RANGE_S['side_left']}, limb zones interpolated)"),
            check("Bottom-view width profile measured", "PASS" if n_valid_w > 150 else "FAIL",
                  f"{n_valid_w} stations (s {ref.VALID_RANGE_S['bottom']})"),
        ])
        run.note("Top-view width (~22 px) under-reads because the dark flank scales merge with the background; "
                 "the bright ventral view (~45 px) is used for lateral width.")

        # ---- 3. calibrated orthographic reference planes
        calib = {}
        for view in ("side_left", "side_right", "front", "back", "top", "bottom"):
            ob = compare.create_reference_plane(view, crops[view])
            cal = compare.calibration(view)
            calib[view] = dict(object=ob.name, metres_per_px=round(cal["mpp"], 6),
                               approximate=cal["approx"], camera=cal["cam_view"],
                               location=[round(v, 4) for v in ob.location])
        cpath = config.DIRS["reports"] / "reference_calibration.json"
        cpath.write_text(json.dumps(calib, indent=2))
        run.output("report", cpath)

        # ---- 4. verify the comparison system
        out = config.DIRS["renders"] / "M02"
        out.mkdir(parents=True, exist_ok=True)
        checks, details = compare.calibration_self_test(out)
        run.add_checks(checks)
        (config.DIRS["reports"] / "calibration_self_test.json").write_text(json.dumps(details, indent=2, default=float))
        tests = []
        for view in calib:
            c, p = compare.plane_render_test(view, out)
            run.add_checks([c])
            tests.append((p, view))
            run.output("render", p)
        render.configure_cycles(config.quality()["render_samples"])

        # ---- 5. preview: reference cage seen from 3/4 front-left
        show = ["REF_side_left", "REF_front", "REF_top"]
        for n in show:
            bpy.data.objects[n].hide_render = False
        render.configure_cycles(16, view_transform="Standard")
        objs = [bpy.data.objects[n] for n in show]
        paths = render.render_views(["three_quarter_front_left"], out, "M02_reference_cage", 16, objs=objs,
                                    res_scale=0.75, margin=1.02)
        for n in show:
            bpy.data.objects[n].hide_render = True
        render.configure_cycles(config.quality()["render_samples"])
        crops_dir = config.REGIONS_DIR
        rows = [[(tests[0][0], "Plane render: side_left"), (crops_dir / "ref_side_left.png", "Sheet crop: side_left")],
                [(tests[4][0], "Plane render: top"), (tests[5][0], "Plane render: bottom")],
                [(tests[2][0], "Plane render: front"), (tests[3][0], "Plane render: back"),
                 (paths["three_quarter_front_left"], "Reference cage (3/4 front-left)")]]
        sheet = render.contact_sheet(rows, out / "M02_preview_sheet.png",
                                     "M02 – calibrated orthographic reference planes", width=2200)
        run.output("preview", sheet)
        bu.save_milestone(run, "references")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--milestone", default="all", choices=["M01", "M02", "all"])
    a = ap.parse_args(bu.script_args())
    if a.milestone in ("M01", "all"):
        m01()
    if a.milestone in ("M02", "all"):
        m02()


if __name__ == "__main__":
    main()
