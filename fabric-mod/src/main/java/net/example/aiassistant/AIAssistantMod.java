package net.example.aiassistant;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonArray;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.registry.RegistryKeys;
import net.minecraft.registry.Registries;
import net.minecraft.server.command.CommandManager;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Box;
import net.minecraft.item.ItemStack;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.CompletableFuture;
import java.util.Set;
import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.ArrayList;

public class AIAssistantMod implements ModInitializer {
    private static final String BACKEND_URL = "http://localhost:8000/chat";
    // Connect timeout: time to establish TCP connection to the local backend.
    // Keep short – if the backend isn’t running, we want a fast failure.
    private static final int CONNECT_TIMEOUT_SECONDS = 10;
    // Request (read) timeout: time to receive a COMPLETE response from the backend.
    // Must be > backend’s overall pipeline timeout (43s) to avoid the client
    // cancelling a request that the backend is still processing.
    private static final int REQUEST_TIMEOUT_SECONDS = 45;
    private static final Gson gson = new Gson();
    private static Path logPath;

    private static final Set<String> FILLER_BLOCKS = Set.of(
        "minecraft:air", "minecraft:cave_air", "minecraft:void_air",
        "minecraft:stone", "minecraft:deepslate", "minecraft:granite", "minecraft:diorite", "minecraft:andesite",
        "minecraft:dirt", "minecraft:grass_block", "minecraft:sand", "minecraft:red_sand",
        "minecraft:sandstone", "minecraft:red_sandstone", "minecraft:gravel",
        "minecraft:netherrack", "minecraft:basalt", "minecraft:blackstone", "minecraft:end_stone",
        "minecraft:water", "minecraft:lava", "minecraft:tuff"
    );

    @Override
    public void onInitialize() {
        setupLogger();
        log("INFO", "AI Assistant Mod initialized. Registering /ai command...");

        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> {
            dispatcher.register(CommandManager.literal("ai")
                .then(CommandManager.argument("message", StringArgumentType.greedyString())
                    .executes(context -> {
                        ServerPlayerEntity player = context.getSource().getPlayer();
                        if (player == null) {
                            context.getSource().sendError(Text.literal("This command can only be executed by a player."));
                            return 0;
                        }

                        String message = StringArgumentType.getString(context, "message");
                        handleAICommand(player, message);
                        return 1;
                    })
                )
            );
        });
    }

    private void handleAICommand(ServerPlayerEntity player, String message) {
        player.sendMessage(Text.literal("Thinking...").formatted(Formatting.GRAY), false);

        ServerWorld world = player.getServerWorld();
        BlockPos playerPos = player.getBlockPos();

        // 1. Gather Player Info
        double x = player.getX();
        double y = player.getY();
        double z = player.getZ();
        float yaw = player.getYaw();
        float pitch = player.getPitch();
        String dimension = world.getRegistryKey().getValue().toString();
        String gamemode = player.interactionManager.getGameMode().getName();
        float health = player.getHealth();
        int food = player.getHungerManager().getFoodLevel();
        float saturation = player.getHungerManager().getSaturationLevel();
        float experience = player.experienceProgress;
        int level = player.experienceLevel;
        String name = player.getName().getString();
        String uuid = player.getUuidAsString();

        // Held Item
        JsonObject heldItemJson = serializeItemStack(player.getMainHandStack());

        // Equipment
        JsonObject equipmentJson = new JsonObject();
        equipmentJson.add("helmet", serializeItemStack(player.getEquippedStack(net.minecraft.entity.EquipmentSlot.HEAD)));
        equipmentJson.add("chestplate", serializeItemStack(player.getEquippedStack(net.minecraft.entity.EquipmentSlot.CHEST)));
        equipmentJson.add("leggings", serializeItemStack(player.getEquippedStack(net.minecraft.entity.EquipmentSlot.LEGS)));
        equipmentJson.add("boots", serializeItemStack(player.getEquippedStack(net.minecraft.entity.EquipmentSlot.FEET)));
        equipmentJson.add("offhand", serializeItemStack(player.getOffHandStack()));

        // Inventory
        net.minecraft.entity.player.PlayerInventory inventory = player.getInventory();
        JsonArray inventoryJson = new JsonArray();
        for (int i = 0; i < inventory.main.size(); i++) {
            ItemStack stack = inventory.main.get(i);
            if (!stack.isEmpty()) {
                JsonObject itemJson = serializeItemStack(stack);
                itemJson.addProperty("slot", i);
                inventoryJson.add(itemJson);
            }
        }

        JsonObject playerInfoJson = new JsonObject();
        playerInfoJson.addProperty("name", name);
        playerInfoJson.addProperty("uuid", uuid);
        playerInfoJson.addProperty("x", x);
        playerInfoJson.addProperty("y", y);
        playerInfoJson.addProperty("z", z);
        playerInfoJson.addProperty("yaw", yaw);
        playerInfoJson.addProperty("pitch", pitch);
        playerInfoJson.addProperty("health", health);
        playerInfoJson.addProperty("food", food);
        playerInfoJson.addProperty("saturation", saturation);
        playerInfoJson.addProperty("experience", experience);
        playerInfoJson.addProperty("level", level);
        playerInfoJson.addProperty("gamemode", gamemode);
        playerInfoJson.addProperty("dimension", dimension);
        playerInfoJson.add("inventory", inventoryJson);
        playerInfoJson.add("equipment", equipmentJson);
        playerInfoJson.add("held_item", heldItemJson);

        // 2. Gather Environment Snapshot
        // Weather
        boolean rain = world.isRaining();
        boolean thunder = world.isThundering();
        boolean clear = !rain && !thunder;
        long timeRemaining = 0;
        try {
            Object props = world.getLevelProperties();
            java.lang.reflect.Method m;
            if (rain) {
                m = props.getClass().getMethod("getRainTime");
            } else if (thunder) {
                m = props.getClass().getMethod("getThunderTime");
            } else {
                m = props.getClass().getMethod("getClearWeatherTime");
            }
            timeRemaining = ((Integer) m.invoke(props)).longValue();
        } catch (Exception e) {
            timeRemaining = 0;
        }

        JsonObject weatherJson = new JsonObject();
        weatherJson.addProperty("rain", rain);
        weatherJson.addProperty("thunder", thunder);
        weatherJson.addProperty("clear", clear);
        weatherJson.addProperty("time_remaining", timeRemaining);

        // Time
        long worldTime = world.getTime();
        long timeOfDay = world.getTimeOfDay() % 24000;
        boolean isDay = timeOfDay >= 0 && timeOfDay < 12000;
        boolean isNight = !isDay;
        int moonPhase = world.getMoonPhase();

        // Light level
        int blockLight = world.getLightLevel(net.minecraft.world.LightType.BLOCK, playerPos);
        int skyLight = world.getLightLevel(net.minecraft.world.LightType.SKY, playerPos);
        int combinedLight = world.getLightLevel(playerPos);
        JsonObject lightJson = new JsonObject();
        lightJson.addProperty("block", blockLight);
        lightJson.addProperty("sky", skyLight);
        lightJson.addProperty("combined", combinedLight);

        // Biome
        String biomeName = "unknown";
        double temperature = 0.0;
        double rainfall = 0.0;
        String category = "unknown";
        try {
            net.minecraft.registry.entry.RegistryEntry<net.minecraft.world.biome.Biome> biomeEntry = world.getBiome(playerPos);
            Identifier biomeId = world.getRegistryManager().get(RegistryKeys.BIOME).getId(biomeEntry.value());
            if (biomeId != null) {
                biomeName = biomeId.toString();
            }
            net.minecraft.world.biome.Biome biomeObj = biomeEntry.value();
            
            try {
                java.lang.reflect.Method tempMethod = biomeObj.getClass().getMethod("getTemperature", BlockPos.class);
                tempMethod.setAccessible(true);
                temperature = ((Float) tempMethod.invoke(biomeObj, playerPos)).doubleValue();
            } catch (Exception e) {
                try {
                    java.lang.reflect.Method tempMethod = biomeObj.getClass().getMethod("getTemperature");
                    temperature = ((Float) tempMethod.invoke(biomeObj)).doubleValue();
                } catch (Exception ex) {
                    temperature = 0.0;
                }
            }

            try {
                java.lang.reflect.Method downfallMethod = biomeObj.getClass().getMethod("getDownfall");
                rainfall = ((Float) downfallMethod.invoke(biomeObj)).doubleValue();
            } catch (Exception e) {
                rainfall = 0.0;
            }
            
            if (biomeName.contains("forest")) category = "forest";
            else if (biomeName.contains("desert")) category = "desert";
            else if (biomeName.contains("plains")) category = "plains";
            else if (biomeName.contains("ocean")) category = "ocean";
            else if (biomeName.contains("river") || biomeName.contains("lake")) category = "river";
            else if (biomeName.contains("swamp")) category = "swamp";
            else if (biomeName.contains("taiga")) category = "taiga";
            else if (biomeName.contains("mountain") || biomeName.contains("hills") || biomeName.contains("peaks")) category = "mountain";
            else if (biomeName.contains("nether") || biomeName.contains("wastes") || biomeName.contains("valley")) category = "nether";
            else if (biomeName.contains("the_end") || biomeName.contains("end")) category = "end";
        } catch (Exception e) {
            log("WARNING", "Failed to retrieve biome info: " + e.getMessage());
        }
        JsonObject biomeJson = new JsonObject();
        biomeJson.addProperty("name", biomeName);
        biomeJson.addProperty("temperature", temperature);
        biomeJson.addProperty("rainfall", rainfall);
        biomeJson.addProperty("category", category);

        // Entities
        JsonArray entitiesJson = new JsonArray();
        try {
            double entityRadius = 64.0;
            Box box = player.getBoundingBox().expand(entityRadius);
            List<net.minecraft.entity.Entity> entities = world.getOtherEntities(player, box);
            for (net.minecraft.entity.Entity entity : entities) {
                JsonObject entityJson = new JsonObject();
                entityJson.addProperty("type", Registries.ENTITY_TYPE.getId(entity.getType()).toString());
                entityJson.addProperty("name", entity.getName().getString());
                
                float entityHealth = 0.0f;
                float entityMaxHealth = 0.0f;
                if (entity instanceof net.minecraft.entity.LivingEntity living) {
                    entityHealth = living.getHealth();
                    entityMaxHealth = living.getMaxHealth();
                }
                entityJson.addProperty("health", entityHealth);
                entityJson.addProperty("max_health", entityMaxHealth);
                entityJson.addProperty("distance", entity.distanceTo(player));
                entityJson.addProperty("x", entity.getX());
                entityJson.addProperty("y", entity.getY());
                entityJson.addProperty("z", entity.getZ());

                String entCat = "other";
                if (entity instanceof ServerPlayerEntity) {
                    entCat = "player";
                } else if (entity instanceof net.minecraft.entity.passive.VillagerEntity) {
                    entCat = "villager";
                } else if (entity instanceof net.minecraft.entity.mob.Monster || entity instanceof net.minecraft.entity.mob.HostileEntity) {
                    entCat = "hostile";
                } else if (entity instanceof net.minecraft.entity.passive.AnimalEntity || entity instanceof net.minecraft.entity.passive.PassiveEntity) {
                    entCat = "passive";
                } else if (entity instanceof net.minecraft.entity.projectile.ProjectileEntity) {
                    entCat = "projectile";
                } else if (entity instanceof net.minecraft.entity.vehicle.BoatEntity || entity instanceof net.minecraft.entity.vehicle.AbstractMinecartEntity) {
                    entCat = "vehicle";
                }
                entityJson.addProperty("category", entCat);
                entitiesJson.add(entityJson);
            }
        } catch (Exception e) {
            log("WARNING", "Failed to retrieve nearby entities: " + e.getMessage());
        }

        // Blocks Scan (Radius 32)
        JsonObject fillerBlocksJson = new JsonObject();
        JsonArray interestingBlocksJson = new JsonArray();
        try {
            int scanRadius = 32;
            Map<String, BlockSummary> fillerSummaries = new HashMap<>();
            Map<String, List<int[]>> interestingOccurrences = new HashMap<>();

            for (int dx = -scanRadius; dx <= scanRadius; dx++) {
                for (int dz = -scanRadius; dz <= scanRadius; dz++) {
                    int chunkX = (playerPos.getX() + dx) >> 4;
                    int chunkZ = (playerPos.getZ() + dz) >> 4;
                    if (!world.getChunkManager().isChunkLoaded(chunkX, chunkZ)) {
                        continue;
                    }

                    for (int dy = -scanRadius; dy <= scanRadius; dy++) {
                        BlockPos targetPos = playerPos.add(dx, dy, dz);
                        if (targetPos.getY() < world.getBottomY() || targetPos.getY() >= world.getTopY()) {
                            continue;
                        }

                        String blockId = Registries.BLOCK.getId(world.getBlockState(targetPos).getBlock()).toString();
                        int dist = Math.max(Math.max(Math.abs(dx), Math.abs(dy)), Math.abs(dz));

                        if (FILLER_BLOCKS.contains(blockId)) {
                            BlockSummary sum = fillerSummaries.computeIfAbsent(blockId, k -> new BlockSummary());
                            sum.incrementCount(dist);
                            sum.updateNearest(dx, dy, dz, dist);
                        } else {
                            List<int[]> occurrences = interestingOccurrences.computeIfAbsent(blockId, k -> new ArrayList<>());
                            if (occurrences.size() < 500) {
                                occurrences.add(new int[]{dx, dy, dz});
                            } else {
                                BlockSummary sum = fillerSummaries.computeIfAbsent(blockId, k -> new BlockSummary());
                                sum.incrementCount(dist);
                                sum.updateNearest(dx, dy, dz, dist);
                            }
                        }
                    }
                }
            }

            for (Map.Entry<String, BlockSummary> entry : fillerSummaries.entrySet()) {
                JsonObject sumJson = new JsonObject();
                JsonArray nearestArr = new JsonArray();
                nearestArr.add(entry.getValue().nearestX);
                nearestArr.add(entry.getValue().nearestY);
                nearestArr.add(entry.getValue().nearestZ);
                sumJson.add("nearest", nearestArr);

                JsonObject countsJson = new JsonObject();
                countsJson.addProperty("8", entry.getValue().count8);
                countsJson.addProperty("16", entry.getValue().count16);
                countsJson.addProperty("32", entry.getValue().count32);
                countsJson.addProperty("64", entry.getValue().count32);
                sumJson.add("counts", countsJson);

                fillerBlocksJson.add(entry.getKey(), sumJson);
            }

            for (Map.Entry<String, List<int[]>> entry : interestingOccurrences.entrySet()) {
                String blockId = entry.getKey();
                for (int[] coord : entry.getValue()) {
                    JsonObject blockObj = new JsonObject();
                    blockObj.addProperty("type", blockId);
                    blockObj.addProperty("x", coord[0]);
                    blockObj.addProperty("y", coord[1]);
                    blockObj.addProperty("z", coord[2]);
                    interestingBlocksJson.add(blockObj);
                }
            }
        } catch (Exception e) {
            log("WARNING", "Failed to scan nearby blocks: " + e.getMessage());
        }

        JsonObject nearbyBlocksJson = new JsonObject();
        nearbyBlocksJson.add("filler_blocks", fillerBlocksJson);
        nearbyBlocksJson.add("interesting_blocks", interestingBlocksJson);

        JsonObject environmentJson = new JsonObject();
        environmentJson.add("weather", weatherJson);
        environmentJson.addProperty("world_time", worldTime);
        environmentJson.addProperty("is_day", isDay);
        environmentJson.addProperty("is_night", isNight);
        environmentJson.addProperty("moon_phase", moonPhase);
        environmentJson.add("light_level", lightJson);
        environmentJson.add("biome", biomeJson);
        environmentJson.add("nearby_blocks", nearbyBlocksJson);
        environmentJson.add("nearby_entities", entitiesJson);

        // 3. Assemble full player context object
        JsonObject playerJson = new JsonObject();
        playerJson.add("player_info", playerInfoJson);
        playerJson.add("environment", environmentJson);

        // Construct Request JSON
        JsonObject requestJson = new JsonObject();
        requestJson.addProperty("message", message);
        requestJson.add("player", playerJson);
        requestJson.add("memory", new JsonObject());

        String requestBody = gson.toJson(requestJson);
        log("REQUEST", requestBody);

        // Asynchronously call local backend
        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(CONNECT_TIMEOUT_SECONDS))
            .build();

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BACKEND_URL))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(requestBody))
            .timeout(Duration.ofSeconds(REQUEST_TIMEOUT_SECONDS))
            .build();

        CompletableFuture.supplyAsync(() -> {
            try {
                HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
                return response;
            } catch (IOException e) {
                throw new RuntimeException("OFFLINE", e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("INTERRUPTED", e);
            } catch (Exception e) {
                throw new RuntimeException("ERROR", e);
            }
        }).thenAcceptAsync(response -> {
            if (response.statusCode() == 200) {
                try {
                    String responseBody = response.body();
                    log("RESPONSE", responseBody);

                    JsonObject responseJson = JsonParser.parseString(responseBody).getAsJsonObject();
                    if (responseJson.has("reply")) {
                        String reply = responseJson.get("reply").getAsString();
                        player.sendMessage(Text.literal(reply).formatted(Formatting.GREEN), false);
                    } else {
                        throw new Exception("Missing 'reply' field in response JSON.");
                    }
                } catch (Exception e) {
                    log("ERROR", "Invalid response JSON: " + e.getMessage());
                    player.sendMessage(Text.literal("AI returned an invalid response format.").formatted(Formatting.RED), false);
                }
            } else {
                log("ERROR", "Server returned HTTP status " + response.statusCode());
                player.sendMessage(Text.literal("AI server returned an error (" + response.statusCode() + ").").formatted(Formatting.RED), false);
            }
        }, player.getServer()::execute).exceptionally(ex -> {
            Throwable cause = ex.getCause();
            if (cause != null && "OFFLINE".equals(cause.getMessage())) {
                log("ERROR", "AI server unavailable.");
                player.sendMessage(Text.literal("AI server unavailable.").formatted(Formatting.RED), false);
            } else if (cause instanceof java.net.http.HttpConnectTimeoutException || cause instanceof java.net.http.HttpTimeoutException) {
                log("ERROR", "AI request timed out.");
                player.sendMessage(Text.literal("AI request timed out.").formatted(Formatting.RED), false);
            } else {
                log("ERROR", "Unexpected error: " + ex.getMessage());
                player.sendMessage(Text.literal("An unexpected error occurred while communicating with the AI.").formatted(Formatting.RED), false);
            }
            return null;
        });
    }

    private JsonObject serializeItemStack(ItemStack stack) {
        JsonObject json = new JsonObject();
        if (stack == null || stack.isEmpty()) {
            json.addProperty("item", "minecraft:air");
            json.addProperty("count", 0);
            json.addProperty("durability", 0);
            json.add("enchantments", new JsonObject());
            return json;
        }

        String itemId = Registries.ITEM.getId(stack.getItem()).toString();
        json.addProperty("item", itemId);
        json.addProperty("count", stack.getCount());

        if (stack.isDamageable()) {
            json.addProperty("durability", stack.getMaxDamage() - stack.getDamage());
        } else {
            json.addProperty("durability", 0);
        }

        JsonObject enchantmentsJson = new JsonObject();
        try {
            net.minecraft.component.type.ItemEnchantmentsComponent enchants = stack.getEnchantments();
            if (enchants != null) {
                for (java.util.Map.Entry<net.minecraft.registry.entry.RegistryEntry<net.minecraft.enchantment.Enchantment>, Integer> entry : enchants.getEnchantmentEntries()) {
                    net.minecraft.registry.entry.RegistryEntry<net.minecraft.enchantment.Enchantment> enchEntry = entry.getKey();
                    int level = entry.getValue();
                    String enchId = enchEntry.getKey().map(key -> key.getValue().toString()).orElse("unknown");
                    enchantmentsJson.addProperty(enchId, level);
                }
            }
        } catch (Exception e) {
            log("WARNING", "Error getting enchantments: " + e.getMessage());
        }
        json.add("enchantments", enchantmentsJson);

        json.addProperty("nbt", stack.getName().getString());

        return json;
    }

    private void setupLogger() {
        try {
            Path gameDir = FabricLoader.getInstance().getGameDir();
            Path logDir;
            if (gameDir.getFileName().toString().equals("run")) {
                logDir = gameDir.getParent().getParent().resolve("logs");
            } else {
                logDir = gameDir.resolve("logs");
            }
            Files.createDirectories(logDir);
            logPath = logDir.resolve("aiassistant.log");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private synchronized static void log(String level, String message) {
        String timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        String logEntry = String.format("[%s] [%s] %s\n", timestamp, level, message);
        System.out.print("[AIAssistant] " + logEntry);
        if (logPath != null) {
            try {
                Files.writeString(logPath, logEntry, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    private static class BlockSummary {
        int nearestX = 0;
        int nearestY = 0;
        int nearestZ = 0;
        int nearestDist = Integer.MAX_VALUE;
        int count8 = 0;
        int count16 = 0;
        int count32 = 0;

        void incrementCount(int dist) {
            if (dist <= 8) {
                count8++;
            }
            if (dist <= 16) {
                count16++;
            }
            if (dist <= 32) {
                count32++;
            }
        }

        void updateNearest(int dx, int dy, int dz, int dist) {
            if (dist < nearestDist) {
                nearestDist = dist;
                nearestX = dx;
                nearestY = dy;
                nearestZ = dz;
            }
        }
    }
}
