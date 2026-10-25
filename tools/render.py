"""
Render a generated Minecraft world (region files) to preview images.

usage: python tools/render.py <world_folder> <out_dir> [radius_blocks]

Makes 3D views of the islands (from above, level and from below) plus a
top-down map, so the shapes can be compared with reference screenshots
without launching the game. Needs numpy and Pillow.
"""
import math
import os
import struct
import sys
import zlib

import numpy as np
from PIL import Image

MIN_Y = -64

# ----------------------------------------------------------------- NBT ----


class Buf:
    __slots__ = ("b", "i")

    def __init__(self, b):
        self.b = b
        self.i = 0

    def take(self, n):
        v = self.b[self.i:self.i + n]
        self.i += n
        return v


def read_payload(buf, t):
    if t == 1:
        return struct.unpack(">b", buf.take(1))[0]
    if t == 2:
        return struct.unpack(">h", buf.take(2))[0]
    if t == 3:
        return struct.unpack(">i", buf.take(4))[0]
    if t == 4:
        return struct.unpack(">q", buf.take(8))[0]
    if t == 5:
        return struct.unpack(">f", buf.take(4))[0]
    if t == 6:
        return struct.unpack(">d", buf.take(8))[0]
    if t == 7:
        n = struct.unpack(">i", buf.take(4))[0]
        return buf.take(n)
    if t == 8:
        n = struct.unpack(">H", buf.take(2))[0]
        return buf.take(n).decode("utf-8", "replace")
    if t == 9:
        et = buf.take(1)[0]
        n = struct.unpack(">i", buf.take(4))[0]
        return [read_payload(buf, et) for _ in range(n)]
    if t == 10:
        d = {}
        while True:
            tt = buf.take(1)[0]
            if tt == 0:
                return d
            nl = struct.unpack(">H", buf.take(2))[0]
            name = buf.take(nl).decode("utf-8", "replace")
            d[name] = read_payload(buf, tt)
    if t == 11:
        n = struct.unpack(">i", buf.take(4))[0]
        return np.frombuffer(buf.take(4 * n), dtype=">i4")
    if t == 12:
        n = struct.unpack(">i", buf.take(4))[0]
        return np.frombuffer(buf.take(8 * n), dtype=">i8")
    raise ValueError(t)


def read_nbt(data):
    buf = Buf(data)
    t = buf.take(1)[0]
    nl = struct.unpack(">H", buf.take(2))[0]
    buf.take(nl)
    return read_payload(buf, t)


# --------------------------------------------------------------- blocks ----

TRANSPARENT_WORDS = ("air", "short_grass", "tall_grass", "fern", "dead_bush", "tulip", "orchid",
                     "allium", "bluet", "daisy", "cornflower", "lily_of_the_valley", "dandelion",
                     "poppy", "rose_bush", "peony", "lilac", "sunflower", "sweet_berry", "vine",
                     "glow_lichen", "torch", "seagrass", "kelp", "sugar_cane", "pink_petals",
                     "mushroom", "button", "rail", "sapling", "bush", "lantern", "carpet", "pressure_plate")

COLORS = {
    "grass_block": (92, 140, 60), "dirt": (134, 96, 67), "coarse_dirt": (119, 85, 59),
    "podzol": (91, 63, 24), "mycelium": (111, 99, 105), "stone": (125, 125, 125),
    "granite": (149, 103, 85), "andesite": (136, 136, 136), "diorite": (188, 188, 188),
    "tuff": (108, 109, 102), "deepslate": (80, 80, 82), "calcite": (223, 224, 220),
    "snow_block": (240, 250, 250), "snow": (240, 250, 250), "sand": (219, 207, 163),
    "sandstone": (216, 203, 155), "red_sand": (190, 102, 33), "gravel": (131, 127, 126),
    "water": (63, 118, 228), "lava": (207, 92, 20), "mud": (60, 57, 60), "moss_block": (89, 109, 45),
    "white_wool": (234, 236, 236), "cobblestone": (120, 120, 120), "bedrock": (60, 60, 60),
    "terracotta": (152, 94, 67), "orange_terracotta": (161, 83, 37), "red_terracotta": (143, 61, 46),
    "smooth_sandstone": (223, 214, 170), "ice": (145, 183, 253), "packed_ice": (141, 180, 250),
    "clay": (160, 166, 179), "dripstone_block": (134, 107, 92), "sculk": (12, 29, 36),
}


def color_for(name):
    n = name.split(":")[-1]
    if n in COLORS:
        return COLORS[n]
    if "leaves" in n:
        return (60, 110, 40) if "cherry" not in n else (230, 170, 200)
    if n.endswith("_log") or n.endswith("_wood") or "stem" in n:
        return (100, 75, 45)
    if "ore" in n:
        return (110, 110, 110) if "deepslate" in n else (135, 130, 125)
    if "planks" in n or "stairs" in n or "slab" in n or "fence" in n or "door" in n:
        return (160, 120, 75)
    if "deepslate" in n:
        return (75, 75, 78)
    if "terracotta" in n:
        return (150, 90, 65)
    return (150, 150, 150)


def is_transparent(name):
    n = name.split(":")[-1]
    if "leaves" in n:
        return False
    return any(w in n for w in TRANSPARENT_WORDS)


# ---------------------------------------------------------------- world ----


def load_world(world, radius, cx=0, cz=0):
    names = ["minecraft:air"]
    index = {"minecraft:air": 0}
    size = radius * 2
    vol = None
    height = None
    region_dir = os.path.join(world, "region")
    for fn in os.listdir(region_dir):
        if not fn.endswith(".mca"):
            continue
        _, rx, rz, _ = fn.split(".")
        rx, rz = int(rx), int(rz)
        data = open(os.path.join(region_dir, fn), "rb").read()
        if len(data) < 8192:
            continue
        for i in range(1024):
            off = int.from_bytes(data[i * 4:i * 4 + 3], "big")
            if off == 0:
                continue
            ccx = rx * 32 + (i % 32)
            ccz = rz * 32 + (i // 32)
            bx, bz = ccx * 16 + radius - cx, ccz * 16 + radius - cz
            if bx < 0 or bz < 0 or bx + 16 > size or bz + 16 > size:
                continue
            o = off * 4096
            ln = int.from_bytes(data[o:o + 4], "big")
            comp = data[o + 4]
            raw = data[o + 5:o + 4 + ln]
            if comp != 2:
                continue
            chunk = read_nbt(zlib.decompress(raw))
            if chunk.get("Status") not in ("minecraft:full", "full"):
                continue
            secs = chunk.get("sections", [])
            if height is None:
                ys = [s["Y"] for s in secs]
                height = (max(ys) + 1) * 16 - MIN_Y
                vol = np.zeros((size, height, size), dtype=np.uint8)
            for s in secs:
                bs = s.get("block_states")
                if not bs:
                    continue
                pal = bs["palette"]
                ids = []
                for p in pal:
                    nm = p["Name"]
                    if is_transparent(nm):
                        nm = "minecraft:air"
                    if nm not in index:
                        index[nm] = len(names)
                        names.append(nm)
                    ids.append(index[nm])
                ids = np.array(ids, dtype=np.uint8)
                sy = s["Y"] * 16 - MIN_Y
                if sy < 0 or sy + 16 > height:
                    continue
                if "data" not in bs:
                    arr = np.full(4096, ids[0], dtype=np.uint8)
                else:
                    bits = max(4, int(math.ceil(math.log2(len(pal)))))
                    per = 64 // bits
                    longs = bs["data"].astype(np.int64).view(np.uint64)
                    mask = np.uint64((1 << bits) - 1)
                    parts = [(longs >> np.uint64(k * bits)) & mask for k in range(per)]
                    idx = np.stack(parts, axis=1).reshape(-1)[:4096].astype(np.int64)
                    arr = ids[idx]
                arr = arr.reshape(16, 16, 16)  # y, z, x
                vol[bx:bx + 16, sy:sy + 16, bz:bz + 16] = arr.transpose(2, 0, 1)
    return vol, names


# --------------------------------------------------------------- render ----

SKY_TOP = np.array([120, 160, 215], dtype=np.float32)
SKY_BOT = np.array([190, 205, 230], dtype=np.float32)


def render_view(vol, names, azimuth_deg, elev_deg, out, scale=1.0):
    pal = np.array([color_for(n) for n in names], dtype=np.float32)
    solid = vol != 0
    X, H, Z = vol.shape
    az = math.radians(azimuth_deg)
    el = math.radians(elev_deg)
    # camera looks along d (towards the scene)
    dx, dz = math.cos(az), math.sin(az)
    d = np.array([dx * math.cos(el), -math.sin(el), dz * math.cos(el)])
    right = np.array([-dz, 0.0, dx])
    up = np.cross(right, d)

    # faces the camera can see
    faces = []
    if d[0] > 0.05:
        faces.append((0, -1, 0.80))
    if d[0] < -0.05:
        faces.append((0, 1, 0.80))
    if d[2] > 0.05:
        faces.append((2, -1, 0.66))
    if d[2] < -0.05:
        faces.append((2, 1, 0.66))
    if d[1] < -0.05:
        faces.append((1, 1, 1.0))   # top faces
    if d[1] > 0.05:
        faces.append((1, -1, 0.48))  # bottom faces

    shade = np.zeros(vol.shape, dtype=np.float32)
    for axis, sign, b in faces:
        air = ~solid
        nb = np.ones_like(solid)
        sl_dst = [slice(None)] * 3
        sl_src = [slice(None)] * 3
        if sign > 0:
            sl_dst[axis] = slice(0, -1)
            sl_src[axis] = slice(1, None)
        else:
            sl_dst[axis] = slice(1, None)
            sl_src[axis] = slice(0, -1)
        nb[tuple(sl_dst)] = air[tuple(sl_src)]
        exposed = solid & nb
        shade = np.where(exposed & (shade < b), b, shade)
    xs, ys, zs = np.nonzero(shade > 0)
    sh = shade[xs, ys, zs]
    col = pal[vol[xs, ys, zs]] * sh[:, None]
    # darker inside deep shadows below big islands: simple height AO
    p = np.stack([xs - X / 2, ys.astype(np.float32), zs - Z / 2], axis=1).astype(np.float32)
    depth = p @ d
    u = p @ right
    v = -(p @ up)
    u = ((u - u.min()) * scale).astype(np.int32)
    v = ((v - v.min()) * scale).astype(np.int32)
    k = int(math.ceil(scale)) + 1
    W, Hh = u.max() + k + 1, v.max() + k + 1
    dn = (depth - depth.min()) / (np.ptp(depth) + 1e-6)
    fog = (dn ** 1.2 * 0.75)[:, None]
    grad = np.linspace(0, 1, Hh)[:, None]
    sky = SKY_TOP * (1 - grad) + SKY_BOT * grad
    img = np.repeat(sky[:, None, :], W, axis=1)
    fogc = SKY_BOT
    col = col * (1 - fog) + fogc * fog
    order = np.argsort(-depth)
    u, v, col = u[order], v[order], col[order]
    for oy in range(k):
        for ox in range(k):
            img[v + oy, u + ox] = col
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out)


def render_map(vol, names, out):
    pal = np.array([color_for(n) for n in names], dtype=np.float32)
    solid = vol != 0
    X, H, Z = vol.shape
    rev = solid[:, ::-1, :]
    top = H - 1 - np.argmax(rev, axis=1)
    has = solid.any(axis=1)
    ids = np.take_along_axis(vol, top[:, None, :], axis=1)[:, 0, :]
    col = pal[ids]
    hs = np.zeros_like(top, dtype=np.float32)
    hs[1:, :] = (top[1:, :] - top[:-1, :])
    light = np.clip(1.0 + hs * 0.05, 0.6, 1.3)
    height_tint = 0.55 + 0.45 * (top / H)
    col = col * (light * height_tint)[:, :, None]
    col[~has] = (40, 50, 90)
    Image.fromarray(np.clip(col.transpose(1, 0, 2), 0, 255).astype(np.uint8)).save(out)


if __name__ == "__main__":
    world, outdir = sys.argv[1], sys.argv[2]
    radius = int(sys.argv[3]) if len(sys.argv) > 3 else 384
    os.makedirs(outdir, exist_ok=True)
    vol, names = load_world(world, radius)
    print("blocks:", len(names), "solid:", int((vol != 0).sum()))
    render_map(vol, names, os.path.join(outdir, "map.png"))
    render_view(vol, names, 45, 18, os.path.join(outdir, "view_above.png"))
    render_view(vol, names, 45, 2, os.path.join(outdir, "view_level.png"))
    render_view(vol, names, 45, -14, os.path.join(outdir, "view_below.png"))
    render_view(vol, names, 135, 6, os.path.join(outdir, "view_level2.png"))
    print("done")
