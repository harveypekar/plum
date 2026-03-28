"""Generate door and door frame .obj mesh files for Unity.

Dimensions (meters):
- Door:  0.9 wide x 2.0 tall x 0.04 thick
- Frame: inner opening 0.92 wide x 2.02 tall, jamb width 0.08, depth 0.1
- Small gap (0.01m per side) so door fits inside frame

Door origin is at the hinge edge (left side, bottom) so it swings correctly.
Frame origin is at the bottom-center of the opening.
"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def write_obj(filepath, vertices, normals, uvs, faces, name="mesh"):
    """Write an OBJ file. faces is list of (vi, vti, vni) index tuples (1-based)."""
    with open(filepath, "w", newline="\n") as f:
        f.write(f"# {name}\n")
        f.write(f"o {name}\n\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        f.write("\n")
        for vt in uvs:
            f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
        f.write("\n")
        for vn in normals:
            f.write(f"vn {vn[0]:.6f} {vn[1]:.6f} {vn[2]:.6f}\n")
        f.write("\n")
        for face in faces:
            parts = " ".join(f"{vi}/{vti}/{vni}" for vi, vti, vni in face)
            f.write(f"f {parts}\n")


def box(x0, y0, z0, x1, y1, z1, v_offset=0):
    """Generate vertices, normals, uvs, and triangulated faces for an axis-aligned box.
    Returns (vertices, normals, uvs, faces) with 1-based indices offset by v_offset.
    """
    # 8 corners
    verts = [
        (x0, y0, z1),  # 0: front-bottom-left
        (x1, y0, z1),  # 1: front-bottom-right
        (x1, y1, z1),  # 2: front-top-right
        (x0, y1, z1),  # 3: front-top-left
        (x0, y0, z0),  # 4: back-bottom-left
        (x1, y0, z0),  # 5: back-bottom-right
        (x1, y1, z0),  # 6: back-top-right
        (x0, y1, z0),  # 7: back-top-left
    ]

    # 6 face normals
    norms = [
        (0, 0, 1),   # front  (1)
        (0, 0, -1),  # back   (2)
        (1, 0, 0),   # right  (3)
        (-1, 0, 0),  # left   (4)
        (0, 1, 0),   # top    (5)
        (0, -1, 0),  # bottom (6)
    ]

    # Simple UVs per face: 4 corners
    uvs = [
        (0, 0),  # 1
        (1, 0),  # 2
        (1, 1),  # 3
        (0, 1),  # 4
    ]

    vo = v_offset  # vertex offset (0-based converted to 1-based below)
    no = v_offset  # normal offset
    to = v_offset  # uv offset

    # Each face: 2 triangles (clockwise winding for Unity)
    # face indices are (vertex_1based, uv_1based, normal_1based)
    # For each of 6 faces, define 4 vertex indices (into verts[]) and normal index
    face_defs = [
        # (v indices into verts[], normal index into norms[])
        ([0, 1, 2, 3], 0),  # front
        ([5, 4, 7, 6], 1),  # back
        ([1, 5, 6, 2], 2),  # right
        ([4, 0, 3, 7], 3),  # left
        ([3, 2, 6, 7], 4),  # top
        ([4, 5, 1, 0], 5),  # bottom
    ]

    all_verts = verts
    all_norms = norms
    all_uvs = uvs
    all_faces = []

    for quad_vis, ni in face_defs:
        a, b, c, d = quad_vis
        # Two triangles: (a,b,c) and (a,c,d) — 1-based
        v1 = vo + a + 1
        v2 = vo + b + 1
        v3 = vo + c + 1
        v4 = vo + d + 1
        n = no + ni + 1
        t1, t2, t3, t4 = to + 1, to + 2, to + 3, to + 4
        all_faces.append([(v1, t1, n), (v2, t2, n), (v3, t3, n)])
        all_faces.append([(v1, t1, n), (v3, t3, n), (v4, t4, n)])

    return all_verts, all_norms, all_uvs, all_faces


def merge_boxes(boxes):
    """Merge multiple box outputs into a single mesh."""
    all_v, all_n, all_uv, all_f = [], [], [], []
    v_off, n_off, uv_off = 0, 0, 0

    for v, n, uv, f in boxes:
        all_v.extend(v)
        all_n.extend(n)
        all_uv.extend(uv)
        # Offset face indices
        for tri in f:
            all_f.append([
                (vi + v_off, ti + uv_off, ni + n_off)
                for vi, ti, ni in tri
            ])
        v_off += len(v)
        n_off += len(n)
        uv_off += len(uv)

    return all_v, all_n, all_uv, all_f


def generate_door():
    """Door panel: 0.9m wide, 2.0m tall, 0.04m thick.
    Origin at hinge edge (x=0, y=0, z centered on thickness).
    Door extends in +X direction.
    """
    w, h, d = 0.9, 2.0, 0.04
    half_d = d / 2
    v, n, uv, f = box(0, 0, -half_d, w, h, half_d)
    write_obj(
        os.path.join(SCRIPT_DIR, "Door", "Door.obj"),
        v, n, uv, f, name="Door"
    )
    print("Generated Door.obj")


def generate_frame():
    """Door frame with inner opening 0.92m wide x 2.02m tall.
    Jamb width: 0.08m, depth: 0.12m.
    Origin at bottom-center of the opening.

    Parts:
    - Left jamb:  from x=-0.54 to x=-0.46, y=0 to y=2.1
    - Right jamb: from x=0.46 to x=0.54, y=0 to y=2.1
    - Header:     from x=-0.54 to x=0.54, y=2.02 to y=2.1
    """
    jw = 0.08      # jamb width
    jd = 0.12      # jamb/frame depth
    half_d = jd / 2
    opening_w = 0.92
    opening_h = 2.02
    header_h = 0.08

    half_ow = opening_w / 2
    total_half_w = half_ow + jw

    # Left jamb
    left = box(-total_half_w, 0, -half_d, -half_ow, opening_h + header_h, half_d)
    # Right jamb
    right = box(half_ow, 0, -half_d, total_half_w, opening_h + header_h, half_d)
    # Header
    header = box(-total_half_w, opening_h, -half_d, total_half_w, opening_h + header_h, half_d)

    v, n, uv, f = merge_boxes([left, right, header])
    os.makedirs(os.path.join(SCRIPT_DIR, "Door"), exist_ok=True)
    write_obj(
        os.path.join(SCRIPT_DIR, "Door", "DoorFrame.obj"),
        v, n, uv, f, name="DoorFrame"
    )
    print("Generated DoorFrame.obj")


if __name__ == "__main__":
    os.makedirs(os.path.join(SCRIPT_DIR, "Door"), exist_ok=True)
    generate_door()
    generate_frame()
    print("Done! Import Door.obj and DoorFrame.obj into Unity.")
