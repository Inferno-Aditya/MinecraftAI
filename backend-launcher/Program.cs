using System;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using System.Diagnostics;
using System.Management;
using System.Runtime.InteropServices;

namespace MinecraftBackendLauncher
{
    public enum LauncherState
    {
        Idle,           // Minecraft is not running. Launcher is monitoring.
        Starting,       // Minecraft running, backend is starting and health checks are running.
        RunningManaged, // Minecraft running, backend spawned by launcher is healthy.
        RunningAttached,// Minecraft running, pre-existing backend detected and is healthy.
        Error           // Backend failed to start or crashed too many times.
    }

    public class LauncherMetrics
    {
        public LauncherState State { get; set; }
        public string StateString { get; set; } = "";
        public Color StateColor { get; set; }
        public bool MinecraftRunning { get; set; }
        public int MinecraftPid { get; set; }
        public bool BackendHealthy { get; set; }
        public int? BackendPid { get; set; }
        public DateTime LauncherUptimeStart { get; set; }
        public DateTime? BackendUptimeStart { get; set; }
        public int RestartAttempts { get; set; }
        public int MaxRestartAttempts { get; set; }
        public DateTime? LastHealthyCheck { get; set; }
        public bool AutoStartBackend { get; set; }
        public string HealthEndpoint { get; set; } = "";
    }

    public class LauncherConfig
    {
        public string BackendDirectory { get; set; } = "../backend";
        public string PythonExecutable { get; set; } = "../backend/venv/Scripts/python.exe";
        public string HealthEndpoint { get; set; } = "http://127.0.0.1:8000/health";
        public int PollIntervalMs { get; set; } = 2000;
        public int MaxRestartAttempts { get; set; } = 3;
        public bool AutoStartBackend { get; set; } = true;
    }

    static class Program
    {
        [STAThread]
        static void Main()
        {
            ApplicationConfiguration.Initialize();
            
            // Check for already running instance of the launcher itself
            using (Mutex mutex = new Mutex(true, "MinecraftAIBackendLauncherMutex", out bool createdNew))
            {
                if (!createdNew)
                {
                    MessageBox.Show("Minecraft AI Companion Launcher is already running in the system tray.", 
                        "Launcher Already Running", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }

                using (var context = new LauncherApplicationContext())
                {
                    Application.Run(context);
                }
            }
        }
    }

    public class LauncherApplicationContext : ApplicationContext
    {
        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyIcon(IntPtr hIcon);

        private NotifyIcon? _notifyIcon;
        private readonly HttpClient _httpClient;
        private readonly CancellationTokenSource _cts;
        
        // Configuration
        private LauncherConfig _config = new LauncherConfig();
        private string _configPath = "";
        private string _logFilePath = "";

        // State variables (protected by lock)
        private readonly object _stateLock = new object();
        private LauncherState _state = LauncherState.Idle;
        private bool _minecraftRunning = false;
        private int _minecraftPid = 0;
        private bool _backendHealthy = false;
        private Process? _managedBackendProcess = null;
        private int _restartAttempts = 0;
        private DateTime _launcherUptimeStart;
        private DateTime? _backendUptimeStart = null;
        private DateTime? _lastHealthyCheck = null;
        private DateTime _backendSpawnTime = DateTime.MinValue;

        // UI Form
        private DashboardForm? _dashboardForm = null;

        // Lock for logging
        private readonly object _logLock = new object();

        public LauncherApplicationContext()
        {
            _launcherUptimeStart = DateTime.Now;
            _cts = new CancellationTokenSource();
            _httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };

            // Initialize Configuration & Logger paths
            InitializeConfigAndPaths();

            LogInfo("Launcher initialized in monitoring mode.");

            // Initialize Tray Icon
            try
            {
                _notifyIcon = new NotifyIcon
                {
                    Text = "Minecraft AI Companion Launcher: Monitoring",
                    Visible = true
                };
                
                // Set initial slate blue icon
                UpdateTrayIcon(LauncherState.Idle);

                // Double click opens dashboard
                _notifyIcon.DoubleClick += (s, e) => ShowDashboard();

                // Set up tray context menu
                var contextMenu = new ContextMenuStrip();
                contextMenu.Items.Add("Status Dashboard", null, (s, e) => ShowDashboard());
                contextMenu.Items.Add("Force Restart Backend", null, (s, e) => ForceRestartBackend());
                contextMenu.Items.Add("-");
                contextMenu.Items.Add("Open Launcher Log", null, (s, e) => OpenLogFile());
                contextMenu.Items.Add("Open Configuration", null, (s, e) => OpenConfigFile());
                contextMenu.Items.Add("-");
                contextMenu.Items.Add("Exit Launcher", null, (s, e) => ExitApplication());
                _notifyIcon.ContextMenuStrip = contextMenu;
            }
            catch (Exception ex)
            {
                LogWarning($"System tray icon not available: {ex.Message}. Running in background mode.");
            }

            // Start background loop
            Task.Run(() => MonitorLoopAsync(_cts.Token));
        }

        private string ResolvePath(string path)
        {
            if (string.IsNullOrEmpty(path)) return "";
            if (Path.IsPathRooted(path)) return path;

            // 1. Find workspace root recursively
            string currentDir = AppDomain.CurrentDomain.BaseDirectory;
            string? workspaceRoot = null;
            while (!string.IsNullOrEmpty(currentDir))
            {
                string possibleBackend = Path.Combine(currentDir, "backend");
                if (Directory.Exists(possibleBackend) && File.Exists(Path.Combine(possibleBackend, "main.py")))
                {
                    workspaceRoot = currentDir;
                    break;
                }
                currentDir = Path.GetDirectoryName(currentDir) ?? "";
            }

            // 2. Resolve relative to workspace root if found
            if (workspaceRoot != null)
            {
                string resolvedPath = Path.GetFullPath(Path.Combine(workspaceRoot, path));
                if (Directory.Exists(resolvedPath) || File.Exists(resolvedPath))
                {
                    return resolvedPath;
                }

                // Try stripping standard relative parts
                if (path.StartsWith(".."))
                {
                    string cleanPath = path;
                    while (cleanPath.StartsWith("../") || cleanPath.StartsWith("..\\"))
                    {
                        cleanPath = cleanPath.Substring(3);
                    }
                    string resolvedCleanPath = Path.GetFullPath(Path.Combine(workspaceRoot, cleanPath));
                    if (Directory.Exists(resolvedCleanPath) || File.Exists(resolvedCleanPath))
                    {
                        return resolvedCleanPath;
                    }
                }
            }

            // 3. Fallback: resolve relative to executable directory
            return Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, path));
        }

        private void InitializeConfigAndPaths()
        {
            _configPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher_config.json");
            LoadConfig();

            // Resolve log file path relative to workspace
            try
            {
                string resolvedBackendDir = ResolvePath(_config.BackendDirectory);
                // Workspace root is the parent of backend directory
                string workspaceRoot = Path.GetDirectoryName(resolvedBackendDir) ?? AppDomain.CurrentDomain.BaseDirectory;
                string logsDir = Path.Combine(workspaceRoot, "logs");
                _logFilePath = Path.Combine(logsDir, "launcher.log");
            }
            catch (Exception ex)
            {
                // Fallback to local logs directory if resolve fails
                string logsDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "logs");
                _logFilePath = Path.Combine(logsDir, "launcher.log");
                Console.WriteLine($"Error resolving workspace paths: {ex.Message}. Using fallback log path.");
            }
        }

        private void LoadConfig()
        {
            try
            {
                if (File.Exists(_configPath))
                {
                    string json = File.ReadAllText(_configPath);
                    var loadedConfig = JsonSerializer.Deserialize<LauncherConfig>(json);
                    if (loadedConfig != null)
                    {
                        _config = loadedConfig;
                    }
                }
                else
                {
                    // Create default configuration file if missing
                    string defaultJson = JsonSerializer.Serialize(_config, new JsonSerializerOptions { WriteIndented = true });
                    File.WriteAllText(_configPath, defaultJson);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Failed to load configuration: {ex.Message}. Using default settings.");
            }
        }

        private void UpdateTrayIcon(LauncherState state)
        {
            if (_notifyIcon == null) return;
            Color color = GetStateColor(state);
            try
            {
                using (Bitmap bmp = new Bitmap(16, 16))
                {
                    using (Graphics g = Graphics.FromImage(bmp))
                    {
                        g.Clear(Color.Transparent);
                        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;

                        // Background filled circle
                        using (Brush brush = new SolidBrush(color))
                        {
                            g.FillEllipse(brush, 1, 1, 14, 14);
                        }

                        // White inner circle dot for clean design
                        using (Brush dotBrush = new SolidBrush(Color.White))
                        {
                            g.FillEllipse(dotBrush, 5, 5, 6, 6);
                        }

                        // Translucent white border
                        using (Pen pen = new Pen(Color.FromArgb(60, 255, 255, 255), 1))
                        {
                            g.DrawEllipse(pen, 1, 1, 14, 14);
                        }
                    }

                    IntPtr hIcon = bmp.GetHicon();
                    Icon? oldIcon = _notifyIcon.Icon;
                    _notifyIcon.Icon = Icon.FromHandle(hIcon);

                    // Free memory of the old icon handle to avoid leaks
                    if (oldIcon != null)
                    {
                        DestroyIcon(oldIcon.Handle);
                    }
                }
            }
            catch (Exception ex)
            {
                LogError($"Failed to update tray icon: {ex.Message}");
            }
        }

        public LauncherMetrics GetMetrics()
        {
            lock (_stateLock)
            {
                return new LauncherMetrics
                {
                    State = _state,
                    StateString = GetStateString(_state),
                    StateColor = GetStateColor(_state),
                    MinecraftRunning = _minecraftRunning,
                    MinecraftPid = _minecraftPid,
                    BackendHealthy = _backendHealthy,
                    BackendPid = _managedBackendProcess?.Id,
                    LauncherUptimeStart = _launcherUptimeStart,
                    BackendUptimeStart = _backendUptimeStart,
                    RestartAttempts = _restartAttempts,
                    MaxRestartAttempts = _config.MaxRestartAttempts,
                    LastHealthyCheck = _lastHealthyCheck,
                    AutoStartBackend = _config.AutoStartBackend,
                    HealthEndpoint = _config.HealthEndpoint
                };
            }
        }

        public static string GetStateString(LauncherState state)
        {
            return state switch
            {
                LauncherState.Idle => "Monitoring (Minecraft not running)",
                LauncherState.Starting => "Starting backend...",
                LauncherState.RunningManaged => "Running (Managed backend active)",
                LauncherState.RunningAttached => "Running (Attached to manual backend)",
                LauncherState.Error => "Error (Backend failed to start/crashed)",
                _ => "Unknown"
            };
        }

        public static Color GetStateColor(LauncherState state)
        {
            return state switch
            {
                LauncherState.Idle => Color.FromArgb(70, 80, 95),       // Slate Blue
                LauncherState.Starting => Color.FromArgb(245, 158, 11),  // Amber / Yellow
                LauncherState.RunningManaged => Color.FromArgb(16, 185, 129), // Emerald Green
                LauncherState.RunningAttached => Color.FromArgb(16, 185, 129), // Emerald Green
                LauncherState.Error => Color.FromArgb(239, 68, 68),      // Crimson Red
                _ => Color.Gray
            };
        }

        private async Task MonitorLoopAsync(CancellationToken cancellationToken)
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                try
                {
                    await TickMonitoringAsync();
                }
                catch (Exception ex)
                {
                    LogError($"Error in monitoring loop: {ex.Message}");
                }
                
                // Read poll interval from config dynamically to allow updates on the fly
                int pollInterval = _config.PollIntervalMs > 0 ? _config.PollIntervalMs : 2000;
                await Task.Delay(pollInterval, cancellationToken);
            }
        }

        private async Task TickMonitoringAsync()
        {
            // 1. Detect Minecraft
            var (mcRunning, mcPid) = DetectMinecraftProcess();
            
            // 2. Perform Health Check
            bool backendHealthy = await CheckBackendHealthAsync();

            lock (_stateLock)
            {
                _minecraftRunning = mcRunning;
                _minecraftPid = mcPid;
                _backendHealthy = backendHealthy;

                if (backendHealthy)
                {
                    _lastHealthyCheck = DateTime.Now;
                }

                // Load config changes if config file was modified
                LoadConfig();

                // 3. State Machine
                switch (_state)
                {
                    case LauncherState.Idle:
                        if (_minecraftRunning)
                        {
                            if (backendHealthy)
                            {
                                LogInfo("Pre-existing healthy backend detected. Attaching to instance.");
                                _backendUptimeStart = DateTime.Now; // Estimate uptime start from attach time
                                TransitionTo(LauncherState.RunningAttached);
                            }
                            else if (_config.AutoStartBackend)
                            {
                                LogInfo($"Minecraft client detected (PID: {_minecraftPid}). Starting backend...");
                                LaunchBackend();
                            }
                            else
                            {
                                if (_notifyIcon != null)
                                {
                                    _notifyIcon.Text = "Minecraft AI: Running (Backend Auto-Start Disabled)";
                                }
                            }
                        }
                        else
                        {
                            // If we have a stale managed backend still running, kill it
                            if (_managedBackendProcess != null && !_managedBackendProcess.HasExited)
                            {
                                LogInfo("Minecraft is not running. Stopping orphaned managed backend...");
                                StopBackend();
                            }
                        }
                        break;

                    case LauncherState.Starting:
                        if (!_minecraftRunning)
                        {
                            LogInfo("Minecraft exited during backend startup. Stopping backend.");
                            StopBackend();
                            TransitionTo(LauncherState.Idle);
                        }
                        else if (backendHealthy)
                        {
                            LogInfo("Backend health check passed. Backend is active and healthy.");
                            _backendUptimeStart = DateTime.Now;
                            _restartAttempts = 0;
                            TransitionTo(LauncherState.RunningManaged);
                        }
                        else
                        {
                            // Check if backend startup health check timed out (30 seconds limit)
                            if ((DateTime.Now - _backendSpawnTime).TotalSeconds > 30)
                            {
                                LogError("Backend health check timed out during startup.");
                                StopBackend();
                                HandleBackendFailure();
                            }
                        }
                        break;

                    case LauncherState.RunningManaged:
                        if (!_minecraftRunning)
                        {
                            LogInfo("Minecraft exited. Shutting down managed backend...");
                            StopBackend();
                            TransitionTo(LauncherState.Idle);
                        }
                        else if (_managedBackendProcess == null || _managedBackendProcess.HasExited || !backendHealthy)
                        {
                            LogWarning("Managed backend process terminated or became unhealthy.");
                            StopBackend();
                            HandleBackendFailure();
                        }
                        break;

                    case LauncherState.RunningAttached:
                        if (!_minecraftRunning)
                        {
                            LogInfo("Minecraft exited. Detaching from backend.");
                            TransitionTo(LauncherState.Idle);
                        }
                        else if (!backendHealthy)
                        {
                            LogWarning("Attached backend went offline.");
                            if (_config.AutoStartBackend)
                            {
                                LogInfo("AutoStart is enabled. Spawning managed backend...");
                                LaunchBackend();
                            }
                            else
                            {
                                TransitionTo(LauncherState.Idle);
                            }
                        }
                        break;

                    case LauncherState.Error:
                        if (!_minecraftRunning)
                        {
                            LogInfo("Minecraft exited. Clearing error state and returning to Idle.");
                            _restartAttempts = 0;
                            TransitionTo(LauncherState.Idle);
                        }
                        else if (backendHealthy)
                        {
                            LogInfo("Healthy backend detected while in error state. Attaching...");
                            _backendUptimeStart = DateTime.Now;
                            TransitionTo(LauncherState.RunningAttached);
                        }
                        break;
                }
            }
        }

        private void TransitionTo(LauncherState newState)
        {
            _state = newState;
            UpdateTrayIcon(newState);
            
            string statusMsg = GetStateString(newState);
            if (newState == LauncherState.RunningManaged && _managedBackendProcess != null)
            {
                statusMsg += $" (PID: {_managedBackendProcess.Id})";
            }
            if (_notifyIcon != null)
            {
                _notifyIcon.Text = $"Minecraft AI Launcher: {statusMsg}";
            }
        }

        private void HandleBackendFailure()
        {
            if (_restartAttempts < _config.MaxRestartAttempts)
            {
                _restartAttempts++;
                LogInfo($"Attempting backend auto-restart ({_restartAttempts}/{_config.MaxRestartAttempts})...");
                LaunchBackend();
            }
            else
            {
                LogError($"Backend startup failed after {_config.MaxRestartAttempts} attempts. Entering error state.");
                TransitionTo(LauncherState.Error);
            }
        }

        private void LaunchBackend()
        {
            string pythonExe = ResolvePath(_config.PythonExecutable);
            string backendDir = ResolvePath(_config.BackendDirectory);

            if (!Directory.Exists(backendDir))
            {
                LogError($"Backend directory does not exist: {backendDir}");
                TransitionTo(LauncherState.Error);
                return;
            }

            if (!File.Exists(pythonExe))
            {
                LogError($"Python executable does not exist: {pythonExe}");
                TransitionTo(LauncherState.Error);
                return;
            }

            try
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = "main.py",
                    WorkingDirectory = backendDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false
                };

                _managedBackendProcess = new Process { StartInfo = startInfo };
                _managedBackendProcess.Start();
                _backendSpawnTime = DateTime.Now;

                // Associate process with Windows Job Object for automatic clean-up on exit
                JobObject.AssociateProcess(_managedBackendProcess);

                LogInfo($"Backend process launched successfully (PID: {_managedBackendProcess.Id}).");
                TransitionTo(LauncherState.Starting);
            }
            catch (Exception ex)
            {
                LogError($"Failed to spawn backend process: {ex.Message}");
                TransitionTo(LauncherState.Error);
            }
        }

        private void StopBackend()
        {
            if (_managedBackendProcess != null)
            {
                try
                {
                    if (!_managedBackendProcess.HasExited)
                    {
                        LogInfo($"Killing backend process tree (PID: {_managedBackendProcess.Id})...");
                        _managedBackendProcess.Kill(entireProcessTree: true);
                    }
                }
                catch (Exception ex)
                {
                    LogError($"Failed to terminate backend process tree: {ex.Message}");
                }
                finally
                {
                    _managedBackendProcess.Dispose();
                    _managedBackendProcess = null;
                    _backendUptimeStart = null;
                }
            }
        }

        public void ForceRestartBackend()
        {
            lock (_stateLock)
            {
                LogInfo("Force-restart triggered by user.");
                StopBackend();
                _restartAttempts = 0;
                if (_minecraftRunning)
                {
                    LaunchBackend();
                }
                else
                {
                    LogInfo("Minecraft is not running. Launcher remains Idle.");
                    TransitionTo(LauncherState.Idle);
                }
            }
        }

        private async Task<bool> CheckBackendHealthAsync()
        {
            try
            {
                using (var response = await _httpClient.GetAsync(_config.HealthEndpoint))
                {
                    if (response.IsSuccessStatusCode)
                    {
                        string body = await response.Content.ReadAsStringAsync();
                        return body.Contains("healthy");
                    }
                }
            }
            catch
            {
                // Health check failed (server offline / unresponsive)
            }
            return false;
        }

        private (bool isRunning, int pid) DetectMinecraftProcess()
        {
            try
            {
                // Query active processes using WMI
                using (var searcher = new ManagementObjectSearcher(
                    "SELECT ProcessId, Name, CommandLine FROM Win32_Process WHERE Name = 'javaw.exe' OR Name = 'java.exe'"))
                {
                    using (var collection = searcher.Get())
                    {
                        foreach (var obj in collection)
                        {
                            var pidVal = obj["ProcessId"];
                            if (pidVal == null) continue;
                            int pid = Convert.ToInt32(pidVal);

                            string commandLine = obj["CommandLine"]?.ToString() ?? "";

                            if (IsMinecraftCommandLine(commandLine))
                            {
                                return (true, pid);
                            }
                        }
                    }
                }
            }
            catch (Exception)
            {
                // Fall back to title-based matching in case of WMI permission errors
                return DetectMinecraftProcessFallback();
            }
            return (false, 0);
        }

        private (bool isRunning, int pid) DetectMinecraftProcessFallback()
        {
            try
            {
                var processes = Process.GetProcessesByName("javaw").Concat(Process.GetProcessesByName("java"));
                foreach (var proc in processes)
                {
                    try
                    {
                        if (!proc.HasExited && (proc.MainWindowTitle.Contains("Minecraft") || proc.MainWindowTitle.Contains("Fabric")))
                        {
                            return (true, proc.Id);
                        }
                    }
                    catch
                    {
                        // Ignore access denied for specific processes
                    }
                }
            }
            catch
            {
                // Ignore fallback errors
            }
            return (false, 0);
        }

        private bool IsMinecraftCommandLine(string cmdLine)
        {
            if (string.IsNullOrEmpty(cmdLine)) return false;

            // Look for client-specific flags
            return cmdLine.Contains("net.minecraft.client.main.Main") ||
                   cmdLine.Contains("net.minecraft.launchwrapper.Launch") ||
                   cmdLine.Contains("--gameDir") ||
                   cmdLine.Contains("-Dminecraft.launcher.brand") ||
                   cmdLine.Contains("fabric-loader");
        }

        private void ShowDashboard()
        {
            if (_dashboardForm == null || _dashboardForm.IsDisposed)
            {
                _dashboardForm = new DashboardForm(this);
            }
            
            if (_dashboardForm.Visible)
            {
                _dashboardForm.Activate();
            }
            else
            {
                _dashboardForm.Show();
            }
        }

        public void OpenLogFile()
        {
            try
            {
                if (File.Exists(_logFilePath))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = _logFilePath,
                        UseShellExecute = true
                    });
                }
                else
                {
                    MessageBox.Show("Launcher log file does not exist yet.", "Log File Not Found", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to open log file: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OpenConfigFile()
        {
            try
            {
                if (File.Exists(_configPath))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = _configPath,
                        UseShellExecute = true
                    });
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to open configuration file: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void LogInfo(string message) => Log("INFO", message);
        private void LogWarning(string message) => Log("WARN", message);
        private void LogError(string message) => Log("ERROR", message);

        private void Log(string level, string message)
        {
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            var logLine = $"[{timestamp}] [{level}] {message}";

            Console.WriteLine(logLine);

            try
            {
                lock (_logLock)
                {
                    if (!string.IsNullOrEmpty(_logFilePath))
                    {
                        string? dir = Path.GetDirectoryName(_logFilePath);
                        if (dir != null && !Directory.Exists(dir))
                        {
                            Directory.CreateDirectory(dir);
                        }
                        File.AppendAllText(_logFilePath, logLine + Environment.NewLine);
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Failed to write to log file: {ex.Message}");
            }
        }

        private void ExitApplication()
        {
            if (MessageBox.Show("Are you sure you want to exit the Minecraft AI Companion Launcher? This will close the AI Backend.", 
                "Exit Launcher", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
            {
                ExitThread();
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _cts.Cancel();
                _cts.Dispose();
                
                // Terminate managed backend process on shutdown
                StopBackend();
                
                // Clean up job objects
                JobObject.CleanUp();

                if (_notifyIcon != null)
                {
                    _notifyIcon.Visible = false;
                    _notifyIcon.Dispose();
                }

                _dashboardForm?.Dispose();
                _httpClient.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}