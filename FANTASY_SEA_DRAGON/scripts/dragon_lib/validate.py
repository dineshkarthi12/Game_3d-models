"""Geometry validation returning PASS / WARNING / FAIL check records.

Nothing is marked PASS unless it was actually measured.
"""
from __future__ import annotations

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

from .log import check


def _bm_from(ob, evaluated: bool):
    bm = bmesh.new()
    if evaluated:
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        bm.from_mesh(me)
        ev.to_mesh_clear()
    else:
        bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bm.normal_update()
    return bm


def mesh_checks(ob, watertight=True, intersections=True, evaluated=False, label=None) -> list[dict]:
    name = label or (ob.name + (" (evaluated)" if evaluated else ""))
    bm = _bm_from(ob, evaluated)
    out = []
    nv, ne, nf = len(bm.verts), len(bm.edges), len(bm.faces)
    out.append(check(f"{name}: geometry present", "PASS" if nf > 0 else "FAIL",
                     f"{nv} verts / {ne} edges / {nf} faces", nf))
    if nf == 0:
        bm.free()
        return out
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    wire = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    loose_v = sum(1 for v in bm.verts if not v.link_edges)
    if watertight:
        st = "PASS" if boundary == 0 and nonman == 0 else "FAIL"
    else:
        st = "PASS" if nonman == 0 else "FAIL"
    out.append(check(f"{name}: manifold", st,
                     f"{nonman} non-manifold edges, {boundary} boundary edges (watertight required: {watertight})",
                     nonman + (boundary if watertight else 0), 0))
    out.append(check(f"{name}: loose geometry", "PASS" if wire == 0 and loose_v == 0 else "FAIL",
                     f"{wire} wire edges, {loose_v} loose verts", wire + loose_v, 0))
    areas = np.array([f.calc_area() for f in bm.faces])
    degen = int((areas < 1e-10).sum())
    out.append(check(f"{name}: degenerate faces", "PASS" if degen == 0 else "FAIL",
                     f"{degen} faces with area < 1e-10 m² (min area {areas.min():.3e})", degen, 0))
    flipped = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    out.append(check(f"{name}: consistent normals", "PASS" if flipped == 0 else "FAIL",
                     f"{flipped} edges between faces with opposing winding", flipped, 0))
    if watertight and boundary == 0:
        vol = bm.calc_volume(signed=True)
        out.append(check(f"{name}: normals point outward", "PASS" if vol > 0 else "FAIL",
                         f"signed volume {vol:.4f} m³", vol, 0))
    if intersections:
        tree = BVHTree.FromBMesh(bm, epsilon=0.0)
        pairs = tree.overlap(tree)
        bm.faces.ensure_lookup_table()
        bad = 0
        for i, j in pairs:
            if i >= j:
                continue
            fi, fj = bm.faces[i], bm.faces[j]
            if set(v.index for v in fi.verts) & set(v.index for v in fj.verts):
                continue          # adjacent faces always 'touch'
            bad += 1
        out.append(check(f"{name}: self-intersections", "PASS" if bad == 0 else "FAIL",
                         f"{bad} intersecting non-adjacent face pairs (BVH overlap test)", bad, 0))
    bm.free()
    return out


def ring_continuity_checks(name, ring_radius: np.ndarray, tangents: np.ndarray,
                           max_rel_step=0.03, max_bend_deg=2.0) -> list[dict]:
    """Abrupt radius change / kink detection along a ring-based body."""
    r = np.asarray(ring_radius, float)
    rel = np.abs(np.diff(r)) / np.maximum(r[:-1], 1e-6)
    i = int(np.argmax(rel))
    t = np.asarray(tangents, float)
    cosang = np.clip(np.einsum("ij,ij->i", t[:-1], t[1:]), -1, 1)
    bend = np.degrees(np.arccos(cosang))
    j = int(np.argmax(bend))
    return [
        check(f"{name}: radius continuity", "PASS" if rel[i] <= max_rel_step else
              "WARNING" if rel[i] <= 2 * max_rel_step else "FAIL",
              f"max ring-to-ring mean-radius change {rel[i]*100:.2f}% at ring {i} (limit {max_rel_step*100:.1f}%)",
              float(rel[i]), max_rel_step),
        check(f"{name}: spine smoothness", "PASS" if bend[j] <= max_bend_deg else
              "WARNING" if bend[j] <= 2 * max_bend_deg else "FAIL",
              f"max tangent change {bend[j]:.3f}° between rings at ring {j} (limit {max_bend_deg}°)",
              float(bend[j]), max_bend_deg),
    ]


def materials_check(ob) -> dict:
    mats = [m for m in ob.data.materials if m is not None]
    return check(f"{ob.name}: material assigned", "PASS" if mats else "FAIL",
                 ", ".join(m.name for m in mats) or "none", len(mats), 1)


def uv_check(ob) -> dict:
    n = len(ob.data.uv_layers)
    return check(f"{ob.name}: UV map present", "PASS" if n else "FAIL",
                 ", ".join(u.name for u in ob.data.uv_layers) or "none", n, 1)
