"""Standard milestone review: full-creature views, focus close-ups and a
sheet-aligned comparison with the reference (requires bpy)."""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

from . import compare, config, reference as ref, render
from .bl_utils import coll, model_objects, world_bbox


def render_aligned(view, objs, out: Path, samples=24, scale=2):
    render.configure_cycles(samples)
    cam, res = compare.sheet_camera(view, scale=scale)
    keep = set(objs)
    hidden = []
    for ob in bpy.context.scene.objects:
        if ob.type in {"MESH", "CURVE"} and ob not in keep and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    render.render_camera(cam, out, res)
    for ob in hidden:
        ob.hide_render = False
    return out


def aligned_rows(aligned: dict, tmp: Path, crop_box=None):
    """Rows of [reference crop | model | 50 % overlay] for comparison sheets."""
    sheet = Image.open(config.REFERENCE_SHEET).convert("RGB")
    tmp.mkdir(parents=True, exist_ok=True)
    rows = []
    for view, p in aligned.items():
        x0, y0, x1, y1 = ref.REGIONS[view]
        crop = sheet.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.LANCZOS)
        mdl = Image.open(p).convert("RGB").resize(crop.size)
        if crop_box is not None:              # sub-region in sheet px (e.g. head)
            bx0, by0, bx1, by1 = crop_box
            box = ((bx0 - x0) * 2, (by0 - y0) * 2, (bx1 - x0) * 2, (by1 - y0) * 2)
            crop, mdl = crop.crop(box), mdl.crop(box)
        blend = Image.blend(crop, mdl, 0.5)
        tag = f"{view}{'_crop' if crop_box else ''}"
        cp, mp, bp = tmp / f"ref_{tag}.png", tmp / f"mdl_{tag}.png", tmp / f"blend_{tag}.png"
        crop.save(cp); mdl.save(mp); blend.save(bp)
        rows.append([(cp, f"Reference: {view}"), (mp, "Model (sheet-aligned camera)"), (bp, "50 % overlay")])
    return rows


def render_focus(objs, out: Path, direction=(1.0, -1.2, 0.6), res=(1400, 900), samples=32,
                 margin=1.15, lens=60.0, context_objs=None, bbox=None):
    """Perspective close-up framing *objs* (other creature parts stay visible)."""
    cam = bpy.data.objects.get("CAM_focus")
    if cam is None:
        cam = bpy.data.objects.new("CAM_focus", bpy.data.cameras.new("CAM_focus"))
        coll(config.CAMERA_COLLECTION).objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.01
    cam.data.clip_end = 500
    lo, hi = (np.asarray(bbox[0], float), np.asarray(bbox[1], float)) if bbox is not None else world_bbox(objs)
    centre = Vector(((lo + hi) / 2).tolist())
    d = Vector(direction).normalized()
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    m = cam.rotation_euler.to_matrix()
    right, up = Vector(m.col[0]), Vector(m.col[1])
    fov_x = 2 * math.atan(18.0 / lens)
    fov_y = 2 * math.atan(math.tan(fov_x / 2) * res[1] / res[0])
    dist = 0.0
    for x in (lo[0], hi[0]):
        for y in (lo[1], hi[1]):
            for z in (lo[2], hi[2]):
                r = Vector((x, y, z)) - centre
                dist = max(dist, abs(r.dot(right)) * margin / math.tan(fov_x / 2) + r.dot(d),
                           abs(r.dot(up)) * margin / math.tan(fov_y / 2) + r.dot(d))
    cam.location = centre + d * dist
    render.configure_cycles(samples)
    render.render_camera(cam, out, res)
    return out


def standard_review(run, mid: str, title: str, focus_objs, focus_dirs=None, samples=None,
                    aligned_views=("side_left",), head_crop=False, extra_rows=None, res_scale=0.6):
    q = config.quality()
    samples = samples or max(24, q["render_samples"] // 2)
    out = config.DIRS["renders"] / mid
    out.mkdir(parents=True, exist_ok=True)
    allobjs = model_objects()
    full = render.render_views(["three_quarter_front_left", "left", "top"], out, f"{mid}_full",
                               samples, objs=allobjs, res_scale=res_scale)
    focus_dirs = focus_dirs or [(1.0, -1.2, 0.6), (-1.0, -0.9, 0.35)]
    foc = []
    for i, d in enumerate(focus_dirs):
        p = render_focus(focus_objs, out / f"{mid}_focus_{i}.png", d, samples=samples,
                         res=(int(1400 * res_scale / 0.6), int(900 * res_scale / 0.6)))
        foc.append(p)
    aligned = {v: render_aligned(v, allobjs, out / f"{mid}_aligned_{v}.png", samples=16) for v in aligned_views}
    rows = [[(full["three_quarter_front_left"], "Full creature – 3/4 front left")] +
            [(p, f"Close-up {i + 1}") for i, p in enumerate(foc)],
            [(full["left"], "Side view (left)")], [(full["top"], "Top view")]]
    rows += aligned_rows(aligned, out / "_tmp")
    if head_crop:
        rows += aligned_rows({"side_left": aligned["side_left"]}, out / "_tmp", crop_box=(10, 38, 300, 243))
    if extra_rows:
        rows += extra_rows
    sheet = render.contact_sheet(rows, out / f"{mid}_review_sheet.png", f"{mid} – {title}", width=2400)
    for p in list(full.values()) + foc + list(aligned.values()):
        run.output("render", p)
    run.output("preview", sheet)
    return sheet
