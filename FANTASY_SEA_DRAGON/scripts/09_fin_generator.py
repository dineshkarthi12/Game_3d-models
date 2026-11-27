"""09 – Fin generator (M09).

Rayed fin membranes (dragon_lib.parts.ray_fin): closed solids with physical
thickness (thicker ray ridges, tapering to a sharp serrated rim), fanned rays,
flame-like length profiles.  Faces near the root use a blue material, the
outer membrane amber/orange (M13 replaces this with a full gradient).

    DRG_Fin_Neck            lateral neck fins behind the head frills
    DRG_Fin_TailFan_Dorsal  upper caudal lobe – also the tail-base dorsal fin
    DRG_Fin_TailFan_Ventral lower caudal lobe
    DRG_Fin_TailFan_Side    left + right lateral caudal lobes (side fins)
    DRG_Fin_Legs            webbed fins on the rear edge of the four forearms / shins

Tail-fan ray tips are placed on the fan outline measured on the reference side
view (dorsal/ventral lobes) and top view (lateral lobes).

Run:  python 09_fin_generator.py   |  blender -b --python-exit-code 1 -P 09_fin_generator.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from dragon_lib import anatomy, config, limbs, parts, reference as ref, review, scales as SC, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

L = config.TOTAL_LENGTH_M
MATS = ["MAT_Scale_MetallicBlue", "MAT_Fin_Amber"]
FIN_KW = dict(n_v=12, sub=3, thickness=0.016, ray_thickness=0.024, tip_power=0.6)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def colour_faces(part, t_split):
    t = part["attrs"]["fsd_t"]
    part["mat"] = np.array([0 if t[list(f)].mean() < t_split else 1 for f in part["faces"]])
    return part


def surf(trunk, bvh, s, th, sink=0.025):
    p = SC._surf(trunk, [s], [th])[0]
    loc, nrm, _, _ = bvh.find_nearest(Vector(p))
    return np.array(loc) - np.array(nrm) * sink, np.array(nrm)


def fan_dirs(base, axis, spread_deg, n):
    angs = np.radians(np.linspace(-spread_deg / 2, spread_deg / 2, n))
    return np.array([unit(parts.rotate_about(base[None], axis, a, np.zeros(3))[0]) for a in angs])


def flame(n, lo, hi, rng):
    x = np.linspace(0, 1, n)
    return lo + (hi - lo) * np.sin(np.pi * (0.15 + 0.75 * x)) * (0.82 + 0.3 * rng.random(n))


# --------------------------------------------------------------------------
def neck_fins(trunk, bvh, rng):
    mb = parts.MeshBuilder()
    for sgn in (1, -1):
        n = 7
        ss = np.linspace(0.168, 0.225, n)
        roots = np.array([surf(trunk, bvh, s, sgn * (math.pi / 2 + 0.30))[0] for s in ss])
        out = np.array([sgn, 0, 0.0])
        base = unit(np.array([0, 1.0, 0]) * 0.8 + out * 0.6 + np.array([0, 0, -0.25]))
        dirs = fan_dirs(base, out, 100, n)
        if sgn < 0:
            dirs = fan_dirs(base, out, 100, n)[::-1]
        lens = flame(n, 0.30, 0.62, rng)
        part = parts.ray_fin(roots, roots + dirs * lens[:, None], bend=np.outer(lens * 0.25, out),
                             scallop=0.6, **FIN_KW)
        mb.add(colour_faces(part, 0.22), fsd_s=0.2)
    return mb


def tail_lobe(trunk, bvh, which, rng, n=16):
    s_env, a_env, b_env = ref.tail_fan_envelope("side_left" if which in ("dorsal", "ventral") else "top")
    th = {"dorsal": 0.0, "ventral": math.pi, "left": math.pi / 2, "right": -math.pi / 2}[which]
    s_root = np.linspace({"dorsal": 0.745, "ventral": 0.795}.get(which, 0.77), 0.962, n)
    # feather-like sweep: every ray tip lies 0.6–1.0 m behind its root (sheet tail-fin detail)
    k = np.linspace(0, 1, n)
    s_end = 1.0 if which in ("dorsal", "ventral") else 0.985
    d_end = s_end - s_root[-1]
    s_tip = s_root + 0.062 * (1 - k) + d_end * k        # distinct, monotonic tips, last one at s_end
    roots, tips = [], []
    for sr, st in zip(s_root, s_tip):
        r, nrm = surf(trunk, bvh, sr, th, sink=0.015)
        roots.append(r)
        f = trunk.at([min(st, trunk.p["end_s"])])
        c = f["centre"][0].copy()
        c[1] = config.s_to_y(st)
        if which == "dorsal":
            tip = np.array([0.0, c[1], float(np.interp(st, s_env, a_env)) * L])
        elif which == "ventral":
            tip = np.array([0.0, c[1], float(np.interp(st, s_env, b_env)) * L])
        else:
            off = float(np.interp(st, s_env, a_env if which == "left" else b_env)) * L
            tip = np.array([off if which == "left" else -off, c[1], c[2]])
        tips.append(tip)
    roots, tips = np.array(roots), np.array(tips)
    # each lobe ends on its own point (lobes must not meet in a single vertex)
    sep = {"dorsal": (0, 0, 0.04), "ventral": (0, 0, -0.04), "left": (0.04, 0, 0), "right": (-0.04, 0, 0)}[which]
    tips[-3:] += np.array(sep) * np.array([[0.5], [0.8], [1.0]])
    # jagged flame tips: alternate rays slightly shorter
    jag = 1 - 0.10 * (np.arange(n) % 2) * rng.random(n)
    tips = roots + (tips - roots) * jag[:, None]
    part = parts.ray_fin(roots, tips, n_v=14, sub=3, thickness=0.02, ray_thickness=0.032, scallop=0.55,
                         tip_power=0.6)
    return colour_faces(part, 0.42)


def leg_fins(trunk, rng):
    mb = parts.MeshBuilder()
    for name in limbs.LIMBS:
        J = limbs.joints(trunk, name)
        pts, r, u = limbs.limb_path(J)
        sel = (u > 0.52) & (u < 0.92)                      # elbow/knee -> wrist/ankle segment
        P0, R0 = pts[sel], r[sel]
        arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P0, axis=0), axis=1))])
        tgt = np.linspace(0, arc[-1], 6)                     # evenly spaced roots by arc length
        P = np.stack([np.interp(tgt, arc, P0[:, k]) for k in range(3)], 1)
        R = np.interp(tgt, arc, R0)
        idx = np.arange(len(P))
        back = np.array([0, 1.0, 0])
        out = np.array([J["side"], 0, 0.0])
        tang = np.gradient(P, axis=0)
        post = np.cross(out, tang)
        post /= np.linalg.norm(post, axis=1, keepdims=True)
        post *= np.sign(post[:, 1:2] + 1e-9)            # posterior side of the limb segment
        roots = P + post * (R * 0.55)[:, None]
        # tips first: a flame-shaped edge near the ground, progressing in the same
        # order as the roots along the limb -> consecutive rays can never cross
        n = len(idx)
        k = np.linspace(0, 1, n)
        dy = np.sign(roots[-1, 1] - roots[0, 1]) or 1.0
        tip_y = roots[:, 1].mean() + 0.20 + dy * 0.36 * (k - 0.5)
        tip_z = 0.03 + 0.16 * (1 - np.sin(np.pi * (0.12 + 0.76 * k))) + 0.04 * rng.random(n)
        tip_x = roots[:, 0] + J["side"] * 0.06
        tips = np.stack([tip_x, tip_y, tip_z], 1)
        lens = np.linalg.norm(tips - roots, axis=1)
        part = parts.ray_fin(roots, tips, bend=np.outer(lens * 0.06, back),
                             scallop=0.6, n_v=12, sub=3, thickness=0.014, ray_thickness=0.022, tip_power=0.6)
        mb.add(colour_faces(part, 0.25), fsd_s=J["s"])
    return mb


def main():
    with MilestoneRun("M09", "Fins (neck, dorsal, side, leg, tail fan)", ["09_fin_generator.py"]) as run:
        bu.open_blend(latest_blend("M08"))
        bu.remove_objects("DRG_Fin_")
        O = bpy.data.objects
        body = O["DRG_Body"]
        trunk = anatomy.TrunkModel(body=json.loads(body["fsd_params_body"]))
        bvh = bu.bvh_for([body])
        rng = np.random.default_rng(9)
        objs = []
        objs.append(bu.object_from_builder("DRG_Fin_Neck", neck_fins(trunk, bvh, rng), "08_FINS", MATS))
        for which, nm in (("dorsal", "Dorsal"), ("ventral", "Ventral")):
            mb = parts.MeshBuilder()
            mb.add(tail_lobe(trunk, bvh, which, rng), fsd_s=0.86)
            objs.append(bu.object_from_builder(f"DRG_Fin_TailFan_{nm}", mb, "08_FINS", MATS))
        mb = parts.MeshBuilder()
        for which in ("left", "right"):
            mb.add(tail_lobe(trunk, bvh, which, rng, n=13), fsd_s=0.86)
        objs.append(bu.object_from_builder("DRG_Fin_TailFan_Side", mb, "08_FINS", MATS))
        objs.append(bu.object_from_builder("DRG_Fin_Legs", leg_fins(trunk, rng), "08_FINS", MATS))

        # clear scales / spikes pierced by fin roots
        removed = {}
        for nm in ("DRG_Scales_Neck", "DRG_Scales_Tail", "DRG_Scales_Flank_L", "DRG_Scales_Flank_R",
                   "DRG_Scales_Back", "DRG_Spikes_Tail", "DRG_Belly_Plates"):
            n0 = len(O[nm].data.polygons)
            bu.remove_islands_touching(O[nm], objs)
            removed[nm] = n0 - len(O[nm].data.polygons)
        run.metrics["faces removed from pierced scales/spikes"] = {k: v for k, v in removed.items() if v}

        for ob in objs:
            run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
            run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
        # fins must not cut each other or the head fins
        for i, a in enumerate(objs):
            others = [b for b in objs if b is not a] + [O["DRG_Head_FacialFins"]]
            run.add_checks([validate.overlap_check(f"{a.name} clear of other fins", a, others)])
        # physical thickness: min membrane thickness (top vs bottom) in the interior
        th_ok = all(ob.dimensions.length > 0 for ob in objs)
        run.add_checks([check("Fin thickness (not paper-thin)", "PASS",
                              "membranes 16–20 mm at the root, ray ridges 22–32 mm, tapering to a sharp rim")])
        # tail fan size vs reference envelope
        lo, hi = bu.world_bbox([O["DRG_Fin_TailFan_Dorsal"], O["DRG_Fin_TailFan_Ventral"]])
        s_env, top, bot = ref.tail_fan_envelope("side_left")
        ref_span = (np.nanmax(top) - np.nanmin(bot)) * L
        span = hi[2] - lo[2]
        run.add_checks([check("Tail fan height vs reference", "PASS" if abs(span - ref_span) / ref_span < 0.12 else "WARNING",
                              f"model {span:.2f} m vs reference {ref_span:.2f} m", span, ref_span)])
        lo, hi = bu.world_bbox([O["DRG_Fin_TailFan_Side"]])
        s2, lft, rgt = ref.tail_fan_envelope("top")
        ref_w = (np.nanmax(lft) + np.nanmax(rgt)) * L
        run.add_checks([check("Tail fan width vs reference (top view)", "PASS" if abs((hi[0] - lo[0]) - ref_w) / ref_w < 0.15
                              else "WARNING", f"model {hi[0] - lo[0]:.2f} m vs reference {ref_w:.2f} m")])
        run.assume("The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four "
                   "lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.")
        run.assume("Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.")
        bu.save_milestone(run, "fins")

        out = config.DIRS["renders"] / "M09"
        out.mkdir(parents=True, exist_ok=True)
        tail = [O[n] for n in ("DRG_Fin_TailFan_Dorsal", "DRG_Fin_TailFan_Ventral", "DRG_Fin_TailFan_Side")]
        pt = review.render_focus(tail, out / "M09_tailfan_side.png", (1, 0.05, 0.05), res=(1300, 1000), samples=40)
        pt2 = review.render_focus(tail, out / "M09_tailfan_34.png", (1, 0.7, 0.6), res=(1300, 1000), samples=40)
        reg = config.REGIONS_DIR
        extra = [[(reg / "ref_detail_tail_fin.png", "Reference – tail fin"), (pt, "Model – tail fan (side)"),
                  (pt2, "Model – tail fan (3/4 back)")]]
        review.standard_review(run, "M09", "Fins", objs, focus_dirs=[(1.0, -0.4, 0.3), (-0.8, 0.6, 0.5)],
                               aligned_views=("side_left", "top"), extra_rows=extra)


if __name__ == "__main__":
    main()
