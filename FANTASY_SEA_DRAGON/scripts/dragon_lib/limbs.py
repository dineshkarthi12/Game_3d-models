"""Limb skeleton (joint chains) – single source of truth for leg meshes (M10),
leg fins (M09), claws (M11) and the rig (M15).  numpy only.

World conventions: forward = -Y, out = +-X (left = +X), up = +Z.
"""
from __future__ import annotations

import math

import numpy as np

from . import config, geometry as G

LIMBS = {
    "Front_L": dict(kind="front", side=1, s=0.305),
    "Front_R": dict(kind="front", side=-1, s=0.305),
    "Rear_L": dict(kind="rear", side=1, s=0.535),
    "Rear_R": dict(kind="rear", side=-1, s=0.535),
}
# offsets in (out, forward, up) metres
KIND = {
    "front": dict(mid=(0.20, 0.06, -0.27), low=(0.04, 0.10, -0.19), palm=(0.02, 0.11, -0.06),
                  r=(0.17, 0.115, 0.075, 0.055), toe_len=(0.15, 0.19, 0.15, 0.09), scale=1.0),
    "rear": dict(mid=(0.22, 0.13, -0.26), low=(0.04, -0.15, -0.19), palm=(0.02, 0.13, -0.06),
                 r=(0.19, 0.125, 0.08, 0.058), toe_len=(0.16, 0.21, 0.16, 0.10), scale=1.08),
}
SURFACE_THETA = math.pi / 2 + 0.55
ROOT_DEPTH = 0.14


def _vec(side, o):
    out, fwd, up = o
    return np.array([side * out, -fwd, up], float)


def surface_point(trunk, s, side):
    th = side * SURFACE_THETA
    f = trunk.at([s])
    sec = trunk.section([s], [th])[0, 0]
    p = f["centre"][0] + f["B"][0] * sec[0] + f["U"][0] * sec[1]
    n = p - f["centre"][0]
    n -= f["T"][0] * np.dot(n, f["T"][0])
    return p, n / np.linalg.norm(n)


def joints(trunk, name):
    L = LIMBS[name]
    K = KIND[L["kind"]]
    side, sc = L["side"], K["scale"]
    S, n = surface_point(trunk, L["s"], side)
    root = S - n * ROOT_DEPTH
    mid = S + _vec(side, K["mid"]) * sc
    low = mid + _vec(side, K["low"]) * sc
    palm = low + _vec(side, K["palm"]) * sc
    # toes: three forward (spread), one rear dewclaw
    fwd = np.array([0, -1.0, 0])
    out = np.array([side, 0, 0.0])
    toes = []
    for i, (ang, down, ln) in enumerate(((-28, 22, K["toe_len"][0]), (0, 20, K["toe_len"][1]),
                                         (28, 22, K["toe_len"][2]), (170, 35, K["toe_len"][3]))):
        a = math.radians(ang * side)
        d = np.array([fwd[0] * math.cos(a) - fwd[1] * math.sin(a), fwd[0] * math.sin(a) + fwd[1] * math.cos(a), 0])
        d = d * math.cos(math.radians(down)) + np.array([0, 0, -math.sin(math.radians(down))])
        d /= np.linalg.norm(d)
        base = palm + d * (0.07 * sc) + np.array([0, 0, -0.01])
        toes.append(dict(base=base, dir=d, length=ln * sc))
    return dict(name=name, kind=L["kind"], side=side, s=L["s"], surface=S, normal=n, root=root,
                mid=mid, low=low, palm=palm, toes=toes, radii=K["r"], scale=sc)


def limb_path(J, n=28):
    """Smooth centre line root -> mid joint -> low joint -> palm, with radii."""
    from .parts import catmull_rom_path
    pts = catmull_rom_path(np.array([J["root"], J["surface"], J["mid"], J["low"], J["palm"]]), n=n)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    u = np.concatenate([[0], np.cumsum(seg)]) / seg.sum()
    r0, r1, r2, r3 = J["radii"]
    sc = J["scale"]
    # muscular profile: thick shoulder, bicep bulge, narrow wrist, slight paw flare
    key_u = [0.0, 0.18, 0.33, 0.50, 0.62, 0.80, 0.92, 1.0]
    key_r = [r0 * 1.15, r0, r0 * 0.92, r1 * 1.05, r1 * 0.95, r2, r2 * 0.95, r3]
    r = G.catmull_rom_1d(key_u, key_r, u) * sc
    return pts, r, u
