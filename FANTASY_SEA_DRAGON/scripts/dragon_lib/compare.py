"""Reference comparison system.

Each orthographic sheet view gets a *calibration*: a mapping between sheet
pixels and world space (origin pixel <-> world point, screen right/up vectors,
metres per pixel).  The same calibration drives

* the orthographic reference image planes in 01_REFERENCES, and
* "sheet-matched" silhouette renders whose pixels align 1:1 with the
  reference crop, so model and reference can be compared numerically
  (per-column dorsal / belly / width error, band IoU) and visually (overlays).
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw

from . import config, reference as ref
from .bl_utils import coll
from .log import check, get_logger
from .render import configure_cycles, ensure_camera, render_camera, view_axes

SHEET_TO_CAMERA = {"side_left": "left", "side_right": "right", "top": "top",
                   "bottom": "bottom", "front": "front", "back": "back"}


def _head_extent_side():
    """Vertical fg extent (sheet px) of the head in the left side view."""
    sheet = ref.load_sheet()
    lm = ref.LANDMARKS["side_left"]
    Lpx = ref.view_length_px("side_left")
    x0, y0, x1, y1 = ref.REGIONS["side_left"]
    a = ref.crop(sheet, "side_left")
    fg = ref.close_mask(ref.classify(a)[0], 3)
    ca = int(lm["nose"][0] + 0.03 * Lpx - x0)
    cb = int(lm["nose"][0] + 0.10 * Lpx - x0)
    rows = np.nonzero(fg[:, ca:cb].any(1))[0]
    return rows.min() + y0, rows.max() + y0


def _fg_bbox(view):
    sheet = ref.load_sheet()
    x0, y0, _, _ = ref.REGIONS[view]
    fg = ref.close_mask(ref.classify(ref.crop(sheet, view))[0], 3)
    ys, xs = np.nonzero(fg)
    return xs.min() + x0, ys.min() + y0, xs.max() + x0, ys.max() + y0


@lru_cache(maxsize=None)
def calibration(view: str) -> dict:
    """Pixel <-> world mapping for an orthographic sheet view."""
    L = config.TOTAL_LENGTH_M
    cam_view = SHEET_TO_CAMERA[view]
    right, up, back = view_axes(cam_view)
    if view in ("side_left", "side_right", "top", "bottom"):
        lm = ref.LANDMARKS[view]
        mpp = L / ref.view_length_px(view)
        if view.startswith("side"):
            origin_px = (lm["nose"][0], lm["ground_y"])
        else:
            origin_px = lm["nose"]
        origin_w = Vector((0.0, -L / 2, 0.0))
        approx = False
    else:
        # front / back: scale by matching the head's vertical extent with the
        # side view (approximate – the sheet is not a calibrated scan).
        side_top, side_bot = _head_extent_side()
        mpp_side = L / ref.view_length_px("side_left")
        bx0, by0, bx1, by1 = _fg_bbox(view)
        mpp = mpp_side * (side_bot - side_top) / (by1 - by0)
        z_top = (ref.LANDMARKS["side_left"]["ground_y"] - side_top) * mpp_side
        origin_px = ((bx0 + bx1) / 2, by0)
        origin_w = Vector((0.0, 0.0, z_top))
        approx = True
    return dict(view=view, cam_view=cam_view, mpp=mpp, origin_px=origin_px,
                origin_w=origin_w, right=right, up=up, back=back, approx=approx)


def px_to_world(cal, px, py) -> Vector:
    return (cal["origin_w"] + cal["right"] * ((px - cal["origin_px"][0]) * cal["mpp"])
            - cal["up"] * ((py - cal["origin_px"][1]) * cal["mpp"]))


def world_to_px(cal, w: Vector):
    d = Vector(w) - cal["origin_w"]
    return (cal["origin_px"][0] + d.dot(cal["right"]) / cal["mpp"],
            cal["origin_px"][1] - d.dot(cal["up"]) / cal["mpp"])


def region_centre_world(cal, region=None):
    x0, y0, x1, y1 = ref.REGIONS[region or cal["view"]]
    return px_to_world(cal, (x0 + x1) / 2, (y0 + y1) / 2)


# --------------------------------------------------------------------------
# Reference image planes
# --------------------------------------------------------------------------
PLANE_DISTANCE_FACTOR = 0.62   # planes sit 0.62 L behind the world origin


def _image_material(name, img_path: Path):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(img_path), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    tex.image = img
    tex.interpolation = "Closest"
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    mat.use_backface_culling = True
    return mat


def create_reference_plane(view: str, img_path: Path):
    cal = calibration(view)
    x0, y0, x1, y1 = ref.REGIONS[view]
    w, h = (x1 - x0) * cal["mpp"], (y1 - y0) * cal["mpp"]
    name = f"REF_{view}"
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)],
                   [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
    ob = bpy.data.objects.new(name, me)
    coll("01_REFERENCES").objects.link(ob)
    from .render import view_rotation
    ob.rotation_euler = view_rotation(cal["cam_view"])
    ob.location = region_centre_world(cal) - cal["back"] * (PLANE_DISTANCE_FACTOR * config.TOTAL_LENGTH_M)
    me.materials.append(_image_material(f"MAT_{name}", img_path))
    ob.hide_render = True          # viewport reference only
    ob.hide_select = True
    ob["fsd_mpp"] = cal["mpp"]
    ob["fsd_calibration_approximate"] = cal["approx"]
    return ob


# --------------------------------------------------------------------------
# Sheet-matched renders
# --------------------------------------------------------------------------
def sheet_camera(view: str, scale: int = 2, depth: float | None = None):
    cal = calibration(view)
    x0, y0, x1, y1 = ref.REGIONS[view]
    W, H = x1 - x0, y1 - y0
    cam = ensure_camera(cal["cam_view"])
    cam.name = cam.name  # keep
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(W, H) * cal["mpp"]
    depth = depth if depth is not None else 1.5 * config.TOTAL_LENGTH_M
    cam.location = region_centre_world(cal) + cal["back"] * depth
    return cam, (W * scale, H * scale)


def render_silhouette(view: str, objs, out: Path, scale: int = 2) -> np.ndarray:
    """Alpha mask (crop resolution) of *objs* rendered sheet-aligned."""
    hidden = []
    keep = set(objs)
    for ob in bpy.context.scene.objects:
        if ob.type in {"MESH", "CURVE"} and ob not in keep and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    sc = bpy.context.scene
    prev = (sc.render.film_transparent, sc.cycles.samples)
    configure_cycles(1, transparent=True, denoise=False)
    sc.cycles.use_adaptive_sampling = False
    sc.render.filter_size = 0.01
    cam, res = sheet_camera(view, scale)
    render_camera(cam, out, res)
    sc.render.filter_size = 1.5
    for ob in hidden:
        ob.hide_render = False
    a = np.asarray(Image.open(out).convert("RGBA")).astype(np.float32)[..., 3] / 255.0
    x0, y0, x1, y1 = ref.REGIONS[view]
    a = a.reshape(y1 - y0, scale, x1 - x0, scale).mean((1, 3))
    return a > 0.5


# --------------------------------------------------------------------------
# Numerical comparison of the trunk against reference profiles
# --------------------------------------------------------------------------
def _columns_s(view):
    x0, _, x1, _ = ref.REGIONS[view]
    lm = ref.LANDMARKS[view]
    Lpx = ref.view_length_px(view)
    cols = np.arange(x0, x1)
    return cols, (cols - lm["nose"][0]) / Lpx


def _compare_mask(s_cols, valid, a_model, b_model, a_ref, b_ref):
    err_a = np.abs(a_model - a_ref)[valid]
    err_b = np.abs(b_model - b_ref)[valid]
    inter = np.clip(np.minimum(b_model, b_ref) - np.maximum(a_model, a_ref), 0, None)[valid]
    union = (np.maximum(b_model, b_ref) - np.minimum(a_model, a_ref))[valid]
    return err_a, err_b, float(inter.sum() / max(union.sum(), 1e-9))


def compare_trunk(objs, out_dir: Path, s_range=(0.17, 0.74), tag="trunk"):
    """Compare model trunk outline with the reference (side + bottom views)."""
    L = config.TOTAL_LENGTH_M
    prof = ref.load_profiles()
    s_grid = np.array(prof["s"])
    out_dir.mkdir(parents=True, exist_ok=True)
    results, checks, overlays = {}, [], {}
    sheet_img = Image.open(config.REFERENCE_SHEET).convert("RGB")

    # ---------------- side view: dorsal & belly lines
    view = "side_left"
    cal = calibration(view)
    mask = render_silhouette(view, objs, out_dir / f"_sil_{tag}_{view}.png")
    cols, s_cols = _columns_s(view)
    _, y0, _, _ = ref.REGIONS[view]
    top_px = np.array([np.argmax(mask[:, i]) if mask[:, i].any() else np.nan for i in range(mask.shape[1])], float) + y0
    bot_px = np.array([mask.shape[0] - 1 - np.argmax(mask[::-1, i]) if mask[:, i].any() else np.nan
                       for i in range(mask.shape[1])], float) + y0
    lm = ref.LANDMARKS[view]
    Lpx = ref.view_length_px(view)
    ref_top = lm["ground_y"] - np.interp(s_cols, s_grid, ref.profile_array(prof, "top_L")) * Lpx
    ref_bot = lm["ground_y"] - np.interp(s_cols, s_grid, ref.profile_array(prof, "bottom_L")) * Lpx
    valid = (s_cols >= s_range[0]) & (s_cols <= s_range[1]) & ~np.isnan(ref_top) & ~np.isnan(top_px)
    for z0, z1 in ref.OCCLUSION_ZONES_S[view]:
        valid &= ~((s_cols >= z0) & (s_cols <= z1))
    e_top, e_bot, iou = _compare_mask(s_cols, valid, top_px, bot_px, ref_top, ref_bot)
    mpp = cal["mpp"]
    results["side"] = dict(columns=int(valid.sum()),
                           dorsal_mae_m=round(float(e_top.mean() * mpp), 4),
                           dorsal_max_m=round(float(e_top.max() * mpp), 4),
                           belly_mae_m=round(float(e_bot.mean() * mpp), 4),
                           belly_max_m=round(float(e_bot.max() * mpp), 4),
                           band_iou=round(iou, 4))
    overlays["side"] = _overlay(sheet_img, view, mask, valid, [(top_px, ref_top), (bot_px, ref_bot)],
                                out_dir / f"compare_{tag}_side_left.png")

    # ---------------- bottom view: lateral width
    view = "bottom"
    cal = calibration(view)
    mask_b = render_silhouette(view, objs, out_dir / f"_sil_{tag}_{view}.png")
    cols, s_cols = _columns_s(view)
    _, y0, _, _ = ref.REGIONS[view]
    lo_px = np.array([np.argmax(mask_b[:, i]) if mask_b[:, i].any() else np.nan for i in range(mask_b.shape[1])], float) + y0
    hi_px = np.array([mask_b.shape[0] - 1 - np.argmax(mask_b[::-1, i]) if mask_b[:, i].any() else np.nan
                      for i in range(mask_b.shape[1])], float) + y0
    Lpx_b = ref.view_length_px(view)
    ref_w = np.interp(s_cols, s_grid, ref.profile_array(prof, "half_width_L")) * 2 * Lpx_b
    mdl_w = hi_px - lo_px + 1
    valid_b = (s_cols >= s_range[0]) & (s_cols <= s_range[1]) & ~np.isnan(ref_w) & ~np.isnan(mdl_w)
    for z0, z1 in ref.OCCLUSION_ZONES_S[view]:
        valid_b &= ~((s_cols >= z0) & (s_cols <= z1))
    e_w = np.abs(mdl_w - ref_w)[valid_b]
    rel_w = (mdl_w[valid_b] - ref_w[valid_b]) / ref_w[valid_b]
    results["bottom"] = dict(columns=int(valid_b.sum()),
                             width_mae_m=round(float(e_w.mean() * cal["mpp"]), 4),
                             width_max_m=round(float(e_w.max() * cal["mpp"]), 4),
                             width_mean_rel_error=round(float(np.mean(rel_w)), 4))
    ctr = (lo_px + hi_px) / 2
    overlays["bottom"] = _overlay(sheet_img, view, mask_b, valid_b,
                                  [(lo_px, ctr - ref_w / 2), (hi_px, ctr + ref_w / 2)],
                                  out_dir / f"compare_{tag}_bottom.png")

    # ---------------- thresholds -> checks
    def grade(name, val, ok, warn, unit="m"):
        st = "PASS" if val <= ok else "WARNING" if val <= warn else "FAIL"
        checks.append(check(name, st, f"{val:.3f} {unit} (PASS <= {ok}, WARNING <= {warn})", val, ok))
    sd = results["side"]
    grade("Reference match – dorsal line MAE (side view)", sd["dorsal_mae_m"], 0.05, 0.10)
    grade("Reference match – belly line MAE (side view)", sd["belly_mae_m"], 0.05, 0.10)
    grade("Reference match – lateral width MAE (bottom view)", results["bottom"]["width_mae_m"], 0.05, 0.10)
    iou = sd["band_iou"]
    checks.append(check("Reference match – side band IoU", "PASS" if iou >= 0.90 else "WARNING" if iou >= 0.80 else "FAIL",
                        f"{iou:.3f} over {sd['columns']} measurable columns (s {s_range[0]}–{s_range[1]}, limb zones excluded)",
                        iou, 0.90))
    return results, checks, overlays


def _overlay(sheet_img, view, mask, valid, line_pairs, out: Path, scale=2):
    x0, y0, x1, y1 = ref.REGIONS[view]
    base = sheet_img.crop((x0, y0, x1, y1)).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.LANCZOS)
    base = Image.blend(base, Image.new("RGB", base.size, (0, 0, 0)), 0.25)
    m = Image.fromarray((mask * 255).astype(np.uint8)).resize(base.size, Image.NEAREST)
    tint = Image.new("RGB", base.size, (40, 230, 255))
    base = Image.composite(Image.blend(base, tint, 0.35), base, m)
    d = ImageDraw.Draw(base)
    for model_line, ref_line in line_pairs:
        for i in range(len(model_line) - 1):
            if not (valid[i] and valid[i + 1]):
                continue
            d.line([(i * scale, (ref_line[i] - y0) * scale), ((i + 1) * scale, (ref_line[i + 1] - y0) * scale)],
                   fill=(255, 60, 200), width=2)
            d.line([(i * scale, (model_line[i] - y0) * scale), ((i + 1) * scale, (model_line[i + 1] - y0) * scale)],
                   fill=(255, 255, 80), width=2)
    d.text((8, 6), "cyan = model silhouette   yellow = model outline   magenta = reference-measured outline",
           fill=(255, 255, 255))
    base.save(out)
    return out


# --------------------------------------------------------------------------
# Calibration self-tests (M02)
# --------------------------------------------------------------------------
def calibration_self_test(out_dir: Path):
    """Render a known box sheet-aligned and verify landmark pixel positions."""
    L = config.TOTAL_LENGTH_M
    checks, details = [], {}
    za, zb, half_x = 0.8, 1.6, 0.30
    me = bpy.data.meshes.new("TMP_CalibBox")
    xs, ys, zs = (-half_x, half_x), (-L / 2, L / 2), (za, zb)
    verts = [(x, y, z) for x in xs for y in ys for z in zs]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new("TMP_CalibBox", me)
    bpy.context.scene.collection.objects.link(ob)
    try:
        for view in ("side_left", "side_right", "top", "bottom"):
            cal = calibration(view)
            mask = render_silhouette(view, [ob], out_dir / f"_calib_{view}.png", scale=2)
            x0, y0, _, _ = ref.REGIONS[view]
            ys_, xs_ = np.nonzero(mask)
            got = dict(left=xs_.min() + x0, right=xs_.max() + x0 + 1, top=ys_.min() + y0, bottom=ys_.max() + y0 + 1)
            lm = ref.LANDMARKS[view]
            ex = sorted([lm["nose"][0], lm["tail"][0]])
            if view.startswith("side"):
                ey = (lm["ground_y"] - zb / cal["mpp"], lm["ground_y"] - za / cal["mpp"])
            else:
                ey = (lm["nose"][1] - half_x / cal["mpp"], lm["nose"][1] + half_x / cal["mpp"])
            err = max(abs(got["left"] - ex[0]), abs(got["right"] - ex[1]),
                      abs(got["top"] - ey[0]), abs(got["bottom"] - ey[1]))
            details[view] = dict(measured=got, expected=dict(left=ex[0], right=ex[1], top=ey[0], bottom=ey[1]),
                                 max_error_px=round(float(err), 2))
            checks.append(check(f"Calibration self-test ({view})",
                                "PASS" if err <= 1.5 else "WARNING" if err <= 3 else "FAIL",
                                f"known 12 m test box lands within {err:.2f} px of the sheet landmarks", err, 1.5))
    finally:
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
    return checks, details


def plane_render_test(view: str, out_dir: Path):
    """Render a reference plane through its camera; correlate with the crop."""
    ob = bpy.data.objects[f"REF_{view}"]
    cal = calibration(view)
    others = [o for o in bpy.context.scene.objects if o.type == "MESH" and o is not ob and not o.hide_render]
    for o in others:
        o.hide_render = True
    ob.hide_render = False
    configure_cycles(4, transparent=False, denoise=False, view_transform="Standard")
    bpy.context.scene.render.filter_size = 0.01
    cam, res = sheet_camera(view, scale=1, depth=3.0 * config.TOTAL_LENGTH_M)
    p = out_dir / f"plane_test_{view}.png"
    render_camera(cam, p, res)
    bpy.context.scene.render.filter_size = 1.5
    ob.hide_render = True
    for o in others:
        o.hide_render = False
    got = np.asarray(Image.open(p).convert("L")).astype(np.float32)
    x0, y0, x1, y1 = ref.REGIONS[view]
    exp = np.asarray(Image.open(config.REFERENCE_SHEET).convert("L").crop((x0, y0, x1, y1))).astype(np.float32)
    g = (got - got.mean()) / (got.std() + 1e-6)
    e = (exp - exp.mean()) / (exp.std() + 1e-6)
    ncc = float((g * e).mean())
    return check(f"Reference plane orientation/scale ({view})",
                 "PASS" if ncc >= 0.95 else "WARNING" if ncc >= 0.8 else "FAIL",
                 f"render-vs-crop normalised cross-correlation {ncc:.4f}", ncc, 0.95), p
