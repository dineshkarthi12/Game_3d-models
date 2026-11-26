"""Preview rendering: camera rig, Cycles setup, multi-view contact sheets."""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Vector
from PIL import Image, ImageDraw, ImageFont

from . import config
from .bl_utils import coll, model_objects, world_bbox
from .log import get_logger

R = math.radians

# Camera conventions (see config: dragon faces -Y, left side = +X, Z up).
# 'dir' points from the subject toward the camera.
VIEWS = {
    "left":   dict(kind="ORTHO", rot=(90, 0, 90),  dir=(1, 0, 0),  res=(2000, 560)),
    "right":  dict(kind="ORTHO", rot=(90, 0, -90), dir=(-1, 0, 0), res=(2000, 560)),
    "front":  dict(kind="ORTHO", rot=(90, 0, 0),   dir=(0, -1, 0), res=(900, 900)),
    "back":   dict(kind="ORTHO", rot=(90, 0, 180), dir=(0, 1, 0),  res=(900, 900)),
    "top":    dict(kind="ORTHO", rot=(0, 0, 90),   dir=(0, 0, 1),  res=(2000, 500)),
    "bottom": dict(kind="ORTHO", rot=(180, 0, 90), dir=(0, 0, -1), res=(2000, 500)),
    "three_quarter_front_left":  dict(kind="PERSP", dir=(1.0, -1.25, 0.55), res=(1600, 900)),
    "three_quarter_front_right": dict(kind="PERSP", dir=(-1.0, -1.25, 0.55), res=(1600, 900)),
    "three_quarter_back_left":   dict(kind="PERSP", dir=(1.0, 1.25, 0.65), res=(1600, 900)),
    "three_quarter_back_right":  dict(kind="PERSP", dir=(-1.0, 1.25, 0.65), res=(1600, 900)),
}
ORTHO_VIEWS = ["left", "right", "front", "back", "top", "bottom"]
LABELS = {
    "left": "Side View (Left)", "right": "Side View (Right)", "front": "Front View",
    "back": "Back View", "top": "Top View", "bottom": "Bottom View",
    "three_quarter_front_left": "3/4 Front Left", "three_quarter_front_right": "3/4 Front Right",
    "three_quarter_back_left": "3/4 Back Left", "three_quarter_back_right": "3/4 Back Right",
}


def view_rotation(view: str) -> Euler:
    v = VIEWS[view]
    if "rot" in v:
        return Euler(tuple(R(a) for a in v["rot"]), "XYZ")
    d = Vector(v["dir"]).normalized()
    return (-d).to_track_quat("-Z", "Y").to_euler("XYZ")


def view_axes(view: str):
    m = view_rotation(view).to_matrix()
    right = Vector(m.col[0])
    up = Vector(m.col[1])
    back = Vector(m.col[2])        # camera looks along -back
    return right, up, back


# --------------------------------------------------------------------------
# Scene setup
# --------------------------------------------------------------------------
def configure_cycles(samples: int, res=(1600, 900), transparent=False, denoise=True,
                     view_transform="AgX", look="AgX - Medium High Contrast"):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = denoise
    if denoise:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = view_transform
    try:
        sc.view_settings.look = look if view_transform == "AgX" else "None"
    except TypeError:
        sc.view_settings.look = "None"
    sc.render.threads_mode = "AUTO"


def setup_world(color=(0.018, 0.02, 0.024), strength=1.0):
    w = bpy.data.worlds.get("WORLD_Studio_Dark") or bpy.data.worlds.new("WORLD_Studio_Dark")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*color, 1)
    bg.inputs[1].default_value = strength
    bpy.context.scene.world = w
    return w


def ensure_camera(view: str):
    name = f"CAM_{view}"
    cam = bpy.data.objects.get(name)
    if cam is None:
        data = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, data)
        coll(config.CAMERA_COLLECTION).objects.link(cam)
    v = VIEWS[view]
    cam.data.type = v["kind"]
    cam.data.clip_start = 0.05
    cam.data.clip_end = 500.0
    cam.data.lens = 50.0
    cam.data.sensor_fit = "AUTO"
    cam.rotation_mode = "XYZ"
    cam.rotation_euler = view_rotation(view)
    return cam


def create_camera_rig(length: float):
    """Default cameras around a creature of the given length (reframed later)."""
    lo = np.array([-0.15 * length, -0.5 * length, 0.0])
    hi = np.array([0.15 * length, 0.5 * length, 0.2 * length])
    cams = {}
    for v in VIEWS:
        cams[v] = frame_camera(v, lo, hi)
    return cams


def create_preview_lights(length: float):
    """Neutral 3-point clay lighting for milestone previews (M16 replaces it)."""
    specs = [
        ("LGT_Preview_Key",  (0.55 * length, -0.45 * length, 0.55 * length), 85.0 * length, 0.25 * length),
        ("LGT_Preview_Fill", (-0.6 * length, -0.25 * length, 0.25 * length), 35.0 * length, 0.35 * length),
        ("LGT_Preview_Rim",  (-0.1 * length, 0.6 * length, 0.45 * length), 120.0 * length, 0.2 * length),
        ("LGT_Preview_Under", (0.0, 0.0, -0.35 * length), 12.0 * length, 0.5 * length),
    ]
    for name, loc, power, size in specs:
        ob = bpy.data.objects.get(name)
        if ob is None:
            ld = bpy.data.lights.new(name, "AREA")
            ob = bpy.data.objects.new(name, ld)
            coll(config.PREVIEW_LIGHT_COLLECTION).objects.link(ob)
        ob.data.energy = power
        ob.data.size = size
        ob.location = loc
        d = Vector((0, 0, 1.0)) - Vector(loc)        # aim at mid-height centre
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# --------------------------------------------------------------------------
# Framing
# --------------------------------------------------------------------------
def frame_camera(view: str, lo, hi, margin=1.08):
    cam = ensure_camera(view)
    v = VIEWS[view]
    resx, resy = v["res"]
    right, up, back = view_axes(view)
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    centre = Vector(((lo + hi) / 2).tolist())
    corners = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    rel = [c - centre for c in corners]
    xs = [r.dot(right) for r in rel]
    ys = [r.dot(up) for r in rel]
    zs = [r.dot(back) for r in rel]
    diag = (Vector(hi.tolist()) - Vector(lo.tolist())).length
    if v["kind"] == "ORTHO":
        ex, ey = (max(xs) - min(xs)) * margin, (max(ys) - min(ys)) * margin
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        if resx >= resy:
            cam.data.ortho_scale = max(ex, ey * resx / resy)
        else:
            cam.data.ortho_scale = max(ey, ex * resy / resx)
        cam.location = centre + right * cx + up * cy + back * (diag + 5.0)
    else:
        fov_x = 2 * math.atan(18.0 / cam.data.lens) if resx >= resy else \
            2 * math.atan(18.0 / cam.data.lens * resx / resy)
        fov_y = 2 * math.atan(math.tan(fov_x / 2) * resy / resx)
        d = 0.0
        for x, y, z in zip(xs, ys, zs):
            d = max(d, abs(x) * margin / math.tan(fov_x / 2) + z,
                    abs(y) * margin / math.tan(fov_y / 2) + z)
        cam.location = centre + back * d
    return cam


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render_camera(cam, path: Path, res):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def render_views(views, out_dir: Path, prefix: str, samples: int, objs=None,
                 res_scale: float = 1.0, margin=1.08):
    log = get_logger()
    out_dir.mkdir(parents=True, exist_ok=True)
    objs = objs if objs is not None else model_objects()
    lo, hi = world_bbox(objs)
    configure_cycles(samples)
    paths = {}
    for v in views:
        cam = frame_camera(v, lo, hi, margin)
        res = tuple(max(64, int(r * res_scale)) for r in VIEWS[v]["res"])
        p = out_dir / f"{prefix}_{v}.png"
        render_camera(cam, p, res)
        log.info("  rendered %s", p.name)
        paths[v] = p
    return paths


def _font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def contact_sheet(items, out: Path, title: str, width=2400, cols=None, bg=(14, 15, 18)):
    """items: list of rows; each row is a list of (path, label)."""
    rows = items
    ft, fl = _font(30), _font(20)
    pad, lab_h, title_h = 16, 30, 56
    row_imgs, total_h = [], title_h
    for row in rows:
        ims = [Image.open(p).convert("RGB") for p, _ in row]
        avail = width - pad * (len(ims) + 1)
        ratios = [im.width / im.height for im in ims]
        h = int(avail / sum(ratios))
        ims = [im.resize((max(1, int(h * r)), h), Image.LANCZOS) for im, r in zip(ims, ratios)]
        row_imgs.append((ims, [lab for _, lab in row], h))
        total_h += h + lab_h + pad
    sheet = Image.new("RGB", (width, total_h + pad), bg)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 12), title, fill=(235, 235, 235), font=ft)
    y = title_h
    for ims, labels, h in row_imgs:
        x = pad
        for im, lab in zip(ims, labels):
            sheet.paste(im, (x, y))
            d.rectangle([x, y, x + im.width - 1, y + h - 1], outline=(45, 48, 55))
            d.text((x + 6, y + h + 4), lab, fill=(200, 200, 200), font=fl)
            x += im.width + pad
        y += h + lab_h + pad
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out
