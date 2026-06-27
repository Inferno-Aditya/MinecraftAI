using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace MinecraftBackendLauncher
{
    public class BackendManager : ServiceManager
    {
        public BackendManager(LauncherApplicationContext context, HttpClient httpClient)
            : base(context, httpClient, "Backend")
        {
        }

        public override async Task<bool> CheckHealthAsync()
        {
            try
            {
                var config = Context.Config;
                using (var response = await HttpClient.GetAsync(config.HealthEndpoint))
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

        protected override void LaunchProcess()
        {
            var config = Context.Config;
            string pythonExe = Context.ResolvePath(config.PythonExecutable);
            string backendDir = Context.ResolvePath(config.BackendDirectory);

            if (!Directory.Exists(backendDir))
            {
                throw new DirectoryNotFoundException($"Backend directory does not exist: {backendDir}");
            }

            if (!File.Exists(pythonExe))
            {
                throw new FileNotFoundException($"Python executable does not exist: {pythonExe}");
            }

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
            return Context.Config.HealthEndpoint;
        }

        public override int GetMaxRestartAttempts()
        {
            return Context.Config.MaxRestartAttempts;
        }

        public override bool IsAutoStartEnabled()
        {
            return Context.Config.AutoStartBackend;
        }

        public override int GetStartupTimeoutSeconds()
        {
            return Context.Config.BackendStartupTimeoutSeconds > 0 
                ? Context.Config.BackendStartupTimeoutSeconds 
                : 30;
        }

        public override string GetWorkingDirectory()
        {
            return Context.ResolvePath(Context.Config.BackendDirectory);
        }

        public override string GetStartupCommand()
        {
            string pythonExe = Context.ResolvePath(Context.Config.PythonExecutable);
            return $"{pythonExe} main.py";
        }
    }
}
