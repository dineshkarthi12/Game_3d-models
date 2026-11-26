"""08 – Dorsal spike generator (M08).

Individually modelled, sharp, swept-back blade spikes along the dorsal ridge.
Heights follow the crest envelope measured on the reference side view
(reference.crest_envelope): ~0.35–0.5 m at the neck, tallest (~0.74 m) over the
upper torso, tapering toward the tail fan.  A smaller spike sits between each
pair of main spikes, as on the sheet.

Categories (07_DORSAL_SPIKES): DRG_Spikes_Neck, _UpperTorso, _MidBody, _Tail
Materials per face: dark-navy structural base (fsd_t < 0.16) + orange blade.
No subdivision modifier – silhouettes and tips stay sharp (validated).
Dorsal scales intersecting a spike root are removed so roots sit in the skin.

Run:  python 08_spine_generator.py   |  blender -b --python-exit-code 1 -P 08_spine_generator.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import bmesh  # noqa: E402  (must follow bpy when running as a module)
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from dragon_lib import anatomy, config, geometry as G, parts, reference as ref, review, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

P = dict(s0=0.158, s1=0.765, sweep=22.0, curl=34.0, small_ratio=0.42, height_scale=0.95, taper=1.45,
         base_dark_t=0.16)
CATS = [("Neck", 0.0, 0.24), ("UpperTorso", 0.24, 0.42), ("MidBody", 0.42, 0.62), ("Tail", 0.62, 1.0)]


def vertical_reach_factor(sweep, curl):
    a0, a1 = math.radians(sweep), math.radians(sweep + curl)
    return 0.55 * (math.cos(a0) + math.cos(a1))


def spike_layout(trunk):
    s_env, h_env = ref.crest_envelope()
    L = config.TOTAL_LENGTH_M
    H = lambda s: float(np.interp(s, s_env, G.gaussian_smooth(h_env, 6))) * L * P["height_scale"]
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(trunk.centre, axis=0), axis=1))])
    a = float(np.interp(P["s0"], trunk.s, arc))
    a1 = float(np.interp(P["s1"], trunk.s, arc))
    out = []
    while a < a1:
        s = float(np.interp(a, arc, trunk.s))
        h = H(s)
        base_len = 2 * (0.18 * h / 0.8 + 0.02)
        spacing = float(np.clip(max(0.50 * h + 0.10, 1.25 * base_len), 0.15, 0.60))
        out.append(dict(s=s, reach=h, kind="main"))
        s_mid = float(np.interp(a + spacing / 2, arc, trunk.s))
        if a + spacing < a1:
            out.append(dict(s=s_mid, reach=H(s_mid) * P["small_ratio"], kind="small"))
        a += spacing
    return out


def tip_half_angle(part, radial=12):
    """Half-angle (deg) of the cone formed by the last section ring and the tip pole."""
    V = np.asarray(part["verts"])
    tip = V[-1]
    d = np.linalg.norm(V[:-1] - tip, axis=1)
    ring = V[np.argsort(d)[:radial]]
    c = ring.mean(0)
    r = np.linalg.norm(ring - c, axis=1).max()
    return math.degrees(math.atan2(r, np.linalg.norm(tip - c)))


def remove_islands_touching(ob, others):
    """Delete whole islands of *ob* (e.g. scales) that intersect any of *others*."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    hit = set()
    for o in others:
        bo = bmesh.new()
        bo.from_mesh(o.data)
        bo.transform(o.matrix_world)
        bo.transform(ob.matrix_world.inverted())
        to = BVHTree.FromBMesh(bo)
        bo.free()
        hit |= {i for i, _ in tree.overlap(to)}
    seen, kill = set(), set()
    for fi in hit:
        if fi in seen:
            continue
        stack = [bm.faces[fi]]
        while stack:
            f = stack.pop()
            if f.index in seen:
                continue
            seen.add(f.index)
            for v in f.verts:
                kill.add(v)
            for e in f.edges:
                stack.extend(x for x in e.link_faces if x.index not in seen)
    if kill:
        bmesh.ops.delete(bm, geom=list(kill), context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(hit)


def main():
    with MilestoneRun("M08", "Dorsal spikes", ["08_spine_generator.py"]) as run:
        bu.open_blend(latest_blend("M07"))
        bu.remove_objects("DRG_Spikes_")
        O = bpy.data.objects
        body = O["DRG_Body"]
        trunk = anatomy.TrunkModel(body=json.loads(body["fsd_params_body"]))
        bvh = bu.bvh_for([body])
        k = vertical_reach_factor(P["sweep"], P["curl"])
        layout = spike_layout(trunk)
        cands = []
        for sp in sorted(layout, key=lambda d: d["kind"] != "main"):      # main spikes have priority
            s = sp["s"]
            f = trunk.at([s])
            c, T, U = f["centre"][0], f["T"][0], f["U"][0]
            top = c + U * (f["half_depth"][0] * 1.2)
            loc, nrm, _, _ = bvh.find_nearest(Vector(top))
            base = np.array(loc)
            h = sp["reach"] / k
            bl = 0.18 * h + 0.02
            bw = 0.022 + 0.040 * h
            part = parts.curved_spike(base, U, T, h, base_long=bl, base_lat=bw, sweep_deg=P["sweep"],
                                      curl_deg=P["curl"], n=18 if sp["kind"] == "main" else 12, radial=12,
                                      sink=0.06, taper=P["taper"])
            t_attr = part["attrs"]["fsd_t"]
            part["mat"] = np.array([0 if t_attr[list(fc)].mean() < P["base_dark_t"] else 1 for fc in part["faces"]])
            part["_meta"] = dict(s=s, h=h, kind=sp["kind"], tip=part["tip"])
            cands.append(part)
        kept, rejected = parts.keep_non_intersecting(cands)
        objs, counts = [], {}
        tip_angles = []
        for name, a, b in CATS:
            mb = parts.MeshBuilder()
            for p in kept:
                m = p["_meta"]
                if a <= m["s"] < b:
                    mb.add(p, fsd_s=m["s"])
                    tip_angles.append(tip_half_angle(p))
            if mb.islands:
                ob = bu.object_from_builder(f"DRG_Spikes_{name}", mb, "07_DORSAL_SPIKES",
                                            ["MAT_Skin_DarkNavy", "MAT_Spike_Orange"])
                objs.append(ob)
                counts[name] = mb.islands
        run.metrics["spikes per category"] = counts
        run.metrics["rejected (would intersect a neighbour)"] = rejected
        hs = [p["_meta"]["h"] for p in kept]
        run.metrics["spike length range (m)"] = f"{min(hs):.2f}–{max(hs):.2f}"
        # remove dorsal scales pierced by spike roots
        removed = {}
        for nm in ("DRG_Scales_Neck", "DRG_Scales_Back", "DRG_Scales_Tail"):
            n0 = len(O[nm].data.polygons)
            remove_islands_touching(O[nm], objs)
            removed[nm] = (n0 - len(O[nm].data.polygons)) // 32
        run.metrics["dorsal scales removed under spike roots"] = removed

        for ob in objs:
            run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
            run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
            run.add_checks([check(f"{ob.name}: no smoothing modifier (sharp silhouette)",
                                  "PASS" if not any(m.type == "SUBSURF" for m in ob.modifiers) else "FAIL",
                                  "geometry rendered as modelled")])
        ta = np.array(tip_angles)
        run.add_checks([check("Spike tip sharpness", "PASS" if ta.max() < 15 else "WARNING" if ta.max() < 25 else "FAIL",
                              f"tip half-angle {ta.mean():.1f}° mean, {ta.max():.1f}° max (limit 15°)", float(ta.max()), 15)])
        scale_objs = [O[x] for x in ("DRG_Scales_Neck", "DRG_Scales_Back", "DRG_Scales_Tail",
                                     "DRG_Scales_Flank_L", "DRG_Scales_Flank_R")]
        for ob in objs:
            run.add_checks([validate.overlap_check(f"{ob.name} clear of scales", ob, scale_objs)])
        run.add_checks([check("Spike categories", "PASS" if len(counts) == 4 else "FAIL", str(counts))])
        # height progression vs reference envelope
        s_env, h_env = ref.crest_envelope()
        main = [p["_meta"] for p in kept if p["_meta"]["kind"] == "main"]
        tops = []
        for m in main:
            f = trunk.at([m["s"]])
            reach = float(np.dot(m["tip"] - f["centre"][0], f["U"][0]) - f["half_depth"][0])
            ref_h = float(np.interp(m["s"], s_env, h_env)) * config.TOTAL_LENGTH_M
            tops.append((reach, ref_h))
        tops = np.array(tops)
        mae = float(np.mean(np.abs(tops[:, 0] - tops[:, 1])))
        run.metrics["crest height MAE vs reference envelope (m)"] = round(mae, 3)
        run.add_checks([check("Crest height follows reference envelope", "PASS" if mae < 0.12 else "WARNING",
                              f"mean |model - reference| tip height {mae:.3f} m over {len(tops)} main spikes", mae, 0.12)])
        bu.save_milestone(run, "dorsal_spikes")

        out = config.DIRS["renders"] / "M08"
        out.mkdir(parents=True, exist_ok=True)
        f = trunk.at([0.36])
        c = f["centre"][0]
        box = (c + np.array([-0.4, -1.1, 0.1]), c + np.array([0.4, 1.1, 1.4]))
        pc = review.render_focus(objs, out / "M08_spikes_closeup.png", (1, -0.25, 0.25), res=(1400, 1000),
                                 samples=48, bbox=box, lens=50)
        reg = config.REGIONS_DIR
        extra = [[(reg / "ref_detail_spine_fin.png", "Reference – spine / fin"), (pc, "Model – dorsal spikes")]]
        review.standard_review(run, "M08", "Dorsal spikes (neck / upper torso / mid-body / tail)", objs,
                               focus_dirs=[(1.0, -0.6, 0.35), (-0.7, 1.0, 0.5)], extra_rows=extra)


if __name__ == "__main__":
    main()
