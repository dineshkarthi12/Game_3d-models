"""Pure-python / numpy geometry helpers (no bpy dependency)."""
from __future__ import annotations

import math

import numpy as np


# --------------------------------------------------------------------------
# 1-D curves
# --------------------------------------------------------------------------
def hermite(t, p0, p1, m0, m1):
    """Cubic Hermite on t in [0, 1] (tangents already scaled to the interval)."""
    t = np.asarray(t, float)
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0
            + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1)


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def gaussian(x, mu, sigma):
    return np.exp(-0.5 * ((np.asarray(x, float) - mu) / sigma) ** 2)


def catmull_rom_1d(xk, yk, x):
    """Monotone-safe Catmull-Rom interpolation of control values yk at xk."""
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    x = np.asarray(x, float)
    if len(xk) == 1:
        return np.full_like(x, yk[0])
    m = np.zeros_like(yk)
    for i in range(len(xk)):
        if i == 0:
            m[i] = (yk[1] - yk[0]) / (xk[1] - xk[0])
        elif i == len(xk) - 1:
            m[i] = (yk[-1] - yk[-2]) / (xk[-1] - xk[-2])
        else:
            m[i] = (yk[i + 1] - yk[i - 1]) / (xk[i + 1] - xk[i - 1])
    out = np.empty_like(x)
    for n, xv in enumerate(x):
        i = int(np.clip(np.searchsorted(xk, xv) - 1, 0, len(xk) - 2))
        h = xk[i + 1] - xk[i]
        t = np.clip((xv - xk[i]) / h, 0, 1)
        out[n] = hermite(t, yk[i], yk[i + 1], m[i] * h, m[i + 1] * h)
    return out


def gaussian_smooth(x, sigma_samples):
    if sigma_samples <= 0:
        return np.asarray(x, float)
    r = int(3 * sigma_samples) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_samples) ** 2)
    k /= k.sum()
    # odd reflection keeps the end slope (edge padding would flatten it and
    # create a curvature spike at the ends of the curve)
    xp = np.pad(np.asarray(x, float), r, mode="reflect", reflect_type="odd")
    return np.convolve(xp, k, mode="valid")


# --------------------------------------------------------------------------
# Frames along a polyline
# --------------------------------------------------------------------------
def _norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def parallel_transport_frames(points: np.ndarray, up=(0.0, 0.0, 1.0)):
    """Rotation-minimising frames.

    Returns (T, U, B): tangent, 'up' normal and binormal (= T x U, which is the
    creature's LEFT side for a tangent pointing toward the tail).
    """
    P = np.asarray(points, float)
    T = np.gradient(P, axis=0)
    T = _norm(T)
    U = np.zeros_like(P)
    u0 = np.asarray(up, float)
    u0 = u0 - T[0] * np.dot(u0, T[0])
    U[0] = u0 / np.linalg.norm(u0)
    for i in range(1, len(P)):
        u = U[i - 1] - T[i] * np.dot(U[i - 1], T[i])   # project previous normal
        U[i] = u / np.linalg.norm(u)
    B = _norm(np.cross(T, U))
    return T, U, B


# --------------------------------------------------------------------------
# Cross-sections
# --------------------------------------------------------------------------
def superellipse(theta, a, b_up, b_dn, n_top, n_bot):
    """Point on an asymmetric superellipse.

    theta = 0 at the dorsal midline, pi/2 on the creature's left (+B),
    pi at the ventral midline.  Returns (lateral, vertical) offsets.
    """
    st, ct = np.sin(theta), np.cos(theta)
    n = np.where(ct >= 0, n_top, n_bot)
    b = np.where(ct >= 0, b_up, b_dn)
    x = a * np.sign(st) * np.abs(st) ** (2.0 / n)
    z = b * np.sign(ct) * np.abs(ct) ** (2.0 / n)
    return x, z


def wrap_angle(theta):
    return (np.asarray(theta) + math.pi) % (2 * math.pi) - math.pi


# --------------------------------------------------------------------------
# Tube mesh builder
# --------------------------------------------------------------------------
def build_tube(centres, T, U, B, section_xz, s_values, cap_front=None, cap_back=None):
    """Build a closed quad tube.

    centres     (N, 3) ring centres
    T, U, B     (N, 3) frames
    section_xz  (N, R, 2) lateral / vertical offsets per ring vertex
    s_values    (N,) arc parameter per ring
    cap_*       None or dict(rings=k, length=metres) – hemispherical pole caps

    Returns dict(verts, faces, face_uvs, attr_s, attr_theta, attr_cap).
    Faces are wound so normals point outward.
    """
    N, R, _ = section_xz.shape
    thetas = 2 * math.pi * np.arange(R) / R
    rings, ring_s, ring_cap = [], [], []

    def ring_pts(i, scale=1.0, push=0.0):
        off = (section_xz[i, :, 0:1] * B[i] + section_xz[i, :, 1:2] * U[i]) * scale
        return centres[i] + off + T[i] * push

    if cap_front:
        k, ln = cap_front["rings"], cap_front["length"]
        for c in range(k, 0, -1):          # small -> large
            a = (c / (k + 1)) * (math.pi / 2)
            rings.append(ring_pts(0, math.cos(a), -ln * math.sin(a)))
            ring_s.append(s_values[0])
            ring_cap.append(1)
    for i in range(N):
        rings.append(ring_pts(i))
        ring_s.append(s_values[i])
        ring_cap.append(0)
    if cap_back:
        k, ln = cap_back["rings"], cap_back["length"]
        for c in range(1, k + 1):
            a = (c / (k + 1)) * (math.pi / 2)
            rings.append(ring_pts(N - 1, math.cos(a), ln * math.sin(a)))
            ring_s.append(s_values[-1])
            ring_cap.append(2)

    verts = np.concatenate(rings, 0)
    attr_s = np.repeat(ring_s, R)
    attr_theta = np.tile(thetas, len(rings))
    attr_cap = np.repeat(ring_cap, R)
    faces, face_uvs = [], []
    M = len(rings)
    # v coordinate: normalised arc along all rings (caps included)
    vcoord = np.linspace(0.0, 1.0, M)
    for k in range(M - 1):
        b0, b1 = k * R, (k + 1) * R
        for j in range(R):
            j1 = (j + 1) % R
            faces.append((b0 + j, b0 + j1, b1 + j1, b1 + j))
            u0, u1 = j / R, (j + 1) / R
            face_uvs.append(((u0, vcoord[k]), (u1, vcoord[k]),
                             (u1, vcoord[k + 1]), (u0, vcoord[k + 1])))
    extra_v = []
    if cap_front:
        pole = centres[0] - T[0] * cap_front["length"]
        pi_ = len(verts) + len(extra_v)
        extra_v.append(pole)
        for j in range(R):
            j1 = (j + 1) % R
            faces.append((pi_, j1, j))
            face_uvs.append((((j + 0.5) / R, 0.0), ((j + 1) / R, vcoord[0]), (j / R, vcoord[0])))
    if cap_back:
        pole = centres[-1] + T[-1] * cap_back["length"]
        pi_ = len(verts) + len(extra_v)
        extra_v.append(pole)
        b0 = (M - 1) * R
        for j in range(R):
            j1 = (j + 1) % R
            faces.append((b0 + j, b0 + j1, pi_))
            face_uvs.append(((j / R, vcoord[-1]), ((j + 1) / R, vcoord[-1]), ((j + 0.5) / R, 1.0)))
    if extra_v:
        verts = np.concatenate([verts, np.array(extra_v)], 0)
        attr_s = np.concatenate([attr_s, [s_values[0]] * bool(cap_front) + [s_values[-1]] * bool(cap_back)])
        attr_theta = np.concatenate([attr_theta, np.zeros(len(extra_v))])
        attr_cap = np.concatenate([attr_cap, [1] * bool(cap_front) + [2] * bool(cap_back)])
    return dict(verts=verts, faces=faces, face_uvs=face_uvs, attr_s=attr_s,
                attr_theta=attr_theta, attr_cap=attr_cap, ring_count=M, radial=R)
