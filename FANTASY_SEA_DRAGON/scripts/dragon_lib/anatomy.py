"""Trunk anatomy model: spine curve + cross-section radii as functions of s.

The model is the single source of truth for every later milestone (scales,
belly plates, spikes, limbs and rig all query it), so it is deterministic and
depends only on ``config`` and the reference profiles JSON.

Construction
------------
* Measured range (reference side + bottom views): s in [S_MEAS0, taper_start].
* Neck (s < S_MEAS0): cubic Hermite blend from a head-junction anchor
  (``BODY.neck_half_depth_m`` / ``neck_half_width_m``, head-centre landmark) to the measured values,
  matching the measured slope -> C1 continuous.
* Tail (s > taper_start): Hermite taper to ``BODY.tail_radius_m`` at end_s
  (zero end slope), raised to ``tail_taper_power``.  Centre height blends to
  the tail-tip landmark height.
* Limb-girdle muscle bulges (gaussians) are added around shoulders and hips.
* A final light gaussian smoothing guarantees no abrupt radius changes.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from . import config, geometry as G, reference

S_MEAS0 = 0.17
S_MEAS0_CENTRE = 0.21     # longer S-curve blend for the neck centre line
RING_LOG_WEIGHT_M = 2.5   # metres of arc "worth" one unit of log-radius change
# Head-junction centre landmark on the side view (sheet px): centre of the
# occipital/neck cross-section just behind the skull, estimated from the
# dorsal crest (y~75) and the throat line hidden behind the neck fins (y~160).
HEAD_JUNCTION_CENTRE_PX = (137, 117)


class TrunkModel:
    def __init__(self, body: dict | None = None, length: float | None = None,
                 samples: int = 2001):
        self.p = dict(config.BODY if body is None else body)
        self.L = float(length or config.TOTAL_LENGTH_M)
        self.prof = reference.load_profiles()
        self.s = np.linspace(self.p["start_s"], self.p["end_s"], samples)
        self._build()

    # ------------------------------------------------------------------
    def _measured(self, key):
        s_ref = np.array(self.prof["s"])
        v = reference.profile_array(self.prof, key)
        ok = ~np.isnan(v)
        return s_ref[ok], v[ok] * self.L

    def _blend_profile(self, key, v_start, v_end, end_power=1.0, s_end_anchor=None, s_meas0=S_MEAS0):
        p = self.p
        sm, vm = self._measured(key)
        s0 = max(s_meas0, sm[0])
        s1 = min(p["tail_taper_start_s"], sm[-1])
        s = self.s
        out = np.interp(s, sm, vm)
        # slopes of the measured data at both junctions (per unit s)
        h = 0.01
        m0 = (np.interp(s0 + h, sm, vm) - np.interp(s0, sm, vm)) / h
        m1 = (np.interp(s1, sm, vm) - np.interp(s1 - h, sm, vm)) / h
        v0 = np.interp(s0, sm, vm)
        v1 = np.interp(s1, sm, vm)
        # neck
        a = p["start_s"]
        sel = s < s0
        t = (s[sel] - a) / (s0 - a)
        out[sel] = G.hermite(t, v_start, v0, 0.0, m0 * (s0 - a))
        # tail
        b = s_end_anchor if s_end_anchor is not None else p["end_s"]
        sel = s > s1
        t = np.clip((s[sel] - s1) / (b - s1), 0, 1)
        if end_power != 1.0:
            # shape the normalised taper, keep end values exact
            base = G.hermite(t, 1.0, 0.0, m1 * (b - s1) / max(v1 - v_end, 1e-6), 0.0)
            out[sel] = v_end + (v1 - v_end) * np.clip(base, 0, None) ** end_power
        else:
            out[sel] = G.hermite(t, v1, v_end, m1 * (b - s1), 0.0)
        return out

    def _build(self):
        p, L, s = self.p, self.L, self.s
        rs = p["radius_scale"]
        # anchors
        tr = p["tail_radius_m"]
        hd = self._blend_profile("half_depth_L", p["neck_half_depth_m"], tr, p["tail_taper_power"])
        hw = self._blend_profile("half_width_L", p["neck_half_width_m"], tr * 0.85, p["tail_taper_power"])
        # centre height
        lm = reference.LANDMARKS["side_left"]
        Lpx = reference.view_length_px("side_left")
        z_head = (lm["ground_y"] - HEAD_JUNCTION_CENTRE_PX[1]) / Lpx * L
        z_tail = (lm["ground_y"] - lm["tail"][1]) / Lpx * L
        cz = self._blend_profile("centre_z_L", z_head, z_tail, s_meas0=S_MEAS0_CENTRE)
        # girdle muscle bulges
        bump = (p["shoulder_bulge"] * G.gaussian(s, p["shoulder_s"], p["girdle_sigma"])
                + p["hip_bulge"] * G.gaussian(s, p["hip_s"], p["girdle_sigma"]))
        hw = hw * (1 + bump)
        hd = hd * (1 + 0.5 * bump)
        hw *= rs * p["width_scale"]
        hd *= rs * p["depth_scale"]
        # final smoothing (sigma ~0.6 % L) for continuity
        ds = s[1] - s[0]
        sig = 0.006 / ds
        self.half_width = G.gaussian_smooth(hw, sig)
        self.half_depth = G.gaussian_smooth(hd, sig)
        cz = G.gaussian_smooth(cz, sig)
        # user control-point offsets
        cp = sorted(p["curve_control_points"])
        cps = [c[0] for c in cp]
        dz = G.catmull_rom_1d(cps, [c[1] for c in cp], np.clip(s, cps[0], cps[-1]))
        dx = G.catmull_rom_1d(cps, [c[2] for c in cp], np.clip(s, cps[0], cps[-1]))
        if not p["use_reference_centerline"]:
            cz = np.full_like(cz, np.median(cz))
        wave = p["lateral_wave_amplitude_m"] * np.sin(
            2 * math.pi * p["lateral_wave_cycles"] * (s - s[0]) / (s[-1] - s[0])) \
            * G.smoothstep(s[0], s[0] + 0.15, s)
        self.centre = np.stack([dx + wave, (s - 0.5) * L, cz + dz], 1)
        self.T, self.U, self.B = G.parallel_transport_frames(self.centre)

    # ------------------------------------------------------------------
    def at(self, s_query):
        """Interpolated (centre, T, U, B, half_width, half_depth) at s."""
        sq = np.atleast_1d(np.asarray(s_query, float))
        def ip(arr):
            if arr.ndim == 1:
                return np.interp(sq, self.s, arr)
            return np.stack([np.interp(sq, self.s, arr[:, k]) for k in range(arr.shape[1])], 1)
        T = ip(self.T); U = ip(self.U); B = ip(self.B)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        U /= np.linalg.norm(U, axis=1, keepdims=True)
        B /= np.linalg.norm(B, axis=1, keepdims=True)
        return dict(centre=ip(self.centre), T=T, U=U, B=B,
                    half_width=ip(self.half_width), half_depth=ip(self.half_depth))

    def section(self, s_ring, thetas):
        """(N, R, 2) lateral/vertical offsets of the trunk surface."""
        p = self.p
        f = self.at(s_ring)
        a = f["half_width"][:, None]
        b = f["half_depth"][:, None]
        th = np.asarray(thetas)[None, :]
        x, z = G.superellipse(th, a, b, b, p["section_exponent_top"], p["section_exponent_bottom"])
        # dorsal ridge (spine line where the dorsal spikes are rooted)
        ridge = p["dorsal_ridge_height"] * b * np.exp(-0.5 * (G.wrap_angle(th) / p["dorsal_ridge_width"]) ** 2)
        # epaxial flank muscles (+-55 deg from the dorsal midline)
        fl = p["flank_muscle_height"] * a * (
            np.exp(-0.5 * ((G.wrap_angle(th) - 0.95) / 0.35) ** 2)
            + np.exp(-0.5 * ((G.wrap_angle(th) + 0.95) / 0.35) ** 2))
        r = np.hypot(x, z)
        nx, nz = x / np.maximum(r, 1e-9), z / np.maximum(r, 1e-9)
        x = x + fl * nx
        z = z + ridge + fl * nz
        return np.stack([np.broadcast_to(x, z.shape), z], -1)

    def ring_s_values(self, n_rings: int):
        """Ring stations distributed by arc length (denser where radius changes)."""
        seg = np.linalg.norm(np.diff(self.centre, axis=0), axis=1)
        # weight: arc length + relative (log) radius change, so the thin tail
        # tip gets enough rings to keep ring-to-ring radius steps small
        dlog = (np.abs(np.diff(np.log(self.half_depth))) + np.abs(np.diff(np.log(self.half_width)))) / 2
        w = seg + RING_LOG_WEIGHT_M * dlog
        cum = np.concatenate([[0], np.cumsum(w)])
        targets = np.linspace(0, cum[-1], n_rings)
        return np.interp(targets, cum, self.s)

    def summary(self) -> dict:
        i_max = int(np.argmax(self.half_depth))
        arc = float(np.sum(np.linalg.norm(np.diff(self.centre, axis=0), axis=1)))
        return dict(
            trunk_arc_length_m=round(arc, 3),
            max_half_depth_m=round(float(self.half_depth.max()), 3),
            max_half_width_m=round(float(self.half_width.max()), 3),
            max_depth_at_s=round(float(self.s[i_max]), 3),
            neck_half_depth_m=round(float(self.half_depth[0]), 3),
            tail_half_depth_m=round(float(self.half_depth[-1]), 3),
            centre_height_range_m=[round(float(self.centre[:, 2].min()), 3),
                                   round(float(self.centre[:, 2].max()), 3)],
        )


@lru_cache(maxsize=1)
def default_trunk() -> TrunkModel:
    return TrunkModel()
