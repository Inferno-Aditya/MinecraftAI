using System;
using System.Drawing;
using System.Windows.Forms;

namespace MinecraftBackendLauncher
{
    public class DashboardForm : Form
    {
        private readonly LauncherApplicationContext _context;
        private readonly System.Windows.Forms.Timer _updateTimer;

        // Labels
        private Label _lblState = null!;
        private Label _lblMinecraft = null!;
        private Label _lblBackend = null!;
        private Label _lblRestartAttempts = null!;
        private Label _lblLastHealthCheck = null!;
        private Label _lblLauncherUptime = null!;
        private Label _lblBackendUptime = null!;

        // Buttons
        private Button _btnRestart = null!;
        private Button _btnViewLogs = null!;
        private Button _btnClose = null!;

        public DashboardForm(LauncherApplicationContext context)
        {
            _context = context;

            // Form properties
            this.Text = "Minecraft AI Companion - Status Dashboard";
            this.Size = new Size(440, 430);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MaximizeBox = false;
            this.MinimizeBox = true;
            this.ShowInTaskbar = true;
            this.BackColor = Color.FromArgb(24, 28, 36);
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
                Size = new Size(this.ClientSize.Width, 55),
                Location = new Point(0, 0),
                BackColor = Color.FromArgb(31, 41, 55)
            };
            this.Controls.Add(pnlHeader);

            Label lblHeaderTitle = new Label
            {
                Text = "Minecraft AI Companion Launcher",
                Font = new Font("Segoe UI", 12, FontStyle.Bold),
                ForeColor = Color.White,
                AutoSize = true,
                Location = new Point(15, 16)
            };
            pnlHeader.Controls.Add(lblHeaderTitle);

            // Group panel for Status information
            GroupBox grpStatus = new GroupBox
            {
                Text = "Status Information",
                Location = new Point(15, 70),
                Size = new Size(this.ClientSize.Width - 30, 245),
                ForeColor = Color.FromArgb(156, 163, 175),
                Font = new Font("Segoe UI", 9, FontStyle.Regular)
            };
            this.Controls.Add(grpStatus);

            int startY = 28;
            int spacingY = 29;
            int labelWidth = 140;
            int valWidth = 220;

            // Helper to add label rows
            void AddRow(string title, ref Label valLabel, int index)
            {
                int y = startY + (index * spacingY);
                Label titleLabel = new Label
                {
                    Text = title,
                    Location = new Point(15, y),
                    Size = new Size(labelWidth, 20),
                    ForeColor = Color.FromArgb(156, 163, 175),
                    Font = new Font("Segoe UI", 9, FontStyle.Bold)
                };
                grpStatus.Controls.Add(titleLabel);

                valLabel = new Label
                {
                    Text = "Loading...",
                    Location = new Point(15 + labelWidth, y),
                    Size = new Size(valWidth, 20),
                    ForeColor = Color.White,
                    Font = new Font("Segoe UI", 9, FontStyle.Regular)
                };
                grpStatus.Controls.Add(valLabel);
            }

            AddRow("Launcher State:", ref _lblState, 0);
            AddRow("Minecraft Client:", ref _lblMinecraft, 1);
            AddRow("AI Backend:", ref _lblBackend, 2);
            AddRow("Restart Attempts:", ref _lblRestartAttempts, 3);
            AddRow("Last Health Check:", ref _lblLastHealthCheck, 4);
            AddRow("Launcher Uptime:", ref _lblLauncherUptime, 5);
            AddRow("Backend Uptime:", ref _lblBackendUptime, 6);

            // Buttons
            _btnRestart = new Button
            {
                Text = "Force Restart Backend",
                Location = new Point(15, 335),
                Size = new Size(150, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(59, 130, 246),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnRestart.FlatAppearance.BorderSize = 0;
            _btnRestart.Click += (s, e) => {
                _context.ForceRestartBackend();
                MessageBox.Show("Backend restart triggered.", "Information", MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
            this.Controls.Add(_btnRestart);

            _btnViewLogs = new Button
            {
                Text = "View Logs",
                Location = new Point(175, 335),
                Size = new Size(100, 32),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(75, 85, 99),
                ForeColor = Color.White,
                Cursor = Cursors.Hand
            };
            _btnViewLogs.FlatAppearance.BorderSize = 0;
            _btnViewLogs.Click += (s, e) => _context.OpenLogFile();
            this.Controls.Add(_btnViewLogs);

            _btnClose = new Button
            {
                Text = "Close",
                Location = new Point(285, 335),
                Size = new Size(100, 32),
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

            _lblState.Text = metrics.StateString;
            _lblState.ForeColor = metrics.StateColor;

            _lblMinecraft.Text = metrics.MinecraftRunning 
                ? $"Running (PID: {metrics.MinecraftPid})" 
                : "Not Running";
            _lblMinecraft.ForeColor = metrics.MinecraftRunning ? Color.FromArgb(16, 185, 129) : Color.FromArgb(239, 68, 68);

            string backendText;
            Color backendColor;
            if (metrics.State == LauncherState.RunningManaged)
            {
                backendText = $"Healthy (Managed, PID: {metrics.BackendPid})";
                backendColor = Color.FromArgb(16, 185, 129);
            }
            else if (metrics.State == LauncherState.RunningAttached)
            {
                backendText = "Healthy (Attached to Pre-existing Instance)";
                backendColor = Color.FromArgb(16, 185, 129);
            }
            else if (metrics.State == LauncherState.Starting)
            {
                backendText = "Starting / Health Checking...";
                backendColor = Color.FromArgb(245, 158, 11);
            }
            else if (metrics.State == LauncherState.Error)
            {
                backendText = "Error / Failed";
                backendColor = Color.FromArgb(239, 68, 68);
            }
            else
            {
                backendText = metrics.AutoStartBackend ? "Stopped" : "Stopped (Auto-Start Disabled)";
                backendColor = Color.FromArgb(156, 163, 175);
            }
            _lblBackend.Text = backendText;
            _lblBackend.ForeColor = backendColor;

            _lblRestartAttempts.Text = $"{metrics.RestartAttempts} / {metrics.MaxRestartAttempts}";
            _lblLastHealthCheck.Text = metrics.LastHealthyCheck.HasValue 
                ? metrics.LastHealthyCheck.Value.ToString("yyyy-MM-dd HH:mm:ss") 
                : "Never";

            // Uptime calculation
            var launcherUptime = DateTime.Now - metrics.LauncherUptimeStart;
            _lblLauncherUptime.Text = FormatTimeSpan(launcherUptime);

            if (metrics.BackendUptimeStart.HasValue)
            {
                var backendUptime = DateTime.Now - metrics.BackendUptimeStart.Value;
                _lblBackendUptime.Text = FormatTimeSpan(backendUptime);
            }
            else
            {
                _lblBackendUptime.Text = "N/A";
            }

            // Enable force restart button only if Minecraft is running
            _btnRestart.Enabled = metrics.MinecraftRunning;
            _btnRestart.BackColor = metrics.MinecraftRunning ? Color.FromArgb(59, 130, 246) : Color.FromArgb(156, 163, 175);
        }

        private string FormatTimeSpan(TimeSpan ts)
        {
            return $"{(int)ts.TotalHours:D2}:{ts.Minutes:D2}:{ts.Seconds:D2}";
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            // Intercept user clicking 'X' button to hide rather than close
            if (e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                this.Hide();
            }
            base.OnFormClosing(e);
        }
    }
}
