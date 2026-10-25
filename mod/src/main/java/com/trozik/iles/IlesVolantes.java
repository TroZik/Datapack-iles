package com.trozik.iles;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.registries.Registries;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.registries.DeferredRegister;

@Mod(IlesVolantes.MOD_ID)
public class IlesVolantes {
    public static final String MOD_ID = "iles_volantes";

    private static final DeferredRegister<MapCodec<? extends DensityFunction>> DENSITY_FUNCTION_TYPES =
            DeferredRegister.create(Registries.DENSITY_FUNCTION_TYPE, MOD_ID);

    static {
        // usable in worldgen JSON as {"type": "iles_volantes:structure_support"}
        DENSITY_FUNCTION_TYPES.register("structure_support", () -> StructureSupport.Marker.CODEC.codec());
    }

    public IlesVolantes(IEventBus modBus) {
        DENSITY_FUNCTION_TYPES.register(modBus);
    }
}
