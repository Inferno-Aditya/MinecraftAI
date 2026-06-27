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
        Starting,       // Minecraft running, backend or dashboard is starting and health checks are running.
        RunningManaged, // Minecraft running, backend/dashboard spawned by launcher is healthy.
        RunningAttached,// Minecraft running, pre-existing backend/dashboard detected and is healthy.
        Error           // Backend or dashboard failed to start or crashed too many times.
    }

    public class LauncherMetrics
    {
        public LauncherState State { get; set; }
        public string StateString { get; set; } = "";
        public Color StateColor { get; set; }
        public bool MinecraftRunning { get; set; }
        public int MinecraftPid { get; set; }
        public DateTime LauncherUptimeStart { get; set; }

        // Backend
        public ServiceState BackendState { get; set; }
        public string BackendStateString { get; set; } = "";
        public Color BackendStateColor { get; set; }
        public int? BackendPid { get; set; }
        public DateTime? BackendUptimeStart { get; set; }
        public int BackendRestartAttempts { get; set; }
        public int BackendMaxRestartAttempts { get; set; }
        public bool BackendHealthCheckResult { get; set; }
        public DateTime? BackendLastHealthyCheck { get; set; }
        public bool AutoStartBackend { get; set; }
        public string BackendHealthUrl { get; set; } = "";
        public bool BackendManuallyOverridden { get; set; }
        public int BackendTotalStarts { get; set; }
        public int BackendTotalRestarts { get; set; }
        public int BackendUnexpectedCrashes { get; set; }
        public DateTime? BackendLastSuccessfulLaunch { get; set; }
        public DateTime? BackendLastSuccessfulShutdown { get; set; }
        public int BackendConsecutiveFailureCount { get; set; }
        public string BackendWorkingDirectory { get; set; } = "";
        public string BackendStartupCommand { get; set; } = "";

        // Dashboard
        public ServiceState DashboardState { get; set; }
        public string DashboardStateString { get; set; } = "";
        public Color DashboardStateColor { get; set; }
        public int? DashboardPid { get; set; }
        public DateTime? DashboardUptimeStart { get; set; }
        public int DashboardRestartAttempts { get; set; }
        public int DashboardMaxRestartAttempts { get; set; }
        public bool DashboardHealthCheckResult { get; set; }
        public DateTime? DashboardLastHealthyCheck { get; set; }
        public bool AutoStartDashboard { get; set; }
        public string DashboardHealthUrl { get; set; } = "";
        public bool DashboardManuallyOverridden { get; set; }
        public int DashboardTotalStarts { get; set; }
        public int DashboardTotalRestarts { get; set; }
        public int DashboardUnexpectedCrashes { get; set; }
        public DateTime? DashboardLastSuccessfulLaunch { get; set; }
        public DateTime? DashboardLastSuccessfulShutdown { get; set; }
        public int DashboardConsecutiveFailureCount { get; set; }
        public string DashboardWorkingDirectory { get; set; } = "";
        public string DashboardStartupCommand { get; set; } = "";
    }

    public class LauncherConfig
    {
        public string BackendDirectory { get; set; } = "../backend";
        public string PythonExecutable { get; set; } = "../backend/venv/Scripts/python.exe";
        public string HealthEndpoint { get; set; } = "http://127.0.0.1:8000/health";
        public int PollIntervalMs { get; set; } = 2000;
        public int MaxRestartAttempts { get; set; } = 3;
        public bool AutoStartBackend { get; set; } = true;

        public bool AutoStartDashboard { get; set; } = true;
        public string DashboardCommand { get; set; } = "npm run dev";
        public string DashboardWorkingDirectory { get; set; } = "../dashboard";
        public string DashboardHealthUrl { get; set; } = "http://localhost:5173";
        public int DashboardRestartAttempts { get; set; } = 3;
        public int BackendStartupTimeoutSeconds { get; set; } = 30;
        public int DashboardStartupTimeoutSeconds { get; set; } = 30;
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

        // Managers
        private readonly BackendManager _backendManager;
        private readonly DashboardManager _dashboardManager;

        // UI Form
        private DashboardForm? _dashboardForm = null;

        // Lock for logging
        private readonly object _logLock = new object();

        private DateTime _launcherUptimeStart;

        public LauncherConfig Config => _config;

        public LauncherApplicationContext()
        {
            _launcherUptimeStart = DateTime.Now;
            _cts = new CancellationTokenSource();
            _httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };

            // Initialize Configuration & Logger paths
            InitializeConfigAndPaths();

            // Instantiate managers
            _backendManager = new BackendManager(this, _httpClient);
            _dashboardManager = new DashboardManager(this, _httpClient);

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
                contextMenu.Items.Add("Force Restart Backend", null, (s, e) => RestartBackendManual());
                contextMenu.Items.Add("Force Restart Dashboard", null, (s, e) => RestartDashboardManual());
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

        public ServiceManager? GetService(string name)
        {
            if (name.Equals("Backend", StringComparison.OrdinalIgnoreCase)) return _backendManager;
            if (name.Equals("Dashboard", StringComparison.OrdinalIgnoreCase)) return _dashboardManager;
            return null;
        }

        public string ResolvePath(string path)
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
                var globalState = DetermineGlobalState();
                return new LauncherMetrics
                {
                    State = globalState,
                    StateString = GetStateString(globalState),
                    StateColor = GetStateColor(globalState),
                    MinecraftRunning = _minecraftRunning,
                    MinecraftPid = _minecraftPid,
                    LauncherUptimeStart = _launcherUptimeStart,

                    // Backend
                    BackendState = _backendManager.State,
                    BackendStateString = GetServiceStateString(_backendManager.State, _backendManager.IsAutoStartEnabled(), _backendManager.IsManuallyStopped),
                    BackendStateColor = GetServiceStateColor(_backendManager.State),
                    BackendPid = _backendManager.ProcessId,
                    BackendUptimeStart = _backendManager.UptimeStart,
                    BackendRestartAttempts = _backendManager.ConsecutiveFailureCount > 0 ? _backendManager.ConsecutiveFailureCount - 1 : 0,
                    BackendMaxRestartAttempts = _backendManager.GetMaxRestartAttempts(),
                    BackendHealthCheckResult = _backendManager.LastHealthCheckResult,
                    BackendLastHealthyCheck = _backendManager.LastHealthyCheckTime,
                    AutoStartBackend = _backendManager.IsAutoStartEnabled(),
                    BackendHealthUrl = _backendManager.GetHealthUrl(),
                    BackendManuallyOverridden = _backendManager.IsManuallyStarted || _backendManager.IsManuallyStopped,
                    BackendTotalStarts = _backendManager.TotalStarts,
                    BackendTotalRestarts = _backendManager.TotalRestarts,
                    BackendUnexpectedCrashes = _backendManager.UnexpectedCrashes,
                    BackendLastSuccessfulLaunch = _backendManager.LastSuccessfulLaunch,
                    BackendLastSuccessfulShutdown = _backendManager.LastSuccessfulShutdown,
                    BackendConsecutiveFailureCount = _backendManager.ConsecutiveFailureCount,
                    BackendWorkingDirectory = _backendManager.GetWorkingDirectory(),
                    BackendStartupCommand = _backendManager.GetStartupCommand(),

                    // Dashboard
                    DashboardState = _dashboardManager.State,
                    DashboardStateString = GetServiceStateString(_dashboardManager.State, _dashboardManager.IsAutoStartEnabled(), _dashboardManager.IsManuallyStopped),
                    DashboardStateColor = GetServiceStateColor(_dashboardManager.State),
                    DashboardPid = _dashboardManager.ProcessId,
                    DashboardUptimeStart = _dashboardManager.UptimeStart,
                    DashboardRestartAttempts = _dashboardManager.ConsecutiveFailureCount > 0 ? _dashboardManager.ConsecutiveFailureCount - 1 : 0,
                    DashboardMaxRestartAttempts = _dashboardManager.GetMaxRestartAttempts(),
                    DashboardHealthCheckResult = _dashboardManager.LastHealthCheckResult,
                    DashboardLastHealthyCheck = _dashboardManager.LastHealthyCheckTime,
                    AutoStartDashboard = _dashboardManager.IsAutoStartEnabled(),
                    DashboardHealthUrl = _dashboardManager.GetHealthUrl(),
                    DashboardManuallyOverridden = _dashboardManager.IsManuallyStarted || _dashboardManager.IsManuallyStopped,
                    DashboardTotalStarts = _dashboardManager.TotalStarts,
                    DashboardTotalRestarts = _dashboardManager.TotalRestarts,
                    DashboardUnexpectedCrashes = _dashboardManager.UnexpectedCrashes,
                    DashboardLastSuccessfulLaunch = _dashboardManager.LastSuccessfulLaunch,
                    DashboardLastSuccessfulShutdown = _dashboardManager.LastSuccessfulShutdown,
                    DashboardConsecutiveFailureCount = _dashboardManager.ConsecutiveFailureCount,
                    DashboardWorkingDirectory = _dashboardManager.GetWorkingDirectory(),
                    DashboardStartupCommand = _dashboardManager.GetStartupCommand()
                };
            }
        }

        public static string GetStateString(LauncherState state)
        {
            return state switch
            {
                LauncherState.Idle => "Monitoring (Minecraft not running)",
                LauncherState.Starting => "Starting services...",
                LauncherState.RunningManaged => "Running (Managed services active)",
                LauncherState.RunningAttached => "Running (Attached to pre-existing services)",
                LauncherState.Error => "Error (Services failed/crashed)",
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

        public static string GetServiceStateString(ServiceState state, bool autoStart, bool manuallyStopped)
        {
            if (manuallyStopped)
            {
                return "Stopped (Manual Override)";
            }
            return state switch
            {
                ServiceState.Stopped => autoStart ? "Stopped" : "Stopped (Auto-Start Disabled)",
                ServiceState.Starting => "Starting...",
                ServiceState.RunningManaged => "Healthy (Managed)",
                ServiceState.RunningAttached => "Healthy (Attached)",
                ServiceState.Error => "Error / Failed",
                _ => "Unknown"
            };
        }

        public static Color GetServiceStateColor(ServiceState state)
        {
            return state switch
            {
                ServiceState.Stopped => Color.FromArgb(156, 163, 175),   // Gray
                ServiceState.Starting => Color.FromArgb(245, 158, 11),  // Amber
                ServiceState.RunningManaged => Color.FromArgb(16, 185, 129), // Emerald
                ServiceState.RunningAttached => Color.FromArgb(16, 185, 129), // Emerald
                ServiceState.Error => Color.FromArgb(239, 68, 68),      // Crimson
                _ => Color.Gray
            };
        }

        private LauncherState DetermineGlobalState()
        {
            if (!_minecraftRunning)
            {
                return LauncherState.Idle;
            }

            if (_backendManager.State == ServiceState.Error || _dashboardManager.State == ServiceState.Error)
            {
                return LauncherState.Error;
            }

            if (_backendManager.State == ServiceState.Starting || _dashboardManager.State == ServiceState.Starting)
            {
                return LauncherState.Starting;
            }

            if (_backendManager.State == ServiceState.RunningManaged || _dashboardManager.State == ServiceState.RunningManaged)
            {
                return LauncherState.RunningManaged;
            }

            if (_backendManager.State == ServiceState.RunningAttached || _dashboardManager.State == ServiceState.RunningAttached)
            {
                return LauncherState.RunningAttached;
            }

            return LauncherState.Idle;
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
                
                int pollInterval = _config.PollIntervalMs > 0 ? _config.PollIntervalMs : 2000;
                await Task.Delay(pollInterval, cancellationToken);
            }
        }

        private async Task TickMonitoringAsync()
        {
            // 1. Detect Minecraft
            var (mcRunning, mcPid) = DetectMinecraftProcess();
            
            string requestId = GenerateRequestId();
            bool mcTransitionedToRunning = mcRunning && !_minecraftRunning;
            bool mcTransitionedToStopped = !mcRunning && _minecraftRunning;

            if (mcTransitionedToRunning)
            {
                LogInfo(requestId, $"Minecraft client launch detected (PID: {mcPid}). Resetting manual overrides.");
                _backendManager.IsManuallyStarted = false;
                _backendManager.IsManuallyStopped = false;
                _dashboardManager.IsManuallyStarted = false;
                _dashboardManager.IsManuallyStopped = false;
            }

            if (mcTransitionedToStopped)
            {
                LogInfo(requestId, "Minecraft client exit detected. Cleaning up managed services.");
                _backendManager.Stop(requestId);
                _dashboardManager.Stop(requestId);

                _backendManager.IsManuallyStarted = false;
                _backendManager.IsManuallyStopped = false;
                _dashboardManager.IsManuallyStarted = false;
                _dashboardManager.IsManuallyStopped = false;
            }

            lock (_stateLock)
            {
                _minecraftRunning = mcRunning;
                _minecraftPid = mcPid;
                
                // Load config changes if config file was modified
                LoadConfig();
            }

            // 2. Tick managers
            await _backendManager.TickAsync(mcRunning, requestId);
            await _dashboardManager.TickAsync(mcRunning, requestId);

            // 3. Update global state and tray icon
            lock (_stateLock)
            {
                var globalState = DetermineGlobalState();
                if (globalState != _state)
                {
                    TransitionTo(globalState);
                }
            }
        }

        private void TransitionTo(LauncherState newState)
        {
            _state = newState;
            UpdateTrayIcon(newState);
            
            string statusMsg = GetStateString(newState);
            if (_notifyIcon != null)
            {
                _notifyIcon.Text = $"Minecraft AI Launcher: {statusMsg}";
            }
        }

        // Manual controls delegates
        public void StartBackend() => _backendManager.Start(GenerateRequestId());
        public void StopBackendManual() => _backendManager.Stop(GenerateRequestId());
        public void RestartBackendManual() => _backendManager.Restart(GenerateRequestId());

        public void StartDashboard() => _dashboardManager.Start(GenerateRequestId());
        public void StopDashboardManual() => _dashboardManager.Stop(GenerateRequestId());
        public void RestartDashboardManual() => _dashboardManager.Restart(GenerateRequestId());

        private string GenerateRequestId()
        {
            return $"Req-{Guid.NewGuid().ToString("N").Substring(0, 8).ToUpper()}";
        }

        private (bool isRunning, int pid) DetectMinecraftProcess()
        {
            try
            {
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
                        // Ignore
                    }
                }
            }
            catch
            {
                // Ignore
            }
            return (false, 0);
        }

        private bool IsMinecraftCommandLine(string cmdLine)
        {
            if (string.IsNullOrEmpty(cmdLine)) return false;

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

        public void LogInfo(string message) => Log("INFO", "", message);
        public void LogWarning(string message) => Log("WARN", "", message);
        public void LogError(string message) => Log("ERROR", "", message);

        public void LogInfo(string requestId, string message) => Log("INFO", requestId, message);
        public void LogWarning(string requestId, string message) => Log("WARN", requestId, message);
        public void LogError(string requestId, string message) => Log("ERROR", requestId, message);

        private void Log(string level, string requestId, string message)
        {
            var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
            var reqPart = string.IsNullOrEmpty(requestId) ? "" : $" [{requestId}]";
            var logLine = $"[{timestamp}] [{level}]{reqPart} {message}";

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
            if (MessageBox.Show("Are you sure you want to exit the Minecraft AI Companion Launcher? This will close all managed services.", 
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
                
                string cleanupReq = "Req-CLEANUP";
                _backendManager?.Stop(cleanupReq);
                _dashboardManager?.Stop(cleanupReq);
                
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