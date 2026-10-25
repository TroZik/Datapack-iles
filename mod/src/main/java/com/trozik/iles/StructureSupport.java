package com.trozik.iles;

import com.mojang.serialization.MapCodec;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import net.minecraft.util.KeyDispatchDataCodec;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.structure.BoundingBox;
import net.minecraft.world.level.levelgen.structure.PoolElementStructurePiece;
import net.minecraft.world.level.levelgen.structure.StructurePiece;
import net.minecraft.world.level.levelgen.structure.StructureStart;
import net.minecraft.world.level.levelgen.synth.ImprovedNoise;

import java.util.ArrayList;
import java.util.List;

/**
 * Support islands under structures.
 * <p>
 * Every structure piece (village house, street, temple, stronghold room...) gets
 * a small floating island under it: solid up to the piece's ground level, then a
 * rocky inverted cone with hanging spikes, like the natural islands. Pieces that
 * already stand on an island are not changed (the support is merged with "max").
 */
public final class StructureSupport {
    /** Value returned where there is no support at all (in blocks, before the final scale). */
    public static final double NONE = -1000.0;
    /** How far (in blocks) a support island can reach outside its structure's bounding box. */
    public static final int MARGIN = 24;

    private static final ImprovedNoise WOBBLE = new ImprovedNoise(RandomSource.create(7_771L));
    private static final ImprovedNoise SPIKES = new ImprovedNoise(RandomSource.create(7_772L));
    private static final ImprovedNoise DEPTH = new ImprovedNoise(RandomSource.create(7_773L));
    private static final ImprovedNoise ROCK = new ImprovedNoise(RandomSource.create(7_774L));

    private StructureSupport() {
    }

    /** Footprint of one structure piece. {@code ground} = first block of air above the support. */
    public record Pad(int minX, int minZ, int maxX, int maxZ, int ground) {
        /** Signed horizontal distance: > 0 inside the footprint, < 0 outside. */
        double signedDistance(int x, int z) {
            int dx = Math.max(Math.max(minX - x, 0), x - maxX);
            int dz = Math.max(Math.max(minZ - z, 0), z - maxZ);
            if (dx == 0 && dz == 0) {
                return Math.min(Math.min(x - minX, maxX - x), Math.min(z - minZ, maxZ - z)) + 1.0;
            }
            return -Math.sqrt((double) dx * dx + (double) dz * dz);
        }
    }

    /** Collects the footprints of every structure piece close to this chunk. */
    public static List<Pad> collect(StructureManager structureManager, ChunkPos chunkPos) {
        List<Pad> pads = new ArrayList<>();
        BoundingBox area = new BoundingBox(chunkPos.getMinBlockX() - MARGIN, -10000, chunkPos.getMinBlockZ() - MARGIN,
                chunkPos.getMaxBlockX() + MARGIN, 10000, chunkPos.getMaxBlockZ() + MARGIN);
        // buried things (treasure, trail ruins...) live inside the ground: no support for them
        List<StructureStart> starts = structureManager.startsForStructure(chunkPos,
                s -> s.step() != GenerationStep.Decoration.UNDERGROUND_STRUCTURES);
        for (StructureStart start : starts) {
            if (!start.isValid()) {
                continue;
            }
            for (StructurePiece piece : start.getPieces()) {
                BoundingBox box = piece.getBoundingBox();
                if (!box.intersects(area)) {
                    continue;
                }
                int ground = box.minY();
                if (piece instanceof PoolElementStructurePiece pool) {
                    ground += pool.getGroundLevelDelta();
                }
                pads.add(new Pad(box.minX(), box.minZ(), box.maxX(), box.maxZ(), ground));
            }
        }
        return pads;
    }

    /** Placeholder written in the worldgen JSON, swapped for a {@link Field} for each chunk. */
    public enum Marker implements DensityFunction.SimpleFunction {
        INSTANCE;

        public static final KeyDispatchDataCodec<Marker> CODEC = KeyDispatchDataCodec.of(MapCodec.unit(INSTANCE));

        @Override
        public double compute(FunctionContext context) {
            return NONE;
        }

        @Override
        public double minValue() {
            return NONE;
        }

        @Override
        public double maxValue() {
            return 1000.0;
        }

        @Override
        public KeyDispatchDataCodec<? extends DensityFunction> codec() {
            return CODEC;
        }
    }

    /** The support density for one chunk being generated. Not thread safe (one per NoiseChunk). */
    public static final class Field implements DensityFunction.SimpleFunction {
        private final List<Pad> pads;
        private final Long2ObjectOpenHashMap<double[]> columns = new Long2ObjectOpenHashMap<>();

        public Field(List<Pad> pads) {
            this.pads = pads;
        }

        /** Per column: {sdf, top, bottom} or null when the column is far from every pad. */
        private double[] column(int x, int z) {
            long key = ChunkPos.asLong(x, z);
            double[] c = columns.get(key);
            if (c == null && !columns.containsKey(key)) {
                c = computeColumn(x, z);
                columns.put(key, c);
            }
            return c;
        }

        private double[] computeColumn(int x, int z) {
            double best = Double.NEGATIVE_INFINITY;
            int bestGround = 0;
            int coverGround = Integer.MAX_VALUE;
            for (Pad pad : pads) {
                double s = pad.signedDistance(x, z);
                if (s > best) {
                    best = s;
                    bestGround = pad.ground();
                }
                if (s > 0 && pad.ground() < coverGround) {
                    coverGround = pad.ground(); // stacked pieces: support the lowest one
                }
            }
            if (best == Double.NEGATIVE_INFINITY) {
                return null;
            }
            int ground = coverGround != Integer.MAX_VALUE ? coverGround : bestGround;
            // ragged outline a few blocks wider than the buildings
            double wobble = WOBBLE.noise(x / 14.0, 0.0, z / 14.0) * 4.0 + WOBBLE.noise(x / 5.0, 3.0, z / 5.0) * 1.5;
            double sdf = best + 6.0 + wobble;
            if (sdf <= -6.0) {
                return null;
            }
            double rimDrop = Math.max(0.0, 4.0 - sdf) * 0.8;
            double top = ground - 1 - rimDrop;
            double cone = 5.0 + Math.max(sdf, 0.0) * 1.15 * (1.0 + 0.35 * DEPTH.noise(x / 24.0, 0.0, z / 24.0));
            double n = SPIKES.noise(x / 9.0, 0.0, z / 9.0) + 0.4 * SPIKES.noise(x / 4.0, 5.0, z / 4.0);
            double spikes = Math.max(0.0, n - 0.1);
            spikes = spikes * spikes * 90.0 * Mth.clamp(sdf / 10.0, 0.2, 1.0);
            double depth = Math.min(cone, 70.0) + spikes;
            return new double[]{sdf, top, top - depth};
        }

        @Override
        public double compute(FunctionContext context) {
            if (pads.isEmpty()) {
                return NONE;
            }
            double[] c = column(context.blockX(), context.blockZ());
            if (c == null) {
                return NONE;
            }
            int y = context.blockY();
            double shape = Math.min(Math.min(c[1] + 0.5 - y, y - c[2]), c[0] * 1.5);
            if (shape < -8.0) {
                return shape;
            }
            // weathered rock, but keep the ground right under the buildings intact
            double rock = ROCK.noise(context.blockX() / 7.0, y / 14.0, context.blockZ() / 7.0) * 3.0;
            double keep = Mth.clamp((c[1] - y) / 4.0, 0.0, 1.0);
            return shape + rock * keep;
        }

        @Override
        public double minValue() {
            return NONE;
        }

        @Override
        public double maxValue() {
            return 1000.0;
        }

        @Override
        public KeyDispatchDataCodec<? extends DensityFunction> codec() {
            return Marker.CODEC;
        }
    }

    /** Implemented by Beardifier (through a mixin) to hand the chunk's footprints to the NoiseChunk. */
    public interface Holder {
        List<Pad> iles$pads();

        void iles$setPads(List<Pad> pads);
    }
}
