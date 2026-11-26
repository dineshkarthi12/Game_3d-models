"""Fantasy Sea Dragon procedural pipeline – shared library.

Modules
-------
config      Paths, quality levels, collection names, dragon design parameters.
log         Logging + milestone run records (JSON / Markdown / pipeline state).
reference   Reference-sheet crops, calibration landmarks, profile extraction.
anatomy     Spine / radius / cross-section model driven by reference profiles.
geometry    Pure-python geometry helpers (frames, ring meshes, smoothing).
bl_utils    Blender scene helpers (collections, versioned saves, materials).
render      Preview rendering, camera framing, contact sheets.
compare     Reference-vs-model silhouette comparison.
validate    Mesh integrity checks returning PASS / WARNING / FAIL records.

Modules that need ``bpy`` import it lazily so that the analysis tools can also
run in a plain Python interpreter with numpy + Pillow.
"""

__version__ = "0.3.0"
