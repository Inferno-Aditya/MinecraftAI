using System;
using System.Drawing;
using System.Windows.Forms;

namespace MinecraftBackendLauncher
{
    public class DashboardForm : Form
    {
        private readonly LauncherApplicationContext _context;
        private readonly System.Windows.Forms.Timer _updateTimer;
        private readonly ToolTip _toolTip;

        // Tab Control
        private TabControl _tabControl = null!;
        private TabPage _tabStatus = null!;
        private TabPage _tabDiagnostics = null!;

        // General Status Labels (Status Tab)
        private Label _lblMinecraft = null!;
        private Label _lblLauncherUptime = null!;

        // Python Backend Status (Status Tab)
        private Label _lblBackendStatus = null!;
        private Label _lblBackendPid = null!;
        private Label _lblBackendUptime = null!;
        private Label _lblBackendMode = null!;
        private Label _lblBackendHealth = null!;
        private Label _lblBackendUrl = null!;
        private Label _lblBackendRestarts = null!;
        private Label _lblBackendLastRestart = null!;
        private Label _lblBackendLastHealthCheck = null!;

        private Button _btnBackendStart = null!;
        private Button _btnBackendStop = null!;
        private Button _btnBackendRestart = null!;

        // Dashboard Status (Status Tab)
        private Label _lblDashboardStatus = null!;
        private Label _lblDashboardPid = null!;
        private Label _lblDashboardUptime = null!;
        private Label _lblDashboardMode = null!;
        private Label _lblDashboardHealth = null!;
        private Label _lblDashboardUrl = null!;
        private Label _lblDashboardRestarts = null!;
        private Label _lblDashboardLastRestart = null!;
        private Label _lblDashboardLastHealthCheck = null!;

        private Button _btnDashboardStart = null!;
        private Button _btnDashboardStop = null!;
        private Button _btnDashboardRestart = null!;

        // Developer Diagnostics - Backend (Diagnostics Tab)
        private Label _lblDevBackendMode = null!;
        private Label _lblDevBackendHealthUrl = null!;
        private Label _lblDevBackendCommand = null!;
        private Label _lblDevBackendDir = null!;
        private Label _lblDevBackendStarts = null!;
        private Label _lblDevBackendRestarts = null!;
        private Label _lblDevBackendCrashes = null!;
        private Label _lblDevBackendConsecutiveFailures = null!;
        private Label _lblDevBackendLastLaunch = null!;
        private Label _lblDevBackendLastShutdown = null!;

        // Developer Diagnostics - Dashboard (Diagnostics Tab)
        private Label _lblDevDashboardMode = null!;
        private Label _lblDevDashboardHealthUrl = null!;
        private Label _lblDevDashboardCommand = null!;
        private Label _lblDevDashboardDir = null!;
        private Label _lblDevDashboardStarts = null!;
        private Label _lblDevDashboardRestarts = null!;
        private Label _lblDevDashboardCrashes = null!;
        private Label _lblDevDashboardConsecutiveFailures = null!;
        private Label _lblDevDashboardLastLaunch = null!;
        private Label _lblDevDashboardLastShutdown = null!;

        // General Buttons (Footer)
        private Button _btnViewLogs = null!;
        private Button _btnOpenConfig = null!;
        private Button _btnClose = null!;

        public DashboardForm(LauncherApplicationContext context)
        {
            _context = context;
            _toolTip = new ToolTip { AutoPopDelay = 10000, InitialDelay = 500, ReshowDelay = 200 };

            // Form properties
            this.Text = "Minecraft AI Companion - Status Dashboard";
            this.Size = new Size(740, 630);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MaximizeBox = false;
            this.MinimizeBox = true;
            this.ShowInTaskbar = true;
            this.BackColor = Color.FromArgb(17, 24, 39); // Tailwind Gray-900
            this.ForeColor = Color.White;

            InitializeComponents();

            // Setup timer to refresh UI
            _updateTimer = new System.Windows.Forms.Timer();
            _updateTimer.Interval = 1000;
            _updateTimer.Tick += (s, e) => UpdateMetrics();
            _updateTimer.Start();

            // Initial update
            UpdateMetrics();
        }

        private void InitializeComponents()
        {
            // Title Header Panel
            Panel pnlHeader = new Panel
            {
                Size = new Size(this.ClientSize.Width, 60),
                Location = new Point(0, 0),
                BackColor = Color.FromArgb(31, 41, 55) // Tailwind Gray-800
            };
            this.Controls.Add(pnlHeader);

            Label lblHeaderTitle = new Label
            {
                Text = "Minecraft AI Companion Controller",
                Font = new Font("Segoe UI", 13, FontStyle.Bold),
                ForeColor = Color.White,
                AutoSize = true,
                Location = new Point(15, 17)
            };
            pnlHeader.Controls.Add(lblHeaderTitle);

            // Tab Control
            _tabControl = new TabControl
            {
                Location = new Point(15, 75),
                Size = new Size(this.ClientSize.Width - 30, 460),
                Font = new Font("Segoe UI", 9, FontStyle.Regular)
            };
            this.Controls.Add(_tabControl);

            // Tab 1: Status Dashboard
            _tabStatus = new TabPage("Status Dashboard");
            _tabControl.TabPages.Add(_tabStatus);

            Panel pnlStatusTab = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.FromArgb(24, 28, 36)
            };
            _tabStatus.Controls.Add(pnlStatusTab);

            // Minecraft Client Status Bar
            Panel pnlMinecraftBar = new Panel
            {
                Location = new Point(15, 15),
                Size = new Size(pnlStatusTab.ClientSize.Width - 30, 45),
                BackColor = Color.FromArgb(31, 41, 55)
            };
            pnlStatusTab.Controls.Add(pnlMinecraftBar);

            _lblMinecraft = new Label
            {
                Text = "Minecraft Client: Detecting...",
                Location = new Point(15, 13),
                Size = new Size(300, 20),
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.White
            };
            pnlMinecraftBar.Controls.Add(_lblMinecraft);

            _lblLauncherUptime = new Label
            {
                Text = "Launcher Uptime: 00:00:00",
                Location = new Point(pnlMinecraftBar.Width - 250, 13),
                Size = new Size(235, 20),
                TextAlign = ContentAlignment.MiddleRight,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(156, 163, 175)
            };
            pnlMinecraftBar.Controls.Add(_lblLauncherUptime);

            // Group panel for Python Backend
            GroupBox grpBackend = new GroupBox
            {
                Text = "Python Backend Service",
                Location = new Point(15, 75),
                Size = new Size(325, 350),
                ForeColor = Color.FromArgb(156, 163, 175),
                Font = new Font("Segoe UI", 9, FontStyle.Bold)
            };
            pnlStatusTab.Controls.Add(grpBackend);

            // Group panel for Dashboard
            GroupBox grpDashboard = new GroupBox
            {
                Text = "AI Dashboard Service",
                Location = new Point(355, 75),
                Size = new Size(325, 350),
                ForeColor = Color.FromArgb(156, 163, 175),
                Font = new Font("Segoe UI", 9, FontStyle.Bold)
            };
            pnlStatusTab.Controls.Add(grpDashboard);

            // Populate symmetrical rows
            int startY = 28;
            int spacingY = 25;

            void AddRow(GroupBox grp, string title, ref Label valLabel, int index)
            {
                int y = startY + (index * spacingY);
                Label titleLabel = new Label
                {
                    Text = title,
                    Location = new Point(12, y),
                    Size = new Size(115, 18),
                    ForeColor = Color.FromArgb(156, 163, 175),
                    Font = new Font("Segoe UI", 8.5f, FontStyle.Bold)
                };
                grp.Controls.Add(titleLabel);

                valLabel = new Label
                {
                    Text = "Loading...",
                    Location = new Point(130, y),
                    Size = new Size(185, 18),
                    ForeColor = Color.White,
                    Font = new Font("Segoe UI", 8.5f, FontStyle.Regular)
                };
                grp.Controls.Add(valLabel);
            }

            // Backend Rows
            AddRow(grpBackend, "Status:", ref _lblBackendStatus, 0);
            AddRow(grpBackend, "PID:", ref _lblBackendPid, 1);
            AddRow(grpBackend, "Uptime:", ref _lblBackendUptime, 2);
            AddRow(grpBackend, "Lifecycle Mode:", ref _lblBackendMode, 3);
            AddRow(grpBackend, "Health Status:", ref _lblBackendHealth, 4);
            AddRow(grpBackend, "Health Endpoint:", ref _lblBackendUrl, 5);
            AddRow(grpBackend, "Restart Count:", ref _lblBackendRestarts, 6);
            AddRow(grpBackend, "Last Restart:", ref _lblBackendLastRestart, 7);
            AddRow(grpBackend, "Last Health Check:", ref _lblBackendLastHealthCheck, 8);

            // Dashboard Rows
            AddRow(grpDashboard, "Status:", ref _lblDashboardStatus, 0);
            AddRow(grpDashboard, "PID:", ref _lblDashboardPid, 1);
            AddRow(grpDashboard, "Uptime:", ref _lblDashboardUptime, 2);
            AddRow(grpDashboard, "Lifecycle Mode:", ref _lblDashboardMode, 3);
            AddRow(grpDashboard, "Health Status:", ref _lblDashboardHealth, 4);
            AddRow(grpDashboard, "Health Endpoint:", ref _lblDashboardUrl, 5);
            AddRow(grpDashboard, "Restart Count:", ref _lblDashboardRestarts, 6);
            AddRow(grpDashboard, "Last Restart:", ref _lblDashboardLastRestart, 7);
            AddRow(grpDashboard, "Last Health Check:", ref _lblDashboardLastHealthCheck, 8);

            // Symmetrical Buttons for Backend
            _btnBackendStart = new Button
            {
                Text = "Start",
                Location = new Point(12, 305),
                Size = new Size(85, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(16, 185, 129),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnBackendStart.FlatAppearance.BorderSize = 0;
            _btnBackendStart.Click += (s, e) => _context.StartBackend();
            grpBackend.Controls.Add(_btnBackendStart);

            _btnBackendStop = new Button
            {
                Text = "Stop",
                Location = new Point(107, 305),
                Size = new Size(85, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(239, 68, 68),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnBackendStop.FlatAppearance.BorderSize = 0;
            _btnBackendStop.Click += (s, e) => _context.StopBackendManual();
            grpBackend.Controls.Add(_btnBackendStop);

            _btnBackendRestart = new Button
            {
                Text = "Restart",
                Location = new Point(202, 305),
                Size = new Size(110, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(59, 130, 246),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnBackendRestart.FlatAppearance.BorderSize = 0;
            _btnBackendRestart.Click += (s, e) => _context.RestartBackendManual();
            grpBackend.Controls.Add(_btnBackendRestart);

            // Symmetrical Buttons for Dashboard
            _btnDashboardStart = new Button
            {
                Text = "Start",
                Location = new Point(12, 305),
                Size = new Size(85, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(16, 185, 129),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnDashboardStart.FlatAppearance.BorderSize = 0;
            _btnDashboardStart.Click += (s, e) => _context.StartDashboard();
            grpDashboard.Controls.Add(_btnDashboardStart);

            _btnDashboardStop = new Button
            {
                Text = "Stop",
                Location = new Point(107, 305),
                Size = new Size(85, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(239, 68, 68),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnDashboardStop.FlatAppearance.BorderSize = 0;
            _btnDashboardStop.Click += (s, e) => _context.StopDashboardManual();
            grpDashboard.Controls.Add(_btnDashboardStop);

            _btnDashboardRestart = new Button
            {
                Text = "Restart",
                Location = new Point(202, 305),
                Size = new Size(110, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(59, 130, 246),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnDashboardRestart.FlatAppearance.BorderSize = 0;
            _btnDashboardRestart.Click += (s, e) => _context.RestartDashboardManual();
            grpDashboard.Controls.Add(_btnDashboardRestart);

            // Tab 2: Developer Diagnostics
            _tabDiagnostics = new TabPage("Developer Diagnostics");
            _tabControl.TabPages.Add(_tabDiagnostics);

            Panel pnlDiagTab = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.FromArgb(24, 28, 36)
            };
            _tabDiagnostics.Controls.Add(pnlDiagTab);

            // Backend Diag Group
            GroupBox grpDevBackend = new GroupBox
            {
                Text = "Backend Service Diagnostics",
                Location = new Point(15, 15),
                Size = new Size(325, 410),
                ForeColor = Color.FromArgb(156, 163, 175),
                Font = new Font("Segoe UI", 9, FontStyle.Bold)
            };
            pnlDiagTab.Controls.Add(grpDevBackend);

            // Dashboard Diag Group
            GroupBox grpDevDashboard = new GroupBox
            {
                Text = "Dashboard Service Diagnostics",
                Location = new Point(355, 15),
                Size = new Size(325, 410),
                ForeColor = Color.FromArgb(156, 163, 175),
                Font = new Font("Segoe UI", 9, FontStyle.Bold)
            };
            pnlDiagTab.Controls.Add(grpDevDashboard);

            // Populate Diag Rows
            void AddDiagRow(GroupBox grp, string title, ref Label valLabel, int index)
            {
                int y = 28 + (index * 36);
                Label titleLabel = new Label
                {
                    Text = title,
                    Location = new Point(12, y),
                    Size = new Size(115, 18),
                    ForeColor = Color.FromArgb(156, 163, 175),
                    Font = new Font("Segoe UI", 8.5f, FontStyle.Bold)
                };
                grp.Controls.Add(titleLabel);

                valLabel = new Label
                {
                    Text = "Loading...",
                    Location = new Point(130, y),
                    Size = new Size(185, 18),
                    ForeColor = Color.White,
                    Font = new Font("Segoe UI", 8.5f, FontStyle.Regular)
                };
                grp.Controls.Add(valLabel);
            }

            // Backend Diag Rows (10 rows)
            AddDiagRow(grpDevBackend, "Mode:", ref _lblDevBackendMode, 0);
            AddDiagRow(grpDevBackend, "Health Endpoint:", ref _lblDevBackendHealthUrl, 1);
            AddDiagRow(grpDevBackend, "Startup Cmd:", ref _lblDevBackendCommand, 2);
            AddDiagRow(grpDevBackend, "Working Dir:", ref _lblDevBackendDir, 3);
            AddDiagRow(grpDevBackend, "Total Starts:", ref _lblDevBackendStarts, 4);
            AddDiagRow(grpDevBackend, "Total Restarts:", ref _lblDevBackendRestarts, 5);
            AddDiagRow(grpDevBackend, "Unexpected Crashes:", ref _lblDevBackendCrashes, 6);
            AddDiagRow(grpDevBackend, "Consecutive Fails:", ref _lblDevBackendConsecutiveFailures, 7);
            AddDiagRow(grpDevBackend, "Last Launch:", ref _lblDevBackendLastLaunch, 8);
            AddDiagRow(grpDevBackend, "Last Shutdown:", ref _lblDevBackendLastShutdown, 9);

            // Dashboard Diag Rows (10 rows)
            AddDiagRow(grpDevDashboard, "Mode:", ref _lblDevDashboardMode, 0);
            AddDiagRow(grpDevDashboard, "Health Endpoint:", ref _lblDevDashboardHealthUrl, 1);
            AddDiagRow(grpDevDashboard, "Startup Cmd:", ref _lblDevDashboardCommand, 2);
            AddDiagRow(grpDevDashboard, "Working Dir:", ref _lblDevDashboardDir, 3);
            AddDiagRow(grpDevDashboard, "Total Starts:", ref _lblDevDashboardStarts, 4);
            AddDiagRow(grpDevDashboard, "Total Restarts:", ref _lblDevDashboardRestarts, 5);
            AddDiagRow(grpDevDashboard, "Unexpected Crashes:", ref _lblDevDashboardCrashes, 6);
            AddDiagRow(grpDevDashboard, "Consecutive Fails:", ref _lblDevDashboardConsecutiveFailures, 7);
            AddDiagRow(grpDevDashboard, "Last Launch:", ref _lblDevDashboardLastLaunch, 8);
            AddDiagRow(grpDevDashboard, "Last Shutdown:", ref _lblDevDashboardLastShutdown, 9);

            // General Footer Buttons (outside tab control)
            _btnViewLogs = new Button
            {
                Text = "View Launcher Log",
                Location = new Point(15, 545),
                Size = new Size(140, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(75, 85, 99),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnViewLogs.FlatAppearance.BorderSize = 0;
            _btnViewLogs.Click += (s, e) => _context.OpenLogFile();
            this.Controls.Add(_btnViewLogs);

            _btnOpenConfig = new Button
            {
                Text = "Edit Configuration",
                Location = new Point(165, 545),
                Size = new Size(150, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(55, 65, 81),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnOpenConfig.FlatAppearance.BorderSize = 0;
            _btnOpenConfig.Click += (s, e) => {
                try
                {
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher_config.json"),
                        UseShellExecute = true
                    });
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Failed to open config file: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            };
            this.Controls.Add(_btnOpenConfig);

            _btnClose = new Button
            {
                Text = "Close Dashboard",
                Location = new Point(this.ClientSize.Width - 145, 545),
                Size = new Size(130, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(239, 68, 68),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnClose.FlatAppearance.BorderSize = 0;
            _btnClose.Click += (s, e) => this.Hide();
            this.Controls.Add(_btnClose);
        }

        private void UpdateMetrics()
        {
            var metrics = _context.GetMetrics();

            // Minecraft Client Status
            _lblMinecraft.Text = metrics.MinecraftRunning 
                ? $"Minecraft Client: Running (PID: {metrics.MinecraftPid})" 
                : "Minecraft Client: Not Running";
            _lblMinecraft.ForeColor = metrics.MinecraftRunning ? Color.FromArgb(16, 185, 129) : Color.FromArgb(239, 68, 68);

            // Launcher Uptime
            var launcherUptime = DateTime.Now - metrics.LauncherUptimeStart;
            _lblLauncherUptime.Text = $"Launcher Uptime: {FormatTimeSpan(launcherUptime)}";

            // Update Symmetrical Service Cards (Tab 1)
            UpdateServiceCard(metrics.BackendState, metrics.BackendStateString, metrics.BackendStateColor, metrics.BackendPid,
                metrics.BackendUptimeStart, metrics.BackendManuallyOverridden, metrics.BackendHealthCheckResult, metrics.BackendHealthUrl,
                metrics.BackendRestartAttempts, metrics.BackendMaxRestartAttempts, metrics.BackendLastSuccessfulLaunch, metrics.BackendLastHealthyCheck,
                _lblBackendStatus, _lblBackendPid, _lblBackendUptime, _lblBackendMode, _lblBackendHealth, _lblBackendUrl,
                _lblBackendRestarts, _lblBackendLastRestart, _lblBackendLastHealthCheck,
                _btnBackendStart, _btnBackendStop, _btnBackendRestart);

            UpdateServiceCard(metrics.DashboardState, metrics.DashboardStateString, metrics.DashboardStateColor, metrics.DashboardPid,
                metrics.DashboardUptimeStart, metrics.DashboardManuallyOverridden, metrics.DashboardHealthCheckResult, metrics.DashboardHealthUrl,
                metrics.DashboardRestartAttempts, metrics.DashboardMaxRestartAttempts, metrics.DashboardLastSuccessfulLaunch, metrics.DashboardLastHealthyCheck,
                _lblDashboardStatus, _lblDashboardPid, _lblDashboardUptime, _lblDashboardMode, _lblDashboardHealth, _lblDashboardUrl,
                _lblDashboardRestarts, _lblDashboardLastRestart, _lblDashboardLastHealthCheck,
                _btnDashboardStart, _btnDashboardStop, _btnDashboardRestart);

            // Update Developer Diagnostics (Tab 2)
            UpdateDeveloperDiagnostics(
                metrics.BackendState, metrics.BackendHealthUrl, metrics.BackendStartupCommand, metrics.BackendWorkingDirectory,
                metrics.BackendTotalStarts, metrics.BackendTotalRestarts, metrics.BackendUnexpectedCrashes, metrics.BackendConsecutiveFailureCount,
                metrics.BackendLastSuccessfulLaunch, metrics.BackendLastSuccessfulShutdown,
                _lblDevBackendMode, _lblDevBackendHealthUrl, _lblDevBackendCommand, _lblDevBackendDir,
                _lblDevBackendStarts, _lblDevBackendRestarts, _lblDevBackendCrashes, _lblDevBackendConsecutiveFailures,
                _lblDevBackendLastLaunch, _lblDevBackendLastShutdown
            );

            UpdateDeveloperDiagnostics(
                metrics.DashboardState, metrics.DashboardHealthUrl, metrics.DashboardStartupCommand, metrics.DashboardWorkingDirectory,
                metrics.DashboardTotalStarts, metrics.DashboardTotalRestarts, metrics.DashboardUnexpectedCrashes, metrics.DashboardConsecutiveFailureCount,
                metrics.DashboardLastSuccessfulLaunch, metrics.DashboardLastSuccessfulShutdown,
                _lblDevDashboardMode, _lblDevDashboardHealthUrl, _lblDevDashboardCommand, _lblDevDashboardDir,
                _lblDevDashboardStarts, _lblDevDashboardRestarts, _lblDevDashboardCrashes, _lblDevDashboardConsecutiveFailures,
                _lblDevDashboardLastLaunch, _lblDevDashboardLastShutdown
            );
        }

        private void UpdateServiceCard(
            ServiceState state, string stateStr, Color stateColor, int? pid, DateTime? uptimeStart,
            bool overridden, bool healthResult, string healthUrl, int restarts, int maxRestarts, DateTime? lastRestart, DateTime? lastHealthy,
            Label lblStatus, Label lblPid, Label lblUptime, Label lblMode, Label lblHealth, Label lblUrl, Label lblRestarts, Label lblLastRestart, Label lblLastHealthCheck,
            Button btnStart, Button btnStop, Button btnRestart)
        {
            lblStatus.Text = stateStr;
            lblStatus.ForeColor = stateColor;

            lblPid.Text = pid.HasValue ? pid.Value.ToString() : "N/A";
            lblPid.ForeColor = pid.HasValue ? Color.White : Color.FromArgb(156, 163, 175);

            lblUptime.Text = uptimeStart.HasValue ? FormatTimeSpan(DateTime.Now - uptimeStart.Value) : "N/A";

            lblMode.Text = overridden ? "Manual Override" : "Auto Managed";
            lblMode.ForeColor = overridden ? Color.FromArgb(59, 130, 246) : Color.FromArgb(16, 185, 129); // Blue for manual, green for auto

            lblHealth.Text = healthResult ? "Healthy" : "Offline / Unhealthy";
            lblHealth.ForeColor = healthResult ? Color.FromArgb(16, 185, 129) : Color.FromArgb(239, 68, 68);

            lblUrl.Text = healthUrl;
            _toolTip.SetToolTip(lblUrl, healthUrl);

            lblRestarts.Text = $"{restarts} / {maxRestarts}";

            lblLastRestart.Text = lastRestart.HasValue ? lastRestart.Value.ToString("HH:mm:ss") : "Never";
            lblLastHealthCheck.Text = lastHealthy.HasValue ? lastHealthy.Value.ToString("HH:mm:ss") : "Never";

            // Enable/disable buttons based on active running state
            bool isRunningOrStarting = state == ServiceState.RunningManaged ||
                                       state == ServiceState.RunningAttached ||
                                       state == ServiceState.Starting;

            btnStart.Enabled = !isRunningOrStarting;
            btnStart.BackColor = !isRunningOrStarting ? Color.FromArgb(16, 185, 129) : Color.FromArgb(75, 85, 99);

            btnStop.Enabled = isRunningOrStarting;
            btnStop.BackColor = isRunningOrStarting ? Color.FromArgb(239, 68, 68) : Color.FromArgb(75, 85, 99);

            btnRestart.Enabled = isRunningOrStarting;
            btnRestart.BackColor = isRunningOrStarting ? Color.FromArgb(59, 130, 246) : Color.FromArgb(75, 85, 99);
        }

        private void UpdateDeveloperDiagnostics(
            ServiceState state, string url, string cmd, string dir,
            int starts, int restarts, int crashes, int fails, DateTime? lastLaunch, DateTime? lastShutdown,
            Label lblMode, Label lblUrl, Label lblCmd, Label lblDir,
            Label lblStarts, Label lblRestarts, Label lblCrashes, Label lblFails, Label lblLastLaunch, Label lblLastShutdown)
        {
            lblMode.Text = state == ServiceState.RunningAttached ? "Attached Mode" : "Managed Mode";
            lblMode.ForeColor = state == ServiceState.RunningAttached ? Color.FromArgb(245, 158, 11) : Color.FromArgb(16, 185, 129);

            lblUrl.Text = url;
            _toolTip.SetToolTip(lblUrl, url);

            lblCmd.Text = cmd;
            _toolTip.SetToolTip(lblCmd, cmd);

            lblDir.Text = dir;
            _toolTip.SetToolTip(lblDir, dir);

            lblStarts.Text = starts.ToString();
            lblRestarts.Text = restarts.ToString();
            lblCrashes.Text = crashes.ToString();
            lblFails.Text = fails.ToString();

            lblLastLaunch.Text = lastLaunch.HasValue ? lastLaunch.Value.ToString("yyyy-MM-dd HH:mm:ss") : "Never";
            lblLastShutdown.Text = lastShutdown.HasValue ? lastShutdown.Value.ToString("yyyy-MM-dd HH:mm:ss") : "Never";
        }

        private string FormatTimeSpan(TimeSpan ts)
        {
            return $"{(int)ts.TotalHours:D2}:{ts.Minutes:D2}:{ts.Seconds:D2}";
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            // Hide rather than close to keep it in system tray
            if (e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                this.Hide();
            }
            base.OnFormClosing(e);
        }
    }
}
