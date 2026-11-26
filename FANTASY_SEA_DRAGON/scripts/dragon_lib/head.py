"""Parametric dragon head (skull + lower jaw) – numpy only.

Surfaces are defined analytically in the hinge-local frame, so teeth, eyes,
whiskers, horns, scales and plates can be placed exactly on them:

    skull_local(t, theta) / jaw_local(t, theta) -> (..., 3) local points
    to_world_skull(p) / to_world_jaw(p)          -> world points (open mouth)
"""
from __future__ import annotations

import math

import numpy as np

from . import config, geometry as G

H = config.HEAD


def _prof(key, t):
    cp = H[key]
    return G.catmull_rom_1d([c[0] for c in cp], [c[1] for c in cp], np.clip(np.asarray(t, float), 0, 1))


def hinge_world():
    return np.array([0.0, config.s_to_y(H["hinge_s"]), H["hinge_z"]])


def _rot_x(p, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    p = np.asarray(p, float)
    out = p.copy()
    out[..., 1] = p[..., 1] * c - p[..., 2] * s
    out[..., 2] = p[..., 1] * s + p[..., 2] * c
    return out


def to_world_skull(p):
    return _rot_x(p, -H["gape_upper_deg"]) + hinge_world()


def to_world_jaw(p):
    return _rot_x(p, H["gape_lower_deg"]) + hinge_world()


def dir_world_skull(v):
    return _rot_x(v, -H["gape_upper_deg"])


def dir_world_jaw(v):
    return _rot_x(v, H["gape_lower_deg"])


def _feature(t, th, ft, fth, st, sth):
    return (np.exp(-0.5 * ((t - ft) / st) ** 2)
            * (np.exp(-0.5 * (G.wrap_angle(th - fth) / sth) ** 2)
               + np.exp(-0.5 * (G.wrap_angle(th + fth) / sth) ** 2)))


def skull_local(t, th):
    t = np.asarray(t, float)
    th = np.asarray(th, float)
    y0, y1 = H["skull_y"]
    y = y0 + (y1 - y0) * t
    a = _prof("skull_width", t)
    bu = _prof("skull_top", t)
    bd = _prof("skull_bottom", t)
    n_bot = 5.0 - 2.5 * G.smoothstep(0.78, 1.0, t)        # flat palate -> round occiput
    x, z = G.superellipse(th, a, bu, bd, 2.3, n_bot)
    r = np.hypot(x, z)
    nx, nz = x / np.maximum(r, 1e-9), z / np.maximum(r, 1e-9)
    off = 0.0
    e, n, b, c = H["eye"], H["nostril"], H["brow"], H["cheek"]
    off = off - (e["radius"] * 0.85) * _feature(t, th, e["t"], e["theta"], 0.035, 0.22)
    off = off - n["depth"] * _feature(t, th, n["t"], n["theta"], 0.018, 0.16)
    off = off + b["height"] * _feature(t, th, b["t"], b["theta"], 0.05, 0.20)
    off = off + c["height"] * _feature(t, th, c["t"], c["theta"], 0.07, 0.30)
    # dorsal ridge along the snout / cranium
    off = off + 0.025 * np.exp(-0.5 * (G.wrap_angle(th) / 0.18) ** 2) * G.smoothstep(0.05, 0.4, t)
    x = x + off * nx
    z = z + off * nz + H["skull_base_z"]
    return np.stack(np.broadcast_arrays(x, y, z), -1)


def jaw_local(t, th):
    t = np.asarray(t, float)
    th = np.asarray(th, float)
    y0, y1 = H["jaw_y"]
    y = y0 + (y1 - y0) * t
    a = _prof("jaw_width", t)
    bd = _prof("jaw_depth", t)
    x, z = G.superellipse(th, a, H["jaw_top"], bd, 5.0, 2.4)
    # chin keel + mandible ridge
    r = np.hypot(x, z)
    nx, nz = x / np.maximum(r, 1e-9), z / np.maximum(r, 1e-9)
    off = 0.02 * np.exp(-0.5 * (G.wrap_angle(th - math.pi) / 0.25) ** 2) * (1 - G.smoothstep(0.0, 0.35, t))
    off = off + 0.03 * _feature(t, th, 0.82, 2.0, 0.08, 0.3)
    x = x + off * nx
    z = z + off * nz + H["jaw_base_z"]
    return np.stack(np.broadcast_arrays(x, y, z), -1)


def _ring_part(fn, n_rings, radial, mouth_side, t_corner):
    """Closed loft from a surface function; per-face material (0 skin, 1 mouth)."""
    t = np.linspace(0.0, 1.0, n_rings)
    th = 2 * math.pi * np.arange(radial) / radial
    P = fn(t[:, None], th[None, :])                       # (N, R, 3)
    cen = P.mean(1)
    cen[:, 0] = 0.0
    T = np.tile([0.0, 1.0, 0.0], (n_rings, 1))
    U = np.tile([0.0, 0.0, 1.0], (n_rings, 1))
    B = np.tile([1.0, 0.0, 0.0], (n_rings, 1))
    sec = np.stack([P[..., 0] - cen[:, None, 0], P[..., 2] - cen[:, None, 2]], -1)
    # ring centres must lie on the true y of each ring
    cen[:, 1] = P[:, 0, 1]
    r0 = min(sec[0, :, 0].max(), sec[0, :, 1].max())
    r1 = min(sec[-1, :, 0].max(), sec[-1, :, 1].max())
    tube = G.build_tube(cen, T, U, B, sec, t, cap_front=dict(rings=3, length=0.55 * r0),
                        cap_back=dict(rings=3, length=0.45 * r1))
    # face materials: inner mouth surface on palate / jaw floor in front of the corner
    mats = []
    Rr = radial
    M = tube["ring_count"]
    ring_t = np.concatenate([[0.0] * 3, t, [1.0] * 3])
    for k in range(M - 1):
        for j in range(Rr):
            thm = 2 * math.pi * (j + 0.5) / Rr
            inside = (math.cos(thm) < -0.55) if mouth_side == "bottom" else (math.cos(thm) > 0.55)
            mats.append(1 if inside and ring_t[k] < t_corner and ring_t[k] > 0.015 else 0)
    mats += [0] * (len(tube["faces"]) - len(mats))
    return dict(verts=tube["verts"], faces=tube["faces"], face_uvs=tube["face_uvs"],
                attrs=dict(fsd_t=tube["attr_s"], fsd_theta=tube["attr_theta"]), mat=np.array(mats))


def skull_part():
    p = _ring_part(skull_local, H["skull_rings"], H["skull_radial"], "bottom", H["mouth_corner_t"])
    p["verts"] = to_world_skull(p["verts"])
    return p


def jaw_part():
    p = _ring_part(jaw_local, H["jaw_rings"], H["jaw_radial"], "top", H["mouth_corner_t"])
    p["verts"] = to_world_jaw(p["verts"])
    return p


def surface_normal(fn, t, th, eps=1e-3):
    """Outward normal of a parametric surface (local frame)."""
    p = fn(t, th)
    dt = fn(t + eps, th) - fn(t - eps, th)
    dth = fn(t, th + eps) - fn(t, th - eps)
    n = np.cross(dth, dt)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    # make sure it points away from the section centre line
    c = np.zeros_like(p)
    c[..., 1] = p[..., 1]
    c[..., 2] = (H["skull_base_z"] if fn is skull_local else H["jaw_base_z"])
    flip = np.sign(np.sum(n * (p - c), axis=-1, keepdims=True))
    return n * np.where(flip == 0, 1, flip)


def eye_centres():
    e = H["eye"]
    out = {}
    for side, sgn in (("L", 1), ("R", -1)):
        th = sgn * e["theta"]
        p = skull_local(np.array(e["t"]), np.array(th))
        # undeformed surface point -> socket floor
        n = surface_normal(skull_local, np.array(e["t"]), np.array(th))
        c = p + n * (e["radius"] * (e["protrude"] - 0.15))
        out[side] = dict(centre=to_world_skull(c), normal=dir_world_skull(n))
    return out


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def skull_point_world(t, th):
    t, th = np.asarray(t, float), np.asarray(th, float)
    p = skull_local(t, th)
    n = surface_normal(skull_local, t, th)
    return to_world_skull(p), _unit(dir_world_skull(n))


def jaw_point_world(t, th):
    t, th = np.asarray(t, float), np.asarray(th, float)
    p = jaw_local(t, th)
    n = surface_normal(jaw_local, t, th)
    return to_world_jaw(p), _unit(dir_world_jaw(n))
