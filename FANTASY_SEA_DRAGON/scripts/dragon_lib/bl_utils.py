"""Blender scene utilities (requires bpy)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import bpy
import numpy as np

from . import config
from .log import get_logger, rel


def script_args() -> list[str]:
    """CLI args for both `python script.py ...` and `blender -b -P script.py -- ...`."""
    argv = sys.argv
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    if Path(argv[0]).name.lower().startswith("blender"):
        return []                       # blender binary without "--"
    return argv[1:]


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def open_blend(path: Path):
    get_logger().info("Opening %s", rel(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))


def next_version_path(milestone_id: str, tag: str) -> Path:
    pdir = config.DIRS["project"]
    pdir.mkdir(parents=True, exist_ok=True)
    pat = re.compile(rf"FSD_{re.escape(milestone_id)}_{re.escape(tag)}_v(\d+)\.blend$")
    vers = [int(m.group(1)) for f in pdir.iterdir() if (m := pat.match(f.name))]
    return pdir / f"FSD_{milestone_id}_{tag}_v{(max(vers) + 1 if vers else 1):03d}.blend"


def save_milestone(run, tag: str) -> Path:
    path = next_version_path(run.id, tag)
    try:
        bpy.ops.file.make_paths_relative()
    except RuntimeError:
        pass  # unsaved file: relative paths resolved on save via relative_remap
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=True)
    run.blend = rel(path)
    run.output("blend", path)
    get_logger().info("Saved %s", rel(path))
    return path


# --------------------------------------------------------------------------
# Collections / objects
# --------------------------------------------------------------------------
def ensure_collections():
    scene = bpy.context.scene
    root = bpy.data.collections.get(config.ROOT_COLLECTION)
    if root is None:
        root = bpy.data.collections.new(config.ROOT_COLLECTION)
        scene.collection.children.link(root)
    for name in config.COLLECTIONS:
        c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
        if c.name not in root.children:
            root.children.link(c)
    light = bpy.data.collections[config.COLLECTIONS[-1]]
    for sub in (config.CAMERA_COLLECTION, config.PREVIEW_LIGHT_COLLECTION):
        c = bpy.data.collections.get(sub) or bpy.data.collections.new(sub)
        if c.name not in light.children:
            light.children.link(c)
    return root


def coll(name: str):
    return bpy.data.collections[name]


def link_to(obj, coll_name: str):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll(coll_name).objects.link(obj)
    return obj


def remove_objects(prefix: str):
    """Delete objects whose name starts with prefix (idempotent re-runs)."""
    for ob in [o for o in bpy.data.objects if o.name.startswith(prefix)]:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_recursive=True)


def mesh_object(name: str, verts, faces, coll_name: str, face_uvs=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    if face_uvs is not None:
        uv = me.uv_layers.new(name="UVMap")
        flat = np.array([c for f in face_uvs for c in f], dtype=np.float32).ravel()
        if len(flat) == len(uv.data) * 2:
            uv.data.foreach_set("uv", flat)
        else:
            raise RuntimeError(f"UV corner count mismatch on {name}: {len(flat)//2} vs {len(uv.data)}")
    if smooth:
        me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll(coll_name).objects.link(ob)
    return ob


def set_point_attr(me, name: str, values, dtype="FLOAT"):
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    a = me.attributes.new(name, dtype, "POINT")
    key = "value"
    a.data.foreach_set(key, np.asarray(values, dtype=np.float32 if dtype == "FLOAT" else np.int32))
    return a


def get_point_attr(me, name: str):
    a = me.attributes[name]
    out = np.zeros(len(me.vertices), dtype=np.float32 if a.data_type == "FLOAT" else np.int32)
    a.data.foreach_get("value", out)
    return out


def get_verts(me):
    co = np.zeros(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def set_verts(me, co):
    me.vertices.foreach_set("co", np.asarray(co, dtype=np.float64).ravel())
    me.update()


def model_objects(exclude_collections=("01_REFERENCES",)):
    """Mesh objects that belong to the creature (for framing / renders)."""
    out = []
    excl = {bpy.data.collections[c] for c in exclude_collections if c in bpy.data.collections}
    for ob in bpy.context.scene.objects:
        if ob.type not in {"MESH", "CURVE"} or ob.hide_render:
            continue
        if any(c in excl for c in ob.users_collection):
            continue
        out.append(ob)
    return out


def world_bbox(objs):
    from mathutils import Vector
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in objs:
        ev = ob.evaluated_get(dg)
        for c in ev.bound_box:
            pts.append(ev.matrix_world @ Vector(c))
    if not pts:
        return np.array([-1, -1, 0.0]), np.array([1, 1, 2.0])
    P = np.array([[p.x, p.y, p.z] for p in pts])
    return P.min(0), P.max(0)


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------
def principled(name, base=(0.6, 0.6, 0.6, 1), rough=0.5, metallic=0.0, fake_user=True):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = base
    mat.use_fake_user = fake_user
    return mat


def clay_material():
    return principled("MAT_Clay_Neutral", (0.55, 0.55, 0.56, 1.0), 0.55)


def assign_material(ob, mat):
    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)


def add_subsurf(ob, viewport: int, render: int):
    m = ob.modifiers.get("Subdivision") or ob.modifiers.new("Subdivision", "SUBSURF")
    m.levels = viewport
    m.render_levels = render
    m.quality = 3
    m.uv_smooth = "PRESERVE_CORNERS"
    return m


def object_from_builder(name: str, mb, coll_name: str, material_names: list[str] | None = None,
                        smooth=True, origin=None):
    """Create (or replace) a mesh object from a parts.MeshBuilder."""
    from . import materials as M
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    V, F, UV, MI, A = mb.arrays()
    if origin is not None:
        V = V - np.asarray(origin, float)
    ob = mesh_object(name, V, F, coll_name, face_uvs=UV, smooth=smooth)
    if origin is not None:
        ob.location = tuple(float(x) for x in origin)
    me = ob.data
    if material_names:
        M.assign(ob, material_names)
        me.polygons.foreach_set("material_index", np.asarray(MI, dtype=np.int32))
    for k, vals in A.items():
        set_point_attr(me, k, vals)
    me.update()
    ob["fsd_islands"] = mb.islands
    return ob


def bvh_for(objs, evaluated=True):
    """World-space BVH (and the bmesh-free polygon normals) of one or more objects."""
    from mathutils.bvhtree import BVHTree
    import bmesh
    bm = bmesh.new()
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in objs:
        ev = ob.evaluated_get(dg) if evaluated else ob
        me = ev.to_mesh()
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(ob.matrix_world)
        m2 = bpy.data.meshes.new("_tmp_bvh")
        tmp.to_mesh(m2)
        tmp.free()
        bm.from_mesh(m2)
        bpy.data.meshes.remove(m2)
        ev.to_mesh_clear()
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def remove_islands_touching(ob, others):
    """Delete whole islands of *ob* (e.g. scales) that intersect any of *others*."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    hit = set()
    for o in others:
        bo = bmesh.new()
        bo.from_mesh(o.data)
        bo.transform(o.matrix_world)
        bo.transform(ob.matrix_world.inverted())
        to = BVHTree.FromBMesh(bo)
        bo.free()
        hit |= {i for i, _ in tree.overlap(to)}
    seen, kill = set(), set()
    for fi in hit:
        if fi in seen:
            continue
        stack = [bm.faces[fi]]
        while stack:
            f = stack.pop()
            if f.index in seen:
                continue
            seen.add(f.index)
            for v in f.verts:
                kill.add(v)
            for e in f.edges:
                stack.extend(x for x in e.link_faces if x.index not in seen)
    if kill:
        bmesh.ops.delete(bm, geom=list(kill), context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(hit)


