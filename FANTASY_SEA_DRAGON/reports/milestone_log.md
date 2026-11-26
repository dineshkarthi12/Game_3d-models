# Fantasy Sea Dragon – Milestone Log

## M01a – Environment detection & directories
* **Status:** COMPLETE_WITH_WARNINGS  
* **Finished:** 2026-11-26T11:36:58 (0.63 s, quality `standard`)  
* **Scripts:** 00_environment_setup.py  
* **Project file:** `None`  
* **Checks:** 16 PASS / 1 WARNING / 0 FAIL  
* blender: 4.5.4 LTS  
* python: 3.11.18  
* cpu_count: 4  
* **Notes:**
  * No OpenGL/EGL context: Workbench and EEVEE cannot render here, so every preview and final render uses Cycles (CPU + OpenImageDenoise).

## M01 – Project initialization
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T11:37:03 (3.91 s, quality `standard`)  
* **Scripts:** 00_environment_setup.py, 01_project_setup.py  
* **Project file:** `project/FSD_M01_init_v001.blend`  
* **Checks:** 7 PASS / 0 WARNING / 0 FAIL  

## M02 – Reference system
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T11:37:11 (7.28 s, quality `standard`)  
* **Scripts:** 01_project_setup.py  
* **Project file:** `project/FSD_M02_references_v001.blend`  
* **Checks:** 13 PASS / 0 WARNING / 0 FAIL  
* max trunk depth (m): 1.176  
* max trunk width (m): 0.584  
* mean depth/width ratio: 1.85  
* **Assumptions:**
  * The sheet is a design reference, not a calibrated scan: every orthographic view is calibrated independently (snout tip / tail-fin tip landmarks) and normalised to the total length L.
  * Side view length 1029 px vs top/bottom 1009–1011 px (1.8 % discrepancy) – resolved by per-view normalisation.
  * Ground (Z = 0) = lowest limb-fin tip on the side view; the sheet shows a swimming pose with hanging webbed feet.
  * Front/back views are scaled by matching the head's vertical extent to the side view (approximate, ±10 %).
  * 3/4 views and head/detail panels are perspective or close-up images: kept as review crops, not projected.
* **Notes:**
  * Top-view width (~22 px) under-reads because the dark flank scales merge with the background; the bright ventral view (~45 px) is used for lateral width.

## M03a – Serpentine body – continuous trunk
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T11:37:18 (7.18 s, quality `standard`)  
* **Scripts:** 02_body_generator.py  
* **Project file:** `project/FSD_M03a_trunk_v001.blend`  
* **Checks:** 20 PASS / 0 WARNING / 0 FAIL  
* trunk arc length m: 10.542  
* max half depth m: 0.583  
* max half width m: 0.3  
* max depth at s: 0.163  
* neck half depth m: 0.44  
* tail half depth m: 0.025  
* centre height range m: [1.141, 1.551]  
* rings x radial: 280 x 32 (+8 cap rings)  
* base faces: 9248  
* **Assumptions:**
  * Neck section (s < 0.17) is hidden behind neck fins on the sheet: blended (C1 Hermite) to a head-junction anchor of 0.44 m half-depth x 0.24 m half-width (tall, narrow skull base).
  * Tail core inside the fan fin (s > 0.74) is not measurable: tapered to 0.025 m at s = 0.975.

## M03 – Serpentine body + neck transition (blockout checkpoint)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T11:38:53 (94.41 s, quality `standard`)  
* **Scripts:** 02_body_generator.py, 03_neck_generator.py  
* **Project file:** `project/FSD_M03_body_blockout_v001.blend`  
* **Checks:** 26 PASS / 0 WARNING / 0 FAIL  
* neck shaping: 1327 verts moved, max displacement 0.054 m  
* vertex groups: {'VG_Neck': 1249, 'VG_Torso': 4928, 'VG_Tail': 4193}  
* sockets: SOCKET_Head, SOCKET_TailFin, SOCKET_Shoulder_L, SOCKET_Shoulder_R, SOCKET_Hip_L, SOCKET_Hip_R  
* reference comparison: {'side': {'columns': 340, 'dorsal_mae_m': 0.0315, 'dorsal_max_m': 0.1628, 'belly_mae_m': 0.0156, 'belly_max_m': 0.0306, 'band_iou': 0.9448}, 'bottom': {'columns': 308, 'width_mae_m': 0.0082, 'width_max_m': 0.0247, 'width_mean_rel_error': -0.0059}}  
* **Notes:**
  * Comparison covers the measurable trunk only (s 0.17–0.74, limb zones excluded); head, fins, spikes and limbs are later milestones, so no whole-creature accuracy claim is made.

## M03 – Serpentine body + neck transition (blockout checkpoint)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T11:40:51 (99.38 s, quality `standard`)  
* **Scripts:** 02_body_generator.py, 03_neck_generator.py  
* **Project file:** `project/FSD_M03_body_blockout_v002.blend`  
* **Checks:** 26 PASS / 0 WARNING / 0 FAIL  
* neck shaping: 1633 verts moved, max displacement 0.054 m  
* vertex groups: {'VG_Neck': 1249, 'VG_Torso': 4928, 'VG_Tail': 4193}  
* sockets: SOCKET_Head, SOCKET_TailFin, SOCKET_Shoulder_L, SOCKET_Shoulder_R, SOCKET_Hip_L, SOCKET_Hip_R  
* reference comparison: {'side': {'columns': 340, 'dorsal_mae_m': 0.0315, 'dorsal_max_m': 0.1628, 'belly_mae_m': 0.0148, 'belly_max_m': 0.0306, 'band_iou': 0.9456}, 'bottom': {'columns': 308, 'width_mae_m': 0.0082, 'width_max_m': 0.0247, 'width_mean_rel_error': -0.0059}}  
* **Notes:**
  * Comparison covers the measurable trunk only (s 0.17–0.74, limb zones excluded); head, fins, spikes and limbs are later milestones, so no whole-creature accuracy claim is made.
