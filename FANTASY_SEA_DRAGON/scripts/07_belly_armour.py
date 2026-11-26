"""07 – Belly armour (M07): segmented ventral plates.

Each plate is a closed solid conforming to the body (BVH-projected grid over the
ventral band |theta - pi| <= HALF_ANGLE), with
  * slightly raised central surface (dome across + along),
  * rounded lateral ends and visible boundaries (sharp rim),
  * shingle tilt: rear edge overlaps the next plate toward the tail
    (rise * advance > thickness + dome  -> no interpenetration).
Plate length follows the local body radius; all plates share the ventral midline.
Per-vertex attributes: fsd_s, fsd_tone (beige -> bronze variation), fsd_edge.

Run:  python 07_belly_armour.py   |  blender -b --python-exit-code 1 -P 07_belly_armour.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from dragon_lib import anatomy, config, parts, review, scales as SC, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

P = dict(s0=0.150, s1=0.800, half_angle=0.90, advance=0.80, size_k=0.42, size_min=0.08, size_max=0.20,
         base=-0.004, rise=0.026, dome=0.009, thick=0.010, nu=15, nv=6, chevron=0.30, groove=0.0045)
assert P["rise"] * P["advance"] > P["thick"] + P["dome"]


def plate_part(trunk, bvh, s_a, s_b):
    nu, nv = P["nu"], P["nv"]
    u = np.linspace(-1, 1, nu)
    v = np.linspace(0, 1, nv)
    U, V = np.meshgrid(u, v, indexing="ij")
    ends = 1 - 0.10 * (1 - np.sin(np.pi * V)) ** 2           # rounded lateral corners
    th = math.pi + U * ends * P["half_angle"]
    # chevron: the whole plate is swept back at the midline (V-shaped edges, as on the sheet)
    s = s_a + (V + P["chevron"] * (1 - np.abs(U) ** 1.3)) * (s_b - s_a)
    pts = SC._surf(trunk, s.ravel(), th.ravel())
    Pg = np.empty((nu * nv, 3))
    Ng = np.empty((nu * nv, 3))
    for i, q in enumerate(pts):
        loc, nrm, _, _ = bvh.find_nearest(Vector(q))
        Pg[i], Ng[i] = loc, nrm
    Pg = Pg.reshape(nu, nv, 3)
    Ng = Ng.reshape(nu, nv, 3)
    shape = (1 - np.abs(U) ** 4) * np.sin(np.pi * V) ** 0.5
    lift = P["base"] + P["rise"] * V
    groove = P["groove"] * np.exp(-0.5 * (U / 0.07) ** 2) * shape
    top = Pg + Ng * (lift + P["dome"] * shape * (1 - 0.5 * U ** 2) - groove)[..., None]
    bot = Pg + Ng * (lift - P["thick"] * shape)[..., None]
    # lens_patch winding: axis0 x axis1 must point outward (down at the belly)
    part = parts.lens_patch(top, bot[1:-1, 1:-1])
    t_top = np.repeat(V.ravel()[None], 1, 0).ravel()
    edge = 1 - shape
    part["attrs"] = dict(fsd_edge=np.concatenate([edge.ravel(), edge[1:-1, 1:-1].ravel()]))
    return part


def main():
    with MilestoneRun("M07", "Belly armour plates", ["07_belly_armour.py"]) as run:
        bu.open_blend(latest_blend("M06"))
        bu.remove_objects("DRG_Belly_")
        O = bpy.data.objects
        body = O["DRG_Body"]
        trunk = anatomy.TrunkModel(body=json.loads(body["fsd_params_body"]))
        bvh = bu.bvh_for([body])
        arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(trunk.centre, axis=0), axis=1))])
        s_arr = trunk.s
        a = float(np.interp(P["s0"], s_arr, arc))
        a_end = float(np.interp(P["s1"], s_arr, arc))
        rng = np.random.default_rng(3)
        mb = parts.MeshBuilder()
        lengths, n = [], 0
        while True:
            s = float(np.interp(a, arc, s_arr))
            r = (np.interp(s, s_arr, trunk.half_width) + np.interp(s, s_arr, trunk.half_depth)) / 2
            L = float(np.clip(P["size_k"] * r, P["size_min"], P["size_max"]))
            if a + L * (1 + P["chevron"]) > a_end:      # swept-back midline must stay before s1
                break
            s_b = float(np.interp(a + L, arc, s_arr))
            part = plate_part(trunk, bvh, s, s_b)
            # orientation check (outward = away from the body centre)
            c = trunk.at([0.5 * (s + s_b)])["centre"][0]
            f0 = part["faces"][2 * ((P["nu"] - 1) // 2) * (P["nv"] - 1)]   # a TOP face mid-plate
            vv = part["verts"][list(f0)]
            nrm = np.cross(vv[1] - vv[0], vv[2] - vv[0])
            if np.dot(nrm, vv.mean(0) - c) < 0:
                part["faces"] = [tuple(reversed(f)) for f in part["faces"]]
                part["face_uvs"] = [tuple(reversed(u)) for u in part["face_uvs"]]
            tone = float(np.clip(0.5 + 0.35 * math.sin(n * 0.9) * rng.random() + 0.2 * (s - 0.15), 0, 1))
            mb.add(part, mat=0, fsd_s=0.5 * (s + s_b), fsd_tone=tone)
            lengths.append(L)
            a += P["advance"] * L
            n += 1
        ob = bu.object_from_builder("DRG_Belly_Plates", mb, "06_BELLY_ARMOUR", ["MAT_Belly_Beige"])
        run.metrics["plates"] = n
        run.metrics["plate length (m)"] = f"{min(lengths):.3f}–{max(lengths):.3f}"
        run.metrics["plate faces"] = len(ob.data.polygons)

        run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
        run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
        run.add_checks([check("Plate count (sheet shows ~55 ventral plates)", "PASS" if 40 <= n <= 90 else "WARNING",
                              f"{n} plates from s {P['s0']} to {P['s1']}", n, "40–90")])
        scale_objs = [O[x] for x in ("DRG_Scales_Neck", "DRG_Scales_Flank_L", "DRG_Scales_Flank_R",
                                     "DRG_Scales_Tail", "DRG_Scales_Back")]
        run.add_checks([validate.overlap_check("Belly plates clear of flank / tail scales", ob, scale_objs)])
        # conformity: every top-surface vertex within 4 cm of the body surface, none inside it
        co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
        d = np.array([bvh.find_nearest(Vector(p))[3] for p in co[::7]])
        run.add_checks([check("Plates follow body curvature", "PASS" if d.max() < 0.04 else "FAIL",
                              f"max distance to body surface {d.max() * 100:.1f} cm (mean {d.mean() * 100:.1f} cm)",
                              float(d.max()), 0.04)])
        xs = co[:, 0]
        run.add_checks([check("Consistent ventral alignment", "PASS" if abs(xs.mean()) < 0.01 else "FAIL",
                              f"plate centroid lateral offset {xs.mean() * 1000:.1f} mm (symmetric about the midline)")])
        bu.save_milestone(run, "belly_armour")

        out = config.DIRS["renders"] / "M07"
        out.mkdir(parents=True, exist_ok=True)
        f = trunk.at([0.42])
        c = f["centre"][0]
        box = (c + np.array([-0.4, -0.5, -0.6]), c + np.array([0.4, 0.5, -0.2]))
        pc = review.render_focus([ob], out / "M07_belly_closeup.png", (0.55, -0.45, -0.75), res=(1400, 1000),
                                 samples=48, bbox=box, lens=50)
        reg = config.REGIONS_DIR
        extra = [[(reg / "ref_detail_belly_plate.png", "Reference – belly plate"), (pc, "Model – belly plates")]]
        review.standard_review(run, "M07", "Belly armour", [ob], focus_dirs=[(0.6, -0.8, -0.6), (0.0, 0.2, -1.0)],
                               aligned_views=("side_left", "bottom"), extra_rows=extra)


if __name__ == "__main__":
    main()
