using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace MinecraftBackendLauncher
{
    public enum ServiceState
    {
        Stopped,
        Starting,
        RunningManaged,
        RunningAttached,
        Error
    }

    public abstract class ServiceManager
    {
        protected readonly LauncherApplicationContext Context;
        protected readonly HttpClient HttpClient;
        protected readonly object Lock = new object();

        // Core properties
        public string ServiceName { get; }
        public ServiceState State { get; protected set; } = ServiceState.Stopped;
        public int? ProcessId { get; protected set; }
        public DateTime? UptimeStart { get; protected set; }
        public List<string> DependsOn { get; } = new List<string>();

        // Statistics
        public int TotalStarts { get; protected set; }
        public int TotalRestarts { get; protected set; }
        public int UnexpectedCrashes { get; protected set; }
        public DateTime? LastSuccessfulLaunch { get; protected set; }
        public DateTime? LastSuccessfulShutdown { get; protected set; }
        public int ConsecutiveFailureCount { get; protected set; }

        // Diagnostics
        public bool LastHealthCheckResult { get; protected set; }
        public DateTime? LastHealthyCheckTime { get; protected set; }

        // Manual controls
        public bool IsManuallyStarted { get; set; }
        public bool IsManuallyStopped { get; set; }

        // Managed process references
        protected Process? ManagedProcess;
        protected DateTime SpawnTime = DateTime.MinValue;
        private bool _waitingLogTriggered = false;

        protected ServiceManager(LauncherApplicationContext context, HttpClient httpClient, string serviceName)
        {
            Context = context;
            HttpClient = httpClient;
            ServiceName = serviceName;
        }

        // Abstract interface to be implemented by services
        public abstract Task<bool> CheckHealthAsync();
        protected abstract void LaunchProcess();
        public abstract string GetHealthUrl();
        public abstract int GetMaxRestartAttempts();
        public abstract bool IsAutoStartEnabled();
        public abstract int GetStartupTimeoutSeconds();
        public abstract string GetWorkingDirectory();
        public abstract string GetStartupCommand();

        public bool AreDependenciesHealthy()
        {
            foreach (var depName in DependsOn)
            {
                var dep = Context.GetService(depName);
                if (dep == null) continue;
                if (dep.State != ServiceState.RunningManaged && dep.State != ServiceState.RunningAttached)
                {
                    return false;
                }
            }
            return true;
        }

        public virtual void Start(string requestId)
        {
            lock (Lock)
            {
                Context.LogInfo(requestId, $"Manual start triggered for {ServiceName}.");
                IsManuallyStarted = true;
                IsManuallyStopped = false;
                ConsecutiveFailureCount = 0;

                if (State == ServiceState.RunningManaged || State == ServiceState.RunningAttached)
                {
                    Context.LogInfo(requestId, $"{ServiceName} is already running. No launch needed.");
                    return;
                }

                // Check dependencies for manual start too
                if (!AreDependenciesHealthy())
                {
                    string deps = string.Join(", ", DependsOn);
                    Context.LogWarning(requestId, $"Cannot start {ServiceName} yet. Waiting for healthy dependencies: {deps}");
                    return;
                }

                LaunchProcessInternal(requestId);
            }
        }

        public virtual void Stop(string requestId)
        {
            lock (Lock)
            {
                Context.LogInfo(requestId, $"Manual stop triggered for {ServiceName}.");
                IsManuallyStopped = true;
                IsManuallyStarted = false;

                StopProcessInternal(requestId);
                State = ServiceState.Stopped;
                LastSuccessfulShutdown = DateTime.Now;
                ConsecutiveFailureCount = 0;
            }
        }

        public virtual void Restart(string requestId)
        {
            lock (Lock)
            {
                Context.LogInfo(requestId, $"Manual restart triggered for {ServiceName}.");
                IsManuallyStarted = true;
                IsManuallyStopped = false;
                ConsecutiveFailureCount = 0;

                StopProcessInternal(requestId);
                LaunchProcessInternal(requestId);
            }
        }

        protected void LaunchProcessInternal(string requestId)
        {
            try
            {
                LaunchProcess();
                TotalStarts++;
                Context.LogInfo(requestId, $"{ServiceName} launched successfully (PID: {ProcessId}).");
            }
            catch (Exception ex)
            {
                ConsecutiveFailureCount++;
                Context.LogError(requestId, $"Failed to launch {ServiceName}: {ex.Message}");
                State = ServiceState.Error;
            }
        }

        protected void StopProcessInternal(string requestId)
        {
            if (ManagedProcess != null)
            {
                try
                {
                    if (!ManagedProcess.HasExited)
                    {
                        Context.LogInfo(requestId, $"Killing {ServiceName} process tree (PID: {ManagedProcess.Id})...");
                        ManagedProcess.Kill(entireProcessTree: true);
                    }
                }
                catch (Exception ex)
                {
                    Context.LogError(requestId, $"Failed to terminate {ServiceName} process tree: {ex.Message}");
                }
                finally
                {
                    ManagedProcess.Dispose();
                    ManagedProcess = null;
                    ProcessId = null;
                    UptimeStart = null;
                }
            }
            else if (State == ServiceState.RunningAttached && ProcessId.HasValue)
            {
                try
                {
                    using (var proc = Process.GetProcessById(ProcessId.Value))
                    {
                        Context.LogInfo(requestId, $"Killing attached {ServiceName} process tree (PID: {ProcessId.Value})...");
                        proc.Kill(entireProcessTree: true);
                    }
                }
                catch (Exception ex)
                {
                    Context.LogError(requestId, $"Failed to terminate attached {ServiceName} process tree: {ex.Message}");
                }
                finally
                {
                    ProcessId = null;
                    UptimeStart = null;
                }
            }
        }

        public virtual async Task TickAsync(bool minecraftRunning, string requestId)
        {
            bool healthy = await CheckHealthAsync();

            lock (Lock)
            {
                LastHealthCheckResult = healthy;
                if (healthy)
                {
                    LastHealthyCheckTime = DateTime.Now;
                }

                // If running managed, check if process died
                if (State == ServiceState.RunningManaged)
                {
                    if (ManagedProcess == null || ManagedProcess.HasExited || !healthy)
                    {
                        UnexpectedCrashes++;
                        ConsecutiveFailureCount++;
                        Context.LogWarning(requestId, $"{ServiceName} managed process terminated or became unhealthy.");
                        StopProcessInternal(requestId);
                        HandleFailure(minecraftRunning, requestId);
                        return;
                    }
                }
                else if (State == ServiceState.RunningAttached)
                {
                    if (!healthy)
                    {
                        Context.LogWarning(requestId, $"{ServiceName} attached process went offline.");
                        ProcessId = null;
                        UptimeStart = null;

                        if (IsAutoStartEnabled() && minecraftRunning && !IsManuallyStopped)
                        {
                            if (AreDependenciesHealthy())
                            {
                                Context.LogInfo(requestId, $"AutoStart enabled and dependencies healthy. Launching managed {ServiceName}...");
                                LaunchProcessInternal(requestId);
                            }
                            else
                            {
                                State = ServiceState.Stopped;
                            }
                        }
                        else
                        {
                            State = ServiceState.Stopped;
                        }
                        return;
                    }
                }

                // State transitions
                switch (State)
                {
                    case ServiceState.Stopped:
                        if (healthy)
                        {
                            AttachToExisting(requestId);
                        }
                        else if (minecraftRunning && IsAutoStartEnabled() && !IsManuallyStopped)
                        {
                            if (AreDependenciesHealthy())
                            {
                                Context.LogInfo(requestId, $"Minecraft detected. Auto-starting {ServiceName}...");
                                LaunchProcessInternal(requestId);
                                _waitingLogTriggered = false;
                            }
                            else if (!_waitingLogTriggered)
                            {
                                string deps = string.Join(", ", DependsOn);
                                Context.LogInfo(requestId, $"Waiting to start {ServiceName}. Dependencies not healthy: {deps}");
                                _waitingLogTriggered = true;
                            }
                        }
                        break;

                    case ServiceState.Starting:
                        if (!minecraftRunning)
                        {
                            Context.LogInfo(requestId, $"Minecraft exited during {ServiceName} startup. Stopping service.");
                            StopProcessInternal(requestId);
                            State = ServiceState.Stopped;
                            LastSuccessfulShutdown = DateTime.Now;
                        }
                        else if (healthy)
                        {
                            Context.LogInfo(requestId, $"{ServiceName} health check passed. Active and healthy.");
                            UptimeStart = DateTime.Now;
                            LastSuccessfulLaunch = DateTime.Now;
                            ConsecutiveFailureCount = 0;
                            State = ServiceState.RunningManaged;
                        }
                        else
                        {
                            // Configurable Startup Timeout Check
                            int timeout = GetStartupTimeoutSeconds();
                            if ((DateTime.Now - SpawnTime).TotalSeconds > timeout)
                            {
                                ConsecutiveFailureCount++;
                                Context.LogError(requestId, $"{ServiceName} health check timed out after {timeout} seconds during startup.");
                                StopProcessInternal(requestId);
                                HandleFailure(minecraftRunning, requestId);
                            }
                        }
                        break;

                    case ServiceState.RunningManaged:
                        if (!minecraftRunning)
                        {
                            Context.LogInfo(requestId, $"Minecraft exited. Shutting down managed {ServiceName}...");
                            StopProcessInternal(requestId);
                            State = ServiceState.Stopped;
                            LastSuccessfulShutdown = DateTime.Now;
                        }
                        break;

                    case ServiceState.RunningAttached:
                        if (!minecraftRunning)
                        {
                            Context.LogInfo(requestId, $"Minecraft exited. Detaching from {ServiceName}.");
                            ProcessId = null;
                            UptimeStart = null;
                            State = ServiceState.Stopped;
                        }
                        break;

                    case ServiceState.Error:
                        if (!minecraftRunning)
                        {
                            Context.LogInfo(requestId, $"Minecraft exited. Clearing {ServiceName} error state.");
                            ConsecutiveFailureCount = 0;
                            State = ServiceState.Stopped;
                        }
                        else if (healthy)
                        {
                            AttachToExisting(requestId);
                        }
                        break;
                }
            }
        }

        private void AttachToExisting(string requestId)
        {
            int? port = GetPortFromUrl(GetHealthUrl());
            int? pid = port.HasValue ? GetPidListeningOnPort(port.Value) : null;
            if (pid.HasValue)
            {
                ProcessId = pid;
                try
                {
                    using (var proc = Process.GetProcessById(pid.Value))
                    {
                        UptimeStart = proc.StartTime;
                    }
                }
                catch
                {
                    UptimeStart = DateTime.Now;
                }
                Context.LogInfo(requestId, $"{ServiceName} detected on port {port}. Attaching to existing instance (PID: {pid}).");
            }
            else
            {
                Context.LogInfo(requestId, $"{ServiceName} detected on port {port}. Attaching to existing instance.");
                UptimeStart = DateTime.Now;
            }
            LastSuccessfulLaunch = DateTime.Now;
            ConsecutiveFailureCount = 0;
            State = ServiceState.RunningAttached;
        }

        private void HandleFailure(bool minecraftRunning, string requestId)
        {
            int maxAttempts = GetMaxRestartAttempts();
            if (minecraftRunning && ConsecutiveFailureCount <= maxAttempts && !IsManuallyStopped)
            {
                TotalRestarts++;
                Context.LogInfo(requestId, $"Attempting {ServiceName} auto-restart ({ConsecutiveFailureCount}/{maxAttempts})...");
                LaunchProcessInternal(requestId);
            }
            else
            {
                Context.LogError(requestId, $"{ServiceName} failed after {ConsecutiveFailureCount - 1} restarts or auto-start is disabled. Entering error state.");
                State = ServiceState.Error;
            }
        }

        private static int? GetPortFromUrl(string url)
        {
            try
            {
                var uri = new Uri(url);
                return uri.Port;
            }
            catch
            {
                return null;
            }
        }

        private static int? GetPidListeningOnPort(int port)
        {
            try
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = "netstat.exe",
                    Arguments = "-ano",
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (var process = Process.Start(startInfo))
                {
                    if (process != null)
                    {
                        string output = process.StandardOutput.ReadToEnd();
                        process.WaitForExit();

                        string[] lines = output.Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries);
                        foreach (var line in lines)
                        {
                            if (line.Contains("LISTENING"))
                            {
                                var parts = line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                                if (parts.Length >= 5)
                                {
                                    string localAddress = parts[1];
                                    string pidStr = parts[parts.Length - 1];

                                    int colonIndex = localAddress.LastIndexOf(':');
                                    if (colonIndex >= 0 && int.TryParse(localAddress.Substring(colonIndex + 1), out int localPort))
                                    {
                                        if (localPort == port && int.TryParse(pidStr, out int pid))
                                        {
                                            return pid;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch
            {
                // Ignore
            }
            return null;
        }
    }
}
