#!/usr/bin/env python3
"""
classcan_cad.py - parametric CadQuery model of the CLASSCAN ceiling turret.

  python classcan_cad.py              build model + wiring + templates + report
  python classcan_cad.py --optimize   re-run the wire-aware layout search first
  python classcan_cad.py --no-sweep   skip the camera collision sweep (faster)

Needs: pip install cadquery   (--optimize alone does not need it)

Outputs (./classcan_cad_out/):
  classcan_assembly.step   open in Autodesk Viewer / Fusion / FreeCAD
  classcan_assembly.glb / .stl   optional extras (skipped if your version can't)
  template_*.svg           1:1 drill templates (print at 100%, check the 100 mm bar)
  report.txt               fit check, wire lengths, pin table, camera sweep

Coordinates (mm): box base on the CEILING at z=0, room is -Z, lid faces down.
+Y = FRONT = the way the camera points at pan 0. Everything marked (approx)
is a guess: measure the real part and edit the number.
"""
import argparse
import json
import math
import os
import random
import sys

try:
    import cadquery as cq
except ImportError:          # --optimize still works without it
    cq = None

# ================================================================ PARAMETERS
OUT_DIR = "classcan_cad_out"
LAYOUT_FILE = "classcan_layout.json"     # written by --optimize, read by the build

# --- enclosure (Lazada listing: outer 174x174x73, inner 160x160x63)
BOX_W = BOX_D = 174.0
BOX_H = 73.0
WALL = 7.0
FLOOR_T = 5.0               # floor against the ceiling (approx)
LID_T = 5.0                 # lid plate (approx)
TRAY_H = BOX_H - LID_T      # 68
CAV = BOX_W - 2 * WALL      # 160 (cavity is square)
CAV_H = TRAY_H - FLOOR_T    # 63
Z_LID_OUT = -(TRAY_H + LID_T)
POST_R, POST_XY = 5.0, 74.0         # lid-screw corner posts (approx)
MOUNT_XY, MOUNT_D = 66.0, 4.5       # 4 ceiling-screw holes through the floor

# --- LCD: on a SIDE WALL, facing the teacher's desk
LCD_WALL = "-Y"     # "-Y","+Y","-X","+X". -Y = the back, opposite the camera's pan-0 direction
LCD_U = 0.0         # position along that wall, seen from OUTSIDE (+ = right)
LCD_Z = -34.0       # vertical centre (ceiling = 0)
LCD_W, LCD_H = 98.0, 60.0
LCD_HOLE_DX, LCD_HOLE_DY, LCD_HOLE_D = 93.0, 55.0, 3.4
LCD_SO = 10.0       # standoff height
LCD_WIRE_D = 8.0

# --- small wall features
SWITCH_L, SWITCH_H, SWITCH_DEPTH, SWITCH_Z = 15.0, 10.0, 20.0, -36.5
USBC_L, USBC_H = 12.0, 7.0
VENT_D = 4.0
VENT_XS = [-15.0, -5.0, 5.0, 15.0]
VENT_ZS = [-12.0, -60.0]

# --- pan/tilt head, hanging under the lid (approx)
HEAD_Y = 0.0
CABLE_D = 16.0                                   # lid hole for the cable bundle
HOLE_CANDS = [(0.0, -28.0), (0.0, 28.0), (28.0, 0.0), (-28.0, 0.0)]   # beside the head base
BASE_HOLE, BASE_HOLE_D = 28.0, 2.2
LID_SCREW_D = 3.4
HEAD_SERVO = (23.0, 12.0, 23.0)      # MG90S body
CAM = (22.0, 28.0, 22.0)             # camera board: x, depth(+Y), z
PLAT = (28.0, 3.0, 28.0)
LED_BAR = (60.0, 3.0, 15.0)
ARM_REACH = 22.0
SWEEP_PAN = [-80, -40, 0, 40, 80]
SWEEP_TILT = [-60, -40, -20, 0, 20, 40]   # negative = looking DOWN

# --- internal parts (approx). size x, y, z at rotation 0
STANDOFF = 3.0
Z_TOP = -(FLOOR_T + STANDOFF)
COMP_NAMES = ["Pi", "ESP32", "Module", "Cell", "Perfboard"]
SPECS = {
    "Pi":        {"label": "Pi 3B + acrylic case", "size": (95.0, 65.0, 40.0)},
    "ESP32":     {"label": "ESP32 board",          "size": (55.0, 28.0, 13.0)},   # bigger if on an expansion board
    "Module":    {"label": "18650 charge module",  "size": (70.0, 28.0, 12.0)},
    "Cell":      {"label": "18650 cell + holder",  "size": (80.0, 21.0, 17.0)},
    "Perfboard": {"label": "Perfboard 5x7",        "size": (70.0, 50.0, 16.0)},
}
# ports at rotation 0: (local x, local y, exit dx, exit dy, plug width, plug clearance)
PORTS = {
    "Pi":        {"usb": (47.5, 8.0, 1, 0, 40.0, 30.0), "pwr": (-30.0, -32.5, 0, -1, 12.0, 25.0)},
    "ESP32":     {"usb": (-27.5, 0.0, -1, 0, 12.0, 25.0), "hdr": (0.0, 0.0, 0, 0, 0.0, 0.0)},
    "Module":    {"usb_a": (-35.0, 0.0, -1, 0, 28.0, 30.0), "usb_c": (35.0, 0.0, 1, 0, 12.0, 0.0),
                  "bat": (0.0, 0.0, 0, 0, 0.0, 0.0)},
    "Cell":      {"leads": (-40.0, 0.0, -1, 0, 10.0, 15.0)},
    "Perfboard": {"bus": (0.0, 0.0, 0, 0, 0.0, 0.0)},
}
TOP_PORTS = {"hdr", "bus", "bat"}        # wires attach on top of the part

# --- cable lengths you actually have (mm). MEASURE these.
SERVICE_LOOP = 80.0          # slack the moving head needs
BEND_SLACK = 20.0
CAM_CABLE_LEN = 500.0
SERVO_LEAD = 250.0           # MG90S leads are about 25 cm
LED_CABLE_LEN = 200.0        # the short USB lead on the LED bar
USB_PI_ESP_LEN = 300.0
USB_PWR_LEN = 300.0
RAIL_LEN = 600.0             # cut-open old USB cable
JUMPER_LEN = 200.0
HOLDER_LEAD = 150.0
FUSE_LEADS = 300.0
SWITCH_LEAD = 400.0

WALL_ANGLE = {"-Y": 0.0, "+X": 90.0, "+Y": 180.0, "-X": 270.0}
DIR_WALL = {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}
OPPOSITE = {"-Y": "+Y", "+Y": "-Y", "+X": "-X", "-X": "+X"}
WALL_FILE = {"-Y": "minusY", "+Y": "plusY", "-X": "minusX", "+X": "plusX"}

# Best layout found by --optimize with the numbers above (overwritten by LAYOUT_FILE)
DEFAULT_LAYOUT = {
    "Pi": [16.0, 31.0, 270],
    "ESP32": [64.5, -1.0, 90],
    "Module": [-43.5, -41.5, 180],
    "Cell": [1.0, -68.0, 0],
    "Perfboard": [-43.5, 9.5, 270],
    "switch": ["+Y", 50.0],
    "hole": [2],
}

assert BOX_W == BOX_D, "layout code assumes a square box"


# ================================================================ PURE-PYTHON LAYOUT MODEL
def rot2(x, y, deg):
    d = int(round(deg)) % 360
    if d == 0:
        return x, y
    if d == 90:
        return -y, x
    if d == 180:
        return -x, -y
    if d == 270:
        return y, -x
    t = math.radians(deg)
    return x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t)


def comp_bb(name, cx, cy, rot):
    sx, sy, _ = SPECS[name]["size"]
    if int(rot) % 180 == 90:
        sx, sy = sy, sx
    return (cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2)


def port_world(name, port, L):
    cx, cy, rot = L[name]
    lx, ly, dx, dy, _, _ = PORTS[name][port]
    px, py = rot2(lx, ly, rot)
    ddx, ddy = rot2(dx, dy, rot)
    sz = SPECS[name]["size"][2]
    z = Z_TOP - sz if port in TOP_PORTS else Z_TOP - sz / 2
    return cx + px, cy + py, z, int(round(ddx)), int(round(ddy))


def port_keepout(name, port, L):
    x, y, _, dx, dy = port_world(name, port, L)
    w, clr = PORTS[name][port][4], PORTS[name][port][5]
    if clr <= 0:
        return None
    if dx != 0:
        a, b = sorted((x, x + dx * clr))
        return (a, b, y - w / 2, y + w / 2)
    a, b = sorted((y, y + dy * clr))
    return (x - w / 2, x + w / 2, a, b)


def switch_bb(sw):
    wall, u = sw
    th = WALL_ANGLE[wall]
    cx, cy = rot2(u, -CAV / 2 + SWITCH_DEPTH / 2, th)
    w, d = SWITCH_L, SWITCH_DEPTH
    if int(th) % 180 == 90:
        w, d = d, w
    return (cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2)


def corner_zones():
    lo, hi = MOUNT_XY - 8.0, CAV / 2
    return [(sx * lo if sx > 0 else -hi, hi if sx > 0 else -lo,
             sy * lo if sy > 0 else -hi, hi if sy > 0 else -lo)
            for sx in (-1, 1) for sy in (-1, 1)]


def overlap_pen(a, b, gap):
    ox = min(a[1], b[1]) - max(a[0], b[0]) + gap
    oy = min(a[3], b[3]) - max(a[2], b[2]) + gap
    return min(ox, oy) if (ox > 0 and oy > 0) else 0.0


def out_of_cavity(bb, margin):
    h = CAV / 2 - margin
    return (max(0.0, -h - bb[0]) + max(0.0, bb[1] - h) +
            max(0.0, -h - bb[2]) + max(0.0, bb[3] - h))


def layout_penalty(L, issues=None):
    pen = 0.0

    def note(msg):
        if issues is not None:
            issues.append(msg)

    bodies = {}
    for n in COMP_NAMES:
        bb = comp_bb(n, *L[n])
        bodies[n] = bb
        o = out_of_cavity(bb, 1.0)
        if o > 0:
            pen += 20 * o
            note(f"{SPECS[n]['label']} is {o:.1f} mm too close to / through a wall")
    bodies["Switch"] = switch_bb(L["switch"])
    names = list(bodies)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p = overlap_pen(bodies[names[i]], bodies[names[j]], 2.0)
            if p > 0:
                pen += 30 * p
                note(f"{names[i]} and {names[j]} are closer than 2 mm (penetration {p:.1f})")
    zones = corner_zones()
    for n, bb in bodies.items():
        for z in zones:
            p = overlap_pen(bb, z, 0.5)
            if p > 0:
                pen += 30 * p
                note(f"{n} sits in a corner screw zone")
    for n in COMP_NAMES:
        for p_name in PORTS[n]:
            ko = port_keepout(n, p_name, L)
            if ko is None:
                continue
            o = out_of_cavity(ko, 0.0)
            if o > 0:
                pen += 20 * o
                note(f"plug space of {n}.{p_name} runs into a wall")
            for m, bb in bodies.items():
                if m == n:
                    continue
                p = overlap_pen(ko, bb, 0.0)
                if p > 0:
                    pen += 30 * p
                    note(f"plug space of {n}.{p_name} is blocked by {m}")
            for z in zones:
                p = overlap_pen(ko, z, 0.0)
                if p > 0:
                    pen += 30 * p
                    note(f"plug space of {n}.{p_name} hits a corner screw zone")
    # module USB-C must face a wall, close, so a charging cable reaches it
    x, y, z, dx, dy = port_world("Module", "usb_c", L)
    h = CAV / 2
    dist = {(1, 0): h - x, (-1, 0): x + h, (0, 1): h - y, (0, -1): y + h}.get((dx, dy), 99.0)
    if dist > 4.0:
        pen += 25 * (dist - 4.0)
        note(f"module USB-C end is {dist:.1f} mm from the nearest wall (needs <= 4)")
    usbc_wall = DIR_WALL.get((dx, dy))
    usbc_u = rot2(x, y, -WALL_ANGLE[usbc_wall])[0] if usbc_wall else 0.0
    sw_wall, sw_u = L["switch"]
    u_max = CAV / 2 - SWITCH_L / 2 - 4.0
    if abs(sw_u) > u_max:
        pen += 20 * (abs(sw_u) - u_max)
        note("switch is too close to a wall corner")
    lcd_half = LCD_W / 2 + 3.0
    if usbc_wall == LCD_WALL and abs(usbc_u - LCD_U) < lcd_half + USBC_L / 2:
        pen += 200
        note("USB-C slot would land behind the LCD")
    if sw_wall == LCD_WALL and abs(sw_u - LCD_U) < lcd_half + SWITCH_L / 2:
        pen += 200
        note("switch would land behind the LCD")
    if sw_wall == usbc_wall and abs(sw_u - usbc_u) < (SWITCH_L + USBC_L) / 2 + 4:
        pen += 100
        note("switch and USB-C slot are too close on the same wall")
    return pen


# --- head geometry (pure numbers, shared by the CAD build and the wire model)
def head_dims():
    sx, sy, sz = HEAD_SERVO
    z0 = Z_LID_OUT
    pan_z = z0 - 3 - sz / 2
    z_pan_bot = z0 - 3 - sz
    tilt_z = z_pan_bot - 2 - sz / 2
    plat_y = HEAD_Y + ARM_REACH
    plat_front = plat_y + PLAT[1] / 2
    led_y = plat_front + LED_BAR[1] / 2
    led_z = tilt_z - CAM[2] / 2 - 0.5 - LED_BAR[2] / 2
    return {
        "z0": z0, "pan_z": pan_z, "z_pan_bot": z_pan_bot, "tilt_z": tilt_z,
        "plat_y": plat_y, "plat_front": plat_front, "led_y": led_y, "led_z": led_z,
        "servo_front": HEAD_Y + sy / 2,
    }


_HD = head_dims()
HEAD_PTS = {
    "pan": (0.0, HEAD_Y, _HD["pan_z"]),
    "tilt": (0.0, HEAD_Y, _HD["tilt_z"]),
    "cam": (0.0, _HD["plat_y"], _HD["tilt_z"]),
    "led": (0.0, _HD["led_y"], _HD["led_z"]),
}


def lcd_hole_pt():
    x, y = rot2(LCD_U, -CAV / 2, WALL_ANGLE[LCD_WALL])
    return (x, y, LCD_Z + 22.0)


# wires: name, end A, end B, supplied length, colour, radius, slack, weight
WIRES = [
    ("Camera USB cable",     ("head", "cam"),   ("Pi", "usb"),        CAM_CABLE_LEN,  (0.75, 0.75, 0.75), 1.8, SERVICE_LOOP, 2.0),
    ("Pan servo leads",      ("head", "pan"),   ("ESP32", "hdr"),     SERVO_LEAD,     (1.0, 0.55, 0.0),   1.0, SERVICE_LOOP, 3.0),
    ("Tilt servo leads",     ("head", "tilt"),  ("ESP32", "hdr"),     SERVO_LEAD,     (1.0, 0.55, 0.0),   1.0, SERVICE_LOOP, 3.0),
    ("LED bar USB lead",     ("head", "led"),   ("Perfboard", "bus"), LED_CABLE_LEN,  (1.0, 0.85, 0.2),   1.2, SERVICE_LOOP, 1.5),
    ("Pi - ESP32 USB",       ("ESP32", "usb"),  ("Pi", "usb"),        USB_PI_ESP_LEN, (0.85, 0.85, 0.85), 1.8, BEND_SLACK,   2.0),
    ("Module - Pi power",    ("Module", "usb_a"), ("Pi", "pwr"),      USB_PWR_LEN,    (0.95, 0.95, 0.95), 1.8, BEND_SLACK,   2.0),
    ("5 V rail cable",       ("Module", "usb_a"), ("Perfboard", "bus"), RAIL_LEN,     (0.9, 0.1, 0.1),    1.2, BEND_SLACK,   1.0),
    ("ESP32 jumpers",        ("ESP32", "hdr"),  ("Perfboard", "bus"), JUMPER_LEN,     (0.2, 0.6, 1.0),    0.8, BEND_SLACK,   1.5),
    ("LCD I2C jumpers",      ("ESP32", "hdr"),  ("lcd", "hole"),      JUMPER_LEN,     (0.2, 0.6, 1.0),    0.8, 45.0,         1.5),
    ("Cell - to module",     ("Cell", "leads"), ("Module", "bat"),    HOLDER_LEAD,    (0.1, 0.1, 0.1),    1.2, 15.0,         1.5),
    ("Cell + to switch",     ("Cell", "leads"), ("Switch", "sw"),     HOLDER_LEAD + FUSE_LEADS, (0.9, 0.1, 0.1), 1.2, 15.0, 1.0),
    ("Switch to module +",   ("Switch", "sw"),  ("Module", "bat"),    SWITCH_LEAD,    (0.9, 0.1, 0.1),    1.2, 15.0,         1.0),
]


def hole_xy(L):
    return HOLE_CANDS[int(L["hole"][0]) % len(HOLE_CANDS)]


def endpoint(ref, L):
    kind, key = ref
    if kind == "head":
        return HEAD_PTS[key]
    if kind == "lcd":
        return lcd_hole_pt()
    if kind == "Switch":
        wall, u = L["switch"]
        gx, gy = rot2(u, -CAV / 2 + SWITCH_DEPTH, WALL_ANGLE[wall])
        return (gx, gy, SWITCH_Z)
    x, y, z, dx, dy = port_world(kind, key, L)
    return (x + dx * 6.0, y + dy * 6.0, z)


def _dedupe(pts):
    out = []
    for p in pts:
        if not out or max(abs(p[i] - out[-1][i]) for i in range(3)) > 1e-6:
            out.append(p)
    return out


def wire_points(idx, a, b, L):
    zc = -(50.0 + 1.3 * idx)
    A, B = endpoint(a, L), endpoint(b, L)
    if a[0] == "head":
        zt = Z_LID_OUT - 6.0
        hx, hy = hole_xy(L)
        pts = [A, (0.0, HEAD_Y, A[2]), (0.0, HEAD_Y, zt), (hx, hy, zt),
               (hx, hy, zc), (B[0], hy, zc), (B[0], B[1], zc), B]
    else:
        pts = [A, (A[0], A[1], zc), (B[0], A[1], zc), (B[0], B[1], zc), B]
    return _dedupe(pts)


def polyline_length(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def wire_needs(L):
    res = []
    for i, (name, a, b, supplied, color, radius, slack, weight) in enumerate(WIRES):
        pts = wire_points(i, a, b, L)
        res.append((name, polyline_length(pts) + slack, supplied, weight, pts, color, radius))
    return res


def wire_cost(L):
    cost = 0.0
    for _, need, supplied, weight, _, _, _ in wire_needs(L):
        cost += 0.05 * need + 0.8 * weight * max(0.0, need - supplied)
    return cost


# ================================================================ LAYOUT SEARCH
def _snap(v, q=0.5):
    return round(v / q) * q


def _clone(L):
    return {k: list(v) for k, v in L.items()}


def _random_layout(rng):
    L = {n: [_snap(rng.uniform(-50, 50)), _snap(rng.uniform(-50, 50)), rng.choice([0, 90, 180, 270])]
         for n in COMP_NAMES}
    L["switch"] = [rng.choice(list(WALL_ANGLE)), _snap(rng.uniform(-60, 60))]
    L["hole"] = [rng.randrange(len(HOLE_CANDS))]
    return L


def _perturb(L, rng):
    L2 = _clone(L)
    r = rng.random()
    if r < 0.04:
        L2["hole"][0] = rng.randrange(len(HOLE_CANDS))
    elif r < 0.12:
        L2["switch"][0] = rng.choice(list(WALL_ANGLE))
    elif r < 0.22:
        L2["switch"][1] = _snap(L2["switch"][1] + rng.gauss(0, 15))
    else:
        n = rng.choice(COMP_NAMES)
        m = rng.random()
        if m < 0.55:
            s = rng.choice([1.0, 4.0, 15.0])
            L2[n][0] = _snap(L2[n][0] + rng.gauss(0, s))
            L2[n][1] = _snap(L2[n][1] + rng.gauss(0, s))
        elif m < 0.72:
            L2[n][2] = (L2[n][2] + rng.choice([90, 180, 270])) % 360
        elif m < 0.84:
            o = rng.choice([x for x in COMP_NAMES if x != n])
            for k in (0, 1):
                L2[n][k], L2[o][k] = L2[o][k], L2[n][k]
        else:
            bb = comp_bb(n, 0.0, 0.0, L2[n][2])
            hw, hh = bb[1], bb[3]
            wall = rng.choice(list(WALL_ANGLE))
            if wall == "+X":
                L2[n][0] = _snap(CAV / 2 - 1.5 - hw)
            elif wall == "-X":
                L2[n][0] = _snap(-CAV / 2 + 1.5 + hw)
            elif wall == "+Y":
                L2[n][1] = _snap(CAV / 2 - 1.5 - hh)
            else:
                L2[n][1] = _snap(-CAV / 2 + 1.5 + hh)
    return L2


def _hand_layout():
    """A sensible starting arrangement (the search refines it)."""
    return {"Pi": [0.0, 40.0, 0], "ESP32": [-30.0, -50.0, 0], "Module": [43.0, -20.0, 0],
            "Cell": [15.0, -66.0, 0], "Perfboard": [-53.0, 5.0, 270],
            "switch": ["-X", 40.0], "hole": [0]}


def optimize(restarts=30, iters=7000, seed=7, verbose=True):
    """Phase 1 finds a valid layout. Phase 2 anneals wire lengths (it may wander
    through invalid states) and keeps the best VALID layout it has seen."""
    rng = random.Random(seed)
    best = None
    for r in range(restarts):
        L = _hand_layout() if r == 0 else _random_layout(rng)
        pen = layout_penalty(L)
        T = 30.0
        for _ in range(iters):
            if pen == 0:
                break
            L2 = _perturb(L, rng)
            p2 = layout_penalty(L2)
            if p2 <= pen or rng.random() < math.exp((pen - p2) / T):
                L, pen = L2, p2
            T = max(0.5, T * 0.999)
        if pen > 0:
            continue
        cur_w = wire_cost(L)
        cur = 4.0 * 0 + cur_w
        best_r = (cur_w, _clone(L))
        T = 30.0
        for _ in range(iters):
            L2 = _perturb(L, rng)
            p2 = layout_penalty(L2)
            w2 = wire_cost(L2)
            c2 = 4.0 * p2 + w2
            if c2 < cur or rng.random() < math.exp((cur - c2) / T):
                L, cur = L2, c2
                if p2 == 0 and w2 < best_r[0]:
                    best_r = (w2, _clone(L2))
            T = max(0.4, T * 0.9993)
        if verbose:
            print(f"  restart {r + 1}/{restarts}: valid layout, wire cost {best_r[0]:.0f}")
        if best is None or best_r[0] < best[0]:
            best = (best_r[0], 0.0, best_r[1])
    if best is None:
        return (1e9, 1.0, _clone(DEFAULT_LAYOUT))
    return best


def load_layout():
    if os.path.exists(LAYOUT_FILE):
        with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return _clone(DEFAULT_LAYOUT)


# ================================================================ WALL FEATURES
def build_features(L):
    F = {w: {"holes": [], "rects": [], "outlines": []} for w in WALL_ANGLE}
    F[LCD_WALL]["outlines"].append((LCD_U, LCD_Z, LCD_W, LCD_H, "LCD outline"))
    for sx in (-1, 1):
        for sz in (-1, 1):
            F[LCD_WALL]["holes"].append((LCD_U + sx * LCD_HOLE_DX / 2, LCD_Z + sz * LCD_HOLE_DY / 2,
                                         LCD_HOLE_D, "LCD screw"))
    F[LCD_WALL]["holes"].append((LCD_U, LCD_Z + 22.0, LCD_WIRE_D, "LCD wires"))
    sw_wall, sw_u = L["switch"]
    F[sw_wall]["rects"].append((sw_u, SWITCH_Z, SWITCH_L, SWITCH_H, "rocker switch 15x10"))
    x, y, z, dx, dy = port_world("Module", "usb_c", L)
    uw = DIR_WALL.get((dx, dy), "+X")
    u = rot2(x, y, -WALL_ANGLE[uw])[0]
    F[uw]["rects"].append((u, z, USBC_L, USBC_H, "USB-C slot 12x7"))
    opp = OPPOSITE[LCD_WALL]
    others = sorted([w for w in WALL_ANGLE if w not in (LCD_WALL, opp)], key=lambda w: len(F[w]["rects"]))
    for w in (opp, others[0]):
        taken = [r[0] for r in F[w]["rects"]]
        u0 = 0.0
        for cand in (0.0, 40.0, -40.0, 60.0, -60.0, 20.0, -20.0):
            if all(abs(cand + du - t) >= 16.0 for du in VENT_XS for t in taken):
                u0 = cand
                break
        for du in VENT_XS:
            for vz in VENT_ZS:
                F[w]["holes"].append((u0 + du, vz, VENT_D, "vent"))
    return F


# ================================================================ CAD HELPERS
def _need_cq():
    if cq is None:
        sys.exit("CadQuery is not installed. Run:  pip install cadquery")


def box(cx, cy, cz, sx, sy, sz):
    return cq.Workplane("XY").box(sx, sy, sz).translate((cx, cy, cz))


def cyl(cx, cy, cz, r, h, axis="Z"):
    c = cq.Workplane("XY").circle(r).extrude(h).translate((0, 0, -h / 2.0))
    if axis == "X":
        c = c.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == "Y":
        c = c.rotate((0, 0, 0), (1, 0, 0), 90)
    return c.translate((cx, cy, cz))


def rotz(obj, deg):
    return obj if int(round(deg)) % 360 == 0 else obj.rotate((0, 0, 0), (0, 0, 1), deg)


def overlap_volume(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0


def seg(p0, p1, r):
    dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return None
    c = cq.Workplane("XY").circle(r).extrude(length).translate((0, 0, -length / 2.0))
    ux, uy, uz = dx / length, dy / length, dz / length
    ax, ay = -uy, ux
    s = math.hypot(ax, ay)
    if s > 1e-9:
        c = c.rotate((0, 0, 0), (ax, ay, 0.0), math.degrees(math.atan2(s, uz)))
    elif uz < 0:
        c = c.rotate((0, 0, 0), (1, 0, 0), 180)
    return c.translate(((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2))


# ================================================================ BUILD PARTS
def wall_cutter_hole(wall, u, z, d):
    yo = -BOX_D / 2 + WALL / 2
    return rotz(cyl(u, yo, z, d / 2, WALL + 4, "Y"), WALL_ANGLE[wall])


def wall_cutter_rect(wall, u, z, w, h):
    yo = -BOX_D / 2 + WALL / 2
    return rotz(box(u, yo, z, w, WALL + 4, h), WALL_ANGLE[wall])


def build_tray(F):
    tray = box(0, 0, -TRAY_H / 2, BOX_W, BOX_D, TRAY_H)
    tray = tray.cut(box(0, 0, -(FLOOR_T + (CAV_H + 2) / 2), CAV, CAV, CAV_H + 2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            tray = tray.union(cyl(sx * POST_XY, sy * POST_XY, -(FLOOR_T + CAV_H / 2), POST_R, CAV_H))
            tray = tray.cut(cyl(sx * MOUNT_XY, sy * MOUNT_XY, -FLOOR_T / 2, MOUNT_D / 2, FLOOR_T + 2))
    for wall, feats in F.items():
        for (u, z, d, _) in feats["holes"]:
            tray = tray.cut(wall_cutter_hole(wall, u, z, d))
        for (u, z, w, h, _) in feats["rects"]:
            tray = tray.cut(wall_cutter_rect(wall, u, z, w, h))
    return tray


def build_lid(L):
    zc = -(TRAY_H + LID_T / 2)
    lid = box(0, 0, zc, BOX_W, BOX_D, LID_T)
    hx, hy = hole_xy(L)
    lid = lid.cut(cyl(hx, hy, zc, CABLE_D / 2, LID_T + 2))
    for sx in (-1, 1):
        for sy in (-1, 1):
            lid = lid.cut(cyl(sx * POST_XY, sy * POST_XY, zc, LID_SCREW_D / 2, LID_T + 2))
            lid = lid.cut(cyl(sx * BASE_HOLE / 2, HEAD_Y + sy * BASE_HOLE / 2, zc, BASE_HOLE_D / 2, LID_T + 2))
    return lid


def build_lcd():
    yo = -BOX_D / 2
    th = WALL_ANGLE[LCD_WALL]
    pcb = box(LCD_U, yo - LCD_SO - 0.8, LCD_Z, LCD_W, 1.6, LCD_H)
    glass = box(LCD_U, yo - LCD_SO - 1.6 - 3.5, LCD_Z, 90, 7, 55)
    backpack = box(LCD_U, yo - LCD_SO + 2.5, LCD_Z + 22, 42, 5, 16)
    body = pcb.union(glass).union(backpack)
    window = box(LCD_U, yo - LCD_SO - 1.6 - 7 - 0.25, LCD_Z, 76, 0.5, 25)
    stand = None
    for sx in (-1, 1):
        for sz in (-1, 1):
            s = cyl(LCD_U + sx * LCD_HOLE_DX / 2, yo - LCD_SO / 2, LCD_Z + sz * LCD_HOLE_DY / 2, 2.5, LCD_SO, "Y")
            stand = s if stand is None else stand.union(s)
    return rotz(body, th), rotz(window, th), rotz(stand, th)


def build_head():
    hd = _HD
    sx, sy, sz = HEAD_SERVO
    base = box(0, HEAD_Y, hd["z0"] - 1.5, 35, 35, 3)
    pan_servo = box(0, HEAD_Y, hd["pan_z"], sx, sy, sz)
    bracket = box(0, HEAD_Y, hd["z_pan_bot"] - 1, 30, 30, 2)
    tilt_servo = box(0, HEAD_Y, hd["tilt_z"], sx, sy, sz)
    plat_back = hd["plat_y"] - PLAT[1] / 2
    arm = box(0, (hd["servo_front"] + plat_back) / 2, hd["tilt_z"], 8, plat_back - hd["servo_front"], 8)
    platform = box(0, hd["plat_y"], hd["tilt_z"], *PLAT)
    camera = box(0, hd["plat_front"] + CAM[1] / 2, hd["tilt_z"], *CAM)
    led = box(0, hd["led_y"], hd["led_z"], *LED_BAR)
    return {
        "base": base, "pan_servo": pan_servo, "bracket": bracket, "tilt_servo": tilt_servo,
        "arm_platform": arm.union(platform), "camera": camera, "led": led,
        "tilt_group": arm.union(platform).union(camera).union(led),
        "pan_group": bracket.union(tilt_servo), "tilt_z": hd["tilt_z"],
    }


def build_internals(L):
    parts = []
    colors = {"Pi": (0.2, 0.65, 0.3), "ESP32": (0.1, 0.1, 0.12), "Module": (0.1, 0.5, 0.55),
              "Cell": (0.12, 0.12, 0.12), "Perfboard": (0.15, 0.5, 0.25)}
    for n in COMP_NAMES:
        cx, cy, rot = L[n]
        sx, sy, sz = SPECS[n]["size"]
        zc = Z_TOP - sz / 2
        if n == "Cell":
            obj = box(0, 0, zc, sx, sy, sz).union(cyl(0, 0, Z_TOP - 9.0, 9.0, 65.0, "X"))
        elif n == "Perfboard":
            obj = box(0, 0, Z_TOP - 0.8, sx, sy, 1.6).union(box(0, 0, Z_TOP - 1.6 - 7, 30, 20, 14))
        else:
            obj = box(0, 0, zc, sx, sy, sz)
        obj = rotz(obj, rot).translate((cx, cy, 0))
        parts.append((SPECS[n]["label"], obj, colors[n]))
    wall, u = L["switch"]
    body = box(u, -CAV / 2 + SWITCH_DEPTH / 2, SWITCH_Z, SWITCH_L, SWITCH_DEPTH, SWITCH_H)
    parts.append(("Rocker switch body", rotz(body, WALL_ANGLE[wall]), (0.85, 0.1, 0.1)))
    return parts


# ================================================================ REPORTS
PIN_TABLE = [
    "PIN / CONNECTION TABLE",
    "  Pi USB          -> camera (Type-C or A) and ESP32 micro-USB (data + power for the ESP32)",
    "  ESP32 GPIO18    -> pan servo signal (orange)      GPIO19 -> tilt servo signal (orange)",
    "  ESP32 GPIO25    -> 100-220 ohm -> MOSFET gate (10k gate-to-GND)",
    "  ESP32 GPIO21/22 -> LCD SDA / SCL, LCD VCC to ESP32 VIN (5 V), GND to GND",
    "  5 V rail        -> servo red wires, LED bar red wire (from module USB-A #2)",
    "  GND rail        -> servo brown wires, MOSFET source, ESP32 GND, LCD GND",
    "  LED bar         -> red to 5 V rail, black to MOSFET DRAIN (cut off its USB plug)",
    "  Battery         -> cell + -> 5 A fuse -> switch -> module B+ ; cell - -> module B-",
    "  Module USB-A #1 -> Pi micro-USB power ; USB-A #2 -> cut USB cable -> 5 V/GND rail",
    "  Remove the LCD backpack's two I2C pull-ups (or add a level shifter): ESP32 pins are 3.3 V only",
]


def fit_report(L):
    lines = ["FIT CHECK (internal layout)"]
    issues = []
    layout_penalty(L, issues)
    if not issues:
        lines.append("  [PASS] no overlaps, plug space clear, USB-C faces a wall, nothing behind the LCD")
    for i in issues:
        lines.append(f"  [FAIL] {i}")
    lines.append("")
    lines.append("LAYOUT (centre x, y, rotation) - floor plan, +Y = front")
    for n in COMP_NAMES:
        cx, cy, rot = L[n]
        lines.append(f"  {SPECS[n]['label']:<24} ({cx:+.1f}, {cy:+.1f})  rot {int(rot)}")
    lines.append(f"  Rocker switch            wall {L['switch'][0]}, u={L['switch'][1]:+.1f}")
    lines.append(f"  LCD                      wall {LCD_WALL}, u={LCD_U:+.1f}, centre z={LCD_Z:.0f}")
    lines.append("")
    lines.append("WIRE LENGTHS (needed incl. slack vs what you have, mm)")
    for name, need, supplied, _, _, _, _ in wire_needs(L):
        if need <= supplied:
            lines.append(f"  [OK]     {name:<22} need {need:5.0f}  have {supplied:5.0f}  spare {supplied - need:4.0f}")
        else:
            lines.append(f"  [EXTEND] {name:<22} need {need:5.0f}  have {supplied:5.0f}  "
                         f"add {need - supplied:4.0f} mm (splice wire or use an extension)")
    lines.append("")
    return lines + PIN_TABLE


def sweep_report(head, lid):
    lines = ["", "CAMERA SWEEP CHECK (negative tilt = looking down; 0 collisions = clear)"]
    tz = head["tilt_z"]
    statics = [("lid", lid), ("base plate", head["base"]), ("pan servo", head["pan_servo"])]
    hits_all = {}
    for pan in SWEEP_PAN:
        for tilt in SWEEP_TILT:
            tg = head["tilt_group"].rotate((0, HEAD_Y, tz), (1, HEAD_Y, tz), tilt)
            tg = tg.rotate((0, HEAD_Y, 0), (0, HEAD_Y, 1), pan)
            pg = head["pan_group"].rotate((0, HEAD_Y, 0), (0, HEAD_Y, 1), pan)
            hits = []
            for sname, s in statics:
                if overlap_volume(tg, s) > 1.0:
                    hits.append(f"camera head hits {sname}")
                if sname != "pan servo" and overlap_volume(pg, s) > 1.0:
                    hits.append(f"pan bracket hits {sname}")
            if overlap_volume(tg, pg) > 1.0:
                hits.append("camera head hits tilt servo / bracket")
            if hits:
                hits_all[(pan, tilt)] = sorted(set(hits))
    if not hits_all:
        lines.append("  all tested pan/tilt combinations are clear")
    else:
        for (pan, tilt), hits in sorted(hits_all.items()):
            lines.append(f"  [HIT] pan {pan:+d}, tilt {tilt:+d}: {', '.join(hits)}")
        lines.append("  -> set those as software limits in the ESP32 firmware")
    return lines


# ================================================================ TEMPLATES (SVG, 1:1)
M = 12.0


def _svg(filename, title, note, w, h, holes, rects, outlines):
    W, H = w + 2 * M, h + 2 * M + 28
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">',
         '<rect width="100%" height="100%" fill="white"/>',
         f'<text x="{M}" y="8" font-family="Arial" font-size="5" font-weight="bold">{title}</text>',
         f'<text x="{M}" y="{M - 2}" font-family="Arial" font-size="3.2">{note}</text>',
         f'<rect x="{M}" y="{M}" width="{w}" height="{h}" fill="none" stroke="black" stroke-width="0.4"/>']
    for (cx, cy, rw, rh, label) in outlines:
        x, y = M + cx, M + cy
        o.append(f'<rect x="{x - rw / 2}" y="{y - rh / 2}" width="{rw}" height="{rh}" fill="none" '
                 f'stroke="#888" stroke-width="0.25" stroke-dasharray="2 1.5"/>')
        o.append(f'<text x="{x - rw / 2 + 1}" y="{y - rh / 2 - 1}" font-family="Arial" font-size="2.8" fill="#666">{label}</text>')
    for (cx, cy, rw, rh, label) in rects:
        x, y = M + cx, M + cy
        o.append(f'<rect x="{x - rw / 2}" y="{y - rh / 2}" width="{rw}" height="{rh}" fill="none" stroke="red" stroke-width="0.3"/>')
        o.append(f'<line x1="{x - 3}" y1="{y}" x2="{x + 3}" y2="{y}" stroke="red" stroke-width="0.25"/>')
        o.append(f'<line x1="{x}" y1="{y - 3}" x2="{x}" y2="{y + 3}" stroke="red" stroke-width="0.25"/>')
        o.append(f'<text x="{x + rw / 2 + 1.5}" y="{y - 1}" font-family="Arial" font-size="3" fill="red">{label}</text>')
    for (cx, cy, d, label) in holes:
        x, y = M + cx, M + cy
        o.append(f'<circle cx="{x}" cy="{y}" r="{d / 2}" fill="none" stroke="red" stroke-width="0.3"/>')
        o.append(f'<line x1="{x - d / 2 - 2}" y1="{y}" x2="{x + d / 2 + 2}" y2="{y}" stroke="red" stroke-width="0.2"/>')
        o.append(f'<line x1="{x}" y1="{y - d / 2 - 2}" x2="{x}" y2="{y + d / 2 + 2}" stroke="red" stroke-width="0.2"/>')
        o.append(f'<text x="{x + d / 2 + 2.5}" y="{y - 1}" font-family="Arial" font-size="3" fill="red">{label}</text>')
    by = M + h + 10
    o.append(f'<line x1="{M}" y1="{by}" x2="{M + 100}" y2="{by}" stroke="black" stroke-width="0.5"/>')
    o.append(f'<line x1="{M}" y1="{by - 2}" x2="{M}" y2="{by + 2}" stroke="black" stroke-width="0.5"/>')
    o.append(f'<line x1="{M + 100}" y1="{by - 2}" x2="{M + 100}" y2="{by + 2}" stroke="black" stroke-width="0.5"/>')
    o.append(f'<text x="{M}" y="{by + 7}" font-family="Arial" font-size="3.5">This bar must measure 100 mm. '
             f'Print at 100% / Actual size (no fit-to-page).</text>')
    o.append('</svg>')
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(o))


def write_templates(folder, L):
    hw = BOX_W / 2
    F = build_features(L)
    # lid, seen from outside (looking up): page-x = -x, FRONT (+Y) at the top
    def pg(x, y):
        return hw - x, hw - y
    holes = [(*pg(*hole_xy(L)), CABLE_D, "camera cable hole")]
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append((*pg(sx * BASE_HOLE / 2, HEAD_Y + sy * BASE_HOLE / 2), BASE_HOLE_D, "head screw"))
    px, py = pg(0, HEAD_Y)
    _svg(os.path.join(folder, "template_lid.svg"), "LID drill template",
         "View: OUTSIDE face of the lid (room side). FRONT = top of sheet. Your lid may already have screw holes.",
         BOX_W, BOX_D, holes, [], [(px, py, 35, 35, "pan/tilt base")])
    holes = [(*pg(sx * MOUNT_XY, sy * MOUNT_XY), MOUNT_D, "ceiling screw") for sx in (-1, 1) for sy in (-1, 1)]
    _svg(os.path.join(folder, "template_floor.svg"), "FLOOR (ceiling side) drill template",
         "View: INSIDE the box looking at the floor. FRONT = top of sheet.", BOX_W, BOX_D, holes, [], [])
    for wall, feats in F.items():
        tags = []
        if feats["outlines"]:
            tags.append("LCD")
        tags += [r[4].split(" ")[0] for r in feats["rects"]]
        if any(h[3] == "vent" for h in feats["holes"]):
            tags.append("vents")
        holes = [(u + hw, -z, d, lab) for (u, z, d, lab) in feats["holes"]]
        rects = [(u + hw, -z, w, h, lab) for (u, z, w, h, lab) in feats["rects"]]
        outl = [(u + hw, -z, w, h, lab) for (u, z, w, h, lab) in feats["outlines"]]
        _svg(os.path.join(folder, f"template_wall_{WALL_FILE[wall]}.svg"),
             f"WALL {wall}: " + (", ".join(tags) if tags else "no features"),
             "View: from OUTSIDE, ceiling edge at TOP, left-to-right as you face the wall. +Y wall = front (camera side).",
             BOX_W, TRAY_H, holes, rects, outl)


# ================================================================ MAIN
def build_all(L, run_sweep):
    _need_cq()
    os.makedirs(OUT_DIR, exist_ok=True)
    F = build_features(L)
    print("Building enclosure, LCD, head...")
    tray, lid = build_tray(F), build_lid(L)
    lcd_body, lcd_window, lcd_stand = build_lcd()
    head = build_head()
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
    add("tilt_arm_platform", head["arm_platform"], (0.15, 0.15, 0.15))
    add("camera", head["camera"], (0.02, 0.02, 0.02))
    add("led_bar", head["led"], (1.0, 0.9, 0.4))
    for name, obj, rgb in build_internals(L):
        add(name, obj, rgb)
    print("Adding wires...")
    for i, (name, need, supplied, _, pts, color, radius) in enumerate(wire_needs(L)):
        tag = name.replace(" ", "_").replace("+", "plus").replace("-", "")
        for k in range(len(pts) - 1):
            s = seg(pts[k], pts[k + 1], radius)
            if s is not None:
                add(f"wire{i:02d}_{tag}_{k}", s, color)
        for k, p in enumerate(pts[1:-1]):
            add(f"wire{i:02d}_{tag}_j{k}", cq.Workplane("XY").sphere(radius).translate(p), color)

    path = os.path.join(OUT_DIR, "classcan_assembly.step")
    assy.save(path)
    print("Saved", path)
    for ext, kind in (("glb", "GLTF"), ("stl", "STL")):
        try:
            assy.save(os.path.join(OUT_DIR, f"classcan_assembly.{ext}"), kind)
            print("Saved", ext)
        except Exception as e:
            print(f"(skipped {ext}: {e})")
    write_templates(OUT_DIR, L)
    report = fit_report(L)
    if run_sweep:
        print("Running camera sweep (can take a minute)...")
        report += sweep_report(head, lid)
    with open(os.path.join(OUT_DIR, "report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print("\n".join(report))
    print(f"\nDone. Open {OUT_DIR}/classcan_assembly.step in Autodesk Viewer or Fusion.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--optimize", action="store_true", help="re-run the wire-aware layout search")
    ap.add_argument("--no-sweep", action="store_true")
    ap.add_argument("--seed", type=int, default=7, help="layout search seed (try another if it fails)")
    args = ap.parse_args()
    if args.optimize:
        print("Searching for a layout with short wires and clear plug space (about a minute)...")
        cost, pen, L = optimize(restarts=40, seed=args.seed)
        print(f"Best: cost {cost:.0f}, penalty {pen:.1f}")
        with open(LAYOUT_FILE, "w", encoding="utf-8") as f:
            json.dump(L, f, indent=1)
        print(f"Saved {LAYOUT_FILE}")
        if pen > 0:
            print("WARNING: no fully valid layout found; try again or loosen sizes.")
    L = load_layout()
    if cq is None:
        print("\n".join(fit_report(L)))
        sys.exit("\nCadQuery is not installed (pip install cadquery). Layout/wire report printed above.")
    build_all(L, not args.no_sweep)


if __name__ == "__main__":
    main()