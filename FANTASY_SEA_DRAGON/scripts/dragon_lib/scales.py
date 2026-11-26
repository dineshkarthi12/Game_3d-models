"""Procedural scale distribution (numpy + mathutils BVH for surface projection).

Each scale is a closed lens solid on a rounded 5x5 grid:
    * raised centre (dome) + central keel
    * sharp outer rim (top and bottom surfaces meet)
    * shingle tilt: front edge tucked slightly below the skin, rear edge lifted,
      so each row overlaps the next toward the tail without interpenetrating
Scales are laid out in staggered rows; size follows the local body radius.
"""
from __future__ import annotations

import math

import numpy as np

from . import geometry as G, head as H, parts

MAT_BLUE, MAT_TURQ, MAT_GOLD, MAT_NAVY = 0, 1, 2, 3
MATERIALS = ["MAT_Scale_MetallicBlue", "MAT_Scale_Turquoise", "MAT_Scale_Gold", "MAT_Scale_DarkNavy"]

GRID = parts.rounded_grid(5)
SHAPE = 1 - np.clip(np.hypot(GRID[..., 0], GRID[..., 1]), 0, 1) ** 2
KEEL = np.exp(-0.5 * (GRID[..., 0] / 0.28) ** 2) * SHAPE


ROW_ADVANCE = 0.62          # row spacing as a fraction of scale length
SHINGLE = dict(base=-0.03, rise=0.25, dome=0.055, keel=0.025, thick=0.035)
# Non-interpenetration of consecutive rows requires
#   rise * ROW_ADVANCE > thick + dome + keel   (rear bottom of row r above front top of row r+1)
assert SHINGLE["rise"] * ROW_ADVANCE > SHINGLE["thick"] + SHINGLE["dome"] + SHINGLE["keel"]


def scale_solid(P, N, length, v_grid, *, base=SHINGLE["base"], rise=SHINGLE["rise"], dome=SHINGLE["dome"],
                keel=SHINGLE["keel"], thick=SHINGLE["thick"]):
    """Lens solid from projected surface points P (5,5,3) and normals N.
    Heights are fractions of the scale length."""
    lift = (base + rise * v_grid) * length
    top = P + N * (lift + (dome * SHAPE + keel * KEEL) * length)[..., None]
    bot = P + N * (lift - thick * SHAPE * length)[..., None]
    return parts.lens_patch(top, bot[1:-1, 1:-1])


def _noise(s, th, seed):
    return (np.sin(37.0 * s + 2.1 * seed) * np.cos(5.3 * th + seed) +
            0.5 * np.sin(91.0 * s - 3.7 * th + 1.3 * seed))


# --------------------------------------------------------------------------
# Trunk
# --------------------------------------------------------------------------
def trunk_surface_point(trunk, s, th):
    f = trunk.at(np.atleast_1d(s))
    sec = trunk.section(np.atleast_1d(s), np.atleast_1d(th))[:, 0, :] if np.ndim(th) == 0 else None
    return f, sec


def _surf(trunk, s, th):
    """Model surface point(s) for paired arrays s, th (no neck shaping)."""
    s = np.atleast_1d(np.asarray(s, float))
    th = np.atleast_1d(np.asarray(th, float))
    f = trunk.at(s)
    out = np.empty((len(s), 3))
    for i in range(len(s)):
        sec = trunk.section([s[i]], [th[i]])[0, 0]
        out[i] = f["centre"][i] + f["B"][i] * sec[0] + f["U"][i] * sec[1]
    return out


def ring_positions(section_xy, th_lo, th_hi, n_per_len, phase, full=False, samples=1440):
    """Place scale centres at equal ARC LENGTH around a cross-section.

    section_xy(th_array) -> (M, 2) section points.  Returns (thetas, spacing)."""
    th = np.linspace(th_lo, th_hi, samples)
    pts = section_xy(th)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    total = cum[-1]
    n = max(4, int(round(total * n_per_len)))
    spacing = total / n
    targets = (np.arange(n) + 0.5 + 0.5 * phase) * spacing
    if not full:
        targets = targets[targets < total - 0.25 * spacing]
    else:
        targets = targets % total
    return np.interp(targets, cum, th), spacing


def trunk_layout(trunk, s0, s1, belly_half_angle, belly_end_s, size_k=0.28, size_min=0.045,
                 size_max=0.13, overlap=ROW_ADVANCE, quality_scale=1.0):
    """Return list of dict(s, th, length, width, row) scale centres."""
    s_arr = trunk.s
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(trunk.centre, axis=0), axis=1))])
    out = []
    a = float(np.interp(s0, s_arr, arc))
    a_end = float(np.interp(s1, s_arr, arc))
    row = 0
    while a < a_end:
        s = float(np.interp(a, arc, s_arr))
        hw = float(np.interp(s, s_arr, trunk.half_width))
        hd = float(np.interp(s, s_arr, trunk.half_depth))
        length = float(np.clip(size_k * (hw + hd) / 2, size_min, size_max)) * quality_scale
        full = s > belly_end_s
        th_max = math.pi if full else math.pi - belly_half_angle
        sec = lambda th: trunk.section([s], th)[0]
        ths, spacing = ring_positions(sec, -th_max, th_max, 1.0 / (0.80 * length), row % 2, full=full)
        for th in ths:
            th = (th + math.pi) % (2 * math.pi) - math.pi
            out.append(dict(s=s, th=float(th), length=length, width=0.95 * spacing, row=row,
                            dth=float(2 * th_max / max(len(ths), 1)), th_max=th_max))
        a += overlap * length
        row += 1
    return out


def trunk_colour(sc, rng):
    s, th, dth = sc["s"], abs(sc["th"]), sc["dth"]
    stripe = 1.30
    if 0.16 <= s <= 0.80 and abs(th - stripe) < 0.5 * dth:
        return MAT_GOLD
    if th < 0.5 * dth and 0.14 <= s <= 0.82:
        return MAT_GOLD                                   # dorsal midline chevrons
    if s < 0.22 and th < 1.0:
        return MAT_GOLD if rng.random() < 0.55 else MAT_TURQ
    if th > sc["th_max"] - 0.45 and sc["th_max"] < math.pi:
        return MAT_NAVY
    if s > 0.80:
        return MAT_NAVY if rng.random() < 0.4 else MAT_BLUE
    nz = _noise(s, th, 1.7) + 0.6 * rng.standard_normal()
    return MAT_TURQ if nz > 0.25 else MAT_BLUE


def build_trunk_scales(trunk, bvh, layout, rng):
    """Returns list of (layout entry, part, material)."""
    out = []
    eps_s = 1e-4
    for sc in layout:
        s, th, L, W = sc["s"], sc["th"], sc["length"], sc["width"]
        p0 = _surf(trunk, [s], [th])[0]
        e_al = _surf(trunk, [s + eps_s], [th])[0] - _surf(trunk, [s - eps_s], [th])[0]
        e_lt = _surf(trunk, [s], [th + 1e-3])[0] - _surf(trunk, [s], [th - 1e-3])[0]
        e_al /= np.linalg.norm(e_al)
        e_lt -= e_al * np.dot(e_lt, e_al)
        e_lt /= np.linalg.norm(e_lt)
        P = np.empty((5, 5, 3))
        N = np.empty((5, 5, 3))
        for i in range(5):
            for j in range(5):
                q = p0 + e_lt * (GRID[i, j, 0] * W / 2) + e_al * (GRID[i, j, 1] * L / 2)
                loc, nrm, _, _ = bvh.find_nearest(q)
                P[i, j] = loc
                N[i, j] = nrm
        v = (GRID[..., 1] + 1) / 2
        out.append((sc, scale_solid(P, N, L, v), trunk_colour(sc, rng)))
    return out


# --------------------------------------------------------------------------
# Head (analytic surface – exact)
# --------------------------------------------------------------------------
def head_layout(t0=0.10, t1=0.97, size=0.05, th_limit=1.45):
    out = []
    t = t0
    row = 0
    while t < t1:
        p = H.skull_local(np.array([t]), np.array([0.0]))[0]
        q = H.skull_local(np.array([t + 1e-3]), np.array([0.0]))[0]
        dt_len = np.linalg.norm(q - p) / 1e-3
        L = size * (0.8 + 0.4 * t)
        sec = lambda th: H.skull_local(np.full_like(th, t), th)[:, [0, 2]]
        ths, spacing = ring_positions(sec, -th_limit, th_limit, 1.0 / (0.80 * L), row % 2)
        for th in ths:
            out.append(dict(t=t, th=float(th), length=L, width=0.95 * spacing, row=row,
                            dth=float(2 * th_limit / max(len(ths), 1))))
        t += ROW_ADVANCE * L / dt_len
        row += 1
    return out


def head_scale_part(sc):
    t, th, L, W = sc["t"], sc["th"], sc["length"], sc["width"]
    fn = H.skull_local
    p = fn(np.array(t), np.array(th))
    dt = (fn(np.array(t + 1e-4), np.array(th)) - fn(np.array(t - 1e-4), np.array(th))) / 2e-4
    dh = (fn(np.array(t), np.array(th + 1e-4)) - fn(np.array(t), np.array(th - 1e-4))) / 2e-4
    tt = t + GRID[..., 1] * (L / 2) / np.linalg.norm(dt)
    hh = th + GRID[..., 0] * (W / 2) / np.linalg.norm(dh)
    P = fn(tt, hh)
    N = H.surface_normal(fn, tt, hh)
    v = (GRID[..., 1] + 1) / 2
    part = scale_solid(P, N, L, v)
    part["verts"] = H.to_world_skull(part["verts"])
    # lens_patch orientation: lateral axis = theta; check outward on the left side
    return part


def head_colour(sc, rng):
    th = abs(sc["th"])
    if th < 0.5 * sc["dth"]:
        return MAT_GOLD
    r = rng.random()
    if sc["t"] > 0.55 and th < 0.9:
        return MAT_GOLD if r < 0.5 else MAT_TURQ
    return MAT_TURQ if r < 0.45 else MAT_BLUE
