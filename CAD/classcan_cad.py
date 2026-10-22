#!/usr/bin/env python3
"""
classcan_cad.py - parametric CadQuery model of the CLASSCAN ceiling turret.

Run:   python classcan_cad.py
Needs: pip install cadquery

Outputs (in ./classcan_cad_out/):
  classcan_assembly.step   open in Autodesk Viewer / Fusion / FreeCAD
  classcan_assembly.glb    optional, any glTF viewer (may be skipped)
  classcan_assembly.stl    optional mesh (may be skipped)
  template_*.svg           1:1 drill templates (print at 100%, check the 100 mm bar)
  report.txt               fit checks + camera sweep check

Coordinates (mm): the box base sits on the CEILING at z=0, the room is -Z,
the lid faces down into the room. +Y is the FRONT (the way the camera faces
at pan 0). Everything marked (approx) is a guess: measure and edit it.
"""
import math
import os
import shutil
import sys

import cadquery as cq

# ============================================================== PARAMETERS
OUT_DIR = "CAD/classcan_cad_out"
RUN_SWEEP = True            # camera pan/tilt collision sweep (slower)

# --- enclosure (from the Lazada listing: outer 174x174x73, inner 160x160x63)
BOX_W, BOX_D, BOX_H = 174.0, 174.0, 73.0
WALL = 7.0
FLOOR_T = 5.0               # floor against the ceiling (approx)
LID_T = 5.0                 # lid plate (approx)
TRAY_H = BOX_H - LID_T      # 68
CAV_W = BOX_W - 2 * WALL    # 160
CAV_D = BOX_D - 2 * WALL    # 160
CAV_H = TRAY_H - FLOOR_T    # 63
POST_R, POST_XY = 5.0, 74.0 # lid-screw corner posts (approx; your box has its own)
MOUNT_XY, MOUNT_D = 66.0, 4.5   # 4 ceiling-screw holes through the floor

# --- wall cutouts
SWITCH_Y, SWITCH_Z, SWITCH_L, SWITCH_H = -40.0, -36.5, 15.0, 10.0   # -X wall
USBC_Y, USBC_Z, USBC_L, USBC_H = 20.0, -14.0, 12.0, 7.0             # +X wall
VENT_D = 4.0
VENT_XS = [-15.0, -5.0, 5.0, 15.0]
VENT_ZS = [-12.0, -60.0]                                             # +/-Y walls

# --- lid features (outside face of the lid faces the room)
LCD_Y = -50.0
LCD_HOLE_DX, LCD_HOLE_DY, LCD_HOLE_D = 93.0, 55.0, 3.4
LCD_SO = 10.0               # standoff height under the LCD
LCD_WIRE_Y, LCD_WIRE_D = -14.0, 8.0
CABLE_Y, CABLE_D = 0.0, 16.0
HEAD_Y = 33.0               # pan axis position on the lid
BASE_HOLE, BASE_HOLE_D = 28.0, 2.2   # pan/tilt base screw square (approx)
LID_SCREW_D = 3.4

# --- internal parts (approx). name, cx, cy, size x, size y, size z
STANDOFF = 3.0              # parts sit 3 mm above the floor
Z_TOP = -(FLOOR_T + STANDOFF)
COMPONENTS = [
    ("Pi 3B + case",   0.0, -42.0, 95.0, 65.0, 40.0),
    ("ESP32 board",   64.0, -28.0, 28.0, 55.0, 13.0),
    ("Charge module", 43.0,  20.0, 70.0, 28.0, 12.0),   # USB-C end toward +X wall
    ("Cell holder",   15.0,  66.0, 80.0, 21.0, 17.0),
    ("Perfboard",    -53.0,  28.0, 50.0, 70.0, 16.0),
]
SWITCH_BODY = ("Rocker switch body", -70.0, SWITCH_Y, 20.0, SWITCH_L, SWITCH_H, SWITCH_Z)

# --- pan/tilt head (approx), built hanging under the lid
HEAD_SERVO = (23.0, 12.0, 23.0)      # MG90S body x,y,z
CAM = (22.0, 28.0, 22.0)             # camera board: x, depth (along +Y), z
PLAT = (28.0, 3.0, 28.0)             # camera platform
LED_BAR = (60.0, 3.0, 15.0)          # LED bar
ARM_REACH = 22.0                     # tilt axis to platform centre (along +Y)
SWEEP_PAN = [-80, -40, 0, 40, 80]
SWEEP_TILT = [-60, -40, -20, 0, 20, 40]   # negative = looking DOWN into the room

# ============================================================== HELPERS
def box(cx, cy, cz, sx, sy, sz):
    return cq.Workplane("XY").box(sx, sy, sz).translate((cx, cy, cz))


def cyl(cx, cy, cz, r, h, axis="Z"):
    c = cq.Workplane("XY").circle(r).extrude(h).translate((0, 0, -h / 2.0))
    if axis == "X":
        c = c.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == "Y":
        c = c.rotate((0, 0, 0), (1, 0, 0), 90)
    return c.translate((cx, cy, cz))


def overlap_volume(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0


# ============================================================== BUILD PARTS
def build_tray():
    tray = box(0, 0, -TRAY_H / 2, BOX_W, BOX_D, TRAY_H)
    cavity = box(0, 0, -(FLOOR_T + (CAV_H + 2) / 2), CAV_W, CAV_D, CAV_H + 2)
    tray = tray.cut(cavity)
    for sx in (-1, 1):
        for sy in (-1, 1):
            tray = tray.union(cyl(sx * POST_XY, sy * POST_XY, -(FLOOR_T + CAV_H / 2), POST_R, CAV_H))
            tray = tray.cut(cyl(sx * MOUNT_XY, sy * MOUNT_XY, -FLOOR_T / 2, MOUNT_D / 2, FLOOR_T + 2))
    wx = BOX_W / 2 - WALL / 2
    wy = BOX_D / 2 - WALL / 2
    tray = tray.cut(box(-wx, SWITCH_Y, SWITCH_Z, WALL + 4, SWITCH_L, SWITCH_H))
    tray = tray.cut(box(wx, USBC_Y, USBC_Z, WALL + 4, USBC_L, USBC_H))
    for sy in (-1, 1):
        for x in VENT_XS:
            for z in VENT_ZS:
                tray = tray.cut(cyl(x, sy * wy, z, VENT_D / 2, WALL + 4, "Y"))
    return tray


def build_lid():
    zc = -(TRAY_H + LID_T / 2)
    lid = box(0, 0, zc, BOX_W, BOX_D, LID_T)
    lid = lid.cut(cyl(0, CABLE_Y, zc, CABLE_D / 2, LID_T + 2))
    lid = lid.cut(cyl(0, LCD_WIRE_Y, zc, LCD_WIRE_D / 2, LID_T + 2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            lid = lid.cut(cyl(sx * POST_XY, sy * POST_XY, zc, LID_SCREW_D / 2, LID_T + 2))
            lid = lid.cut(cyl(sx * LCD_HOLE_DX / 2, LCD_Y + sy * LCD_HOLE_DY / 2, zc, LCD_HOLE_D / 2, LID_T + 2))
            lid = lid.cut(cyl(sx * BASE_HOLE / 2, HEAD_Y + sy * BASE_HOLE / 2, zc, BASE_HOLE_D / 2, LID_T + 2))
    return lid


def build_lcd():
    z_out = -(TRAY_H + LID_T)           # outside face of the lid
    z_pcb = z_out - LCD_SO              # lid-side face of the LCD PCB
    pcb = box(0, LCD_Y, z_pcb - 0.8, 98, 60, 1.6)
    glass = box(0, LCD_Y, z_pcb - 1.6 - 3.5, 90, 55, 7)
    backpack = box(0, LCD_Y + 22, z_pcb + 2.5, 42, 16, 5)
    body = pcb.union(glass).union(backpack)
    window = box(0, LCD_Y, z_pcb - 1.6 - 7 - 0.25, 76, 25, 0.5)
    stand = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            s = cyl(sx * LCD_HOLE_DX / 2, LCD_Y + sy * LCD_HOLE_DY / 2, z_out - LCD_SO / 2, 2.5, LCD_SO)
            stand = s if stand is None else stand.union(s)
    return body, window, stand


def build_head():
    z0 = -(TRAY_H + LID_T)
    sx, sy, sz = HEAD_SERVO
    base = box(0, HEAD_Y, z0 - 1.5, 35, 35, 3)
    pan_servo = box(0, HEAD_Y, z0 - 3 - sz / 2, sx, sy, sz)
    z_pan_bot = z0 - 3 - sz
    bracket = box(0, HEAD_Y, z_pan_bot - 1, 30, 30, 2)
    tilt_z = z_pan_bot - 2 - sz / 2
    tilt_servo = box(0, HEAD_Y, tilt_z, sx, sy, sz)
    servo_front = HEAD_Y + sy / 2
    plat_y = HEAD_Y + ARM_REACH
    plat_back = plat_y - PLAT[1] / 2
    plat_front = plat_y + PLAT[1] / 2
    arm = box(0, (servo_front + plat_back) / 2, tilt_z, 8, plat_back - servo_front, 8)
    platform = box(0, plat_y, tilt_z, PLAT[0], PLAT[1], PLAT[2])
    camera = box(0, plat_front + CAM[1] / 2, tilt_z, CAM[0], CAM[1], CAM[2])
    led = box(0, plat_front + LED_BAR[1] / 2, tilt_z - CAM[2] / 2 - 0.5 - LED_BAR[2] / 2,
              LED_BAR[0], LED_BAR[1], LED_BAR[2])
    tilt_group = arm.union(platform).union(camera).union(led)
    pan_group = bracket.union(tilt_servo)
    return {
        "base": base, "pan_servo": pan_servo, "pan_group": pan_group,
        "tilt_group": tilt_group, "camera": camera, "led": led,
        "tilt_z": tilt_z, "camera_front_y": plat_front + CAM[1],
        "platform": platform, "arm": arm, "bracket": bracket, "tilt_servo": tilt_servo,
    }


def build_internals():
    parts = []
    for name, cx, cy, sx, sy, sz in COMPONENTS:
        zc = Z_TOP - sz / 2
        if name == "Cell holder":
            holder = box(cx, cy, zc, sx, sy, sz)
            cell = cyl(cx, cy, Z_TOP - 9.0, 9.0, 65.0, "X")
            parts.append((name, holder.union(cell), (0.12, 0.12, 0.12)))
        elif name == "Perfboard":
            plate = box(cx, cy, Z_TOP - 0.8, sx, sy, 1.6)
            parts_blk = box(cx, cy, Z_TOP - 1.6 - 7, 30, 20, 14)
            parts.append((name, plate.union(parts_blk), (0.15, 0.5, 0.25)))
        else:
            color = {"Pi 3B + case": (0.2, 0.65, 0.3), "ESP32 board": (0.1, 0.1, 0.12),
                     "Charge module": (0.1, 0.5, 0.55)}.get(name, (0.5, 0.5, 0.5))
            parts.append((name, box(cx, cy, zc, sx, sy, sz), color))
    n, cx, cy, sx, sy, sz, zc = SWITCH_BODY
    parts.append((n, box(cx, cy, zc, sx, sy, sz), (0.85, 0.1, 0.1)))
    return parts


# ============================================================== CHECKS
def comp_aabbs():
    items = []
    for name, cx, cy, sx, sy, sz in COMPONENTS:
        items.append((name, (cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, Z_TOP - sz, Z_TOP)))
    n, cx, cy, sx, sy, sz, zc = SWITCH_BODY
    items.append((n, (cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, zc - sz / 2, zc + sz / 2)))
    return items


def keepout_aabbs():
    z0, z1 = -TRAY_H, -FLOOR_T
    items = [("USB-A plug clearance", (-22.0, 8.0, 6.0, 34.0, z0, z1))]
    lo = MOUNT_XY - 8.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            xs = sorted((sx * lo, sx * CAV_W / 2))
            ys = sorted((sy * lo, sy * CAV_D / 2))
            items.append((f"Corner screw zone {'+' if sx > 0 else '-'}x{'+' if sy > 0 else '-'}y",
                          (xs[0], xs[1], ys[0], ys[1], z0, z1)))
    return items


def axis_gap(a, b):
    gaps = [max(a[i] - b[i + 1], b[i] - a[i + 1]) for i in (0, 2, 4)]
    return max(gaps)


def fit_report():
    lines = ["FIT CHECKS (internal layout, millimetres)"]
    comps = comp_aabbs()
    keeps = keepout_aabbs()
    bad = 0
    for name, bb in comps:
        wall_gap = min(bb[0] + CAV_W / 2, CAV_W / 2 - bb[1], bb[2] + CAV_D / 2, CAV_D / 2 - bb[3])
        lid_clear = bb[4] + TRAY_H
        status = "PASS"
        if wall_gap < 0 or lid_clear < 0:
            status, bad = "FAIL", bad + 1
        elif wall_gap < 2 or lid_clear < 5:
            status = "WARN"
        lines.append(f"  [{status}] {name}: wall gap {wall_gap:.1f}, lid clearance {lid_clear:.1f}")
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            g = axis_gap(comps[i][1], comps[j][1])
            if g < 0:
                bad += 1
                lines.append(f"  [FAIL] {comps[i][0]} overlaps {comps[j][0]}")
            elif g < 2:
                lines.append(f"  [WARN] {comps[i][0]} / {comps[j][0]}: only {g:.1f} mm apart")
    for cname, cbb in comps:
        for kname, kbb in keeps:
            g = axis_gap(cbb, kbb)
            if g < 0:
                bad += 1
                lines.append(f"  [FAIL] {cname} intrudes into {kname}")
            elif g < 2:
                lines.append(f"  [WARN] {cname} is only {g:.1f} mm from {kname}")
    lines.append(f"  -> {'ALL CLEAR' if bad == 0 else str(bad) + ' problem(s): edit COMPONENTS positions'}")
    return lines


def sweep_report(head, lid, lcd_body):
    lines = ["", "CAMERA SWEEP CHECK (collision volume in mm^3; 0 = clear)"]
    tz = head["tilt_z"]
    statics = [("lid", lid), ("LCD", lcd_body), ("base plate", head["base"]), ("pan servo", head["pan_servo"])]
    worst = {}
    for pan in SWEEP_PAN:
        for tilt in SWEEP_TILT:
            tg = head["tilt_group"].rotate((0, HEAD_Y, tz), (1, HEAD_Y, tz), tilt)
            tg = tg.rotate((0, HEAD_Y, 0), (0, HEAD_Y, 1), pan)
            pg = head["pan_group"].rotate((0, HEAD_Y, 0), (0, HEAD_Y, 1), pan)
            hits = []
            for sname, s in statics:
                v = overlap_volume(tg, s)
                if v > 1.0:
                    hits.append(f"camera head hits {sname}")
                v = overlap_volume(pg, s) if sname not in ("pan servo",) else 0.0
                if v > 1.0:
                    hits.append(f"pan bracket hits {sname}")
            if overlap_volume(tg, pg) > 1.0:
                hits.append("camera head hits pan bracket/tilt servo")
            if hits:
                worst.setdefault((pan, tilt), hits)
    if not worst:
        lines.append("  all pan/tilt combinations clear")
    else:
        for (pan, tilt), hits in sorted(worst.items()):
            lines.append(f"  [HIT] pan {pan:+d}, tilt {tilt:+d}: {', '.join(sorted(set(hits)))}")
        lines.append("  -> limit those angles in the ESP32 firmware (negative tilt = looking down)")
    return lines


# ============================================================== TEMPLATES
M = 12.0  # sheet margin (mm)


def _svg(filename, title, view_note, w, h, holes, rects, dashed_rects):
    W, H = w + 2 * M, h + 2 * M + 28
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">',
           '<rect width="100%" height="100%" fill="white"/>',
           f'<text x="{M}" y="8" font-family="Arial" font-size="5" font-weight="bold">{title}</text>',
           f'<text x="{M}" y="{M - 2}" font-family="Arial" font-size="3.2">{view_note}</text>',
           f'<rect x="{M}" y="{M}" width="{w}" height="{h}" fill="none" stroke="black" stroke-width="0.4"/>']
    for (cx, cy, rw, rh, label) in dashed_rects:
        out.append(f'<rect x="{M + cx - rw / 2}" y="{M + cy - rh / 2}" width="{rw}" height="{rh}" fill="none" '
                   f'stroke="#888" stroke-width="0.25" stroke-dasharray="2 1.5"/>')
        out.append(f'<text x="{M + cx - rw / 2 + 1}" y="{M + cy - rh / 2 - 1}" font-family="Arial" font-size="2.8" fill="#666">{label}</text>')
    for (cx, cy, rw, rh, label) in rects:
        x, y = M + cx, M + cy
        out.append(f'<rect x="{x - rw / 2}" y="{y - rh / 2}" width="{rw}" height="{rh}" fill="none" stroke="red" stroke-width="0.3"/>')
        out.append(f'<line x1="{x - 3}" y1="{y}" x2="{x + 3}" y2="{y}" stroke="red" stroke-width="0.25"/>')
        out.append(f'<line x1="{x}" y1="{y - 3}" x2="{x}" y2="{y + 3}" stroke="red" stroke-width="0.25"/>')
        out.append(f'<text x="{x + rw / 2 + 1.5}" y="{y - 1}" font-family="Arial" font-size="3" fill="red">{label}</text>')
    for (cx, cy, d, label) in holes:
        x, y = M + cx, M + cy
        out.append(f'<circle cx="{x}" cy="{y}" r="{d / 2}" fill="none" stroke="red" stroke-width="0.3"/>')
        out.append(f'<line x1="{x - d / 2 - 2}" y1="{y}" x2="{x + d / 2 + 2}" y2="{y}" stroke="red" stroke-width="0.2"/>')
        out.append(f'<line x1="{x}" y1="{y - d / 2 - 2}" x2="{x}" y2="{y + d / 2 + 2}" stroke="red" stroke-width="0.2"/>')
        out.append(f'<text x="{x + d / 2 + 2.5}" y="{y - 1}" font-family="Arial" font-size="3" fill="red">{label}</text>')
    by = M + h + 10
    out.append(f'<line x1="{M}" y1="{by}" x2="{M + 100}" y2="{by}" stroke="black" stroke-width="0.5"/>')
    out.append(f'<line x1="{M}" y1="{by - 2}" x2="{M}" y2="{by + 2}" stroke="black" stroke-width="0.5"/>')
    out.append(f'<line x1="{M + 100}" y1="{by - 2}" x2="{M + 100}" y2="{by + 2}" stroke="black" stroke-width="0.5"/>')
    out.append(f'<text x="{M}" y="{by + 7}" font-family="Arial" font-size="3.5">This bar must measure 100 mm. '
               f'Print at 100% / Actual size (no fit-to-page).</text>')
    out.append('</svg>')
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def write_templates(folder):
    hw, hd = BOX_W / 2, BOX_D / 2
    # lid and floor are both viewed looking along +Z: page-x = -x, FRONT (+Y) at the top
    def pg(x, y):
        return hw - x, hd - y
    holes, dashed = [], []
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = pg(sx * LCD_HOLE_DX / 2, LCD_Y + sy * LCD_HOLE_DY / 2)
            holes.append((px, py, LCD_HOLE_D, "LCD screw"))
            px, py = pg(sx * BASE_HOLE / 2, HEAD_Y + sy * BASE_HOLE / 2)
            holes.append((px, py, BASE_HOLE_D, "head screw"))
    px, py = pg(0, LCD_WIRE_Y)
    holes.append((px, py, LCD_WIRE_D, "LCD wires"))
    px, py = pg(0, CABLE_Y)
    holes.append((px, py, CABLE_D, "camera cable"))
    px, py = pg(0, LCD_Y)
    dashed.append((px, py, 98, 60, "LCD outline"))
    px, py = pg(0, HEAD_Y)
    dashed.append((px, py, 35, 35, "pan/tilt base"))
    _svg(os.path.join(folder, "template_lid.svg"), "LID drill template",
         "View: OUTSIDE face of the lid (the side facing the room). FRONT = top of sheet. "
         "Your lid may already have screw holes: do not add those.",
         BOX_W, BOX_D, holes, [], dashed)

    holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = pg(sx * MOUNT_XY, sy * MOUNT_XY)
            holes.append((px, py, MOUNT_D, "ceiling screw"))
    _svg(os.path.join(folder, "template_floor.svg"), "FLOOR (ceiling side) drill template",
         "View: INSIDE of the floor, looking at it from the lid side. FRONT = top of sheet.",
         BOX_W, BOX_D, holes, [], [])

    # side walls: viewed from OUTSIDE, ceiling edge at the TOP
    def wall(fname, title, note, w, items_h, items_r, xmap):
        holes = [(xmap(a), -z, d, lab) for (a, z, d, lab) in items_h]
        rects = [(xmap(a), -z, rw, rh, lab) for (a, z, rw, rh, lab) in items_r]
        _svg(os.path.join(folder, fname), title, note, w, TRAY_H, holes, rects, [])

    wall("template_wall_minusX_switch.svg", "-X WALL: rocker switch cutout",
         "View: from OUTSIDE, ceiling edge at TOP. Drill the 4 corners, then file to the rectangle.",
         BOX_D, [], [(SWITCH_Y, SWITCH_Z, SWITCH_L, SWITCH_H, "switch 15x10")],
         lambda y: hd - y)
    wall("template_wall_plusX_usbc.svg", "+X WALL: USB-C charging slot",
         "View: from OUTSIDE, ceiling edge at TOP. Align with the module's USB-C port before cutting.",
         BOX_D, [], [(USBC_Y, USBC_Z, USBC_L, USBC_H, "USB-C slot 12x7")],
         lambda y: y + hd)
    vents = [(x, z, VENT_D, "vent") for x in VENT_XS for z in VENT_ZS]
    wall("template_wall_plusY_vents.svg", "+Y WALL (front): vent holes",
         "View: from OUTSIDE, ceiling edge at TOP.", BOX_W, vents, [], lambda x: hw - x)
    wall("template_wall_minusY_vents.svg", "-Y WALL (back): vent holes",
         "View: from OUTSIDE, ceiling edge at TOP.", BOX_W, vents, [], lambda x: x + hw)


# ============================================================== MAIN
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Building enclosure...")
    tray, lid = build_tray(), build_lid()
    lcd_body, lcd_window, lcd_stand = build_lcd()
    head = build_head()
    internals = build_internals()

    assy = cq.Assembly(name="CLASSCAN")

    def add(name, obj, rgb, alpha=1.0):
        assy.add(obj, name=name, color=cq.Color(rgb[0], rgb[1], rgb[2], alpha))

    add("ceiling", box(0, 0, 5.0, 320, 320, 10), (0.95, 0.95, 0.95), 0.18)
    add("box_tray", tray, (0.12, 0.12, 0.14))
    add("box_lid", lid, (0.2, 0.2, 0.23))
    add("lcd_body", lcd_body, (0.1, 0.35, 0.85))
    add("lcd_window", lcd_window, (0.03, 0.08, 0.25))
    add("lcd_standoffs", lcd_stand, (0.8, 0.8, 0.8))
    add("head_base", head["base"], (0.15, 0.15, 0.15))
    add("pan_servo", head["pan_servo"], (0.1, 0.2, 0.6))
    add("pan_bracket", head["bracket"], (0.15, 0.15, 0.15))
    add("tilt_servo", head["tilt_servo"], (0.1, 0.2, 0.6))
    add("tilt_arm_platform", head["arm"].union(head["platform"]), (0.15, 0.15, 0.15))
    add("camera", head["camera"], (0.02, 0.02, 0.02))
    add("led_bar", head["led"], (1.0, 0.9, 0.4))
    for name, obj, rgb in internals:
        add(name, obj, rgb)

    path = os.path.join(OUT_DIR, "classcan_assembly.step")
    assy.save(path)
    print("Saved", path)
    for ext, kind in (("glb", "GLTF"), ("stl", "STL")):
        try:
            assy.save(os.path.join(OUT_DIR, f"classcan_assembly.{ext}"), kind)
            print("Saved", ext)
        except Exception as e:
            print(f"(skipped {ext}: {e})")

    print("Writing 1:1 drill templates...")
    write_templates(OUT_DIR)

    report = fit_report()
    if RUN_SWEEP:
        print("Running camera sweep check (can take a minute)...")
        report += sweep_report(head, lid, lcd_body)
    with open(os.path.join(OUT_DIR, "report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("\n".join(report))
    print(f"\nDone. Open {OUT_DIR}/classcan_assembly.step in Autodesk Viewer or Fusion.")


if __name__ == "__main__":
    main()