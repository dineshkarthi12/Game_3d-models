"""Central configuration for the Fantasy Sea Dragon pipeline.

Everything that controls the look or density of the asset lives here so that
milestone scripts stay free of magic numbers.  Values can be overridden with
environment variables:

    FSD_QUALITY = preview | standard | high      (geometry + render density)
    FSD_LENGTH  = total creature length in metres (default 12.0)
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
ROOT = SCRIPTS_DIR.parent

DIRS = {name: ROOT / name for name in (
    "references", "scripts", "assets", "textures",
    "renders", "exports", "reports", "project")}

REFERENCE_SHEET = DIRS["references"] / "fantasy_sea_dragon_multiview_reference.png"
REGIONS_DIR = DIRS["references"] / "regions"
ANALYSIS_DIR = DIRS["references"] / "analysis"
PROFILE_JSON = ANALYSIS_DIR / "reference_profiles.json"

STATE_JSON = DIRS["reports"] / "pipeline_state.json"
MILESTONE_LOG_MD = DIRS["reports"] / "milestone_log.md"
PIPELINE_LOG = DIRS["reports"] / "pipeline.log"

# --------------------------------------------------------------------------
# Quality levels
# --------------------------------------------------------------------------
QUALITY_LEVELS = {
    # fast iteration / optimized game output
    "preview": dict(body_rings=150, body_radial=24, subsurf_viewport=0,
                    subsurf_render=1, render_samples=16, render_res=0.5,
                    selfcheck_intersections=True),
    # default production setting
    "standard": dict(body_rings=280, body_radial=32, subsurf_viewport=1,
                     subsurf_render=2, render_samples=48, render_res=1.0,
                     selfcheck_intersections=True),
    # cinematic / high-detail output
    "high": dict(body_rings=440, body_radial=48, subsurf_viewport=1,
                 subsurf_render=2, render_samples=128, render_res=1.0,
                 selfcheck_intersections=True),
}
QUALITY = os.environ.get("FSD_QUALITY", "standard")
if QUALITY not in QUALITY_LEVELS:
    raise ValueError(f"FSD_QUALITY must be one of {list(QUALITY_LEVELS)}")


def quality() -> dict:
    return dict(QUALITY_LEVELS[QUALITY], name=QUALITY)


# --------------------------------------------------------------------------
# Scene organisation
# --------------------------------------------------------------------------
COLLECTIONS = [
    "01_REFERENCES", "02_BODY", "03_NECK", "04_HEAD", "05_SCALES",
    "06_BELLY_ARMOUR", "07_DORSAL_SPIKES", "08_FINS", "09_LEGS", "10_CLAWS",
    "11_TAIL", "12_EYES", "13_TEETH", "14_WHISKERS", "15_MATERIALS",
    "16_RIG", "17_LIGHTING",
]
CAMERA_COLLECTION = "17a_CAMERAS"          # child of 17_LIGHTING
PREVIEW_LIGHT_COLLECTION = "17b_PREVIEW_LIGHTS"  # child of 17_LIGHTING

ROOT_COLLECTION = "FANTASY_SEA_DRAGON"

# Object naming prefixes (kept stable for Maya / Unreal round-trips)
PREFIX = "DRG_"

# --------------------------------------------------------------------------
# World conventions
# --------------------------------------------------------------------------
# * Metric units, 1 Blender unit = 1 metre.
# * Z up.  The dragon faces -Y (Blender "front" convention), tail toward +Y.
# * The dragon's LEFT side is +X, RIGHT side is -X.
# * Arc parameter s in [0, 1]: s = 0 at the snout tip, s = 1 at tail-fin tip.
#   World Y = (s - 0.5) * total_length.
# * Ground (Z = 0) is the claw contact plane measured on the side view.
TOTAL_LENGTH_M = float(os.environ.get("FSD_LENGTH", "12.0"))


def s_to_y(s: float) -> float:
    return (s - 0.5) * TOTAL_LENGTH_M


# --------------------------------------------------------------------------
# Dragon design parameters (body milestone)
# --------------------------------------------------------------------------
BODY = dict(
    # extent of the continuous trunk mesh (neck root -> tail core tip)
    start_s=0.100,          # overlaps the back of the 12 %-L head by ~2 % L
    end_s=0.975,            # tail core ends inside the terminal fan fin
    # global multipliers on reference-measured radii
    radius_scale=1.00,
    width_scale=1.00,
    depth_scale=1.00,
    # explicit anchors where the reference is occluded
    neck_half_depth_m=0.44,  # head-junction section (s = start_s): tall ...
    neck_half_width_m=0.24,  # ... and narrow, like the skull behind the jaw hinge
    tail_radius_m=0.025,    # radius at the tail core tip (s = end_s)
    tail_taper_start_s=0.74,  # reference measurement trusted until here
    tail_taper_power=1.35,  # >1 keeps the tail fuller for longer
    # cross-section shape (superellipse exponents; 2 = ellipse)
    section_exponent_top=2.25,
    section_exponent_bottom=2.70,   # flatter belly for the armour plates
    dorsal_ridge_height=0.06,       # fraction of half-depth
    dorsal_ridge_width=0.28,        # radians (gaussian sigma)
    flank_muscle_height=0.035,      # lateral epaxial muscle bulge
    # local muscle volume around limb girdles (gaussian bumps along s)
    shoulder_s=0.305, hip_s=0.535, girdle_sigma=0.035,
    shoulder_bulge=0.07, hip_bulge=0.06,
    # spine curve: reference centre line + user control-point offsets
    use_reference_centerline=True,
    # (s, dz_m, dx_m) offsets interpolated with a smooth spline
    curve_control_points=[(0.10, 0.0, 0.0), (0.30, 0.0, 0.0),
                          (0.55, 0.0, 0.0), (0.80, 0.0, 0.0),
                          (0.975, 0.0, 0.0)],
    lateral_wave_amplitude_m=0.0,   # 0 = straight bind pose (matches top view)
    lateral_wave_cycles=1.5,
    # end caps
    cap_rings=4,
)

NECK = dict(
    start_s=0.100, end_s=0.235,
    nape_crest=0.10,        # extra dorsal crest height (fraction of radius)
    throat_sag=0.08,        # throat/dewlap fullness under the jaw
    lateral_muscle=0.05,    # sternocleidomastoid-like side bulge
    head_socket_s=0.118,    # where the skull's occipital ring will sit
)

# Limb girdle landmarks (used by later milestones and for profile masking)
LIMB_ZONES_S = {"front": (0.255, 0.360), "rear": (0.478, 0.585)}

# Proportions printed on the reference sheet
SHEET_PROPORTIONS = {"head": 0.12, "body": 0.68, "tail": 0.20}
