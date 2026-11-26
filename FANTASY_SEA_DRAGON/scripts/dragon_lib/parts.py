"""Procedural part builders (numpy only – no bpy).

Every builder returns a *part* dict:
    verts (N,3), faces [tuple], face_uvs [tuple of (u,v) per corner],
    attrs {name: (N,) array}  – per-vertex attributes (fsd_t = along-part 0..1, …)
    mat   int                 – material slot index for all faces of the part

Parts are combined with ``MeshBuilder`` into one Blender mesh (bl side).
All solids are closed 2-manifolds with outward normals.
"""
from __future__ import annotations

import math

import numpy as np

from . import geometry as G


# --------------------------------------------------------------------------
# Mesh accumulation
# --------------------------------------------------------------------------
class MeshBuilder:
    def __init__(self):
        self.verts, self.faces, self.uvs, self.mats = [], [], [], []
        self.attrs: dict[str, list] = {}
        self.n = 0
        self.islands = 0

    def add(self, part: dict, mat: int | None = None, **const_attrs):
        v = np.asarray(part["verts"], float)
        off = self.n
        self.verts.append(v)
        self.faces.extend(tuple(i + off for i in f) for f in part["faces"])
        self.uvs.extend(part["face_uvs"])
        m = part.get("mat", 0) if mat is None else mat
        if np.ndim(m) == 0:
            self.mats.extend([int(m)] * len(part["faces"]))
        else:
            self.mats.extend(int(x) for x in m)
        names = set(self.attrs) | set(part.get("attrs", {})) | set(const_attrs)
        for name in names:
            if name in part.get("attrs", {}):
                vals = np.asarray(part["attrs"][name], float)
            elif name in const_attrs:
                vals = np.full(len(v), float(const_attrs[name]))
            else:
                vals = np.zeros(len(v))
            if name not in self.attrs:
                self.attrs[name] = [np.zeros(off)] if off else []
            self.attrs[name].append(vals)
        self.n += len(v)
        self.islands += 1
        return off

    def arrays(self):
        V = np.concatenate(self.verts, 0) if self.verts else np.zeros((0, 3))
        A = {k: np.concatenate(v) if v else np.zeros(0) for k, v in self.attrs.items()}
        return V, self.faces, self.uvs, self.mats, A


# --------------------------------------------------------------------------
# Lofted tubes (horns, spikes, teeth, claws, whiskers, limb segments)
# --------------------------------------------------------------------------
def frames_with_hint(points, up_hint):
    P = np.asarray(points, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    u = np.asarray(up_hint, float)
    if abs(np.dot(u / np.linalg.norm(u), T[0])) > 0.98:
        u = np.cross(T[0], [1.0, 0, 0]) if abs(T[0][0]) < 0.9 else np.cross(T[0], [0, 1.0, 0])
    return G.parallel_transport_frames(P, up=u)


def loft(points, rx, ry=None, radial=12, up_hint=(0, 0, 1), exp=2.0,
         start="pole", end="pole", start_len=None, end_len=None, cap_rings=2,
         offset_y=None):
    """Tube through *points* with elliptical sections (rx lateral, ry 'up').

    start / end: 'pole' rounded cap, 'point' sharp tip (single pole, no cap
    rings), None for open (not used – solids stay closed).
    offset_y: optional (N,) shift of the section centre along U (asymmetric blades).
    """
    P = np.asarray(points, float)
    N = len(P)
    rx = np.broadcast_to(np.asarray(rx, float), (N,)).copy()
    ry = rx.copy() if ry is None else np.broadcast_to(np.asarray(ry, float), (N,)).copy()
    T, U, B = frames_with_hint(P, up_hint)
    th = 2 * math.pi * np.arange(radial) / radial
    sx, sz = G.superellipse(th[None, :], rx[:, None], ry[:, None], ry[:, None], exp, exp)
    if offset_y is not None:
        sz = sz + np.asarray(offset_y, float)[:, None]
    sec = np.stack([sx, sz], -1)
    s_vals = np.linspace(0, 1, N)
    rmin0 = max(min(rx[0], ry[0]), 1e-4)
    rmin1 = max(min(rx[-1], ry[-1]), 1e-4)
    cf = None if start is None else dict(rings=0 if start == "point" else cap_rings,
                                          length=start_len if start_len is not None else 0.8 * rmin0)
    cb = None if end is None else dict(rings=0 if end == "point" else cap_rings,
                                       length=end_len if end_len is not None else 0.8 * rmin1)
    tube = G.build_tube(P, T, U, B, sec, s_vals, cap_front=cf, cap_back=cb)
    # along-part parameter
    t = np.concatenate([tube["attr_s"]])
    return dict(verts=tube["verts"], faces=tube["faces"], face_uvs=tube["face_uvs"],
                attrs=dict(fsd_t=t), frames=(T, U, B))


def bezier(p0, p1, p2, p3=None, n=16):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = map(lambda x: np.asarray(x, float), (p0, p1, p2))
    if p3 is None:
        return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2
    p3 = np.asarray(p3, float)
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def curved_spike(base, up, back, height, base_long, base_lat, sweep_deg=45.0, curl_deg=25.0,
                 n=14, radial=10, sink=0.03, taper=0.9, profile="blade"):
    """Sharp curved spike / horn / tooth / claw.

    base       root point on the surface
    up         surface normal (growth direction before sweep)
    back       direction the spike sweeps toward (tangent, e.g. toward the tail)
    height     straight-line length from base to tip
    base_long  half-size of the base along *back*
    base_lat   half-size of the base sideways
    sweep_deg  angle of the base direction from *up* toward *back*
    curl_deg   additional bend of the tip toward *back*
    """
    up = np.asarray(up, float) / np.linalg.norm(up)
    back = np.asarray(back, float)
    back = back - up * np.dot(back, up)
    back /= np.linalg.norm(back)
    a0 = math.radians(sweep_deg)
    a1 = math.radians(sweep_deg + curl_deg)
    d0 = up * math.cos(a0) + back * math.sin(a0)
    d1 = up * math.cos(a1) + back * math.sin(a1)
    base = np.asarray(base, float) - up * sink
    p0 = base
    p1 = base + d0 * height * 0.55
    p2 = p1 + d1 * height * 0.55
    pts = bezier(p0, p1, p2, n=n)
    t = np.linspace(0, 1, n)
    prof = (1 - t * 0.97) ** taper
    if profile == "blade":
        # long along the sweep plane (ry, 'up' of the frame ~ back dir), thin sideways
        rx, ry = base_lat * prof, base_long * prof
    else:
        rx, ry = base_lat * prof, base_long * prof
    tip_len = float(np.linalg.norm(pts[-1] - pts[-2])) * 0.9
    part = loft(pts[:-1], rx[:-1], ry[:-1], radial=radial, up_hint=back, start="pole",
                end="point", start_len=0.3 * min(base_lat, base_long), end_len=tip_len)
    part["tip"] = pts[-1]
    return part


# --------------------------------------------------------------------------
# Closed lens-shaped patches (scales, armour plates) from top/bottom grids
# --------------------------------------------------------------------------
def lens_patch(top: np.ndarray, bottom_interior: np.ndarray, uv_grid=None):
    """Closed solid from a (nu, nv, 3) top grid and an (nu-2, nv-2, 3) bottom
    interior grid; the bottom shares the top's boundary ring (sharp rim)."""
    nu, nv, _ = top.shape
    idx_top = np.arange(nu * nv).reshape(nu, nv)
    verts = [top.reshape(-1, 3)]
    idx_bot = idx_top.copy()
    if nu > 2 and nv > 2:
        inner = np.arange((nu - 2) * (nv - 2)).reshape(nu - 2, nv - 2) + nu * nv
        idx_bot[1:-1, 1:-1] = inner
        verts.append(bottom_interior.reshape(-1, 3))
    faces, uvs = [], []
    if uv_grid is None:
        uu, vv = np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv), indexing="ij")
    else:
        uu, vv = uv_grid
    for i in range(nu - 1):
        for j in range(nv - 1):
            faces.append((idx_top[i, j], idx_top[i + 1, j], idx_top[i + 1, j + 1], idx_top[i, j + 1]))
            uvs.append(((uu[i, j], vv[i, j]), (uu[i + 1, j], vv[i + 1, j]),
                        (uu[i + 1, j + 1], vv[i + 1, j + 1]), (uu[i, j + 1], vv[i, j + 1])))
            faces.append((idx_bot[i, j], idx_bot[i, j + 1], idx_bot[i + 1, j + 1], idx_bot[i + 1, j]))
            uvs.append(((uu[i, j], vv[i, j]), (uu[i, j + 1], vv[i, j + 1]),
                        (uu[i + 1, j + 1], vv[i + 1, j + 1]), (uu[i + 1, j], vv[i + 1, j])))
    return dict(verts=np.concatenate(verts, 0), faces=faces, face_uvs=uvs, attrs={})


def rounded_grid(n=5):
    """Square grid mapped onto a disk (elliptical grid mapping): (n,n,2) in [-1,1]."""
    a = np.linspace(-1, 1, n)
    u, v = np.meshgrid(a, a, indexing="ij")
    x = u * np.sqrt(np.clip(1 - v * v / 2, 0, 1))
    y = v * np.sqrt(np.clip(1 - u * u / 2, 0, 1))
    return np.stack([x, y], -1)


# --------------------------------------------------------------------------
# Rayed fin membranes
# --------------------------------------------------------------------------
def ray_fin(roots, tips, bend=None, n_v=10, sub=3, thickness=0.02, ray_thickness=0.03,
            scallop=0.35, tip_power=1.0):
    """Thin closed fin membrane spanning rays roots[i] -> tips[i].

    roots, tips  (R,3) ray root / tip points (R >= 2)
    bend         (R,3) optional offset added with weight v^2 (curling)
    sub          membrane columns between consecutive rays
    scallop      how far the free edge recedes between rays (0..1) – serrated look
    Thickness tapers to zero on the whole boundary, so the solid closes with a
    sharp rim; rays are thicker ridges.
    """
    roots = np.asarray(roots, float)
    tips = np.asarray(tips, float)
    R = len(roots)
    bend = np.zeros_like(roots) if bend is None else np.asarray(bend, float)
    nu = (R - 1) * sub + 1
    uu = np.linspace(0, R - 1, nu)
    vv = np.linspace(0, 1, n_v)
    i0 = np.clip(np.floor(uu).astype(int), 0, R - 2)
    f = uu - i0
    rootu = roots[i0] * (1 - f)[:, None] + roots[i0 + 1] * f[:, None]
    tipu = tips[i0] * (1 - f)[:, None] + tips[i0 + 1] * f[:, None]
    bendu = bend[i0] * (1 - f)[:, None] + bend[i0 + 1] * f[:, None]
    recede = 1 - scallop * np.sin(math.pi * f) ** 0.8
    V = np.tile(vv, (nu, 1))  # (nu, nv): along-ray parameter
    reach = V * recede[:, None] ** (V ** tip_power)
    # bend follows the actual reach (not the grid row) so the receding serrated
    # edge between rays never folds back over the membrane
    P = rootu[:, None, :] + (tipu - rootu)[:, None, :] * reach[..., None] + bendu[:, None, :] * (reach ** 2)[..., None]
    # membrane normal
    du = np.gradient(P, axis=0)
    dv = np.gradient(P, axis=1)
    Nn = np.cross(du, dv)
    Nn /= np.maximum(np.linalg.norm(Nn, axis=2, keepdims=True), 1e-9)
    near = np.minimum(f, 1 - f)
    ray_w = np.exp(-0.5 * (near / 0.12) ** 2)
    edge_u = np.sin(math.pi * np.arange(nu) / (nu - 1)) ** 0.25
    th = (thickness * (1 - 0.75 * V) + ray_thickness * ray_w[:, None] * (1 - 0.85 * V))
    th *= edge_u[:, None] * np.sin(math.pi * np.clip(V * 0.98 + 0.02, 0, 1)) ** 0.35
    top = P + Nn * (th / 2)[..., None]
    bot = P - Nn * (th / 2)[..., None]
    uvg = (np.repeat((uu / (R - 1))[:, None], n_v, 1), np.repeat(vv[None, :], nu, 0))
    part = lens_patch(top, bot[1:-1, 1:-1], uv_grid=uvg)
    # attributes: along-ray parameter and ray ridge weight
    t_top = V.reshape(-1)
    t_bot = V[1:-1, 1:-1].reshape(-1)
    r_top = np.repeat(ray_w, n_v)
    r_bot = np.repeat(ray_w[1:-1], n_v - 2)
    part["attrs"] = dict(fsd_t=np.concatenate([t_top, t_bot]), fsd_ray=np.concatenate([r_top, r_bot]))
    return part


def rotate_about(points, axis, angle, pivot):
    """Rodrigues rotation of points about an axis through pivot."""
    k = np.asarray(axis, float) / np.linalg.norm(axis)
    p = np.asarray(points, float) - pivot
    c, s = math.cos(angle), math.sin(angle)
    return (p * c + np.cross(k, p) * s + np.outer(p @ k, k) * (1 - c)) + pivot


# --------------------------------------------------------------------------
# Greedy rejection of intersecting parts (spikes, teeth, claws …)
# --------------------------------------------------------------------------
def _bbox(p):
    v = np.asarray(p["verts"])
    return v.min(0), v.max(0)


def parts_intersect(a, b, tree_cache=None) -> bool:
    from mathutils.bvhtree import BVHTree
    (amin, amax), (bmin, bmax) = _bbox(a), _bbox(b)
    if np.any(amax < bmin) or np.any(bmax < amin):
        return False
    ta = BVHTree.FromPolygons([tuple(v) for v in a["verts"]], [tuple(f) for f in a["faces"]], epsilon=0.0)
    tb = BVHTree.FromPolygons([tuple(v) for v in b["verts"]], [tuple(f) for f in b["faces"]], epsilon=0.0)
    return len(ta.overlap(tb)) > 0


def keep_non_intersecting(candidates, existing=()):
    """Greedy filter: keep candidates (in priority order) that touch no kept part.
    Uses a bounding-box prefilter so large sets (hundreds of scales) stay fast."""
    kept, rejected = list(existing), 0
    boxes = [_bbox(k) for k in kept]
    out = []
    for c in candidates:
        cmin, cmax = _bbox(c)
        hit = False
        for k, (kmin, kmax) in zip(kept, boxes):
            if np.any(cmax < kmin) or np.any(kmax < cmin):
                continue
            if parts_intersect(c, k):
                hit = True
                break
        if hit:
            rejected += 1
            continue
        kept.append(c)
        boxes.append((cmin, cmax))
        out.append(c)
    return out, rejected


def catmull_rom_path(points, n=64):
    """Centripetal-ish uniform Catmull-Rom through 3-D control points."""
    P = np.asarray(points, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    segs = len(P) - 3
    out = []
    for i in range(segs):
        p0, p1, p2, p3 = P[i:i + 4]
        m = max(2, n // segs)
        t = np.linspace(0, 1, m, endpoint=(i == segs - 1))[:, None]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.concatenate(out, 0)
