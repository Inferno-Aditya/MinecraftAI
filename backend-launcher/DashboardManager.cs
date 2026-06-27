using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace MinecraftBackendLauncher
{
    public class DashboardManager : ServiceManager
    {
        public DashboardManager(LauncherApplicationContext context, HttpClient httpClient)
            : base(context, httpClient, "Dashboard")
        {
            // By default, dashboard does not strictly depend on the backend to start up,
            // but we support dependencies in the base class. We can add dependencies here if needed.
        }

        public override async Task<bool> CheckHealthAsync()
        {
            try
            {
                var config = Context.Config;
                using (var response = await HttpClient.GetAsync(config.DashboardHealthUrl))
                {
                    // For dashboard, we check if the server responds successfully
                    return response.IsSuccessStatusCode;
                }
            }
            catch
            {
                // Health check failed (server offline / unresponsive)
            }
            return false;
        }

        protected override void LaunchProcess()
        {
            var config = Context.Config;
            string workingDir = Context.ResolvePath(config.DashboardWorkingDirectory);

            if (!Directory.Exists(workingDir))
            {
                throw new DirectoryNotFoundException($"Dashboard working directory does not exist: {workingDir}");
            }

            // Execute npm dev server through cmd.exe /c to handle bat/cmd scripts on Windows correctly
            var startInfo = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = $"/c {config.DashboardCommand}",
                WorkingDirectory = workingDir,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = false,
                RedirectStandardError = false
            };

            ManagedProcess = new Process { StartInfo = startInfo };
            ManagedProcess.Start();
            SpawnTime = DateTime.Now;
            ProcessId = ManagedProcess.Id;
            State = ServiceState.Starting;

            // Associate process with Windows Job Object for automatic clean-up on exit
            JobObject.AssociateProcess(ManagedProcess);
        }

        public override string GetHealthUrl()
        {
            return Context.Config.DashboardHealthUrl;
        }

        public override int GetMaxRestartAttempts()
        {
            return Context.Config.DashboardRestartAttempts;
        }

        public override bool IsAutoStartEnabled()
        {
            return Context.Config.AutoStartDashboard;
        }

        public override int GetStartupTimeoutSeconds()
        {
            return Context.Config.DashboardStartupTimeoutSeconds > 0 
                ? Context.Config.DashboardStartupTimeoutSeconds 
                : 30;
        }

        public override string GetWorkingDirectory()
        {
            return Context.ResolvePath(Context.Config.DashboardWorkingDirectory);
        }

        public override string GetStartupCommand()
        {
            return Context.Config.DashboardCommand;
        }
    }
}
