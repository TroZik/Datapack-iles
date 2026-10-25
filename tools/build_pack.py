"""
Generates the "Iles Volantes" datapack (Minecraft Java 1.21.1).

All island shapes are made with vanilla density functions, so the pack needs
no mod. Tweak the PARAMS below, run `python tools/build_pack.py`, and the
`data/` folder at the repository root is rewritten.
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NS = "iles"

# ---------------------------------------------------------------------------
# World height: -64 .. 383 (448 blocks) to give room for three island levels.
# ---------------------------------------------------------------------------
MIN_Y = -64
HEIGHT = 448

# ---------------------------------------------------------------------------
# Island levels. Each level lives in its own vertical band [floor, cap], and
# the bands never overlap, so islands of different levels can never touch.
#   a = sky level (grass, trees, villages)  b = stone level  c = deepslate level
# ---------------------------------------------------------------------------
LEVELS = {
    "a": dict(
        floor=118, cap=380,
        base=252, height_var=20, roll=3.0,
        mask_octave=-8, mask_amps=[1.0, 0.8, 0.45, 0.25, 0.1],
        warp=70.0, threshold=0.28,
        edge_k=260.0,               # e -> roughly "blocks from the rim"
        thick0=9.0,                 # cliff height at the rim before the cone starts
        depth_pts=[(0.0, 0.0), (0.03, 6.0), (0.08, 17.0), (0.15, 33.0),
                   (0.25, 54.0), (0.4, 80.0), (0.6, 108.0, 100.0)],
        depth_var=0.3,
        spike_pts=[(0.08, 0.0), (0.25, 8.0), (0.4, 22.0), (0.6, 45.0), (0.9, 70.0, 60.0)],
        spike_size=[(0.0, 0.15), (0.04, 0.5), (0.15, 1.0)],
        keel_pts=[(0.0, 0.0), (0.2, 12.0), (0.45, 40.0), (0.8, 80.0, 80.0)],
        keel_size=[(0.0, 0.0), (0.06, 0.4), (0.25, 1.0)],
        rim_pts=[(0.0, -4.0), (0.015, -1.0), (0.05, 1.5), (0.2, 4.0), (0.6, 6.0)],
        mountains=60.0,
        detail=3.5,
    ),
    "b": dict(
        floor=34, cap=110,
        base=94, height_var=7, roll=2.0,
        mask_octave=-7, mask_amps=[1.0, 0.8, 0.45, 0.25],
        warp=40.0, threshold=0.34,
        edge_k=150.0,
        thick0=5.0,
        depth_pts=[(0.0, 0.0), (0.03, 4.0), (0.08, 11.0), (0.15, 20.0),
                   (0.3, 34.0), (0.6, 46.0, 10.0)],
        depth_var=0.3,
        spike_pts=[(0.08, 0.0), (0.25, 5.0), (0.45, 14.0), (0.75, 26.0, 30.0)],
        spike_size=[(0.0, 0.2), (0.04, 0.6), (0.12, 1.0)],
        keel_pts=[(0.0, 0.0), (0.25, 6.0), (0.5, 16.0), (0.8, 26.0, 20.0)],
        keel_size=[(0.0, 0.0), (0.06, 0.5), (0.2, 1.0)],
        rim_pts=[(0.0, -3.0), (0.02, 0.0), (0.1, 2.0), (0.5, 3.0)],
        mountains=0.0,
        detail=3.0,
    ),
    "c": dict(
        floor=-62, cap=26,
        base=12, height_var=7, roll=2.0,
        mask_octave=-7, mask_amps=[1.0, 0.8, 0.45, 0.25],
        warp=40.0, threshold=0.34,
        edge_k=150.0,
        thick0=5.0,
        depth_pts=[(0.0, 0.0), (0.03, 4.0), (0.08, 12.0), (0.15, 22.0),
                   (0.3, 38.0), (0.6, 50.0, 10.0)],
        depth_var=0.3,
        spike_pts=[(0.08, 0.0), (0.25, 5.0), (0.45, 14.0), (0.75, 28.0, 30.0)],
        spike_size=[(0.0, 0.2), (0.04, 0.6), (0.12, 1.0)],
        keel_pts=[(0.0, 0.0), (0.25, 6.0), (0.5, 16.0), (0.8, 26.0, 20.0)],
        keel_size=[(0.0, 0.0), (0.06, 0.5), (0.2, 1.0)],
        rim_pts=[(0.0, -3.0), (0.02, 0.0), (0.1, 2.0), (0.5, 3.0)],
        mountains=0.0,
        detail=3.0,
    ),
}

# Small floating rocks between the big sky islands.
ISLETS = dict(base=236, height_var=50, gap=0.07)

# Final density is scaled down so structures' terrain adaptation (beardifier)
# keeps roughly the same strength as in vanilla.
DENSITY_SCALE = 0.1

# ---------------------------------------------------------------------------
# Small helpers to write density function JSON.
# ---------------------------------------------------------------------------
files = {}


def put(path, obj):
    files[path] = obj


def ref(name):
    return f"{NS}:{name}"


def df(name, obj):
    put(f"{NS}/worldgen/density_function/{name}.json", obj)
    return ref(name)


def noise_def(name, octave, amps):
    put(f"{NS}/worldgen/noise/{name}.json", {"firstOctave": octave, "amplitudes": amps})
    return ref(name)


def add(a, b):
    return {"type": "minecraft:add", "argument1": a, "argument2": b}


def mul(a, b):
    return {"type": "minecraft:mul", "argument1": a, "argument2": b}


def dmin(a, b):
    return {"type": "minecraft:min", "argument1": a, "argument2": b}


def dmax(a, b):
    return {"type": "minecraft:max", "argument1": a, "argument2": b}


def clamp(x, lo, hi):
    return {"type": "minecraft:clamp", "input": x, "min": lo, "max": hi}


def dabs(x):
    return {"type": "minecraft:abs", "argument": x}


def square(x):
    return {"type": "minecraft:square", "argument": x}


def flat(x):
    return {"type": "minecraft:flat_cache", "argument": x}


def interp(x):
    return {"type": "minecraft:interpolated", "argument": x}


def noise2d(n, xz=1.0):
    return {"type": "minecraft:noise", "noise": n, "xz_scale": xz, "y_scale": 0.0}


def noise3d(n, xz=1.0, y=1.0):
    return {"type": "minecraft:noise", "noise": n, "xz_scale": xz, "y_scale": y}


def shifted2d(n, sx, sz, xz=1.0):
    return {"type": "minecraft:shifted_noise", "noise": n, "xz_scale": xz, "y_scale": 0.0,
            "shift_x": sx, "shift_y": 0.0, "shift_z": sz}


def spline(coord, pts):
    """Smooth 1D curve through (location, value) points (Catmull-Rom style slopes)."""
    out = []
    for i, pt in enumerate(pts):
        x, v = pt[0], pt[1]
        if len(pt) > 2:
            d = pt[2]
        elif 0 < i < len(pts) - 1:
            d = (pts[i + 1][1] - pts[i - 1][1]) / (pts[i + 1][0] - pts[i - 1][0])
        else:
            d = 0.0
        out.append({"location": x, "value": v, "derivative": d})
    return {"type": "minecraft:spline", "spline": {"coordinate": coord, "points": out}}


def neg(x):
    return mul(x, -1.0)


Y = "minecraft:y"

# ---------------------------------------------------------------------------
# Island levels
# ---------------------------------------------------------------------------
detail_noise = noise_def("detail", -4, [1.0, 0.6, 0.3])


def build_level(k, p):
    mask_n = noise_def(f"{k}/mask", p["mask_octave"], p["mask_amps"])
    warpx_n = noise_def(f"{k}/warp_x", p["mask_octave"] + 2, [1.0, 0.5])
    warpz_n = noise_def(f"{k}/warp_z", p["mask_octave"] + 2, [1.0, 0.5])
    height_n = noise_def(f"{k}/height", -8, [1.0, 0.4])
    roll_n = noise_def(f"{k}/roll", -6, [1.0, 0.5])
    depthv_n = noise_def(f"{k}/depth_var", -6, [1.0, 0.5])
    spike_n = noise_def(f"{k}/spike", -4, [1.0, 0.5, 0.2])
    keel_n = noise_def(f"{k}/keel", -6, [1.0, 0.4])

    # e = how far inside an island we are (0 at the rim, > 0 inside, < 0 in the void)
    e = df(f"{k}/e", flat(add(
        shifted2d(mask_n, mul(noise2d(warpx_n), p["warp"]), mul(noise2d(warpz_n), p["warp"])),
        -p["threshold"])))

    spike_raw = df(f"{k}/spike_raw", flat(noise2d(spike_n)))

    # --- top surface -------------------------------------------------------
    top_base = add(add(p["base"], mul(noise2d(height_n), p["height_var"])),
                   add(mul(noise2d(roll_n), p["roll"]), spline(e, p["rim_pts"])))
    top_base = df(f"{k}/top_base", flat(top_base))

    top = top_base
    if p["mountains"] > 0:
        sel_n = noise_def(f"{k}/mountain_sel", -8, [1.0, 0.5])
        ridge_n = noise_def(f"{k}/mountain_ridge", -6, [1.0, 0.5, 0.25])
        sel = df(f"{k}/mountain_sel", flat(noise2d(sel_n)))
        ridge = square(square(add(1.0, neg(dabs(noise2d(ridge_n))))))
        inland = spline(e, [(0.02, 0.0), (0.1, 0.35), (0.22, 1.0)])
        amount = spline(sel, [(0.05, 0.0), (0.35, 1.0)])
        top = add(top_base, mul(mul(ridge, p["mountains"]), mul(inland, amount)))

    top = df(f"{k}/top", interp(flat(dmin(top, float(p["cap"])))))

    # --- underside: inverted cone + hanging spikes ----------------------------
    depth = add(p["thick0"], mul(spline(e, p["depth_pts"]),
                                 add(1.0, mul(noise2d(depthv_n), p["depth_var"]))))
    spikes = mul(spline(spike_raw, p["spike_pts"]), spline(e, p["spike_size"]))
    if "keel_pts" in p:
        # a few big hanging rock masses (inverted mountains) under large islands
        keel_raw = df(f"{k}/keel_raw", flat(noise2d(keel_n)))
        spikes = add(spikes, mul(spline(keel_raw, p["keel_pts"]), spline(e, p["keel_size"])))
    bottom_raw = df(f"{k}/bottom_raw", flat(add(top_base, neg(add(depth, spikes)))))
    # soft floor: deep bottoms get squashed smoothly instead of being cut flat
    f0 = float(p["floor"])
    bottom = spline(bottom_raw, [(f0 - 80.0, f0 + 1.0, 0.0), (f0 - 10.0, f0 + 9.0), (f0 + 25.0, f0 + 28.0, 1.0)])
    bottom = df(f"{k}/bottom", interp(flat(bottom)))

    edge = df(f"{k}/edge", interp(flat(mul(e, p["edge_k"]))))

    # --- 3D density -------------------------------------------------------
    shape = dmin(dmin(add(top, neg(Y)), add(Y, neg(bottom))), edge)
    # vertical streaks on cliffs and spikes, faded out near the grass top
    streaks = mul(interp(noise3d(detail_noise, 1.0, 0.25)),
                  mul(clamp(mul(add(top, neg(Y)), 0.2), 0.0, 1.0), p["detail"]))
    return df(f"{k}/density", add(shape, streaks))


level_density = {k: build_level(k, p) for k, p in LEVELS.items()}

# --- islets (small rocks floating between sky islands) ----------------------
isl_n = noise_def("islet/mask", -5, [1.0, 0.4])
isl_sel_n = noise_def("islet/sel", -8, [1.0])
isl_h_n = noise_def("islet/height", -7, [1.0])
isl_spk = noise_def("islet/spike", -3, [1.0, 0.5])
ie = df("islet/e", flat(add(add(noise2d(isl_n), mul(noise2d(isl_sel_n), 0.5)), -0.78)))
it = df("islet/top", interp(flat(add(add(ISLETS["base"], mul(noise2d(isl_h_n), ISLETS["height_var"])),
                                     spline(ie, [(0.0, -1.0), (0.1, 1.0)])))))
ib = df("islet/bottom", interp(flat(add(it, neg(add(
    add(2.0, spline(ie, [(0.0, 0.0), (0.05, 6.0), (0.15, 16.0), (0.35, 30.0)])),
    spline(df("islet/spike_raw", flat(noise2d(isl_spk))),
           [(0.1, 0.0), (0.6, 8.0), (1.0, 18.0)])))))))
iedge = df("islet/edge", interp(flat(dmin(mul(ie, 120.0),
                                          mul(add(neg(ref("a/e")), -ISLETS["gap"]), 160.0)))))
islet_density = df("islet/density", add(
    dmin(dmin(add(it, neg(Y)), add(Y, neg(ib))), iedge),
    mul(interp(noise3d(detail_noise, 1.0, 0.25)), 2.0)))

final = dmax(dmax(level_density["a"], level_density["b"]),
             dmax(level_density["c"], islet_density))
final_density = df("final_density", mul(final, DENSITY_SCALE))

# ---------------------------------------------------------------------------
# Climate (biomes). Continentalness follows the sky islands so that:
#  - the world spawn is always found on a sky island,
#  - bigger islands get "inland" biomes (forests, mountains...).
# Depth stays at "surface" values everywhere so the lower levels do not turn
# into lush caves (water pools, moss) or deep dark (sculk): they stay plain
# stone / deepslate full of ores.
# ---------------------------------------------------------------------------
continents = df("climate/continents", flat(clamp(mul(add(ref("a/e"), -0.012), 7.0), -1.0, 1.0)))
depth = df("climate/depth", {
    "type": "minecraft:range_choice", "input": Y,
    "min_inclusive": 130.0, "max_exclusive": 10000.0,
    "when_in_range": 0.0,
    "when_out_of_range": {
        "type": "minecraft:range_choice", "input": Y,
        "min_inclusive": 30.0, "max_exclusive": 130.0,
        "when_in_range": 0.0, "when_out_of_range": 1.0}})

# ---------------------------------------------------------------------------
# Surface rules
# ---------------------------------------------------------------------------
strata_n = noise_def("strata", -5, [1.0, 0.6, 0.3])
dirtband_n = noise_def("dirt_band", -5, [1.0, 0.5])


def block(name, props=None):
    s = {"Name": name}
    if props:
        s["Properties"] = props
    return {"type": "minecraft:block", "result_state": s}


def cond(c, then):
    return {"type": "minecraft:condition", "if_true": c, "then_run": then}


def seq(*rules):
    return {"type": "minecraft:sequence", "sequence": list(rules)}


def biome(*names):
    return {"type": "minecraft:biome", "biome_is": [f"minecraft:{n}" for n in names]}


def floor_depth(offset=0, add_surface=False, secondary=0):
    return {"type": "minecraft:stone_depth", "offset": offset, "add_surface_depth": add_surface,
            "secondary_depth_range": secondary, "surface_type": "floor"}


def ceiling_depth(offset=0):
    return {"type": "minecraft:stone_depth", "offset": offset, "add_surface_depth": False,
            "secondary_depth_range": 0, "surface_type": "ceiling"}


def y_above(y):
    return {"type": "minecraft:y_above", "anchor": {"absolute": y},
            "surface_depth_multiplier": 0, "add_stone_depth": False}


def noise_th(n, lo, hi):
    return {"type": "minecraft:noise_threshold", "noise": n, "min_threshold": lo, "max_threshold": hi}


def nott(c):
    return {"type": "minecraft:not", "invert": c}


GRASS = block("minecraft:grass_block", {"snowy": "false"})
DIRT = block("minecraft:dirt")
COARSE = block("minecraft:coarse_dirt")
STONE = block("minecraft:stone")
SNOW = block("minecraft:snow_block")
SAND = block("minecraft:sand")
SANDSTONE = block("minecraft:sandstone")
RED_SAND = block("minecraft:red_sand")
DEEPSLATE = block("minecraft:deepslate", {"axis": "y"})

SNOWY_PEAKS = biome("frozen_peaks", "jagged_peaks", "snowy_slopes", "ice_spikes")
BADLANDS = biome("badlands", "eroded_badlands", "wooded_badlands")

top_block = seq(
    cond(biome("desert"), SAND),
    cond(BADLANDS, RED_SAND),
    cond(biome("mushroom_fields"), block("minecraft:mycelium", {"snowy": "false"})),
    cond(biome("mangrove_swamp"), block("minecraft:mud")),
    cond(SNOWY_PEAKS, SNOW),
    cond(biome("stony_peaks"), block("minecraft:calcite")),
    cond(biome("old_growth_pine_taiga", "old_growth_spruce_taiga"), seq(
        cond(noise_th("minecraft:surface", 0.1, 10.0), block("minecraft:podzol", {"snowy": "false"})),
        cond(noise_th("minecraft:surface", -10.0, -0.3), COARSE))),
    cond(biome("windswept_gravelly_hills"), seq(
        cond(noise_th("minecraft:surface", 0.2, 10.0), block("minecraft:gravel")))),
    GRASS,
)

under_block = seq(
    cond(biome("desert"), SANDSTONE),
    cond(BADLANDS, block("minecraft:orange_terracotta")),
    cond(SNOWY_PEAKS, SNOW),
    cond(biome("stony_peaks"), block("minecraft:calcite")),
    cond(noise_th(ref("dirt_band"), 0.35, 10.0), COARSE),
    DIRT,
)

# brown/grey streaked cliffs like on the screenshots (2D noise -> vertical stripes)
cliff_mix = seq(
    cond(BADLANDS, seq(
        cond(noise_th(ref("strata"), 0.2, 10.0), block("minecraft:terracotta")),
        cond(noise_th(ref("strata"), -10.0, -0.3), block("minecraft:red_terracotta")),
        block("minecraft:orange_terracotta"))),
    cond(biome("desert"), seq(
        cond(noise_th(ref("strata"), 0.3, 10.0), block("minecraft:smooth_sandstone")),
        SANDSTONE)),
    cond(noise_th(ref("strata"), 0.45, 10.0), block("minecraft:granite")),
    cond(noise_th(ref("strata"), 0.25, 0.45), block("minecraft:coarse_dirt")),
    cond(noise_th(ref("strata"), -0.5, -0.25), block("minecraft:andesite")),
    cond(noise_th(ref("strata"), -10.0, -0.7), block("minecraft:tuff")),
    STONE,
)

sky_level = seq(
    cond(floor_depth(0), top_block),
    cond(floor_depth(0, True), under_block),
    # thick brown layer right under the soil, like the screenshots
    cond(floor_depth(4, True, 4), seq(
        cond(noise_th(ref("dirt_band"), -0.2, 10.0), block("minecraft:granite")),
        cond(noise_th(ref("dirt_band"), -10.0, -0.6), DIRT),
        COARSE)),
    cliff_mix,
)

stone_level = seq(
    cond(noise_th(ref("strata"), 0.55, 10.0), block("minecraft:andesite")),
    cond(noise_th(ref("strata"), -10.0, -0.65), block("minecraft:tuff")),
    STONE,
)

deep_level = seq(
    cond(noise_th(ref("strata"), 0.6, 10.0), block("minecraft:tuff")),
    DEEPSLATE,
)

surface_rule = seq(
    cond(y_above(130), sky_level),
    cond(y_above(30), stone_level),
    deep_level,
)

# ---------------------------------------------------------------------------
# Noise settings (overrides the vanilla overworld so the "Default" world type
# uses the islands).
# ---------------------------------------------------------------------------
vanilla_spawn_target = [
    {"continentalness": [-0.11, 1.0], "depth": 0.0, "erosion": [-1.0, 1.0], "humidity": [-1.0, 1.0],
     "offset": 0.0, "temperature": [-1.0, 1.0], "weirdness": [-1.0, -0.16]},
    {"continentalness": [-0.11, 1.0], "depth": 0.0, "erosion": [-1.0, 1.0], "humidity": [-1.0, 1.0],
     "offset": 0.0, "temperature": [-1.0, 1.0], "weirdness": [0.16, 1.0]},
]

veins = {
    "vein_toggle": {"type": "minecraft:interpolated", "argument": {
        "type": "minecraft:range_choice", "input": "minecraft:y", "max_exclusive": 51.0, "min_inclusive": -60.0,
        "when_in_range": {"type": "minecraft:noise", "noise": "minecraft:ore_veininess", "xz_scale": 1.5, "y_scale": 1.5},
        "when_out_of_range": 0.0}},
    "vein_ridged": {"type": "minecraft:add", "argument1": -0.07999999821186066, "argument2": {
        "type": "minecraft:max",
        "argument1": {"type": "minecraft:abs", "argument": {"type": "minecraft:interpolated", "argument": {
            "type": "minecraft:range_choice", "input": "minecraft:y", "max_exclusive": 51.0, "min_inclusive": -60.0,
            "when_in_range": {"type": "minecraft:noise", "noise": "minecraft:ore_vein_a", "xz_scale": 4.0, "y_scale": 4.0},
            "when_out_of_range": 0.0}}},
        "argument2": {"type": "minecraft:abs", "argument": {"type": "minecraft:interpolated", "argument": {
            "type": "minecraft:range_choice", "input": "minecraft:y", "max_exclusive": 51.0, "min_inclusive": -60.0,
            "when_in_range": {"type": "minecraft:noise", "noise": "minecraft:ore_vein_b", "xz_scale": 4.0, "y_scale": 4.0},
            "when_out_of_range": 0.0}}}}},
    "vein_gap": {"type": "minecraft:noise", "noise": "minecraft:ore_gap", "xz_scale": 1.0, "y_scale": 1.0},
}

noise_settings = {
    "sea_level": MIN_Y,
    "disable_mob_generation": False,
    "aquifers_enabled": False,
    "ore_veins_enabled": True,
    "legacy_random_source": False,
    "default_block": {"Name": "minecraft:stone"},
    "default_fluid": {"Name": "minecraft:air"},
    "noise": {"min_y": MIN_Y, "height": HEIGHT, "size_horizontal": 1, "size_vertical": 1},
    "noise_router": {
        "barrier": 0.0,
        "fluid_level_floodedness": 0.0,
        "fluid_level_spread": 0.0,
        "lava": 0.0,
        "temperature": {"type": "minecraft:shifted_noise", "noise": "minecraft:temperature",
                        "shift_x": "minecraft:shift_x", "shift_y": 0.0, "shift_z": "minecraft:shift_z",
                        "xz_scale": 0.25, "y_scale": 0.0},
        "vegetation": {"type": "minecraft:shifted_noise", "noise": "minecraft:vegetation",
                       "shift_x": "minecraft:shift_x", "shift_y": 0.0, "shift_z": "minecraft:shift_z",
                       "xz_scale": 0.25, "y_scale": 0.0},
        "continents": continents,
        "erosion": "minecraft:overworld/erosion",
        "depth": depth,
        "ridges": "minecraft:overworld/ridges",
        "initial_density_without_jaggedness": 0.0,
        "final_density": final_density,
        **veins,
    },
    "spawn_target": vanilla_spawn_target,
    "surface_rule": surface_rule,
}
put("minecraft/worldgen/noise_settings/overworld.json", noise_settings)

put("minecraft/dimension_type/overworld.json", {
    "ambient_light": 0.0, "bed_works": True, "coordinate_scale": 1.0,
    "effects": "minecraft:overworld", "has_ceiling": False, "has_raids": True,
    "has_skylight": True, "height": HEIGHT, "infiniburn": "#minecraft:infiniburn_overworld",
    "logical_height": HEIGHT, "min_y": MIN_Y,
    "monster_spawn_block_light_limit": 0,
    "monster_spawn_light_level": {"type": "minecraft:uniform", "max_inclusive": 7, "min_inclusive": 0},
    "natural": True, "piglin_safe": False, "respawn_anchor_works": False, "ultrawarm": False,
})

# Structures that would only spawn floating in the void (ocean stuff, mineshafts
# at the bottom of the world) are switched off.
for tag in ["ocean_monument", "shipwreck", "ocean_ruin_cold", "ocean_ruin_warm",
            "ruined_portal_ocean", "mineshaft", "mineshaft_mesa", "trial_chambers"]:
    put(f"minecraft/tags/worldgen/biome/has_structure/{tag}.json", {"replace": True, "values": []})

# ---------------------------------------------------------------------------
# Clouds: puffy white blobs stuck to the flanks of the sky islands, at about
# half their depth (like the screenshots). Made with the "ore" feature that
# replaces air, placed only next to island walls. The feature is appended to
# every overworld biome (copied from vanilla 1.21.1).
# ---------------------------------------------------------------------------
VANILLA_BIOMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vanilla_biomes")


def cloud_feature(name, block_name, size):
    put(f"{NS}/worldgen/configured_feature/{name}.json", {
        "type": "minecraft:ore",
        "config": {"size": size, "discard_chance_on_air_exposure": 0.0,
                   "targets": [{"target": {"predicate_type": "minecraft:block_match", "block": "minecraft:air"},
                                "state": {"Name": block_name}}]}})


def near_wall(dist):
    offs = [[dist, 0, 0], [-dist, 0, 0], [0, 0, dist], [0, 0, -dist]]
    return {"type": "minecraft:any_of", "predicates": [
        {"type": "minecraft:solid", "offset": o} for o in offs]}


def cloud_placed(name, feature, count, y0, y1, dist):
    put(f"{NS}/worldgen/placed_feature/{name}.json", {
        "feature": ref(feature),
        "placement": [
            {"type": "minecraft:rarity_filter", "chance": 2},
            {"type": "minecraft:count", "count": count},
            {"type": "minecraft:in_square"},
            {"type": "minecraft:height_range", "height": {
                "type": "minecraft:trapezoid", "min_inclusive": {"absolute": y0},
                "max_inclusive": {"absolute": y1}, "plateau": (y1 - y0) // 3}},
            {"type": "minecraft:block_predicate_filter", "predicate": {"type": "minecraft:all_of", "predicates": [
                {"type": "minecraft:matching_blocks", "blocks": "minecraft:air"},
                near_wall(dist)]}},
        ]})
    return ref(name)


cloud_feature("cloud_blob", "minecraft:white_wool", 48)
cloud_feature("cloud_snow_blob", "minecraft:snow_block", 32)
# one cloud = a cluster of blobs spread horizontally
put(f"{NS}/worldgen/configured_feature/cloud.json", {
    "type": "minecraft:random_patch",
    "config": {"tries": 32, "xz_spread": 12, "y_spread": 2, "feature": {
        "feature": {"type": "minecraft:random_selector", "config": {
            "features": [{"chance": 0.3, "feature": {"feature": ref("cloud_snow_blob"), "placement": []}}],
            "default": {"feature": ref("cloud_blob"), "placement": []}}},
        "placement": []}}})
CLOUD_PLACED = [cloud_placed("cloud", "cloud", 3, 176, 226, 3)]

for fn in sorted(os.listdir(VANILLA_BIOMES)):
    b = json.load(open(os.path.join(VANILLA_BIOMES, fn), encoding="utf-8"))
    feats = b.get("features", [])
    while len(feats) < 1:
        feats.append([])
    feats[0] = list(feats[0]) + CLOUD_PLACED
    b["features"] = feats
    put(f"minecraft/worldgen/biome/{fn}", b)

# ---------------------------------------------------------------------------
# Write everything
# ---------------------------------------------------------------------------
if os.path.isdir(DATA):
    shutil.rmtree(DATA)
for path, obj in files.items():
    full = os.path.join(DATA, *path.split("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

with open(os.path.join(ROOT, "pack.mcmeta"), "w", encoding="utf-8") as f:
    json.dump({"pack": {"pack_format": 48,
                        "description": "Iles volantes - generation d'iles flottantes (1.21.1)"}}, f, indent=2)

print(f"wrote {len(files)} files")

# Ready-to-install zip (drop it in the "Data Packs" screen when creating a world)
import zipfile
dist = os.path.join(ROOT, "dist")
os.makedirs(dist, exist_ok=True)
zpath = os.path.join(dist, "Iles-Volantes-1.21.1.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(ROOT, "pack.mcmeta"), "pack.mcmeta")
    for base, _, names in os.walk(DATA):
        for n in names:
            full = os.path.join(base, n)
            z.write(full, os.path.relpath(full, ROOT).replace(os.sep, "/"))
print("zip:", zpath)
