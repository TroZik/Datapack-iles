package com.trozik.iles.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.trozik.iles.StructureSupport;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.structure.BoundingBox;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * A chunk only "sees" the structures whose bounding box touches it. Support islands
 * stick out a bit around a structure, so chunks next to it must see it too.
 */
@Mixin(ChunkGenerator.class)
public abstract class ChunkGeneratorMixin {
    @WrapOperation(method = "createReferences",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/world/level/levelgen/structure/BoundingBox;intersects(IIII)Z"))
    private boolean iles$wideReferences(BoundingBox box, int minX, int minZ, int maxX, int maxZ,
                                        Operation<Boolean> original) {
        return original.call(box, minX, minZ, maxX, maxZ)
                || original.call(box.inflatedBy(StructureSupport.MARGIN), minX, minZ, maxX, maxZ);
    }
}
