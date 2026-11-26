"""03 – Neck generator (M03, part 2) + body blockout review.

Operates on the continuous trunk from 02 (no separate neck mesh, so there is
no seam or intersection at the neck/torso transition):

* nape crest     – raised dorsal crest behind the skull (dorsal spikes root here)
* throat         – fuller ventral throat under the jaw hinge
* neck muscles   – lower-lateral muscle volume (sternocleidomastoid analogue)
* vertex groups  – VG_Neck / VG_Torso / VG_Tail smooth region weights
* sockets        – SOCKET_Head, SOCKET_TailFin, SOCKET_Shoulder_L/R, SOCKET_Hip_L/R
                   (attachment frames for M04 head, M10 limbs, M12 tail)

Review stage (M03 checkpoint): full validation, numeric reference comparison,
10-view clay renders, reference-aligned comparison sheet.

Run:  python 03_neck_generator.py   |  blender -b --python-exit-code 1 -P 03_neck_generator.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image  # noqa: E402

from dragon_lib import anatomy, compare, config, geometry as G, reference as ref, render, validate  # noqa: E402
from dragon_lib import bl_utils as bu  # noqa: E402
from dragon_lib.log import MilestoneRun, check, latest_blend, rel  # noqa: E402

BODY_NAME = config.PREFIX + "Body"


# --------------------------------------------------------------------------
def shape_neck(ob, trunk, p):
    me = ob.data
    co = bu.get_verts(me)
    s = bu.get_point_attr(me, "fsd_s").astype(float)
    th = G.wrap_angle(bu.get_point_attr(me, "fsd_theta").astype(float))
    f = trunk.at(s)
    c, T, U = f["centre"], f["T"], f["U"]
    hd, hw = f["half_depth"], f["half_width"]
    w = 1.0 - G.smoothstep(p["head_socket_s"] + 0.03, p["end_s"], s)
    crest = p["nape_crest"] * hd * np.exp(-0.5 * (th / 0.30) ** 2) * G.gaussian(s, 0.15, 0.035)
    throat = p["throat_sag"] * hd * np.exp(-0.5 * (G.wrap_angle(th - math.pi) / 0.55) ** 2) \
        * G.gaussian(s, p["head_socket_s"] + 0.02, 0.045)   # soft falloff: no notch behind the jaw
    lat = p["lateral_muscle"] * hw * (np.exp(-0.5 * ((th - 2.0) / 0.35) ** 2)
                                      + np.exp(-0.5 * ((th + 2.0) / 0.35) ** 2)) * w
    radial = co - c
    radial -= T * np.einsum("ij,ij->i", radial, T)[:, None]
    radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-9)
    disp = U * (crest - throat)[:, None] + radial * lat[:, None]
    bu.set_verts(me, co + disp)
    return float(np.abs(disp).max()), int((np.linalg.norm(disp, axis=1) > 1e-5).sum())


def vertex_groups(ob):
    me = ob.data
    s = bu.get_point_attr(me, "fsd_s").astype(float)
    neck = 1.0 - G.smoothstep(0.17, config.NECK["end_s"], s)
    tail = G.smoothstep(0.70, 0.78, s)
    torso = np.clip(1.0 - neck - tail, 0, 1)
    out = {}
    for name, wts in (("VG_Neck", neck), ("VG_Torso", torso), ("VG_Tail", tail)):
        vg = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
        for val in np.unique(np.round(wts, 3)):
            idx = np.nonzero(np.round(wts, 3) == val)[0].tolist()
            if val > 0:
                vg.add(idx, float(val), "REPLACE")
        out[name] = int((wts > 0).sum())
    return out


def make_socket(name, coll_name, pos, T, U, B, size=0.3):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = size
    # X = creature's right (-B), Y = forward (-T), Z = up (U)  -> right-handed
    m = Matrix((Vector(-B), Vector(-T), Vector(U))).transposed().to_4x4()
    m.translation = Vector(pos)
    e.matrix_world = m
    bu.coll(coll_name).objects.link(e)
    return e


def sockets(trunk):
    made = {}
    p = config.NECK
    f = trunk.at([p["head_socket_s"]])
    made["SOCKET_Head"] = make_socket("SOCKET_Head", "03_NECK", f["centre"][0], f["T"][0], f["U"][0], f["B"][0])
    f = trunk.at([trunk.p["end_s"]])
    made["SOCKET_TailFin"] = make_socket("SOCKET_TailFin", "11_TAIL", f["centre"][0], f["T"][0], f["U"][0], f["B"][0])
    for label, s_g in (("Shoulder", trunk.p["shoulder_s"]), ("Hip", trunk.p["hip_s"])):
        f = trunk.at([s_g])
        for side, th in (("L", math.pi / 2 + 0.55), ("R", -(math.pi / 2 + 0.55))):
            sec = trunk.section([s_g], [th])[0, 0]
            pos = f["centre"][0] + f["B"][0] * sec[0] + f["U"][0] * sec[1]
            made[f"SOCKET_{label}_{side}"] = make_socket(f"SOCKET_{label}_{side}", "09_LEGS", pos,
                                                          f["T"][0], f["U"][0], f["B"][0], 0.2)
    return made


def ring_stats(ob):
    """Mean radius and tangent per trunk ring from the actual mesh."""
    me = ob.data
    R = ob["fsd_radial"]
    k0 = ob["fsd_front_cap_rings"]
    n = ob["fsd_body_rings"]
    co = bu.get_verts(me)[: ob["fsd_ring_count"] * R].reshape(-1, R, 3)[k0:k0 + n]
    cen = co.mean(1)
    rad = np.linalg.norm(co - cen[:, None, :], axis=2).mean(1)
    t = np.gradient(cen, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    return rad, t


def render_aligned(view, objs, out, samples):
    render.configure_cycles(samples)
    cam, res = compare.sheet_camera(view, scale=2)
    for ob in bpy.context.scene.objects:
        if ob.type in {"MESH", "CURVE"} and ob not in objs:
            ob["_was_hidden"] = ob.hide_render
            ob.hide_render = True
    render.render_camera(cam, out, res)
    for ob in bpy.context.scene.objects:
        if "_was_hidden" in ob:
            ob.hide_render = ob["_was_hidden"]
            del ob["_was_hidden"]
    return out


def comparison_sheet(aligned: dict, out):
    rows = []
    sheet = Image.open(config.REFERENCE_SHEET).convert("RGB")
    tmp = out.parent / "_tmp"
    tmp.mkdir(exist_ok=True)
    for view, p in aligned.items():
        x0, y0, x1, y1 = ref.REGIONS[view]
        crop = sheet.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.LANCZOS)
        mdl = Image.open(p).convert("RGB").resize(crop.size)
        blend = Image.blend(crop, mdl, 0.5)
        cp, bp = tmp / f"ref_{view}.png", tmp / f"blend_{view}.png"
        crop.save(cp)
        blend.save(bp)
        rows.append([(cp, f"Reference: {view}"), (p, f"Model (sheet-aligned): {view}"), (bp, "50 % overlay")])
    return render.contact_sheet(rows, out, "M03 – body blockout vs reference (sheet-aligned orthographic cameras)",
                                width=2600)


# --------------------------------------------------------------------------
def main():
    q = config.quality()
    with MilestoneRun("M03", "Serpentine body + neck transition (blockout checkpoint)",
                      ["02_body_generator.py", "03_neck_generator.py"]) as run:
        bu.open_blend(latest_blend("M03a"))
        render.create_preview_lights(config.TOTAL_LENGTH_M)   # refresh preview rig values
        ob = bpy.data.objects[BODY_NAME]
        trunk = anatomy.TrunkModel(body=json.loads(ob["fsd_params_body"]))
        maxd, nmoved = shape_neck(ob, trunk, config.NECK)
        ob["fsd_params_neck"] = json.dumps(config.NECK)
        run.metrics["neck shaping"] = f"{nmoved} verts moved, max displacement {maxd:.3f} m"
        vg = vertex_groups(ob)
        run.metrics["vertex groups"] = vg
        socks = sockets(trunk)
        run.metrics["sockets"] = ", ".join(socks)

        # ---- validation
        run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True))
        run.add_checks(validate.mesh_checks(ob, watertight=True, intersections=True, evaluated=True))
        rad, tan = ring_stats(ob)
        run.add_checks(validate.ring_continuity_checks(f"{BODY_NAME} (after neck shaping)", rad, tan))
        run.add_checks([validate.uv_check(ob), validate.materials_check(ob)])
        run.add_checks([check("Region vertex groups", "PASS" if all(vg.values()) else "FAIL",
                              ", ".join(f"{k}: {v} verts" for k, v in vg.items()))])
        run.add_checks([check("Attachment sockets", "PASS" if len(socks) == 6 else "FAIL", ", ".join(socks))])
        # neck socket must sit inside the trunk (head will attach here)
        bm_inside = trunk.at([config.NECK["head_socket_s"]])
        run.add_checks([check("Head socket inside neck volume", "PASS"
                              if bm_inside["half_depth"][0] > 0.2 else "FAIL",
                              f"neck half-depth at socket {bm_inside['half_depth'][0]:.3f} m")])

        # ---- reference comparison
        out = config.DIRS["renders"] / "M03"
        results, cchecks, overlays = compare.compare_trunk([ob], out, tag="M03")
        run.add_checks(cchecks)
        run.metrics["reference comparison"] = results
        for p in overlays.values():
            run.output("comparison", p)
        (config.DIRS["reports"] / "M03_reference_comparison.json").write_text(json.dumps(results, indent=2))
        run.note("Comparison covers the measurable trunk only (s 0.17–0.74, limb zones excluded); head, fins, "
                 "spikes and limbs are later milestones, so no whole-creature accuracy claim is made.")

        bu.save_milestone(run, "body_blockout")

        # ---- previews
        views = list(render.VIEWS)
        paths = render.render_views(views, out, "M03_body", samples=q["render_samples"],
                                    objs=[ob], res_scale=q["render_res"] * 0.8)
        for p in paths.values():
            run.output("render", p)
        L = render.LABELS
        sheet = render.contact_sheet(
            [[(paths["left"], L["left"])], [(paths["right"], L["right"])],
             [(paths["top"], L["top"])], [(paths["bottom"], L["bottom"])],
             [(paths["front"], L["front"]), (paths["back"], L["back"]),
              (paths["three_quarter_front_left"], L["three_quarter_front_left"]),
              (paths["three_quarter_back_right"], L["three_quarter_back_right"])]],
            out / "M03_preview_sheet.png", "M03 – serpentine body blockout (clay, Cycles)", width=2400)
        run.output("preview", sheet)
        aligned = {}
        for view in ("side_left", "top", "bottom"):
            aligned[view] = render_aligned(view, [ob], out / f"M03_aligned_{view}.png", 24)
        cs = comparison_sheet(aligned, out / "M03_reference_comparison_sheet.png")
        run.output("preview", cs)
        run.add_checks([check("Preview renders written", "PASS" if all(p.exists() for p in paths.values()) else "FAIL",
                              f"{len(paths)} views + comparison sheet")])


if __name__ == "__main__":
    main()
