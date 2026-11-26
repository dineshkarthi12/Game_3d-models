"""Reference-sheet handling: region crops, calibration and profile extraction.

The supplied sheet (1536 x 1024 px) is a *design* reference, not a calibrated
scan.  We therefore

1. crop every view / detail panel into its own image (references/regions);
2. calibrate each orthographic view independently with manually located
   landmarks (snout tip, tail-fin tip, claw ground line);
3. colour-segment the side and bottom views to measure the trunk's dorsal
   line, belly line and lateral width per column;
4. normalise every measurement to fractions of the total length L, so views
   with slightly different scales (side view L = 1029 px, top/bottom views
   L ~ 1010 px) can be combined;
5. smooth, mask limb / fin occlusions, and store the result in
   references/analysis/reference_profiles.json.

Only numpy and Pillow are required (no bpy), so this module also runs in a
plain Python interpreter.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import config

# --------------------------------------------------------------------------
# Region map (x0, y0, x1, y1) in sheet pixels.  Labels excluded where possible.
# --------------------------------------------------------------------------
REGIONS = {
    # orthographic full-body views
    "side_left":   (10, 38, 1075, 243),
    "side_right":  (10, 255, 1075, 458),
    "top":         (10, 462, 1075, 586),
    "bottom":      (10, 600, 1075, 722),
    "front":       (1095, 38, 1320, 230),
    "back":        (1325, 38, 1530, 230),
    # perspective views (not usable as ortho planes – kept for review)
    "three_quarter_front_left":  (1095, 258, 1320, 424),
    "three_quarter_front_right": (1325, 258, 1530, 424),
    "three_quarter_back_left":   (1095, 455, 1320, 700),
    "three_quarter_back_right":  (1325, 455, 1530, 700),
    # head detail strip
    "head_front":         (10, 778, 152, 962),
    "head_left_profile":  (155, 785, 333, 962),
    "head_right_profile": (343, 785, 515, 962),
    "head_top":           (515, 770, 618, 962),
    "head_bottom":        (622, 770, 732, 962),
    # component & texture details
    "detail_scales":      (754, 783, 874, 867),
    "detail_spine_fin":   (887, 783, 1008, 867),
    "detail_tail_fin":    (1022, 783, 1157, 867),
    "detail_claw_foot":   (754, 896, 850, 982),
    "detail_belly_plate": (862, 896, 953, 982),
    "detail_teeth":       (965, 896, 1055, 982),
    "detail_eye":         (1067, 896, 1157, 982),
    # proportion diagram
    "proportions":        (1180, 780, 1530, 1000),
}

# Text labels that intrude into a crop and must be blanked before analysis.
LABEL_BOXES = {
    "side_left": [(110, 218, 228, 243)],
    "side_right": [(110, 436, 232, 456)],
}

# Manually located calibration landmarks (sheet pixels).  See
# references/analysis/landmarks.md for how they were measured (4x zoom).
LANDMARKS = {
    # ground_y = lowest limb-fin tip (swimming pose; Z = 0 in world space)
    "side_left":  dict(nose=(34, 103), tail=(1063, 148), ground_y=250),
    "side_right": dict(nose=(1047, 330), tail=(22, 358), ground_y=455),
    "top":        dict(nose=(37, 527), tail=(1046, 527)),
    "bottom":     dict(nose=(37, 663), tail=(1048, 666)),
}

# Columns (as arc fraction s) hidden by limbs / limb fins in each view.
OCCLUSION_ZONES_S = {
    "side_left": [(0.250, 0.365), (0.470, 0.595)],
    "bottom":    [(0.240, 0.350), (0.445, 0.555)],
}
# Arc ranges in which the trunk outline is directly measurable.
VALID_RANGE_S = {
    "side_left": (0.165, 0.760),   # before: head + neck fins; after: tail fan
    "bottom":    (0.215, 0.800),   # before 0.215 the lateral neck fins inflate the width
}


def view_length_px(view: str) -> float:
    lm = LANDMARKS[view]
    return float(abs(lm["tail"][0] - lm["nose"][0]))


def load_sheet() -> np.ndarray:
    return np.asarray(Image.open(config.REFERENCE_SHEET).convert("RGB")).astype(np.float32) / 255.0


def crop(sheet: np.ndarray, region: str, blank_labels=True) -> np.ndarray:
    x0, y0, x1, y1 = REGIONS[region]
    a = sheet[y0:y1, x0:x1].copy()
    if blank_labels:
        for bx0, by0, bx1, by1 in LABEL_BOXES.get(region, []):
            a[max(by0 - y0, 0):max(by1 - y0, 0), max(bx0 - x0, 0):max(bx1 - x0, 0)] = 0
    return a


def crop_regions(out_dir: Path | None = None) -> dict[str, Path]:
    out_dir = out_dir or config.REGIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(config.REFERENCE_SHEET).convert("RGB")
    paths = {}
    for name, box in REGIONS.items():
        p = out_dir / f"ref_{name}.png"
        im.crop(box).save(p)
        paths[name] = p
    return paths


# --------------------------------------------------------------------------
# Colour classification helpers
# --------------------------------------------------------------------------
def hsv(a: np.ndarray):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(-1)
    mn = a.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, ((g - b) / d) % 6,
                 np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def classify(a: np.ndarray, v_thresh=0.10):
    """Return boolean masks: foreground, blue scales, orange fins, beige belly."""
    h, s, v = hsv(a)
    fg = v > v_thresh
    blue = fg & (h > 170) & (h < 260) & (s > 0.25)
    orange = fg & (h < 48) & (s > 0.55) & (v > 0.35)
    beige = fg & ~blue & ~orange & (s < 0.55) & (v > 0.25)
    return fg, blue, orange, beige


def morph(mask: np.ndarray, r: int, op: str) -> np.ndarray:
    """Binary dilation / erosion with a disc of radius r (pure numpy)."""
    pad_val = op == "erode"
    p = np.pad(mask, r, constant_values=pad_val)
    H, W = mask.shape
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            sl = p[r + dy:r + dy + H, r + dx:r + dx + W]
            out = (out | sl) if op == "dilate" else (out & sl)
    return out


def close_mask(mask, r=4):
    return morph(morph(mask, r, "dilate"), r, "erode")


# --------------------------------------------------------------------------
# 1-D signal helpers
# --------------------------------------------------------------------------
def rolling_median(x: np.ndarray, w: int) -> np.ndarray:
    p = w // 2
    xp = np.pad(x, p, mode="edge")
    out = np.full_like(x, np.nan)
    for i in range(len(x)):
        win = xp[i:i + w]
        if np.any(~np.isnan(win)):
            out[i] = np.nanmedian(win)
    return out


def fill_nan_linear(x: np.ndarray) -> np.ndarray:
    idx = np.arange(len(x))
    ok = ~np.isnan(x)
    if ok.sum() < 2:
        return x
    return np.interp(idx, idx[ok], x[ok])


def gaussian_smooth(x: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return x
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    xp = np.pad(x, r, mode="edge")
    return np.convolve(xp, k, mode="valid")


# --------------------------------------------------------------------------
# Measurements
# --------------------------------------------------------------------------
def measure_side(sheet) -> dict:
    """Dorsal (top) and belly (bottom) lines of the trunk in the left view."""
    view = "side_left"
    a = crop(sheet, view)
    x0, y0, _, _ = REGIONS[view]
    fg, blue, orange, _ = classify(a)
    fgc = close_mask(fg, 4)
    H, W = fg.shape
    top = np.full(W, np.nan)
    bot = np.full(W, np.nan)
    for x in range(W):
        run = np.convolve(blue[:, x].astype(int), np.ones(4, int), "valid") >= 4
        idx = np.nonzero(run)[0]
        if not len(idx):
            continue
        t = idx[0]
        y = t
        while y < H - 1 and fgc[y + 1, x]:
            y += 1
        top[x], bot[x] = t + y0, y + y0          # back to sheet coordinates
    lm = LANDMARKS[view]
    Lpx = view_length_px(view)
    cols = np.arange(W) + x0
    s = (cols - lm["nose"][0]) / Lpx
    # heights above ground in units of L
    top_L = (lm["ground_y"] - top) / Lpx
    bot_L = (lm["ground_y"] - bot) / Lpx
    return dict(s=s, top_L=top_L, bot_L=bot_L, raw_top_px=top, raw_bot_px=bot)


def measure_bottom_width(sheet) -> dict:
    """Lateral width of the trunk from the ventral view (bright belly plates)."""
    view = "bottom"
    a = crop(sheet, view)
    x0, y0, _, _ = REGIONS[view]
    fg, *_ = classify(a)
    fgc = close_mask(fg, 3)
    H, W = fg.shape
    ctr = int(np.argmax(fgc[:, 200:800].sum(1)))
    lo_a = np.full(W, np.nan)
    hi_a = np.full(W, np.nan)
    for x in range(W):
        c = fgc[:, x]
        cc = ctr
        if not c[cc]:
            nz = np.nonzero(c[max(ctr - 6, 0):ctr + 7])[0]
            if not len(nz):
                continue
            cc = max(ctr - 6, 0) + nz[np.argmin(abs(nz - 6))]
        lo = hi = cc
        while lo > 0 and c[lo - 1]:
            lo -= 1
        while hi < H - 1 and c[hi + 1]:
            hi += 1
        lo_a[x], hi_a[x] = lo + y0, hi + y0
    lm = LANDMARKS[view]
    Lpx = view_length_px(view)
    cols = np.arange(W) + x0
    s = (cols - lm["nose"][0]) / Lpx
    width_L = (hi_a - lo_a + 1) / Lpx
    return dict(s=s, width_L=width_L, raw_lo_px=lo_a, raw_hi_px=hi_a,
                centre_row_px=ctr + y0)


def _process(s_src, values, view, s_grid, med_w=41, sigma_s=0.012):
    """Mask occlusions, robust-filter, resample to s_grid, smooth."""
    v = values.copy()
    a, b = VALID_RANGE_S[view]
    v[(s_src < a) | (s_src > b)] = np.nan
    for z0, z1 in OCCLUSION_ZONES_S.get(view, []):
        v[(s_src >= z0) & (s_src <= z1)] = np.nan
    v = rolling_median(v, med_w)
    for z0, z1 in OCCLUSION_ZONES_S.get(view, []):      # median may leak in
        v[(s_src >= z0) & (s_src <= z1)] = np.nan
    v[(s_src < a) | (s_src > b)] = np.nan
    vg = np.interp(s_grid, s_src, v, left=np.nan, right=np.nan)
    valid = (s_grid >= a) & (s_grid <= b)
    filled = fill_nan_linear(np.where(valid, vg, np.nan))
    ds = s_grid[1] - s_grid[0]
    sm = gaussian_smooth(filled, sigma_s / ds)
    sm[~valid] = np.nan
    return sm, valid


def extract_profiles(write=True) -> dict:
    sheet = load_sheet()
    side = measure_side(sheet)
    bott = measure_bottom_width(sheet)
    s_grid = np.round(np.linspace(0.0, 1.0, 401), 6)
    top_L, v_side = _process(side["s"], side["top_L"], "side_left", s_grid)
    bot_L, _ = _process(side["s"], side["bot_L"], "side_left", s_grid)
    width_L, v_w = _process(bott["s"], bott["width_L"], "bottom", s_grid)
    centre = (top_L + bot_L) / 2
    half_depth = (top_L - bot_L) / 2
    half_width = width_L / 2

    def js(x):
        return [None if (isinstance(v, float) and np.isnan(v)) or v is None or np.isnan(v)
                else round(float(v), 6) for v in x]

    prof = dict(
        source=config.REFERENCE_SHEET.name,
        units="fractions of total length L (heights above claw ground line)",
        landmarks=LANDMARKS,
        view_length_px={v: view_length_px(v) for v in LANDMARKS},
        valid_range_s=VALID_RANGE_S,
        occlusion_zones_s=OCCLUSION_ZONES_S,
        s=s_grid.tolist(),
        top_L=js(top_L), bottom_L=js(bot_L),
        centre_z_L=js(centre), half_depth_L=js(half_depth),
        half_width_L=js(half_width),
        raw=dict(side_s=js(side["s"]), side_top_px=js(side["raw_top_px"]),
                 side_bot_px=js(side["raw_bot_px"]), bottom_s=js(bott["s"]),
                 bottom_lo_px=js(bott["raw_lo_px"]), bottom_hi_px=js(bott["raw_hi_px"])),
    )
    # summary statistics for the log
    hd = np.array([np.nan if v is None else v for v in prof["half_depth_L"]], float)
    hw = np.array([np.nan if v is None else v for v in prof["half_width_L"]], float)
    both = ~np.isnan(hd) & ~np.isnan(hw)
    prof["summary"] = dict(
        max_half_depth_L=float(np.nanmax(hd)), max_half_width_L=float(np.nanmax(hw)),
        mean_depth_to_width=float(np.nanmean(hd[both] / hw[both])),
        side_vs_bottom_length_ratio=view_length_px("side_left") / view_length_px("bottom"),
    )
    if write:
        config.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        config.PROFILE_JSON.write_text(json.dumps(prof, indent=1))
        _debug_overlays(sheet, side, bott, prof)
    return prof


def load_profiles() -> dict:
    if not config.PROFILE_JSON.exists():
        return extract_profiles(write=True)
    return json.loads(config.PROFILE_JSON.read_text())


def profile_array(prof: dict, key: str) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in prof[key]], float)


# --------------------------------------------------------------------------
# Debug visualisation
# --------------------------------------------------------------------------
def _poly(draw, pts, fill, width):
    seg = []
    for p in pts:
        if p is None or any(np.isnan(p)):
            if len(seg) > 1:
                draw.line(seg, fill=fill, width=width)
            seg = []
        else:
            seg.append(p)
    if len(seg) > 1:
        draw.line(seg, fill=fill, width=width)


def _debug_overlays(sheet, side, bott, prof):
    s_grid = np.array(prof["s"])
    # --- side view
    view = "side_left"
    x0, y0, x1, y1 = REGIONS[view]
    lm = LANDMARKS[view]
    Lpx = view_length_px(view)
    img = Image.fromarray((crop(sheet, view, False) * 255).astype(np.uint8)).convert("RGB")
    sc = 2
    img = img.resize((img.width * sc, img.height * sc), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    for z0, z1 in OCCLUSION_ZONES_S[view]:
        xa = (lm["nose"][0] + z0 * Lpx - x0) * sc
        xb = (lm["nose"][0] + z1 * Lpx - x0) * sc
        d.rectangle([xa, 0, xb, img.height], fill=(255, 0, 0, 40))
    a, b = VALID_RANGE_S[view]
    for sv in (a, b):
        X = (lm["nose"][0] + sv * Lpx - x0) * sc
        d.line([(X, 0), (X, img.height)], fill=(255, 255, 255, 120), width=1)
    for key, col in (("raw_top_px", (0, 255, 0, 110)), ("raw_bot_px", (255, 0, 255, 110))):
        pts = [((c - x0) * sc, (v - y0) * sc) for c, v in zip(np.arange(len(side[key])) + x0, side[key])]
        for p in pts:
            if not np.isnan(p[1]):
                d.point(p, fill=col)
    for key, col in (("top_L", (0, 255, 0, 255)), ("bottom_L", (255, 0, 255, 255))):
        vals = profile_array(prof, key)
        pts = [None if np.isnan(v) else ((lm["nose"][0] + sv * Lpx - x0) * sc,
                                          (lm["ground_y"] - v * Lpx - y0) * sc)
               for sv, v in zip(s_grid, vals)]
        _poly(d, pts, col, 3)
    gy = (lm["ground_y"] - y0) * sc
    d.line([(0, gy), (img.width, gy)], fill=(255, 255, 0, 160), width=1)
    img.save(config.ANALYSIS_DIR / "side_profile_overlay.png")

    # --- bottom view
    view = "bottom"
    x0, y0, _, _ = REGIONS[view]
    lm = LANDMARKS[view]
    Lpx = view_length_px(view)
    img = Image.fromarray((crop(sheet, view, False) * 255).astype(np.uint8)).convert("RGB")
    img = img.resize((img.width * sc, img.height * sc), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    for z0, z1 in OCCLUSION_ZONES_S[view]:
        xa = (lm["nose"][0] + z0 * Lpx - x0) * sc
        xb = (lm["nose"][0] + z1 * Lpx - x0) * sc
        d.rectangle([xa, 0, xb, img.height], fill=(255, 0, 0, 40))
    hw = profile_array(prof, "half_width_L")
    raw_c = rolling_median((bott["raw_lo_px"] + bott["raw_hi_px"]) / 2, 61)
    cy = np.interp(s_grid, bott["s"], fill_nan_linear(raw_c))
    for key, col in (("raw_lo_px", (0, 255, 0, 110)), ("raw_hi_px", (255, 0, 255, 110))):
        for c, v in zip(np.arange(len(bott[key])) + x0, bott[key]):
            if not np.isnan(v):
                d.point(((c - x0) * sc, (v - y0) * sc), fill=col)
    for sign, col in ((-1, (0, 255, 0, 255)), (1, (255, 0, 255, 255))):
        pts = [None if np.isnan(v) else ((lm["nose"][0] + sv * Lpx - x0) * sc,
                                          (c + sign * v * Lpx - y0) * sc)
               for sv, v, c in zip(s_grid, hw, cy)]
        _poly(d, pts, col, 3)
    img.save(config.ANALYSIS_DIR / "bottom_width_overlay.png")

    # --- profile chart
    W, H, pad = 1100, 420, 50
    chart = Image.new("RGB", (W, H), (18, 20, 24))
    d = ImageDraw.Draw(chart)
    ymax = 0.1
    def P(sv, v):
        return pad + sv * (W - 2 * pad), H - pad - v / ymax * (H - 2 * pad)
    for gv in np.arange(0, ymax + 1e-9, 0.02):
        d.line([P(0, gv), P(1, gv)], fill=(50, 54, 60))
        d.text((5, P(0, gv)[1] - 6), f"{gv:.2f}L", fill=(150, 150, 150))
    for gs in np.arange(0, 1.01, 0.1):
        d.line([P(gs, 0), P(gs, ymax)], fill=(40, 44, 50))
        d.text((P(gs, 0)[0] - 8, H - pad + 6), f"{gs:.1f}", fill=(150, 150, 150))
    for key, col, lab in (("half_depth_L", (255, 120, 40), "half depth (side)"),
                          ("half_width_L", (60, 170, 255), "half width (bottom)"),
                          ("centre_z_L", (200, 200, 200), "centre height")):
        vals = profile_array(prof, key)
        _poly(d, [None if np.isnan(v) else P(sv, v) for sv, v in zip(s_grid, vals)], col, 2)
        d.text((W - 230, 20 + 16 * ["half_depth_L", "half_width_L", "centre_z_L"].index(key)), lab, fill=col)
    d.text((pad, 10), "Reference-measured trunk profiles vs arc fraction s (0 = snout, 1 = tail tip)",
           fill=(230, 230, 230))
    chart.save(config.ANALYSIS_DIR / "profile_chart.png")
