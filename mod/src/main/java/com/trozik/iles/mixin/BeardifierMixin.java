package com.trozik.iles.mixin;

import com.trozik.iles.StructureSupport;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.levelgen.Beardifier;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;

/** When the game gathers the structures around a chunk, also keep their footprints for the support islands. */
@Mixin(Beardifier.class)
public abstract class BeardifierMixin implements StructureSupport.Holder {
    @Unique
    private List<StructureSupport.Pad> iles$pads = List.of();

    @Inject(method = "forStructuresInChunk", at = @At("RETURN"))
    private static void iles$collectPads(StructureManager structureManager, ChunkPos chunkPos,
                                         CallbackInfoReturnable<Beardifier> cir) {
        ((StructureSupport.Holder) cir.getReturnValue()).iles$setPads(StructureSupport.collect(structureManager, chunkPos));
    }

    @Override
    public List<StructureSupport.Pad> iles$pads() {
        return iles$pads;
    }

    @Override
    public void iles$setPads(List<StructureSupport.Pad> pads) {
        this.iles$pads = pads;
    }
}
