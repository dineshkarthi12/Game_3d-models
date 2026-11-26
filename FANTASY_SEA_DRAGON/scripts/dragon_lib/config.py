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
    start_s=0.120,          # front cap buried inside the back of the skull
    end_s=0.975,            # tail core ends inside the terminal fan fin
    # global multipliers on reference-measured radii
    radius_scale=1.00,
    width_scale=1.00,
    depth_scale=1.00,
    # explicit anchors where the reference is occluded
    neck_half_depth_m=0.42,  # head-junction section (s = start_s): tall ...
    neck_half_width_m=0.21,  # ... and narrow, like the skull behind the jaw hinge
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
    curve_control_points=[(0.12, 0.0, 0.0), (0.30, 0.0, 0.0),
                          (0.55, 0.0, 0.0), (0.80, 0.0, 0.0),
                          (0.975, 0.0, 0.0)],
    lateral_wave_amplitude_m=0.0,   # 0 = straight bind pose (matches top view)
    lateral_wave_cycles=1.5,
    # end caps
    cap_rings=4,
)

NECK = dict(
    start_s=0.120, end_s=0.235,
    nape_crest=0.05,        # extra dorsal crest height (fraction of radius)
    throat_sag=0.08,        # throat/dewlap fullness under the jaw
    lateral_muscle=0.05,    # sternocleidomastoid-like side bulge
    head_socket_s=0.126,    # where the skull's occipital ring will sit
)

# Limb girdle landmarks (used by later milestones and for profile masking)
LIMB_ZONES_S = {"front": (0.255, 0.360), "rear": (0.478, 0.585)}

# Proportions printed on the reference sheet
SHEET_PROPORTIONS = {"head": 0.12, "body": 0.68, "tail": 0.20}

# --------------------------------------------------------------------------
# Head (M04/M05).  Local frame: origin at the jaw hinge, forward = -Y, up = +Z,
# left = +X.  Lengths in metres.  Profiles are (t, value) control points with
# t = 0 at the snout / chin and t = 1 at the back of the skull / jaw.
# --------------------------------------------------------------------------
HEAD = dict(
    hinge_s=0.103, hinge_z=1.35,
    gape_upper_deg=10.0,     # skull rotated snout-up about the hinge
    gape_lower_deg=30.0,     # lower jaw rotated down (sheet: wide open roar)
    skull_y=(-1.30, 0.40),   # local y of snout tip / back of cranium
    skull_width=[(0, 0.12), (0.08, 0.155), (0.25, 0.19), (0.45, 0.20), (0.62, 0.235),
                 (0.80, 0.27), (0.92, 0.29), (1.0, 0.27)],
    skull_top=[(0, 0.12), (0.08, 0.18), (0.25, 0.25), (0.45, 0.34), (0.60, 0.48),
               (0.75, 0.64), (0.90, 0.76), (1.0, 0.74)],
    skull_bottom=[(0, 0.05), (0.30, 0.06), (0.60, 0.07), (0.78, 0.13), (0.90, 0.26), (1.0, 0.30)],
    skull_base_z=0.04,
    jaw_y=(-1.22, 0.20),
    jaw_width=[(0, 0.09), (0.20, 0.13), (0.50, 0.17), (0.80, 0.23), (1.0, 0.24)],
    jaw_depth=[(0, 0.09), (0.15, 0.11), (0.50, 0.16), (0.80, 0.23), (1.0, 0.25)],
    jaw_top=0.035, jaw_base_z=-0.02,
    mouth_corner_t=0.74,     # skull / jaw t beyond which the mouth is closed (lips meet)
    eye=dict(t=0.66, theta=0.98, radius=0.072, protrude=0.45),
    nostril=dict(t=0.06, theta=0.55, depth=0.022),
    brow=dict(t=0.57, theta=0.72, height=0.065),
    cheek=dict(t=0.80, theta=1.65, height=0.045),
    skull_rings=96, skull_radial=48, jaw_rings=72, jaw_radial=36,
)
