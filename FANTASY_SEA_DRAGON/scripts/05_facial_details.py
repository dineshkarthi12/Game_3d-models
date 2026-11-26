"""05 – Facial details (M05): teeth and whiskers.

    DRG_Teeth_Upper / DRG_Teeth_Lower   individual curved conical teeth on the jaw
                                        rims: large fangs at the front, varied
                                        lengths, curving back/inward (13_TEETH)
    DRG_Whiskers                        long looping barbels from the upper lip +
                                        short chin barbels, tubular geometry (14_WHISKERS)
    WHISKER_Guide_*                     editable Bezier guide curves (render-hidden)

Teeth are filtered so no tooth intersects another; teeth and whiskers are
checked against the opposite jaw, tongue and facial parts.
Run:  python 05_facial_details.py   |  blender -b --python-exit-code 1 -P 05_facial_details.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from dragon_lib import config, head, parts, review, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

UP = np.array([0.0, 0.0, 1.0])
BACK = np.array([0.0, 1.0, 0.0])
RIM_TH = 0.48           # angle offset of the dental rim below / above the lateral midline


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def tooth_layout(n, rng, fang_t=0.075):
    """(t, length, radius) per tooth along one side of a jaw, front -> back."""
    ts = np.linspace(0.025, 0.66, n) + rng.normal(0, 0.006, n)
    out = []
    for t in ts:
        fang = math.exp(-0.5 * ((t - fang_t) / 0.02) ** 2)
        length = (0.055 + 0.04 * (1 - t / 0.7)) * (0.85 + 0.3 * rng.random()) + 0.11 * fang
        radius = 0.018 + 0.012 * fang + 0.006 * (1 - t / 0.7)
        out.append((t, length, radius))
    return out


def build_teeth(kind, rng):
    cands = []
    for sgn in (1, -1):
        for t, L, r in tooth_layout(18 if kind == "upper" else 16, rng,
                                    fang_t=0.07 if kind == "upper" else 0.09):
            if kind == "upper":
                p, n = head.skull_point_world(t, sgn * (math.pi / 2 + RIM_TH))
                down = unit(head.dir_world_skull(-UP))
            else:
                p, n = head.jaw_point_world(t, sgn * (math.pi / 2 - RIM_TH))
                down = unit(head.dir_world_jaw(UP))          # lower teeth grow 'up' out of the jaw
            inward = unit(np.array([-sgn, 0, 0]))
            grow = unit(down + 0.15 * inward)
            cands.append(parts.curved_spike(p, grow, BACK, L, base_long=r, base_lat=r * 0.85,
                                            sweep_deg=8, curl_deg=18, n=10, radial=10, sink=0.025,
                                            taper=1.0, profile="round"))
    # incisors across the snout / chin front
    for x in np.linspace(-0.6, 0.6, 4):
        if kind == "upper":
            p, n = head.skull_point_world(0.012, math.pi + x)
            grow = unit(head.dir_world_skull(-UP))
        else:
            p, n = head.jaw_point_world(0.02, x)
            grow = unit(head.dir_world_jaw(UP))
        cands.append(parts.curved_spike(p, grow, BACK, 0.05, base_long=0.014, base_lat=0.012, sweep_deg=5,
                                        curl_deg=10, n=8, radial=8, sink=0.02, profile="round"))
    # big fangs first in priority, then the rest
    order = sorted(range(len(cands)), key=lambda i: -np.ptp(cands[i]["verts"], axis=0).max())
    kept, rejected = parts.keep_non_intersecting([cands[i] for i in order])
    mb = parts.MeshBuilder()
    for c in kept:
        mb.add(c, mat=0)
    name = "DRG_Teeth_Upper" if kind == "upper" else "DRG_Teeth_Lower"
    ob = bu.object_from_builder(name, mb, "13_TEETH", ["MAT_Teeth_Ivory"])
    ob["fsd_teeth_rejected"] = rejected
    return ob, len(kept), rejected


def whisker_paths():
    paths = []
    for sgn in (1, -1):
        # long upper-lip whisker: forward-out, down, loops back under the jaw
        p, n = head.skull_point_world(0.12, sgn * 1.45)
        cps = [p, p + [sgn * 0.12, -0.30, -0.02], p + [sgn * 0.32, -0.38, -0.40],
               p + [sgn * 0.42, -0.05, -0.80], p + [sgn * 0.40, 0.45, -0.85], p + [sgn * 0.30, 0.80, -0.55]]
        paths.append(("long", sgn, np.array(cps), 0.020))
        # second, shorter whisker
        p, n = head.skull_point_world(0.20, sgn * 1.62)
        cps = [p, p + [sgn * 0.14, -0.18, -0.05], p + [sgn * 0.30, -0.10, -0.35],
               p + [sgn * 0.34, 0.25, -0.55], p + [sgn * 0.28, 0.55, -0.45]]
        paths.append(("mid", sgn, np.array(cps), 0.015))
        # chin barbel
        p, n = head.jaw_point_world(0.05, sgn * 2.4)
        cps = [p, p + [sgn * 0.05, -0.05, -0.12], p + [sgn * 0.09, 0.02, -0.28], p + [sgn * 0.10, 0.14, -0.38]]
        paths.append(("chin", sgn, np.array(cps), 0.010))
    return paths


def build_whiskers():
    mb = parts.MeshBuilder()
    guides = []
    for kind, sgn, cps, r0 in whisker_paths():
        pts = parts.catmull_rom_path(cps, n=48)
        tt = np.linspace(0, 1, len(pts))
        r = r0 * (1 - 0.85 * tt ** 0.9) + 0.0015
        part = parts.loft(pts, r, r, radial=10, up_hint=UP, start="pole", end="point",
                          end_len=r[-1] * 3)
        mb.add(part, mat=0)
        guides.append((f"WHISKER_Guide_{kind}_{'L' if sgn > 0 else 'R'}", cps))
    ob = bu.object_from_builder("DRG_Whiskers", mb, "14_WHISKERS", ["MAT_Whisker"])
    for name, cps in guides:
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(cps) - 1)
        for bp, c in zip(sp.bezier_points, cps):
            bp.co = tuple(c)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        g = bpy.data.objects.new(name, cu)
        bu.coll("14_WHISKERS").objects.link(g)
        g.hide_render = True
    return ob


def main():
    with MilestoneRun("M05", "Teeth and whiskers", ["05_facial_details.py"]) as run:
        bu.open_blend(latest_blend("M04"))
        for pre in ("DRG_Teeth_", "DRG_Whiskers", "WHISKER_Guide_"):
            bu.remove_objects(pre)
        rng = np.random.default_rng(5)
        up, n_up, rej_up = build_teeth("upper", rng)
        lo, n_lo, rej_lo = build_teeth("lower", rng)
        wh = build_whiskers()
        run.metrics["teeth"] = f"upper {n_up} (+{rej_up} rejected for overlap), lower {n_lo} (+{rej_lo} rejected)"
        run.metrics["whiskers"] = len(whisker_paths())
        for ob in (up, lo, wh):
            run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
            run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
        O = bpy.data.objects
        run.add_checks([check("Tooth count", "PASS" if n_up >= 24 and n_lo >= 20 else "WARNING",
                              f"{n_up} upper / {n_lo} lower individual teeth")])
        run.add_checks([
            validate.overlap_check("Upper teeth clear of lower jaw/tongue", up,
                                   [O["DRG_Head_Jaw_Lower"], O["DRG_Head_Tongue"], lo]),
            validate.overlap_check("Lower teeth clear of skull/tongue", lo,
                                   [O["DRG_Head_Skull"], O["DRG_Head_Tongue"]]),
            validate.overlap_check("Whiskers clear of head parts (root excluded)", wh,
                                   [O[n] for n in ("DRG_Head_Skull", "DRG_Head_Jaw_Lower", "DRG_Head_FacialFins",
                                                   "DRG_Head_Spikes", "DRG_Head_Horns", "DRG_Teeth_Upper",
                                                   "DRG_Teeth_Lower", "DRG_Body")], a_mask="fsd_t", a_min=0.08),
        ])
        # sharpness: tip vertices must be true points
        bu.save_milestone(run, "facial_details")
        head_objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render and
                     (o.name.startswith(("DRG_Head", "DRG_Eye", "DRG_Teeth", "DRG_Whisk")))]
        out = config.DIRS["renders"] / "M05"
        out.mkdir(parents=True, exist_ok=True)
        f1 = review.render_focus([up, lo], out / "M05_teeth_front.png", (0.25, -1, 0.15), res=(1300, 1000), samples=40)
        f2 = review.render_focus(head_objs, out / "M05_head_left.png", (1, -0.1, 0.05), res=(1300, 1000), samples=40)
        reg = config.REGIONS_DIR
        extra = [[(reg / "ref_head_left_profile.png", "Reference – left profile"), (f2, "Model – left"),
                  (reg / "ref_detail_teeth.png", "Reference – teeth"), (f1, "Model – teeth close-up")]]
        review.standard_review(run, "M05", "Teeth & whiskers", head_objs,
                               focus_dirs=[(1.0, -1.3, 0.35), (-0.9, -1.0, -0.15)], head_crop=True, extra_rows=extra)


if __name__ == "__main__":
    main()
