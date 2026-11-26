"""02 – Serpentine body generator (M03, part 1: continuous trunk).

Builds one continuous, watertight, quad-dominant trunk mesh from the neck root
(inside the future head) to the tail core tip (inside the future tail fan),
using the reference-driven ``TrunkModel``:

* spine     – reference centre line + user control points, parallel-transport frames
* sections  – asymmetric superellipse (flatter belly), dorsal ridge, flank muscles
* radii     – side-view depth + ventral-view width, neck/tail anchors, girdle bulges
* rings     – arc-length + radius-change weighted distribution
* caps      – hemispherical pole caps at both ends (buried in head / tail fan)

Per-vertex attributes written for later milestones:
    fsd_s      arc fraction (0 snout -> 1 tail tip)
    fsd_theta  angle around the trunk (0 dorsal, pi/2 left, pi ventral)
    fsd_cap    0 trunk ring, 1 front cap, 2 back cap

All parameters live in dragon_lib/config.py (BODY, QUALITY_LEVELS).
Run:  python 02_body_generator.py      |  blender -b --python-exit-code 1 -P 02_body_generator.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from dragon_lib import anatomy, config, geometry as G, render, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

BODY_NAME = config.PREFIX + "Body"


def build_trunk(trunk: anatomy.TrunkModel, q: dict):
    n_rings, radial = q["body_rings"], q["body_radial"]
    s_rings = trunk.ring_s_values(n_rings)
    f = trunk.at(s_rings)
    thetas = 2 * math.pi * np.arange(radial) / radial
    sec = trunk.section(s_rings, thetas)
    r_front = min(f["half_width"][0], f["half_depth"][0])
    r_back = min(f["half_width"][-1], f["half_depth"][-1])
    tube = G.build_tube(f["centre"], f["T"], f["U"], f["B"], sec, s_rings,
                        cap_front=dict(rings=trunk.p["cap_rings"], length=0.6 * r_front),
                        cap_back=dict(rings=trunk.p["cap_rings"], length=1.6 * r_back))
    return tube, s_rings, f, sec


def spine_guide(trunk, name="DRG_Spine_Guide", n=96):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    idx = np.linspace(0, len(trunk.s) - 1, n).astype(int)
    sp.points.add(n - 1)
    for p, i in zip(sp.points, idx):
        p.co = (*trunk.centre[i], 1.0)
    ob = bpy.data.objects.new(name, cu)
    bu.coll("02_BODY").objects.link(ob)
    ob.hide_render = True
    return ob


def main():
    q = config.quality()
    with MilestoneRun("M03a", "Serpentine body – continuous trunk", ["02_body_generator.py"]) as run:
        bu.open_blend(latest_blend("M02"))
        bu.remove_objects(BODY_NAME)
        bu.remove_objects("DRG_Spine_Guide")
        trunk = anatomy.TrunkModel()
        tube, s_rings, f, sec = build_trunk(trunk, q)
        ob = bu.mesh_object(BODY_NAME, tube["verts"], tube["faces"], "02_BODY", face_uvs=tube["face_uvs"])
        me = ob.data
        bu.set_point_attr(me, "fsd_s", tube["attr_s"])
        bu.set_point_attr(me, "fsd_theta", tube["attr_theta"])
        bu.set_point_attr(me, "fsd_cap", tube["attr_cap"], "INT")
        ob["fsd_ring_count"] = tube["ring_count"]
        ob["fsd_radial"] = tube["radial"]
        ob["fsd_body_rings"] = len(s_rings)
        ob["fsd_front_cap_rings"] = trunk.p["cap_rings"]
        ob["fsd_params_body"] = json.dumps(trunk.p)
        ob["fsd_quality"] = q["name"]
        bu.assign_material(ob, bu.clay_material())
        bu.add_subsurf(ob, q["subsurf_viewport"], q["subsurf_render"])
        spine_guide(trunk)

        summ = trunk.summary()
        run.metrics.update({k.replace("_", " "): v for k, v in summ.items()})
        run.metrics["rings x radial"] = f"{len(s_rings)} x {q['body_radial']} (+{2 * trunk.p['cap_rings']} cap rings)"
        run.metrics["base faces"] = len(me.polygons)

        # ---- validation
        run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
        run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=q["selfcheck_intersections"],
                                            evaluated=True))
        ring_r = np.hypot(sec[..., 0], sec[..., 1]).mean(1)
        run.add_checks(validate.ring_continuity_checks(BODY_NAME, ring_r, f["T"]))
        run.add_checks([validate.uv_check(ob), validate.materials_check(ob)])
        span = (f["centre"][-1, 1] - f["centre"][0, 1]) / config.TOTAL_LENGTH_M
        exp_span = trunk.p["end_s"] - trunk.p["start_s"]
        run.add_checks([check("Trunk extent matches parameters",
                              "PASS" if abs(span - exp_span) < 1e-3 else "FAIL",
                              f"spans s {trunk.p['start_s']}–{trunk.p['end_s']} ({span * config.TOTAL_LENGTH_M:.2f} m along Y)")])
        lo, hi = bu.world_bbox([ob])
        run.add_checks([check("Trunk above ground plane", "PASS" if lo[2] > 0 else "FAIL",
                              f"lowest point z = {lo[2]:.3f} m")])
        run.assume("Neck section (s < 0.17) is hidden behind neck fins on the sheet: blended (C1 Hermite) "
                   f"to a head-junction anchor of {trunk.p['neck_half_depth_m']} m half-depth x "
                   f"{trunk.p['neck_half_width_m']} m half-width (tall, narrow skull base).")
        run.assume("Tail core inside the fan fin (s > 0.74) is not measurable: tapered to "
                   f"{trunk.p['tail_radius_m']} m at s = {trunk.p['end_s']}.")
        bu.save_milestone(run, "trunk")

        out = config.DIRS["renders"] / "M03"
        paths = render.render_views(["left", "three_quarter_front_left"], out, "M03a_trunk",
                                    samples=24, objs=[ob], res_scale=0.6)
        for p in paths.values():
            run.output("render", p)


if __name__ == "__main__":
    main()
