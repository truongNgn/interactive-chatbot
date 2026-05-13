"""
Blender background script — add ARKit-compatible shape keys to fashion_girl_asian_girl.glb.

Strategy:
  - Import GLB
  - Find the face/head mesh (the one with the most vertices in the upper body area)
  - Add shape keys: jawOpen, mouthSmile_L/R, mouthFrown_L/R, eyeWide_L/R, browInnerUp, etc.
  - Each shape key deforms vertices in the relevant anatomical region
  - Export back to GLB

Run:
  blender --background --python add_shape_keys.py
"""

import sys
import math
import bpy
import bmesh
from mathutils import Vector

GLB_IN  = r"D:\Coder-IT\AI\interactive-chatbot\frontend\public\models\fashion_girl_asian_girl.glb"
GLB_OUT = r"D:\Coder-IT\AI\interactive-chatbot\frontend\public\models\fashion_girl_asian_girl.glb"

# ── 1. Clear scene ─────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ── 2. Import ──────────────────────────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=GLB_IN)
print(f"\n[OK] Imported: {GLB_IN}")

# ── 3. Collect all mesh objects ────────────────────────────────────────────────
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
print(f"[INFO] Mesh objects: {len(meshes)}")
for m in meshes:
    bb = m.bound_box
    y_vals = [m.matrix_world @ Vector(v) for v in bb]
    y_max = max(v.z for v in y_vals)
    vc = len(m.data.vertices)
    print(f"  '{m.name}': verts={vc}, z_max={y_max:.3f}")

# ── 4. Pick the face mesh: highest z_max (head is on top) ─────────────────────
def get_world_z_max(obj):
    return max((obj.matrix_world @ Vector(v.co)).z for v in obj.data.vertices)

# Sort by z_max descending, pick the one with most vertices among top candidates
sorted_by_z = sorted(meshes, key=get_world_z_max, reverse=True)
# The face mesh is typically the topmost mesh
face_mesh = sorted_by_z[0] if sorted_by_z else None

if face_mesh is None:
    print("[ERROR] No mesh found, aborting.")
    sys.exit(1)

print(f"\n[INFO] Selected face mesh: '{face_mesh.name}' (verts={len(face_mesh.data.vertices)})")

# ── 5. Enter edit mode to measure geometry bounds ─────────────────────────────
bpy.context.view_layer.objects.active = face_mesh
face_mesh.select_set(True)

# Get world-space vertex positions
verts_ws = [(face_mesh.matrix_world @ v.co) for v in face_mesh.data.vertices]
if not verts_ws:
    print("[ERROR] No vertices, aborting.")
    sys.exit(1)

z_all = [v.z for v in verts_ws]
y_all = [v.y for v in verts_ws]
x_all = [v.x for v in verts_ws]

z_min, z_max = min(z_all), max(z_all)
z_range = z_max - z_min
x_min, x_max = min(x_all), max(x_all)
y_min, y_max = min(y_all), max(y_all)

print(f"  Bounds: Z=[{z_min:.3f}, {z_max:.3f}], X=[{x_min:.3f}, {x_max:.3f}], Y=[{y_min:.3f}, {y_max:.3f}]")

# Jaw area: lower 25% of Z range, middle X
z_jaw_threshold  = z_min + z_range * 0.25   # below this → jaw vertices
z_mouth_top      = z_min + z_range * 0.45   # mouth center
z_eye_bottom     = z_min + z_range * 0.60   # eye lower bound
z_eye_top        = z_min + z_range * 0.80   # eye upper bound
z_brow_bottom    = z_min + z_range * 0.72   # brow
x_mid            = (x_min + x_max) / 2

print(f"  Jaw Z < {z_jaw_threshold:.3f}, Mouth Z = [{z_jaw_threshold:.3f}, {z_mouth_top:.3f}]")

# ── 6. Ensure shape key basis exists ──────────────────────────────────────────
mesh_data = face_mesh.data
if mesh_data.shape_keys is None:
    face_mesh.shape_key_add(name='Basis', from_mix=False)

basis_key = mesh_data.shape_keys.reference_key

def add_shape_key(name: str, deltas: dict[int, Vector]):
    """Add a shape key with given vertex index → delta mapping."""
    existing = mesh_data.shape_keys.key_blocks.get(name)
    if existing:
        mesh_data.shape_keys.key_blocks.remove(existing)

    sk = face_mesh.shape_key_add(name=name, from_mix=False)
    sk.value = 0.0

    for vi, delta in deltas.items():
        # Shape key data is in local space → convert delta from world to local
        local_delta = face_mesh.matrix_world.inverted().to_3x3() @ delta
        sk.data[vi].co = basis_key.data[vi].co + local_delta

    return sk

# ── 7. Compute shape key deltas ───────────────────────────────────────────────
n = len(face_mesh.data.vertices)

jaw_verts   = {}   # jawOpen: move jaw verts downward
smile_l     = {}   # mouthSmile_L
smile_r     = {}   # mouthSmile_R
frown_l     = {}   # mouthFrown_L
frown_r     = {}   # mouthFrown_R
eye_wide_l  = {}   # eyeWide_L
eye_wide_r  = {}   # eyeWide_R
brow_up     = {}   # browInnerUp

JAW_DROP    = 0.012   # world units — how far jaw drops
SMILE_DIST  = 0.008
FROWN_DIST  = 0.006
EYE_WIDE    = 0.004
BROW_RAISE  = 0.005

for i, wp in enumerate(verts_ws):
    x, y, z = wp.x, wp.y, wp.z

    # ── jawOpen: jaw and chin area ──────────────────────────────────────────
    if z < z_jaw_threshold:
        # Weight by how far below threshold (more movement at bottom)
        t = (z_jaw_threshold - z) / (z_jaw_threshold - z_min)
        t = max(0.0, min(1.0, t))
        jaw_verts[i] = Vector((0, 0, -JAW_DROP * t))

    # ── mouthSmile: vertices in mouth horizontal band ──────────────────────
    if z_jaw_threshold < z < z_mouth_top:
        t = (z - z_jaw_threshold) / (z_mouth_top - z_jaw_threshold)
        t = 0.5 - abs(t - 0.5)   # peak in middle of band
        if x < x_mid:   # left side
            smile_l[i] = Vector((-SMILE_DIST * t, 0, SMILE_DIST * t * 0.5))
            frown_l[i]  = Vector((-FROWN_DIST * t, 0, -FROWN_DIST * t))
        else:            # right side
            smile_r[i] = Vector((SMILE_DIST * t, 0, SMILE_DIST * t * 0.5))
            frown_r[i]  = Vector((FROWN_DIST * t, 0, -FROWN_DIST * t))

    # ── eyeWide: upper lid area ────────────────────────────────────────────
    if z_eye_bottom < z < z_eye_top:
        t = 1.0 - abs((z - (z_eye_bottom + z_eye_top) / 2) / ((z_eye_top - z_eye_bottom) / 2))
        t = max(0.0, t)
        if x < x_mid:
            eye_wide_l[i] = Vector((0, 0, EYE_WIDE * t))
        else:
            eye_wide_r[i] = Vector((0, 0, EYE_WIDE * t))

    # ── browInnerUp: brow area center ─────────────────────────────────────
    if z > z_brow_bottom and abs(x - x_mid) < (x_max - x_min) * 0.3:
        t = (z - z_brow_bottom) / (z_max - z_brow_bottom)
        brow_up[i] = Vector((0, 0, BROW_RAISE * t))

# ── 8. Create shape keys ───────────────────────────────────────────────────────
print("\n[INFO] Adding shape keys...")

shapes = {
    'jawOpen':       jaw_verts,
    'mouthSmile_L':  smile_l,
    'mouthSmile_R':  smile_r,
    'mouthFrown_L':  frown_l,
    'mouthFrown_R':  frown_r,
    'eyeWide_L':     eye_wide_l,
    'eyeWide_R':     eye_wide_r,
    'browInnerUp':   brow_up,
    # Mouth open variants (use jaw as proxy)
    'mouthLowerDown_L': {k: Vector((v.x * 0.5, v.y, v.z * 0.7)) for k, v in jaw_verts.items()},
    'mouthLowerDown_R': {k: Vector((v.x * 0.5, v.y, v.z * 0.7)) for k, v in jaw_verts.items()},
    'mouthFunnel':      {k: Vector((0, v.z * -0.3, v.z * 0.5)) for k, v in jaw_verts.items()},
    'mouthPucker':      {k: Vector((0, v.z * -0.4, 0)) for k, v in jaw_verts.items()},
}

for name, deltas in shapes.items():
    if deltas:
        add_shape_key(name, deltas)
        print(f"  + {name}: {len(deltas)} verts")
    else:
        print(f"  ! {name}: no verts matched (bounds may differ)")

# ── 9. Export to GLB ───────────────────────────────────────────────────────────
print(f"\n[INFO] Exporting to: {GLB_OUT}")
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    use_selection=False,
    export_morph=True,          # include shape keys as morph targets
    export_morph_normal=False,
    export_texcoords=True,
    export_normals=True,
    export_materials='EXPORT',
    export_animations=True,
)
print("[OK] Export complete.")
print(f"\n[DONE] fashion_girl_asian_girl.glb now has {len(shapes)} ARKit shape keys.")
