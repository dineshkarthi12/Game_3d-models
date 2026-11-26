"""06 – Individual scale generator (M06).

Real geometry for every scale (closed shingled lens: raised centre + keel,
sharp rim, rear edge lifted over the next row), laid out in staggered rows on
the actual body surface (BVH projection) and on the analytic skull surface.

Region objects (05_SCALES):
    DRG_Scales_Neck, DRG_Scales_Back, DRG_Scales_Flank_L, DRG_Scales_Flank_R,
    DRG_Scales_Tail, DRG_Scales_Head
Limb-surface scales are generated together with the limbs in M10 (same builder).
Materials: metallic blue / turquoise / gold / dark navy (slot = colour region).
The ventral band (|theta - pi| < 0.95 rad, s < 0.80) is left for the belly armour (M07).

Run:  python 06_scale_generator.py   |  blender -b --python-exit-code 1 -P 06_scale_generator.py
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

PARAMS = dict(s0=0.145, s1=0.965, belly_half_angle=0.95, belly_end_s=0.80,
              quality_size={"preview": 1.35, "standard": 1.0, "high": 0.8})


def inside(tree, p, d=Vector((0.0, 0.0, 1.0))):
    cnt, o = 0, Vector(p)
    for _ in range(32):
        loc, _, _, _ = tree.ray_cast(o, d)
        if loc is None:
            break
        cnt += 1
        o = loc + d * 1e-4
    return cnt % 2 == 1


def region_of(sc):
    if sc["s"] < 0.24:
        return "Neck"
    if sc["s"] > 0.74:
        return "Tail"
    if abs(sc["th"]) < 0.70:
        return "Back"
    return "Flank_L" if sc["th"] > 0 else "Flank_R"


def main():
    q = config.quality()
    with MilestoneRun("M06", "Individual scale generation", ["06_scale_generator.py"]) as run:
        bu.open_blend(latest_blend("M05"))
        bu.remove_objects("DRG_Scales_")
        O = bpy.data.objects
        body = O["DRG_Body"]
        trunk = anatomy.TrunkModel(body=json.loads(body["fsd_params_body"]))
        bvh = bu.bvh_for([body])
        rng = np.random.default_rng(21)
        k = PARAMS["quality_size"][q["name"]]
        layout = SC.trunk_layout(trunk, PARAMS["s0"], PARAMS["s1"], PARAMS["belly_half_angle"],
                                 PARAMS["belly_end_s"], quality_scale=k)
        built = SC.build_trunk_scales(trunk, bvh, layout, rng)
        # clearance: drop scales whose centre is inside the skull / jaw / throat
        head_trees = [bu.bvh_for([O[n]]) for n in ("DRG_Head_Skull", "DRG_Head_Jaw_Lower", "DRG_Head_MouthInterior")]
        groups = {r: parts.MeshBuilder() for r in ("Neck", "Back", "Flank_L", "Flank_R", "Tail")}
        dropped = 0
        counts = {}
        for sc, part, mat in built:
            c = part["verts"][12]
            if sc["s"] < 0.20 and any(inside(t, c) for t in head_trees):
                dropped += 1
                continue
            r = region_of(sc)
            groups[r].add(part, mat=mat, fsd_s=sc["s"], fsd_theta=sc["th"])
            counts[r] = counts.get(r, 0) + 1
        objs = []
        for r, mb in groups.items():
            if mb.islands:
                objs.append(bu.object_from_builder(f"DRG_Scales_{r}", mb, "05_SCALES", SC.MATERIALS))
        # ---- head scales (exact analytic surface), avoiding eyes / armour / horns / spike bases
        block = bu.bvh_for([O[n] for n in ("DRG_Eye_L", "DRG_Eye_R", "DRG_Head_CheekArmour", "DRG_Head_Horns",
                                           "DRG_Head_Spikes", "DRG_Head_FacialFins")])
        mbh = parts.MeshBuilder()
        nh, skipped_h = 0, 0
        cands = []
        for sc in SC.head_layout(size=0.05 * k):
            part = SC.head_scale_part(sc)
            pts = part["verts"][:25]
            if min(block.find_nearest(Vector(p))[3] for p in pts[::3]) < 0.02:
                skipped_h += 1
                continue
            part["_sc"] = sc
            cands.append(part)
        # high-curvature areas (brows, sockets): keep only non-intersecting scales
        kept, rej = parts.keep_non_intersecting(cands)
        run.metrics["head scales rejected (curvature overlap)"] = rej
        for part in kept:
            sc = part["_sc"]
            mbh.add(part, mat=SC.head_colour(sc, rng), fsd_s=-1.0, fsd_theta=sc["th"])
            nh += 1
        objs.append(bu.object_from_builder("DRG_Scales_Head", mbh, "05_SCALES", SC.MATERIALS))
        counts["Head"] = nh

        total = sum(counts.values())
        run.metrics["scales per region"] = counts
        run.metrics["total scales"] = total
        run.metrics["scale faces"] = sum(len(o.data.polygons) for o in objs)
        run.metrics["dropped (inside head)"] = dropped
        run.metrics["head scales skipped near eyes/armour/spikes"] = skipped_h
        lengths = np.array([s["length"] for s in layout])
        run.metrics["trunk scale length (m)"] = f"{lengths.min():.3f}–{lengths.max():.3f}"

        # ---- validation
        for ob in objs:
            run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
            run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
        names = [o.name for o in objs]
        for i, a in enumerate(objs[:-1]):
            others = [b for b in objs[:-1] if b is not a]
            run.add_checks([validate.overlap_check(f"{a.name} clear of neighbouring regions", a, others)])
        # coverage of the dorsal + lateral trunk surface
        area = sum(f.area for o in objs[:-1] for f in o.data.polygons) / 2     # top+bottom ~ 2x
        s_arr = trunk.s
        mask = (s_arr >= PARAMS["s0"]) & (s_arr <= PARAMS["s1"])
        hw, hd = trunk.half_width[mask], trunk.half_depth[mask]
        perim = math.pi * (3 * (hw + hd) - np.sqrt((3 * hw + hd) * (hw + 3 * hd)))
        frac = np.where(s_arr[mask] > PARAMS["belly_end_s"], 1.0, (math.pi - PARAMS["belly_half_angle"]) / math.pi)
        ds = np.gradient(s_arr[mask]) * config.TOTAL_LENGTH_M
        target = float(np.sum(perim * frac * ds))
        cov = area / target
        run.metrics["scale area / scaled-skin area"] = round(cov, 3)
        run.add_checks([check("Scale coverage (incl. overlap)", "PASS" if 0.9 <= cov <= 1.8 else "WARNING",
                              f"scale top area {area:.2f} m² over {target:.2f} m² of non-ventral skin ({cov:.2f}x)", cov, 0.9)])
        cols = {SC.MATERIALS[i]: 0 for i in range(4)}
        for ob in objs:
            idx = np.zeros(len(ob.data.polygons), dtype=np.int32)
            ob.data.polygons.foreach_get("material_index", idx)
            for i, n in enumerate(SC.MATERIALS):
                cols[n] += int((idx == i).sum())
        run.metrics["faces per colour material"] = cols
        run.add_checks([check("Colour variation (4 scale materials used)", "PASS" if all(cols.values()) else "FAIL",
                              ", ".join(f"{k.split('_')[-1]} {v}" for k, v in cols.items()))])
        run.note("Scales are embedded ~0.035 x length at their front edge (attached to the skin), "
                 "so contact with DRG_Body / DRG_Head_Skull is intentional and not counted as an intersection.")
        bu.save_milestone(run, "scales")

        # ---- review
        out = config.DIRS["renders"] / "M06"
        out.mkdir(parents=True, exist_ok=True)
        f = trunk.at([0.40])
        c = f["centre"][0]
        box = (c + np.array([0.0, -0.45, -0.25]), c + np.array([0.55, 0.45, 0.45]))
        pc = review.render_focus(objs, out / "M06_scales_closeup.png", (1, -0.35, 0.35), res=(1400, 1000),
                                 samples=48, bbox=box, lens=50)
        reg = config.REGIONS_DIR
        extra = [[(reg / "ref_detail_scales.png", "Reference – scale detail"), (pc, "Model – mid-body scales (real geometry)")]]
        review.standard_review(run, "M06", "Individual scales (blue / turquoise / gold / navy)", objs,
                               focus_dirs=[(1.0, -0.9, 0.5), (0.2, -0.4, 1.0)], extra_rows=extra)


if __name__ == "__main__":
    main()
