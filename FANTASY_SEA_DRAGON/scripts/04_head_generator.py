"""04 – Head generator (M04).

Builds the open-mouthed fantasy sea-dragon head from the parametric model in
dragon_lib/head.py (hinge-local frame, jaw opened as on the reference sheet):

    DRG_Head_Skull          cranium + upper jaw (brow ridges, eye sockets,
                            nostrils, cheekbones; palate = mouth material)
    DRG_Head_Jaw_Lower      separate lower jaw (mouth floor = mouth material)
    DRG_Head_MouthInterior  throat / back of the mouth between the jaws
    DRG_Head_Tongue
    DRG_Eye_L / DRG_Eye_R   glossy eyeballs + slit pupils  (12_EYES)
    DRG_Head_Horns          swept-back main horns
    DRG_Head_Spikes         crown crest, brow and jaw-corner spikes
    DRG_Head_CheekArmour    overlapping cheek plates
    DRG_Head_FacialFins     cheek frills + under-jaw fins

Run:  python 04_head_generator.py   |  blender -b --python-exit-code 1 -P 04_head_generator.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from dragon_lib import config, head, parts, review, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend  # noqa: E402

HC = config.HEAD
SKIN = "MAT_Skin_DarkNavy"
BACK = np.array([0.0, 1.0, 0.0])
UP = np.array([0.0, 0.0, 1.0])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# --------------------------------------------------------------------------
def build_skull_and_jaw():
    mb = parts.MeshBuilder()
    mb.add(head.skull_part())
    skull = bu.object_from_builder("DRG_Head_Skull", mb, "04_HEAD", [SKIN, "MAT_Mouth_Interior"],
                                   origin=head.hinge_world())
    mb = parts.MeshBuilder()
    mb.add(head.jaw_part())
    jaw = bu.object_from_builder("DRG_Head_Jaw_Lower", mb, "04_HEAD", [SKIN, "MAT_Mouth_Interior"],
                                 origin=head.hinge_world())
    for ob in (skull, jaw):
        bu.add_subsurf(ob, 1, 2)
    return skull, jaw


def mouth_line(d):
    """Palate and floor centre points (world) at distance d (local -y) from the hinge."""
    y = -np.asarray(d, float)
    def t_of(y, yr):
        return (y - yr[0]) / (yr[1] - yr[0])
    ts = t_of(y, HC["skull_y"])
    tj = t_of(y, HC["jaw_y"])
    top = head.to_world_skull(head.skull_local(ts, math.pi))
    bot = head.to_world_jaw(head.jaw_local(tj, 0.0))
    ws = head.skull_local(ts, math.pi / 2)[..., 0]
    wj = head.jaw_local(tj, math.pi / 2)[..., 0]
    return top, bot, np.minimum(ws, wj)


def build_mouth_interior():
    d = np.linspace(-0.08, 0.30, 14)
    top, bot, w = mouth_line(d)
    centre = (top + bot) / 2
    half_h = np.linalg.norm(top - bot, axis=1) / 2 * 1.08 + 0.01
    part = parts.loft(centre, w * 0.82, half_h, radial=24, up_hint=unit(top[-1] - bot[-1]),
                      start="pole", end="pole", cap_rings=3, end_len=0.10)
    mb = parts.MeshBuilder()
    mb.add(part, mat=0)
    ob = bu.object_from_builder("DRG_Head_MouthInterior", mb, "04_HEAD", ["MAT_Mouth_Interior"],
                                origin=head.hinge_world())
    bu.add_subsurf(ob, 1, 2)
    return ob


def build_tongue():
    d = np.linspace(0.18, 0.95, 16)
    _, bot, w = mouth_line(d)
    jaw_up = head.dir_world_jaw(UP)
    curl = (np.linspace(0, 1, len(d)) ** 3)[:, None] * 0.08
    pts = bot + jaw_up * (0.028 + curl)
    tt = np.linspace(0, 1, len(d))
    rx = 0.075 * (1 - 0.55 * tt ** 1.5)
    ry = 0.022 * (1 - 0.4 * tt)
    part = parts.loft(pts, rx, ry, radial=20, up_hint=jaw_up, start="pole", end="pole")
    mb = parts.MeshBuilder()
    mb.add(part)
    ob = bu.object_from_builder("DRG_Head_Tongue", mb, "04_HEAD", ["MAT_Tongue"], origin=head.hinge_world())
    bu.add_subsurf(ob, 1, 2)
    return ob


def sphere_part(c, n, r, radial=48, rings=26):
    phi = np.linspace(0.12, math.pi - 0.12, rings)
    pts = c[None, :] - n[None, :] * (r * np.cos(phi))[:, None]       # back pole -> front pole
    rad = r * np.sin(phi)
    cap = r * (1 - math.cos(0.12))
    return parts.loft(pts, rad, rad, radial=radial, up_hint=UP, start="point", end="point",
                      start_len=cap, end_len=cap)


def build_eyes():
    """Eyeball with a vertical slit pupil (material region – no overlapping shells)."""
    objs = []
    for side, e in head.eye_centres().items():
        c, n = e["centre"], unit(e["normal"])
        n = unit(n + np.array([0, -0.35, 0.10]))              # look forward-out like the sheet
        r = HC["eye"]["radius"]
        part = sphere_part(c, n, r)
        upv = unit(UP - n * np.dot(UP, n))
        side_v = np.cross(n, upv)
        V = part["verts"]
        mats = []
        for f in part["faces"]:
            d = (V[list(f)].mean(0) - c) / r
            fwd, lat, ver = d @ n, d @ side_v, d @ upv
            slit_w = 0.16 * np.sqrt(max(0.0, 1 - (ver / 0.62) ** 2))
            mats.append(1 if fwd > 0.55 and abs(lat) < slit_w else 0)
        part["mat"] = np.array(mats)
        mb = parts.MeshBuilder()
        mb.add(part)
        ob = bu.object_from_builder(f"DRG_Eye_{side}", mb, "12_EYES", ["MAT_Eye_Glossy", "MAT_Eye_Pupil"],
                                    origin=c)
        ob["fsd_eye_axis"] = list(map(float, n))
        objs.append(ob)
    return objs


def skull_pt(t, th):
    p = head.skull_local(np.array(t), np.array(th))
    n = head.surface_normal(head.skull_local, np.array(t), np.array(th))
    return head.to_world_skull(p), unit(head.dir_world_skull(n))


def jaw_pt(t, th):
    p = head.jaw_local(np.array(t), np.array(th))
    n = head.surface_normal(head.jaw_local, np.array(t), np.array(th))
    return head.to_world_jaw(p), unit(head.dir_world_jaw(n))


def build_horns():
    mb = parts.MeshBuilder()
    for sgn in (1, -1):
        p, n = skull_pt(0.86, sgn * 0.42)
        back = unit(BACK + np.array([sgn * 0.35, 0, 0.15]))
        part = parts.curved_spike(p, n, back, height=0.80, base_long=0.085, base_lat=0.075,
                                  sweep_deg=58, curl_deg=22, n=18, radial=14, sink=0.05, taper=1.1,
                                  profile="round")
        mb.add(part, mat=0)
    ob = bu.object_from_builder("DRG_Head_Horns", mb, "04_HEAD", ["MAT_Horn_Gold"])
    return ob


class SpikePlacer:
    """Adds spikes to a MeshBuilder, skipping any whose base or blade would hit another."""

    def __init__(self, mb, avoid=()):
        self.mb, self.bases, self.skipped, self.parts = mb, list(avoid), 0, []

    def add(self, p, n, back, h, sweep=45, curl=25, long_f=0.30, lat_f=0.045, lat0=0.03, **kw):
        bl, bw = long_f * h, lat0 + lat_f * h
        r = max(bl, bw)
        for q, rq in self.bases:
            if np.linalg.norm(p - q) < (r + rq) * 1.05:
                self.skipped += 1
                return False
        part = parts.curved_spike(p, n, back, h, base_long=bl, base_lat=bw, sweep_deg=sweep,
                                  curl_deg=curl, sink=0.03, **kw)
        if any(parts.parts_intersect(part, q) for q in self.parts):
            self.skipped += 1                      # blades would cross a neighbour
            return False
        self.bases.append((p, r))
        self.parts.append(part)
        self.mb.add(part, mat=0)
        return True


def build_head_spikes():
    mb = parts.MeshBuilder()
    horn_bases = [(skull_pt(0.86, s * 0.42)[0], 0.10) for s in (1, -1)]
    sp = SpikePlacer(mb, avoid=horn_bases)
    for t, h in [(0.40, 0.09), (0.50, 0.13), (0.60, 0.18), (0.70, 0.24), (0.80, 0.30), (0.90, 0.36), (0.99, 0.42)]:
        p, n = skull_pt(t, 0.0)
        sp.add(p, n, BACK, h, sweep=38, curl=30, long_f=0.32, lat_f=0.05, lat0=0.035)
    rng = np.random.default_rng(7)
    for sgn in (1, -1):
        for t, th, h in ((0.52, 0.86, 0.10), (0.60, 0.80, 0.13)):        # brow spikes
            p, n = skull_pt(t, sgn * th)
            sp.add(p, n, unit(BACK + np.array([sgn * 0.5, 0, 0.0])), h, sweep=55, curl=25)
        # radiating mane around the back of the skull (front-view crown on the sheet)
        for k, th in enumerate(np.linspace(0.70, 2.60, 11)):
            t = 0.90 + 0.08 * (k % 2) + 0.02 * rng.random()          # two staggered rows
            p, n = skull_pt(t, sgn * th)
            h = 0.36 + 0.20 * math.sin((th - 0.70) / 1.9 * math.pi) + 0.08 * rng.random()
            back = unit(BACK * 0.7 + n * 0.45)
            sp.add(p, n, back, h, sweep=42, curl=24, long_f=0.18, lat_f=0.035, lat0=0.022)
        for t, th, h in ((0.80, 1.9, 0.20), (0.92, 2.1, 0.24)):          # jaw-corner spikes
            p, n = jaw_pt(t, sgn * th)
            sp.add(p, n, unit(BACK + np.array([sgn * 0.4, 0, -0.2])), h, sweep=60, curl=20)
    ob = bu.object_from_builder("DRG_Head_Spikes", mb, "04_HEAD", ["MAT_Spike_Orange"])
    ob["fsd_spikes_skipped_overlap"] = sp.skipped
    return ob


def shingle_patch(fn, to_world, t0, t1, th0, th1, n=6, base=-0.006, rise=0.030, dome=0.012, thick=0.010):
    """Plate on a parametric surface, tilted so its rear edge (t1) overlaps the next plate."""
    g = parts.rounded_grid(n)
    v = (g[..., 1] + 1) / 2                     # 0 front .. 1 rear
    tt = t0 + v * (t1 - t0)
    th = th0 + (g[..., 0] + 1) / 2 * (th1 - th0)
    P = fn(tt, th)
    N = head.surface_normal(fn, tt, th)
    shape = 1 - np.clip(np.hypot(g[..., 0], g[..., 1]), 0, 1) ** 2
    lift = base + rise * v
    top = to_world(P + N * (lift + dome * shape)[..., None])
    bot = to_world(P + N * (lift - thick * shape)[..., None])
    return parts.lens_patch(top, bot[1:-1, 1:-1])


def build_cheek_armour():
    mb = parts.MeshBuilder()
    for sgn in (1, -1):
        for row, (th0, th1) in enumerate(((1.30, 1.62), (1.66, 1.98))):
            for i, t0 in enumerate(np.arange(0.66, 0.92, 0.065)):
                o = 0.03 if row else 0.0
                a0, a1 = sorted((sgn * th0, sgn * th1))
                mb.add(shingle_patch(head.skull_local, head.to_world_skull, t0 + o, t0 + o + 0.085, a0, a1), mat=0)
    return bu.object_from_builder("DRG_Head_CheekArmour", mb, "04_HEAD", ["MAT_Scale_Gold"])


def fin_from_root_curve(roots, dirs, lengths, bend_dir, bend_amt, **kw):
    tips = roots + dirs * lengths[:, None]
    bend = np.outer(lengths * bend_amt, bend_dir)
    return parts.ray_fin(roots, tips, bend=bend, **kw)


def fan(base_dir, axis, spread_deg, n):
    """n directions obtained by rotating base_dir about axis across +-spread/2."""
    angs = np.radians(np.linspace(-spread_deg / 2, spread_deg / 2, n))
    return np.array([unit(parts.rotate_about(base_dir[None, :], axis, a, np.zeros(3))[0]) for a in angs])


def flame_lengths(n, lo, hi, rng):
    """Flame-like length profile: longest in the middle, jagged variation."""
    x = np.linspace(0, 1, n)
    return lo + (hi - lo) * np.sin(np.pi * (0.15 + 0.75 * x)) * (0.8 + 0.35 * rng.random(n))


def build_facial_fins():
    mb = parts.MeshBuilder()
    rng = np.random.default_rng(11)
    for sgn in (1, -1):
        # cheek frill: rays fan from up-back to down-back, flaring outward
        n = 8
        ts = np.linspace(0.78, 0.99, n)
        ths = sgn * np.linspace(1.45, 2.30, n)
        roots = np.array([skull_pt(t, th)[0] - skull_pt(t, th)[1] * 0.02 for t, th in zip(ts, ths)])
        out = unit(np.array([sgn * 1.0, 0, 0]))
        base = unit(BACK * 0.85 + out * 0.6)
        dirs = fan(base, out, 120, n)[::-1] if sgn > 0 else fan(base, out, 120, n)
        lengths = flame_lengths(n, 0.30, 0.72, rng)
        mb.add(fin_from_root_curve(roots, dirs, lengths, out * 0.6 + BACK * 0.3, 0.30,
                                   n_v=12, sub=3, thickness=0.014, ray_thickness=0.022, scallop=0.62,
                                   tip_power=0.6), mat=0)
        # under-jaw fin: hangs from the rear mandible, rays fan forward-down to back-down
        n = 8
        ts = np.linspace(0.42, 0.92, n)
        roots = np.array([jaw_pt(t, sgn * 2.75)[0] - jaw_pt(t, sgn * 2.75)[1] * 0.02 for t in ts])
        base = unit(np.array([sgn * 0.15, 0.25, -1.0]))
        axis = np.array([1.0, 0, 0])
        dirs = fan(base, axis, 70, n)
        lengths = flame_lengths(n, 0.32, 0.80, rng)
        mb.add(fin_from_root_curve(roots, dirs, lengths, BACK, 0.30,
                                   n_v=12, sub=3, thickness=0.014, ray_thickness=0.022, scallop=0.62,
                                   tip_power=0.6), mat=0)
    return bu.object_from_builder("DRG_Head_FacialFins", mb, "04_HEAD", ["MAT_Fin_Amber"])


# --------------------------------------------------------------------------
def inside_fraction(points, objs, directions=((0.0, 0.0, 1.0), (0.3, 0.2, -1.0), (1.0, 0.1, 0.2))):
    """Fraction of points inside the union of closed meshes (majority vote of ray parity)."""
    from mathutils import Vector
    trees = [bu.bvh_for([o]) for o in objs]
    inside = 0
    for p in points:
        votes = 0
        for d in directions:
            dv = Vector(d).normalized()
            hit_any = False
            for tree in trees:
                cnt, origin = 0, Vector(p)
                for _ in range(64):
                    loc, nrm, idx, dist = tree.ray_cast(origin, dv)
                    if loc is None:
                        break
                    cnt += 1
                    origin = loc + dv * 1e-4
                if cnt % 2 == 1:
                    hit_any = True
                    break
            votes += hit_any
        inside += votes >= 2
    return inside / max(len(points), 1)


def main():
    with MilestoneRun("M04", "Head generation", ["04_head_generator.py"]) as run:
        bu.open_blend(latest_blend("M03"))
        for pre in ("DRG_Head_", "DRG_Eye_"):
            bu.remove_objects(pre)
        skull, jaw = build_skull_and_jaw()
        mouth = build_mouth_interior()
        tongue = build_tongue()
        eyes = build_eyes()
        horns = build_horns()
        spikes = build_head_spikes()
        armour = build_cheek_armour()
        fins = build_facial_fins()
        objs = [skull, jaw, mouth, tongue, *eyes, horns, spikes, armour, fins]
        bpy.context.scene["fsd_params_head"] = json.dumps(HC)

        # ---- validation
        for ob in objs:
            run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
            run.add_checks([validate.materials_check(ob), validate.uv_check(ob)])
        run.metrics["head objects"] = len(objs)
        run.metrics["head faces (base)"] = sum(len(o.data.polygons) for o in objs)
        run.metrics["spikes"] = f"{spikes['fsd_islands']} placed, {spikes['fsd_spikes_skipped_overlap']} skipped (base overlap)"
        # head/neck join: the neck's front cap must be buried inside the head
        body = bpy.data.objects["DRG_Body"]
        co = bu.get_verts(body.data)
        s = bu.get_point_attr(body.data, "fsd_s")
        s_cap = config.BODY["start_s"] + 0.012
        sel = co[s < s_cap]
        frac = inside_fraction(sel[:: max(1, len(sel) // 300)], [skull, jaw, mouth])
        run.add_checks([check("Neck front cap hidden inside head", "PASS" if frac >= 0.95 else
                              "WARNING" if frac >= 0.8 else "FAIL",
                              f"{frac * 100:.1f}% of trunk vertices with s < {s_cap:.3f} lie inside skull/jaw/throat", frac, 0.95)])
        # mouth open as on the sheet
        snout = skull.matrix_world @ skull.data.vertices[0].co
        gape = HC["gape_upper_deg"] + HC["gape_lower_deg"]
        run.add_checks([check("Mouth open (separate jaws)", "PASS" if gape >= 30 else "FAIL",
                              f"gape {gape:.0f}° (upper {HC['gape_upper_deg']}°, lower {HC['gape_lower_deg']}°)")])
        lo, hi = bu.world_bbox([skull, jaw])
        s_front = (lo[1] / config.TOTAL_LENGTH_M) + 0.5
        run.add_checks([check("Snout at reference nose landmark", "PASS" if abs(s_front) < 0.01 else "WARNING",
                              f"head front at s = {s_front:.4f} (sheet snout tip = 0)", s_front, 0.01)])
        run.assume("Head proportions come from the side profile and head-detail panels; the skull "
                   "width (~0.47 m) is taken from the top view without cheek fins.")
        bu.save_milestone(run, "head")

        extra = []
        out = config.DIRS["renders"] / "M04"
        head_objs = objs
        pf = review.render_focus(head_objs, out / "M04_head_left.png", (1, 0, 0.02), res=(1200, 900), samples=32)
        pfr = review.render_focus(head_objs, out / "M04_head_front.png", (0.0, -1, 0.05), res=(900, 900), samples=32)
        reg = config.REGIONS_DIR
        extra.append([(reg / "ref_head_left_profile.png", "Reference head – left profile"),
                      (pf, "Model head – left"), (reg / "ref_head_front.png", "Reference head – front"),
                      (pfr, "Model head – front")])
        review.standard_review(run, "M04", "Head (skull, open jaws, eyes, horns, spikes, facial fins)",
                               head_objs, focus_dirs=[(1.0, -1.1, 0.45), (-0.8, -1.2, 0.2)],
                               head_crop=True, extra_rows=extra)


if __name__ == "__main__":
    main()
