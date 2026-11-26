"""Material library.

Modelling milestones (M04–M12) assign these materials by *name* with a simple
Principled setup so previews read in colour.  M13 rebuilds the node trees in
place (procedural bump, roughness variation, colour gradients), and M14 wires
in the generated texture maps – assignments never change.
"""
from __future__ import annotations

import bpy

# name: (base colour RGBA, metallic, roughness)
PRESETS = {
    "MAT_Scale_MetallicBlue": ((0.020, 0.160, 0.520, 1), 0.55, 0.30),
    "MAT_Scale_Turquoise":    ((0.010, 0.420, 0.560, 1), 0.45, 0.32),
    "MAT_Scale_Gold":         ((0.880, 0.560, 0.080, 1), 0.75, 0.28),
    "MAT_Scale_DarkNavy":     ((0.008, 0.030, 0.110, 1), 0.35, 0.40),
    "MAT_Skin_DarkNavy":      ((0.010, 0.040, 0.120, 1), 0.20, 0.45),
    "MAT_Spike_Orange":       ((0.950, 0.300, 0.020, 1), 0.10, 0.35),
    "MAT_Fin_Amber":          ((0.960, 0.420, 0.030, 1), 0.05, 0.40),
    "MAT_Belly_Beige":        ((0.620, 0.520, 0.360, 1), 0.10, 0.50),
    "MAT_Claw_Dark":          ((0.025, 0.022, 0.020, 1), 0.00, 0.30),
    "MAT_Teeth_Ivory":        ((0.880, 0.820, 0.660, 1), 0.00, 0.25),
    "MAT_Eye_Glossy":         ((1.000, 0.550, 0.020, 1), 0.00, 0.05),
    "MAT_Eye_Pupil":          ((0.005, 0.004, 0.003, 1), 0.00, 0.10),
    "MAT_Mouth_Interior":     ((0.450, 0.060, 0.070, 1), 0.00, 0.35),
    "MAT_Tongue":             ((0.700, 0.260, 0.320, 1), 0.00, 0.30),
    "MAT_Horn_Gold":          ((0.800, 0.450, 0.080, 1), 0.30, 0.35),
    "MAT_Whisker":            ((0.600, 0.200, 0.030, 1), 0.10, 0.40),
}


def ensure(name: str):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    base, metal, rough = PRESETS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = base
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    mat.diffuse_color = base
    return mat


def assign(ob, names: list[str]):
    """Set the object's material slots to *names* (slot index = list index)."""
    ob.data.materials.clear()
    for n in names:
        ob.data.materials.append(ensure(n))
