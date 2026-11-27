"""10 – Limb generator (M10): four connected muscular legs.

Built on the shared skeleton (dragon_lib.limbs) that the leg fins (M09), claws
(M11) and rig (M15) also use:

    DRG_Legs          4 continuous limb tubes: root buried in the body ->
                      shoulder/hip -> elbow/knee -> wrist/ankle (muscular
                      radius profile: thick girdle, bicep bulge, narrow wrist)
    DRG_Feet          4 flattened palms rooted inside the wrists
    DRG_Toes          16 toes (3 forward + 1 dewclaw per foot), 2-segment curve
    DRG_Scales_Limbs  limb-surface scales (same shingled lens builder as M06)

Run:  python 10_limb_generator.py   |  blender -b --python-exit-code 1 -P 10_limb_generator.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from dragon_lib import anatomy, config, limbs, parts, review, scales as SC, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

FWD = np.array([0, -1.0, 0])
UP = np.array([0, 0, 1.0])


def limb_part(J):
    pts, r, u = limbs.limb_path(J, n=36)
    part = parts.loft(pts, r, r * 0.88, radial=22, up_hint=FWD, start="pole", end="pole")
    return part, pts, r, u


def foot_part(J):
    sc = J["scale"]
    low, palm = J["low"], J["palm"]
    d = palm - low
    d[2] = 0
    d = d / np.linalg.norm(d) if np.linalg.norm(d) > 1e-6 else FWD
    pts = np.array([low + UP * 0.02, 0.5 * (low + palm), palm, palm + d * 0.07 * sc, palm + d * 0.11 * sc])
    rx = np.array([0.060, 0.070, 0.085, 0.080, 0.060]) * sc
    ry = np.array([0.055, 0.045, 0.038, 0.032, 0.026]) * sc
    return parts.loft(pts, rx, ry, radial=20, up_hint=UP, start="pole", end="pole")


def toe_parts(J):
    out = []
    for i, T in enumerate(J["toes"]):
        b, d, ln = T["base"], T["dir"], T["length"]
        start = b
        pts = parts.catmull_rom_path(np.array([start, b + d * ln * 0.45 + UP * 0.005,
                                               b + d * ln * 0.85 - UP * 0.025, b + d * ln - UP * 0.045]), n=14)
        tt = np.linspace(0, 1, len(pts))
        r0 = (0.024 if i < 3 else 0.020) * J["scale"]
        r = r0 * (1 - 0.35 * tt) * (1 + 0.12 * np.exp(-0.5 * ((tt - 0.5) / 0.08) ** 2))   # knuckle
        p = parts.loft(pts, r, r * 0.85, radial=12, up_hint=UP, start="pole", end="pole")
        p["tip"] = pts[-1]
        p["tip_dir"] = (pts[-1] - pts[-3]) / np.linalg.norm(pts[-1] - pts[-3])
        out.append(p)
    return out


def limb_scales(J, pts, r, rng, fin_band=0.55):
    """Scales on the limb tube surface (analytic loft surface)."""
    rx, ry = r, r * 0.88
    T, U, B = parts.frames_with_hint(pts, FWD)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    arc = np.concatenate([[0], np.cumsum(seg)])
    u_idx = np.arange(len(pts))

    def S(a, phi):
        i = np.interp(a, arc, u_idx)
        k = int(np.clip(np.floor(i), 0, len(pts) - 2))
        f = i - k
        lerp = lambda X: X[k] * (1 - f) + X[k + 1] * f
        Pc, Tc, Uc, Bc = lerp(pts), lerp(T), lerp(U), lerp(B)
        return Pc + Bc * lerp(rx) * math.sin(phi) + Uc * lerp(ry) * math.cos(phi)

    out = []
    a = arc[-1] * 0.24
    row = 0
    while a < arc[-1] * 0.88:
        i = np.interp(a, arc, u_idx)
        rr = float(np.interp(i, u_idx, rx))
        L = float(np.clip(0.30 * rr, 0.028, 0.05))
        sec = lambda ph: np.stack([np.interp(i, u_idx, rx) * np.sin(ph), np.interp(i, u_idx, ry) * np.cos(ph)], -1)
        phis, spacing = SC.ring_positions(sec, -math.pi, math.pi, 1.0 / (0.8 * L), row % 2, full=True)
        for ph in phis:
            # posterior strip (fin roots) stays free; U points forward so posterior = phi ~ pi
            if abs(((ph + math.pi) % (2 * math.pi)) - 0) < fin_band or abs(ph - math.pi) < fin_band \
                    or abs(ph + math.pi) < fin_band:
                if a > arc[-1] * 0.45:
                    continue
            W = 0.95 * spacing
            p0 = S(a, ph)
            e_al = S(a + 1e-3, ph) - S(a - 1e-3, ph)
            e_al /= np.linalg.norm(e_al)
            e_lt = S(a, ph + 1e-3) - S(a, ph - 1e-3)
            e_lt -= e_al * np.dot(e_lt, e_al)
            e_lt /= np.linalg.norm(e_lt)
            P = np.empty((5, 5, 3))
            for gi in range(5):
                for gj in range(5):
                    da = SC.GRID[gi, gj, 1] * L / 2
                    dph = SC.GRID[gi, gj, 0] * W / 2 / max(np.linalg.norm(S(a, ph + 1e-3) - S(a, ph - 1e-3)) / 2e-3, 1e-6)
                    P[gi, gj] = S(a + da, ph + dph)
            c = pts[int(round(i))]
            N = P - c
            N -= np.einsum("ijk,k->ij", N, e_al)[..., None] * e_al
            N /= np.linalg.norm(N, axis=2, keepdims=True)
            v = (SC.GRID[..., 1] + 1) / 2
            part = SC.scale_solid(P, N, L, v)
            # winding: lateral axis must cross the along axis outward
            tv = part["verts"][12]
            f0 = part["faces"][0]
            vv = part["verts"][list(f0)]
            if np.dot(np.cross(vv[1] - vv[0], vv[2] - vv[0]), vv.mean(0) - c) < 0:
                part["faces"] = [tuple(reversed(x)) for x in part["faces"]]
                part["face_uvs"] = [tuple(reversed(x)) for x in part["face_uvs"]]
            mat = SC.MAT_NAVY if abs(ph) > 2.3 else (SC.MAT_TURQ if rng.random() < 0.45 else SC.MAT_BLUE)
            out.append((part, mat))
        a += SC.ROW_ADVANCE * L
        row += 1
    return out


def inside(tree, p, d=Vector((0.0, 0.0, 1.0))):
    cnt, o = 0, Vector(p)
    for _ in range(32):
        loc, _, _, _ = tree.ray_cast(o, d)
        if loc is None:
            break
        cnt += 1
        o = loc + d * 1e-4
    return cnt % 2 == 1


def main():
    with MilestoneRun("M10", "Four limbs (legs, feet, toes, limb scales)", ["10_limb_generator.py"]) as run:
        bu.open_blend(latest_blend("M09"))
        for pre in ("DRG_Legs", "DRG_Feet", "DRG_Toes", "DRG_Scales_Limbs"):
            bu.remove_objects(pre)
        O = bpy.data.objects
        body = O["DRG_Body"]
        trunk = anatomy.TrunkModel(body=json.loads(body["fsd_params_body"]))
        rng = np.random.default_rng(13)
        mb_leg, mb_foot, mb_toe, mb_sc = (parts.MeshBuilder() for _ in range(4))
        joints, toe_tips = {}, {}
        for name in limbs.LIMBS:
            J = limbs.joints(trunk, name)
            joints[name] = J
            lp, pts, r, u = limb_part(J)
            mb_leg.add(lp, mat=0, fsd_s=J["s"])
            mb_foot.add(foot_part(J), mat=0, fsd_s=J["s"])
            tips = []
            for tp in toe_parts(J):
                mb_toe.add(tp, mat=0, fsd_s=J["s"])
                tips.append((tp["tip"].tolist(), tp["tip_dir"].tolist()))
            toe_tips[name] = tips
            cands = []
            for part, mat in limb_scales(J, pts, r, rng):
                part["_mat"] = mat
                cands.append(part)
            kept, rej = parts.keep_non_intersecting(cands)
            limb_rej = run.metrics.get("limb scales rejected (curvature overlap)", 0) + rej
            run.metrics["limb scales rejected (curvature overlap)"] = limb_rej
            for part in kept:
                mb_sc.add(part, mat=part["_mat"], fsd_s=J["s"])
        legs = bu.object_from_builder("DRG_Legs", mb_leg, "09_LEGS", ["MAT_Skin_DarkNavy"])
        feet = bu.object_from_builder("DRG_Feet", mb_foot, "09_LEGS", ["MAT_Skin_DarkNavy"])
        toes = bu.object_from_builder("DRG_Toes", mb_toe, "09_LEGS", ["MAT_Skin_DarkNavy"])
        for ob in (legs, feet, toes):
            bu.add_subsurf(ob, 1, 2)
        lsc = bu.object_from_builder("DRG_Scales_Limbs", mb_sc, "05_SCALES", SC.MATERIALS)
        bpy.context.scene["fsd_toe_tips"] = json.dumps(toe_tips)
        n0 = len(lsc.data.polygons)
        bu.remove_islands_touching(lsc, [O[n] for n in ("DRG_Scales_Flank_L", "DRG_Scales_Flank_R", "DRG_Scales_Back",
                                                         "DRG_Belly_Plates", "DRG_Fin_Legs", "DRG_Feet")])
        run.metrics["limb scales"] = len(lsc.data.polygons) // 32
        run.metrics["limb scales removed (touching body scales/plates/fins)"] = (n0 - len(lsc.data.polygons)) // 32
        # body scales / plates pierced where the limbs enter the body
        pierced = {}
        for nm in ("DRG_Scales_Flank_L", "DRG_Scales_Flank_R", "DRG_Belly_Plates"):
            m0 = len(O[nm].data.polygons)
            bu.remove_islands_touching(O[nm], [legs])
            pierced[nm] = m0 - len(O[nm].data.polygons)
        run.metrics["body faces removed at limb roots"] = pierced

        objs = [legs, feet, toes, lsc]
        for ob in objs:
            run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
            run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
        # ---- connectivity
        tb = bu.bvh_for([body])
        tl = bu.bvh_for([legs])
        tf = bu.bvh_for([feet])
        conn = []
        for name, J in joints.items():
            conn.append((f"{name} root inside body", inside(tb, J["root"])))
            conn.append((f"{name} foot rooted inside wrist", inside(tl, J["low"] + UP * 0.02)))
            for i, T in enumerate(J["toes"]):
                conn.append((f"{name} toe {i} rooted in foot", inside(tf, T["base"] + T["dir"] * 0.004)))
        bad = [n for n, ok in conn if not ok]
        run.add_checks([check("Limb connectivity (root in body, foot in wrist, toes in foot)",
                              "PASS" if not bad else "FAIL", f"{len(conn) - len(bad)}/{len(conn)} joints connected"
                              + (f"; missing: {bad}" if bad else ""))])
        fins = O["DRG_Fin_Legs"]
        run.add_checks([check("Leg fins attached to limbs", "PASS" if validate.objects_overlap(fins, legs) > 0 else "FAIL",
                              "fin roots embedded in the forearm / shin surface")])
        run.add_checks([validate.overlap_check("Legs clear of belly plates and body scales", legs,
                                               [O[n] for n in ("DRG_Belly_Plates", "DRG_Scales_Flank_L",
                                                               "DRG_Scales_Flank_R")])])
        lo, hi = bu.world_bbox([legs, feet, toes])
        run.add_checks([check("Feet above ground", "PASS" if lo[2] >= 0 else "FAIL", f"lowest toe point z = {lo[2]:.3f} m")])
        run.metrics["limb joint heights (m)"] = {n: [round(float(J[k][2]), 2) for k in ("root", "mid", "low", "palm")]
                                                 for n, J in joints.items()}
        run.assume("Limb proportions follow the side view (short legs, feet ~0.4 m above ground, webbed fins below); "
                   "elbow/knee angles are a neutral swimming pose.")
        bu.save_milestone(run, "limbs")

        out = config.DIRS["renders"] / "M10"
        out.mkdir(parents=True, exist_ok=True)
        fl = [legs, feet, toes, lsc, fins]
        J = joints["Front_L"]
        box = (J["root"] - np.array([0.1, 0.5, 0.5]), J["root"] + np.array([0.7, 0.4, 0.3]))
        p1 = review.render_focus(fl, out / "M10_front_leg.png", (1, -0.6, 0.2), res=(1200, 1000), samples=48, bbox=box)
        J = joints["Rear_L"]
        box = (J["root"] - np.array([0.1, 0.5, 0.5]), J["root"] + np.array([0.7, 0.4, 0.3]))
        p2 = review.render_focus(fl, out / "M10_rear_leg.png", (1, 0.3, 0.1), res=(1200, 1000), samples=48, bbox=box)
        reg = config.REGIONS_DIR
        extra = [[(reg / "ref_detail_claw_foot.png", "Reference – claw / foot"), (p1, "Model – front leg"),
                  (p2, "Model – rear leg")]]
        review.standard_review(run, "M10", "Four limbs", fl, focus_dirs=[(1.0, -0.8, 0.1), (0.5, -0.3, -1.0)],
                               aligned_views=("side_left", "bottom"), extra_rows=extra)


if __name__ == "__main__":
    main()
