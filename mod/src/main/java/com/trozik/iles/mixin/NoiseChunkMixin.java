package com.trozik.iles.mixin;

import com.trozik.iles.StructureSupport;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.DensityFunctions;
import net.minecraft.world.level.levelgen.NoiseChunk;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Swaps the "structure_support" marker for the real support field of the chunk being generated. */
@Mixin(NoiseChunk.class)
public abstract class NoiseChunkMixin {
    @Shadow
    @Final
    private DensityFunctions.BeardifierOrMarker beardifier;

    @Inject(method = "wrapNew", at = @At("HEAD"), cancellable = true)
    private void iles$wrapSupport(DensityFunction function, CallbackInfoReturnable<DensityFunction> cir) {
        if (function instanceof StructureSupport.Marker) {
            if (beardifier instanceof StructureSupport.Holder holder && !holder.iles$pads().isEmpty()) {
                cir.setReturnValue(new StructureSupport.Field(holder.iles$pads()));
            } else {
                cir.setReturnValue(function);
            }
        }
    }
}
