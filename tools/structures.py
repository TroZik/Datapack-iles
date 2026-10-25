"""
New structures for the islands, built block by block and saved as structure
templates (.nbt). Used by build_pack.py.

Coordinates: x/z horizontal, y up. y = 0 is the ground layer (it replaces the
surface block), y = 1 is the first layer standing on the ground.
"""
import gzip
import io
import math
import random
import struct

DATA_VERSION = 3955  # Minecraft 1.21.1

# ------------------------------------------------------------------ NBT ----
TAG_END, TAG_INT, TAG_STRING, TAG_LIST, TAG_COMPOUND = 0, 3, 8, 9, 10


class Int(int):
    pass


def _w_string(out, s):
    b = s.encode("utf-8")
    out.write(struct.pack(">H", len(b)))
    out.write(b)


def _tag_type(v):
    if isinstance(v, bool):
        raise TypeError("no bools in NBT")
    if isinstance(v, int):
        return TAG_INT
    if isinstance(v, str):
        return TAG_STRING
    if isinstance(v, list):
        return TAG_LIST
    if isinstance(v, dict):
        return TAG_COMPOUND
    raise TypeError(type(v))


def _w_payload(out, v):
    t = _tag_type(v)
    if t == TAG_INT:
        out.write(struct.pack(">i", v))
    elif t == TAG_STRING:
        _w_string(out, v)
    elif t == TAG_LIST:
        et = _tag_type(v[0]) if v else TAG_END
        out.write(struct.pack(">bi", et, len(v)))
        for e in v:
            _w_payload(out, e)
    else:
        for k, e in v.items():
            out.write(struct.pack(">b", _tag_type(e)))
            _w_string(out, k)
            _w_payload(out, e)
        out.write(b"\x00")


def nbt_bytes(root):
    out = io.BytesIO()
    out.write(struct.pack(">b", TAG_COMPOUND))
    _w_string(out, "")
    _w_payload(out, root)
    return gzip.compress(out.getvalue())


# ------------------------------------------------------------- builder ----
class Build:
    def __init__(self):
        self.blocks = {}  # (x, y, z) -> (name, props, nbt)

    def set(self, x, y, z, name, nbt=None, **props):
        if not name.startswith("minecraft:"):
            name = "minecraft:" + name
        self.blocks[(x, y, z)] = (name, {k: str(v).lower() for k, v in props.items()}, nbt)

    def fill(self, x0, y0, z0, x1, y1, z1, name, **props):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    self.set(x, y, z, name, **props)

    def get(self, x, y, z):
        b = self.blocks.get((x, y, z))
        return b[0] if b else None

    def chest(self, x, y, z, loot, facing="north"):
        self.set(x, y, z, "chest", nbt={"id": "minecraft:chest", "LootTable": loot}, facing=facing, type="single",
                 waterlogged="false")

    def to_nbt(self):
        xs = [p[0] for p in self.blocks]
        ys = [p[1] for p in self.blocks]
        zs = [p[2] for p in self.blocks]
        ox, oy, oz = min(xs), min(ys), min(zs)
        size = [Int(max(xs) - ox + 1), Int(max(ys) - oy + 1), Int(max(zs) - oz + 1)]
        palette, index, blocks = [], {}, []
        for (x, y, z), (name, props, nbt) in sorted(self.blocks.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
            key = (name, tuple(sorted(props.items())))
            if key not in index:
                index[key] = len(palette)
                entry = {"Name": name}
                if props:
                    entry["Properties"] = dict(props)
                palette.append(entry)
            b = {"pos": [Int(x - ox), Int(y - oy), Int(z - oz)], "state": Int(index[key])}
            if nbt:
                b["nbt"] = nbt
            blocks.append(b)
        return nbt_bytes({"DataVersion": Int(DATA_VERSION), "size": size, "palette": palette,
                          "blocks": blocks, "entities": []})


def clear_above(b, x0, z0, x1, z1, y0, y1):
    """Air everywhere not already set (removes grass, flowers, leaves in the way)."""
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in range(y0, y1 + 1):
                if (x, y, z) not in b.blocks:
                    b.set(x, y, z, "air")


# ------------------------------------------------------- forest cabin ----
def cabin():
    b = Build()
    W, D = 9, 7  # x 0..8, z 0..6 ; door on z = 0
    b.fill(0, 0, 0, W - 1, 0, D - 1, "cobblestone")
    b.fill(1, 0, 1, W - 2, 0, D - 2, "spruce_planks")
    for y in range(1, 4):
        for x in range(W):
            for z in range(D):
                edge_x, edge_z = x in (0, W - 1), z in (0, D - 1)
                if edge_x and edge_z:
                    b.set(x, y, z, "spruce_log", axis="y")
                elif edge_x or edge_z:
                    b.set(x, y, z, "spruce_planks" if y != 3 else "stripped_spruce_log",
                          **({"axis": "x" if edge_z else "z"} if y == 3 else {}))
                else:
                    b.set(x, y, z, "air")
    # door + windows
    b.set(4, 1, 0, "spruce_door", facing="south", half="lower", hinge="left", open="false", powered="false")
    b.set(4, 2, 0, "spruce_door", facing="south", half="upper", hinge="left", open="false", powered="false")
    for (x, z) in [(2, 0), (6, 0), (2, D - 1), (6, D - 1), (0, 3), (W - 1, 3)]:
        b.set(x, 2, z, "glass_pane")
    # gable roof along x, overhang of one block
    for i, (zl, zr) in enumerate([(-1, D), (0, D - 1), (1, D - 2), (2, D - 3)]):
        y = 4 + i
        for x in range(-1, W + 1):
            b.set(x, y, zl, "spruce_stairs", facing="south", half="bottom", shape="straight", waterlogged="false")
            b.set(x, y, zr, "spruce_stairs", facing="north", half="bottom", shape="straight", waterlogged="false")
        for x in (0, W - 1):  # gable walls
            for z in range(zl + 1, zr):
                b.set(x, y, z, "spruce_planks")
        for x in range(1, W - 1):
            for z in range(zl + 1, zr):
                b.set(x, y, z, "air")
    for x in range(-1, W + 1):
        b.set(x, 8, 3, "spruce_slab", type="bottom", waterlogged="false")
    for x in range(1, W - 1):
        b.set(x, 4, 3, "air")
    # chimney
    b.fill(W, 0, 4, W, 7, 5, "cobblestone")
    b.set(W, 8, 4, "campfire", lit="true", facing="north", signal_fire="false", waterlogged="false")
    # interior
    b.set(1, 1, 5, "red_bed", facing="east", part="foot", occupied="false")
    b.set(2, 1, 5, "red_bed", facing="east", part="head", occupied="false")
    b.set(1, 1, 1, "crafting_table")
    b.set(W - 2, 1, 5, "furnace", facing="west", lit="false")
    b.chest(W - 2, 1, 1, "minecraft:chests/village/village_taiga_house", facing="west")
    b.set(W - 2, 1, 3, "barrel", facing="up", open="false")
    b.set(4, 3, 3, "lantern", hanging="true", waterlogged="false")
    b.set(3, 1, 5, "potted_fern")
    b.set(2, 1, 1, "spruce_stairs", facing="west", half="bottom", shape="straight", waterlogged="false")
    # woodpile and path outside
    for z in range(1, 5):
        b.set(-1, 1, z, "oak_log", axis="z")
    b.set(-1, 2, 2, "oak_log", axis="z")
    b.set(-1, 2, 3, "oak_log", axis="z")
    for z in range(-3, 0):
        b.set(4, 0, z, "dirt_path")
    b.set(3, 1, -1, "lantern", hanging="false", waterlogged="false")
    clear_above(b, -1, -3, W, D, 1, 8)
    return b


# ------------------------------------------------------------- farm ----
def farm():
    b = Build()
    rnd = random.Random(4)
    # field x 0..12, z 0..10 ; fence around ; water channels at x = 4 and 8
    X0, X1, Z0, Z1 = 0, 12, 0, 10
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            border = x in (X0, X1) or z in (Z0, Z1)
            if border:
                b.set(x, 0, z, "coarse_dirt")
                b.set(x, 1, z, "oak_fence")
            elif x in (4, 8):
                b.set(x, 0, z, "water", level=0)
                b.set(x, -1, z, "dirt")
            else:
                b.set(x, 0, z, "farmland", moisture=7)
                b.set(x, -1, z, "dirt")
                if x < 4:
                    crop = "wheat"
                elif x < 8:
                    crop = "carrots" if z <= 5 else "potatoes"
                else:
                    crop = "beetroots" if z <= 5 else "wheat"
                age = 3 if crop == "beetroots" else 7
                b.set(x, 1, z, crop, age=rnd.choice([age, age, age - 2]))
    b.set(6, 1, Z0, "oak_fence_gate", facing="south", in_wall="false", open="false", powered="false")
    for z in range(-3, 0):
        b.set(6, 0, z, "dirt_path")
    # scarecrow
    b.set(6, 1, 5, "oak_fence")
    b.set(6, 2, 5, "hay_block", axis="y")
    b.set(6, 3, 5, "carved_pumpkin", facing="south")
    b.set(5, 2, 5, "oak_fence")
    b.set(7, 2, 5, "oak_fence")
    b.set(6, 0, 5, "dirt")
    # shed x 14..18, z 2..7 (open front facing the field)
    SX0, SX1, SZ0, SZ1 = 14, 18, 2, 7
    b.fill(SX0, 0, SZ0, SX1, 0, SZ1, "oak_planks")
    for x in range(SX0, SX1 + 1):
        for z in range(SZ0, SZ1 + 1):
            corner = x in (SX0, SX1) and z in (SZ0, SZ1)
            for y in range(1, 4):
                if corner:
                    b.set(x, y, z, "oak_log", axis="y")
                elif x == SX1 or z in (SZ0, SZ1):
                    b.set(x, y, z, "oak_planks")
                else:
                    b.set(x, y, z, "air")
    for x in range(SX0 - 1, SX1 + 2):
        for z in range(SZ0 - 1, SZ1 + 2):
            b.set(x, 4, z, "dark_oak_slab", type="bottom", waterlogged="false")
    b.set(SX1 - 1, 1, SZ0 + 1, "hay_block", axis="y")
    b.set(SX1 - 1, 2, SZ0 + 1, "hay_block", axis="x")
    b.set(SX1 - 1, 1, SZ0 + 2, "hay_block", axis="z")
    b.set(SX1 - 1, 1, SZ1 - 1, "composter", level=4)
    b.chest(SX1 - 1, 1, SZ1 - 2, "minecraft:chests/village/village_plains_house", facing="west")
    b.set(SX0 + 1, 1, SZ1 - 1, "barrel", facing="up", open="false")
    b.set(SX0, 3, (SZ0 + SZ1) // 2, "lantern", hanging="true", waterlogged="false")
    for z in range(SZ0, SZ1 + 1):
        b.set(SX0 - 1, 0, z, "dirt_path")
    clear_above(b, -1, -3, SX1 + 1, Z1 + 1, 1, 5)
    return b


# ------------------------------------------------------------ ruins ----
def ruin_block(rnd):
    return rnd.choices(["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "cobblestone",
                        "mossy_cobblestone"], [5, 4, 3, 2, 3])[0]


def ruins():
    b = Build()
    rnd = random.Random(11)
    N = 13
    # floor: broken pavement
    for x in range(N):
        for z in range(N):
            if rnd.random() < 0.75:
                b.set(x, 0, z, rnd.choice(["mossy_cobblestone", "cobblestone", "stone_bricks", "gravel", "mossy_stone_bricks"]))
    # walls of an old hall (x 1..11, z 1..11) with broken heights
    for x in range(1, N - 1):
        for z in range(1, N - 1):
            if x in (1, N - 2) or z in (1, N - 2):
                h = int(1 + 5 * abs(math.sin(x * 0.7 + z * 1.3)) * rnd.random() ** 0.5)
                if (x, z) in [(6, 1), (6, 11)]:
                    h = 0  # doorways
                for y in range(1, h + 1):
                    b.set(x, y, z, ruin_block(rnd))
    # an arch still standing
    for y in range(1, 7):
        b.set(4, y, 6, "stone_bricks" if y < 6 else "chiseled_stone_bricks")
        b.set(8, y, 6, "mossy_stone_bricks" if y % 2 else "stone_bricks")
    for x in range(4, 9):
        b.set(x, 7, 6, "stone_brick_slab", type="bottom", waterlogged="false")
    b.set(5, 6, 6, "stone_brick_stairs", facing="east", half="top", shape="straight", waterlogged="false")
    b.set(7, 6, 6, "stone_brick_stairs", facing="west", half="top", shape="straight", waterlogged="false")
    # fallen pillar
    for x in range(8, 12):
        b.set(x, 1, 9, "stone_brick_wall" if x == 11 else "polished_andesite")
    # treasure
    b.chest(3, 1, 9, "minecraft:chests/simple_dungeon", facing="east")
    b.set(3, 1, 10, "cobweb")
    b.set(10, 1, 3, "cobweb")
    b.set(9, 1, 3, "candle", candles=3, lit="false", waterlogged="false")
    b.set(2, 1, 2, "mossy_cobblestone_slab", type="bottom", waterlogged="false")
    clear_above(b, 1, 1, N - 2, N - 2, 1, 3)
    return b


# ----------------------------------------------------- ruined tower ----
def tower():
    b = Build()
    rnd = random.Random(23)
    R = 4.6
    C = 5
    top_h = 22
    for x in range(-1, 2 * C + 2):
        for z in range(-1, 2 * C + 2):
            d = math.hypot(x - C, z - C)
            if d <= R + 0.5:
                b.set(x, 0, z, ruin_block(rnd))
            if R - 1.0 < d <= R + 0.5:
                ang = math.atan2(z - C, x - C)
                # broken top: height depends on the angle
                h = int(top_h - 9 * (0.5 + 0.5 * math.sin(ang * 2 + 0.8)) - rnd.random() * 3)
                for y in range(1, h + 1):
                    if (x, z) == (C, C - 5) or (x, z) == (C, C - 4):
                        if y <= 2:
                            continue  # entrance
                    if y in (7, 13) and abs(math.sin(ang * 3)) > 0.95:
                        b.set(x, y, z, "air")  # arrow slits
                        continue
                    b.set(x, y, z, ruin_block(rnd))
            elif d <= R - 1.0:
                for y in range(1, top_h):
                    b.set(x, y, z, "air")
    # half-collapsed floors
    for fy in (8, 15):
        for x in range(2 * C + 1):
            for z in range(2 * C + 1):
                if math.hypot(x - C, z - C) <= R - 1.0 and rnd.random() < 0.7 and not (x == C + 3 and z == C):
                    b.set(x, fy, z, "spruce_planks")
    for y in range(1, 16):
        b.set(C + 3, y, C, "ladder", facing="west", waterlogged="false")
    b.chest(C - 2, 16, C + 1, "minecraft:chests/village/village_weaponsmith", facing="east")
    b.set(C - 1, 9, C - 2, "cobweb")
    b.set(C + 1, 16, C - 2, "cobweb")
    # rubble at the foot
    for _ in range(14):
        a = rnd.random() * 6.28
        r = R + 1 + rnd.random() * 2.5
        x, z = int(C + r * math.cos(a)), int(C + r * math.sin(a))
        if rnd.random() < 0.3:
            b.set(x, 1, z, "stone_brick_slab", type="bottom", waterlogged="false")
        else:
            b.set(x, 1, z, rnd.choice(["mossy_cobblestone", "cobblestone", "mossy_stone_bricks"]))
    return b


STRUCTURES = {
    "cabin": cabin,
    "farm": farm,
    "ruins": ruins,
    "ruined_tower": tower,
}
