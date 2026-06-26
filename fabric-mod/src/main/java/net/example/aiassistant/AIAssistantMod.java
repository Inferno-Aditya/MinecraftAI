package net.example.aiassistant;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.registry.RegistryKeys;
import net.minecraft.server.command.CommandManager;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.text.Text;
import net.minecraft.util.Formatting;
import net.minecraft.util.Identifier;

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

public class AIAssistantMod implements ModInitializer {
    private static final String BACKEND_URL = "http://localhost:8000/chat";
    private static final int TIMEOUT_SECONDS = 10;
    private static final Gson gson = new Gson();
    private static Path logPath;

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

        // Gather Player Context
        double x = player.getX();
        double y = player.getY();
        double z = player.getZ();
        float yaw = player.getYaw();
        float pitch = player.getPitch();
        String dimension = player.getWorld().getRegistryKey().getValue().toString();
        String gamemode = player.interactionManager.getGameMode().getName();
        float health = player.getHealth();
        int food = player.getHungerManager().getFoodLevel();
        long worldTime = player.getWorld().getTime();
        String playerName = player.getName().getString();

        // Biome detection
        String biome = "unknown";
        try {
            Identifier biomeId = player.getWorld().getRegistryManager()
                .get(RegistryKeys.BIOME)
                .getId(player.getWorld().getBiome(player.getBlockPos()).value());
            if (biomeId != null) {
                biome = biomeId.toString();
            }
        } catch (Exception e) {
            log("WARNING", "Failed to retrieve biome info: " + e.getMessage());
        }

        // Construct Request JSON
        JsonObject requestJson = new JsonObject();
        requestJson.addProperty("message", message);

        JsonObject playerJson = new JsonObject();
        playerJson.addProperty("name", playerName);
        playerJson.addProperty("x", x);
        playerJson.addProperty("y", y);
        playerJson.addProperty("z", z);
        playerJson.addProperty("yaw", yaw);
        playerJson.addProperty("pitch", pitch);
        playerJson.addProperty("dimension", dimension);
        playerJson.addProperty("gamemode", gamemode);
        playerJson.addProperty("health", health);
        playerJson.addProperty("food", food);
        playerJson.addProperty("world_time", worldTime);
        playerJson.addProperty("biome", biome);

        requestJson.add("player", playerJson);
        requestJson.add("memory", new JsonObject()); // Empty for Phase 1

        String requestBody = gson.toJson(requestJson);
        log("REQUEST", requestBody);

        // Asynchronously call local backend
        HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(TIMEOUT_SECONDS))
            .build();

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BACKEND_URL))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(requestBody))
            .timeout(Duration.ofSeconds(TIMEOUT_SECONDS))
            .build();

        CompletableFuture.supplyAsync(() -> {
            try {
                HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
                return response;
            } catch (IOException e) {
                // Connection offline
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

    private void setupLogger() {
        try {
            Path gameDir = FabricLoader.getInstance().getGameDir();
            Path logDir;
            if (gameDir.getFileName().toString().equals("run")) {
                // IDE environment
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
}
