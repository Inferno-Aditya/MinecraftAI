# Minecraft AI Companion: Automatic Backend Launcher (v0.4.2)

The **Automatic Backend Launcher** is a standalone, lightweight Windows background utility that automates the lifecycle of the Minecraft AI Python backend. It eliminates the need to manually start or stop the backend command prompt windows.

---

## Features

1. **Automatic Minecraft Detection**: Monitors running processes for the Minecraft Java client (`javaw.exe`/`java.exe`) using command-line argument analysis, ignoring launcher processes.
2. **Backend Lifecycle Automation**: Starts the FastAPI backend automatically using the project's virtual environment python executable when Minecraft launches.
3. **Graceful Shutdown**: Automatically shuts down the backend process and all its children when Minecraft exits.
4. **Health Check Validation**: Polls the `/health` endpoint after starting to confirm the server is fully ready.
5. **No Duplicate Processes**: Before spawning a new backend instance, it queries `/health`. If a healthy backend is already running (manually or otherwise), it automatically attaches to it.
6. **Orphan Prevention (Job Objects)**: Integrates native Windows Job Objects (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`). If the launcher crashes or is killed, Windows guarantees that no orphan Python processes are left behind.
7. **System Tray Integration**: Operates completely in the background with a dynamic, color-coded system tray icon:
   * 🔘 **Slate Blue**: Idle / Monitoring (Minecraft not running)
   * 🟡 **Amber/Yellow**: Starting backend / performing health checks
   * 🟢 **Emerald Green**: Running (Minecraft and backend active)
   * 🔴 **Crimson Red**: Error (Backend failed to start or crashed too many times)
8. **Status Dashboard**: A lightweight, dark-themed UI window showing real-time details of Minecraft status, backend health, uptimes, restart counters, and configuration values.

---

## Configuration

A configuration file named `launcher_config.json` is located next to the executable.

```json
{
  "BackendDirectory": "../backend",
  "PythonExecutable": "../backend/venv/Scripts/python.exe",
  "HealthEndpoint": "http://127.0.0.1:8000/health",
  "PollIntervalMs": 2000,
  "MaxRestartAttempts": 3,
  "AutoStartBackend": true
}
```

### Config Options:
* `BackendDirectory`: Path to the Python backend source directory (relative to launcher directory or absolute).
* `PythonExecutable`: Path to the Python executable within the virtual environment.
* `HealthEndpoint`: The HTTP URL of the FastAPI health check.
* `PollIntervalMs`: Time in milliseconds between monitoring checks (e.g., `2000` = 2 seconds).
* `MaxRestartAttempts`: Maximum backend restart attempts on unexpected crashes.
* `AutoStartBackend`: Set to `true` (default) to start the backend automatically. Set to `false` to use the launcher purely as a monitor/dashboard without spawning a managed backend.

---

## Building the Launcher

To build the launcher into a lightweight, standalone Windows application:

1. Open PowerShell or Command Prompt.
2. Navigate to the `backend-launcher` directory:
   ```powershell
   cd e:\Personal\minecraft\backend-launcher
   ```
3. Compile using the .NET CLI:
   ```powershell
   dotnet publish -c Release -r win-x64 --self-contained false -o publish
   ```
4. Find the output files inside the `publish` directory:
   * `MinecraftAICompanion.exe` (Standalone background utility)
   * `launcher_config.json` (Configuration file)

---

## Usage

1. Run `MinecraftAICompanion.exe`.
2. The application will start silently, placing a status icon in the Windows system tray.
3. **Double-click** the system tray icon (or right-click and select **Status Dashboard**) to open the visual monitor window.
4. Right-click the system tray icon to access quick actions:
   * **Status Dashboard**: Open the monitoring window.
   * **Force Restart Backend**: Restart the AI backend manually (active when Minecraft is running).
   * **Open Launcher Log**: View the dedicated log file.
   * **Open Configuration**: Edit `launcher_config.json`.
   * **Exit Launcher**: Safely shutdown the launcher and close any active backend.

---

## Logging

All launcher operations are logged to the standard `logs/` directory of the workspace:
📂 `<workspace>/logs/launcher.log`

The launcher appends entries in a clean, standardized format:
```log
[2026-06-26 20:00:00] [INFO] Launcher initialized in monitoring mode.
[2026-06-26 20:00:02] [INFO] Minecraft client detected (PID: 12345). Starting backend...
[2026-06-26 20:00:03] [INFO] Backend process launched successfully (PID: 67890).
[2026-06-26 20:00:05] [INFO] Backend health check passed. Backend is active and healthy.
[2026-06-26 20:05:00] [INFO] Minecraft exited. Shutting down managed backend...
[2026-06-26 20:05:01] [INFO] Killing backend process tree (PID: 67890)...
[2026-06-26 20:05:01] [INFO] Minecraft exited. Clearing error state and returning to Idle.
```

Sensitive information, including API keys and LLM prompts, is **never** logged by the launcher.
