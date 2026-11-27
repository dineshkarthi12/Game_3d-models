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

## M04 – Head generation
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T11:56:35 (67.84 s, quality `standard`)  
* **Scripts:** 04_head_generator.py  
* **Project file:** `project/FSD_M04_head_v001.blend`  
* **Checks:** 87 PASS / 0 WARNING / 6 FAIL  
* head objects: 10  
* head faces (base): 14948  
* spikes: 19  
* **Assumptions:**
  * Head proportions come from the side profile and head-detail panels; the skull width (~0.47 m) is taken from the top view without cheek fins.

## M03a – Serpentine body – continuous trunk
* **Status:** COMPLETE_WITH_WARNINGS  
* **Finished:** 2026-11-26T11:58:29 (7.32 s, quality `standard`)  
* **Scripts:** 02_body_generator.py  
* **Project file:** `project/FSD_M03a_trunk_v002.blend`  
* **Checks:** 19 PASS / 1 WARNING / 0 FAIL  
* trunk arc length m: 10.31  
* max half depth m: 0.577  
* max half width m: 0.3  
* max depth at s: 0.167  
* neck half depth m: 0.42  
* tail half depth m: 0.025  
* centre height range m: [1.141, 1.551]  
* rings x radial: 280 x 32 (+8 cap rings)  
* base faces: 9248  
* **Assumptions:**
  * Neck section (s < 0.17) is hidden behind neck fins on the sheet: blended (C1 Hermite) to a head-junction anchor of 0.42 m half-depth x 0.21 m half-width (tall, narrow skull base).
  * Tail core inside the fan fin (s > 0.74) is not measurable: tapered to 0.025 m at s = 0.975.

## M03 – Serpentine body + neck transition (blockout checkpoint)
* **Status:** COMPLETE_WITH_WARNINGS  
* **Finished:** 2026-11-26T12:00:04 (94.44 s, quality `standard`)  
* **Scripts:** 02_body_generator.py, 03_neck_generator.py  
* **Project file:** `project/FSD_M03_body_blockout_v003.blend`  
* **Checks:** 25 PASS / 1 WARNING / 0 FAIL  
* neck shaping: 1553 verts moved, max displacement 0.041 m  
* vertex groups: {'VG_Neck': 1121, 'VG_Torso': 5024, 'VG_Tail': 4225}  
* sockets: SOCKET_Head, SOCKET_TailFin, SOCKET_Shoulder_L, SOCKET_Shoulder_R, SOCKET_Hip_L, SOCKET_Hip_R  
* reference comparison: {'side': {'columns': 340, 'dorsal_mae_m': 0.0317, 'dorsal_max_m': 0.1584, 'belly_mae_m': 0.0153, 'belly_max_m': 0.054, 'band_iou': 0.9449}, 'bottom': {'columns': 308, 'width_mae_m': 0.0082, 'width_max_m': 0.0247, 'width_mean_rel_error': -0.0059}}  
* **Notes:**
  * Comparison covers the measurable trunk only (s 0.17–0.74, limb zones excluded); head, fins, spikes and limbs are later milestones, so no whole-creature accuracy claim is made.

## M04 – Head generation
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:01:10 (66.05 s, quality `standard`)  
* **Scripts:** 04_head_generator.py  
* **Project file:** `project/FSD_M04_head_v002.blend`  
* **Checks:** 91 PASS / 0 WARNING / 2 FAIL  
* head objects: 10  
* head faces (base): 17320  
* spikes: 21 placed, 10 skipped (base overlap)  
* **Assumptions:**
  * Head proportions come from the side profile and head-detail panels; the skull width (~0.47 m) is taken from the top view without cheek fins.

## M03a – Serpentine body – continuous trunk
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:03:03 (7.32 s, quality `standard`)  
* **Scripts:** 02_body_generator.py  
* **Project file:** `project/FSD_M03a_trunk_v003.blend`  
* **Checks:** 20 PASS / 0 WARNING / 0 FAIL  
* trunk arc length m: 10.303  
* max half depth m: 0.577  
* max half width m: 0.3  
* max depth at s: 0.167  
* neck half depth m: 0.42  
* tail half depth m: 0.025  
* centre height range m: [1.141, 1.551]  
* rings x radial: 280 x 32 (+8 cap rings)  
* base faces: 9248  
* **Assumptions:**
  * Neck section (s < 0.17) is hidden behind neck fins on the sheet: blended (C1 Hermite) to a head-junction anchor of 0.42 m half-depth x 0.21 m half-width (tall, narrow skull base).
  * Tail core inside the fan fin (s > 0.74) is not measurable: tapered to 0.025 m at s = 0.975.

## M03 – Serpentine body + neck transition (blockout checkpoint)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:04:36 (93.01 s, quality `standard`)  
* **Scripts:** 02_body_generator.py, 03_neck_generator.py  
* **Project file:** `project/FSD_M03_body_blockout_v004.blend`  
* **Checks:** 26 PASS / 0 WARNING / 0 FAIL  
* neck shaping: 1548 verts moved, max displacement 0.042 m  
* vertex groups: {'VG_Neck': 1121, 'VG_Torso': 5024, 'VG_Tail': 4225}  
* sockets: SOCKET_Head, SOCKET_TailFin, SOCKET_Shoulder_L, SOCKET_Shoulder_R, SOCKET_Hip_L, SOCKET_Hip_R  
* reference comparison: {'side': {'columns': 340, 'dorsal_mae_m': 0.0421, 'dorsal_max_m': 0.2074, 'belly_mae_m': 0.0244, 'belly_max_m': 0.1123, 'band_iou': 0.923}, 'bottom': {'columns': 308, 'width_mae_m': 0.0082, 'width_max_m': 0.0247, 'width_mean_rel_error': -0.0059}}  
* **Notes:**
  * Comparison covers the measurable trunk only (s 0.17–0.74, limb zones excluded); head, fins, spikes and limbs are later milestones, so no whole-creature accuracy claim is made.

## M04 – Head generation
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:05:43 (66.67 s, quality `standard`)  
* **Scripts:** 04_head_generator.py  
* **Project file:** `project/FSD_M04_head_v003.blend`  
* **Checks:** 93 PASS / 0 WARNING / 0 FAIL  
* head objects: 10  
* head faces (base): 17160  
* spikes: 20 placed, 11 skipped (base overlap)  
* **Assumptions:**
  * Head proportions come from the side profile and head-detail panels; the skull width (~0.47 m) is taken from the top view without cheek fins.

## M04 – Head generation
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:07:17 (63.89 s, quality `standard`)  
* **Scripts:** 04_head_generator.py  
* **Project file:** `project/FSD_M04_head_v004.blend`  
* **Checks:** 93 PASS / 0 WARNING / 0 FAIL  
* head objects: 10  
* head faces (base): 17552  
* spikes: 19 placed, 18 skipped (base overlap)  
* **Assumptions:**
  * Head proportions come from the side profile and head-detail panels; the skull width (~0.47 m) is taken from the top view without cheek fins.

## M04 – Head generation
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:08:38 (64.61 s, quality `standard`)  
* **Scripts:** 04_head_generator.py  
* **Project file:** `project/FSD_M04_head_v005.blend`  
* **Checks:** 93 PASS / 0 WARNING / 0 FAIL  
* head objects: 10  
* head faces (base): 17552  
* spikes: 19 placed, 18 skipped (base overlap)  
* **Assumptions:**
  * Head proportions come from the side profile and head-detail panels; the skull width (~0.47 m) is taken from the top view without cheek fins.

## M05 – Teeth and whiskers
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:11:32 (89.05 s, quality `standard`)  
* **Scripts:** 05_facial_details.py  
* **Project file:** `project/FSD_M05_facial_details_v001.blend`  
* **Checks:** 31 PASS / 0 WARNING / 0 FAIL  
* teeth: upper 37 (+3 rejected for overlap), lower 32 (+4 rejected)  
* whiskers: 6  

## M06 – Individual scale generation
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:15:15 (101.35 s, quality `standard`)  
* **Scripts:** 06_scale_generator.py  
* **Project file:** `project/FSD_M06_scales_v001.blend`  
* **Checks:** 51 PASS / 0 WARNING / 10 FAIL  
* scales per region: {'Neck': 358, 'Flank_R': 741, 'Back': 741, 'Flank_L': 741, 'Tail': 1298, 'Head': 788}  
* total scales: 4667  
* scale faces: 149344  
* dropped (inside head): 0  
* head scales skipped near eyes/armour/spikes: 331  
* trunk scale length (m): 0.045–0.116  
* scale area / scaled-skin area: 1.279  
* faces per colour material: {'MAT_Scale_MetallicBlue': 61024, 'MAT_Scale_Turquoise': 37152, 'MAT_Scale_Gold': 21696, 'MAT_Scale_DarkNavy': 29472}  
* **Notes:**
  * Scales are embedded ~0.035 x length at their front edge (attached to the skin), so contact with DRG_Body / DRG_Head_Skull is intentional and not counted as an intersection.

## M06 – Individual scale generation
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:17:43 (100.16 s, quality `standard`)  
* **Scripts:** 06_scale_generator.py  
* **Project file:** `project/FSD_M06_scales_v002.blend`  
* **Checks:** 60 PASS / 0 WARNING / 1 FAIL  
* scales per region: {'Neck': 423, 'Flank_R': 968, 'Back': 626, 'Flank_L': 968, 'Tail': 1416, 'Head': 844}  
* total scales: 5245  
* scale faces: 167840  
* dropped (inside head): 0  
* head scales skipped near eyes/armour/spikes: 359  
* trunk scale length (m): 0.045–0.116  
* scale area / scaled-skin area: 1.406  
* faces per colour material: {'MAT_Scale_MetallicBlue': 74272, 'MAT_Scale_Turquoise': 43744, 'MAT_Scale_Gold': 18752, 'MAT_Scale_DarkNavy': 31072}  
* **Notes:**
  * Scales are embedded ~0.035 x length at their front edge (attached to the skin), so contact with DRG_Body / DRG_Head_Skull is intentional and not counted as an intersection.

## M06 – Individual scale generation
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:19:37 (97.89 s, quality `standard`)  
* **Scripts:** 06_scale_generator.py  
* **Project file:** `project/FSD_M06_scales_v003.blend`  
* **Checks:** 61 PASS / 0 WARNING / 0 FAIL  
* head scales rejected (curvature overlap): 16  
* scales per region: {'Neck': 423, 'Flank_R': 968, 'Back': 626, 'Flank_L': 968, 'Tail': 1416, 'Head': 828}  
* total scales: 5229  
* scale faces: 167328  
* dropped (inside head): 0  
* head scales skipped near eyes/armour/spikes: 359  
* trunk scale length (m): 0.045–0.116  
* scale area / scaled-skin area: 1.406  
* faces per colour material: {'MAT_Scale_MetallicBlue': 74272, 'MAT_Scale_Turquoise': 43680, 'MAT_Scale_Gold': 18304, 'MAT_Scale_DarkNavy': 31072}  
* **Notes:**
  * Scales are embedded ~0.035 x length at their front edge (attached to the skin), so contact with DRG_Body / DRG_Head_Skull is intentional and not counted as an intersection.

## M07 – Belly armour plates
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:21:58 (76.39 s, quality `standard`)  
* **Scripts:** 07_belly_armour.py  
* **Project file:** `project/FSD_M07_belly_armour_v001.blend`  
* **Checks:** 11 PASS / 1 WARNING / 1 FAIL  
* plates: 108  
* plate length (m): 0.060–0.124  
* plate faces: 10800  

## M07 – Belly armour plates
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:23:26 (77.38 s, quality `standard`)  
* **Scripts:** 07_belly_armour.py  
* **Project file:** `project/FSD_M07_belly_armour_v002.blend`  
* **Checks:** 13 PASS / 0 WARNING / 0 FAIL  
* plates: 78  
* plate length (m): 0.080–0.174  
* plate faces: 7800  

## M07 – Belly armour plates
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:25:00 (80.27 s, quality `standard`)  
* **Scripts:** 07_belly_armour.py  
* **Project file:** `project/FSD_M07_belly_armour_v003.blend`  
* **Checks:** 12 PASS / 0 WARNING / 1 FAIL  
* plates: 78  
* plate length (m): 0.080–0.174  
* plate faces: 10920  

## M07 – Belly armour plates
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:26:24 (77.17 s, quality `standard`)  
* **Scripts:** 07_belly_armour.py  
* **Project file:** `project/FSD_M07_belly_armour_v004.blend`  
* **Checks:** 13 PASS / 0 WARNING / 0 FAIL  
* plates: 77  
* plate length (m): 0.080–0.174  
* plate faces: 10780  

## M08 – Dorsal spikes
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:29:03 (86.76 s, quality `standard`)  
* **Scripts:** 08_spine_generator.py  
* **Project file:** `project/FSD_M08_dorsal_spikes_v001.blend`  
* **Checks:** 46 PASS / 0 WARNING / 1 FAIL  
* spikes per category: {'Neck': 2, 'UpperTorso': 3, 'MidBody': 3, 'Tail': 7}  
* rejected (would intersect a neighbour): 32  
* spike length range (m): 0.18–1.01  
* dorsal scales removed under spike roots: {'DRG_Scales_Neck': 18, 'DRG_Scales_Back': 135, 'DRG_Scales_Tail': 9}  
* crest height MAE vs reference envelope (m): 0.052  

## M08 – Dorsal spikes
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:31:00 (83.99 s, quality `standard`)  
* **Scripts:** 08_spine_generator.py  
* **Project file:** `project/FSD_M08_dorsal_spikes_v002.blend`  
* **Checks:** 47 PASS / 0 WARNING / 0 FAIL  
* spikes per category: {'Neck': 4, 'UpperTorso': 5, 'MidBody': 10, 'Tail': 19}  
* rejected (would intersect a neighbour): 17  
* spike length range (m): 0.06–0.84  
* dorsal scales removed under spike roots: {'DRG_Scales_Neck': 24, 'DRG_Scales_Back': 136, 'DRG_Scales_Tail': 9}  
* crest height MAE vs reference envelope (m): 0.052  

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:35:09 (93.36 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v001.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 840}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:36:47 (87.6 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v002.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 840}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:38:19 (85.61 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v003.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 840}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:40:16 (88.46 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v004.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:41:54 (86.5 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v005.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:43:34 (86.75 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v006.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:45:17 (88.16 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v007.blend`  
* **Checks:** 53 PASS / 0 WARNING / 0 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12512, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:46:58 (86.42 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v008.blend`  
* **Checks:** 48 PASS / 0 WARNING / 5 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 13120, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:48:47 (92.72 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v009.blend`  
* **Checks:** 53 PASS / 0 WARNING / 0 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12448, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T12:51:54 (89.09 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v010.blend`  
* **Checks:** 53 PASS / 0 WARNING / 0 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12448, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M10 – Four limbs (legs, feet, toes, limb scales)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:54:29 (154.71 s, quality `standard`)  
* **Scripts:** 10_limb_generator.py  
* **Project file:** `project/FSD_M10_limbs_v001.blend`  
* **Checks:** 36 PASS / 0 WARNING / 4 FAIL  
* limb scales: 2057  
* limb scales removed (touching body scales/plates/fins): 137  
* limb joint heights (m): {'Front_L': [1.01, 0.63, 0.44, 0.38], 'Front_R': [1.01, 0.63, 0.44, 0.38], 'Rear_L': [1.03, 0.64, 0.44, 0.37], 'Rear_R': [1.03, 0.64, 0.44, 0.37]}  
* **Assumptions:**
  * Limb proportions follow the side view (short legs, feet ~0.4 m above ground, webbed fins below); elbow/knee angles are a neutral swimming pose.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:56:50 (89.06 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v011.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12448, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T12:58:27 (87.96 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v012.blend`  
* **Checks:** 52 PASS / 0 WARNING / 1 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12448, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M09 – Fins (neck, dorsal, side, leg, tail fan)
* **Status:** COMPLETE  
* **Finished:** 2026-11-26T13:00:07 (87.22 s, quality `standard`)  
* **Scripts:** 09_fin_generator.py  
* **Project file:** `project/FSD_M09_fins_v013.blend`  
* **Checks:** 53 PASS / 0 WARNING / 0 FAIL  
* faces removed from pierced scales/spikes: {'DRG_Scales_Neck': 832, 'DRG_Scales_Tail': 12448, 'DRG_Spikes_Tail': 648, 'DRG_Belly_Plates': 140}  
* **Assumptions:**
  * The sheet's tail fan reads as fan lobes in both the side and the top view; it is modelled as four lobes (dorsal, ventral, left, right).  The dorsal lobe doubles as the tail-base dorsal fin.
  * Leg fins are attached to the limb skeleton (dragon_lib.limbs) that M10 uses for the leg meshes.

## M10 – Four limbs (legs, feet, toes, limb scales)
* **Status:** FAILED_VALIDATION  
* **Finished:** 2026-11-26T13:02:47 (159.58 s, quality `standard`)  
* **Scripts:** 10_limb_generator.py  
* **Project file:** `project/FSD_M10_limbs_v002.blend`  
* **Checks:** 37 PASS / 0 WARNING / 3 FAIL  
* limb scales rejected (curvature overlap): 2  
* limb scales: 1662  
* limb scales removed (touching body scales/plates/fins): 92  
* body faces removed at limb roots: {'DRG_Scales_Flank_L': 1152, 'DRG_Scales_Flank_R': 1152, 'DRG_Belly_Plates': 560}  
* limb joint heights (m): {'Front_L': [1.13, 0.78, 0.59, 0.53], 'Front_R': [1.13, 0.78, 0.59, 0.53], 'Rear_L': [1.12, 0.77, 0.56, 0.5], 'Rear_R': [1.12, 0.77, 0.56, 0.5]}  
* **Assumptions:**
  * Limb proportions follow the side view (short legs, feet ~0.4 m above ground, webbed fins below); elbow/knee angles are a neutral swimming pose.
