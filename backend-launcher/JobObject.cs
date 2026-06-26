using System;
using System.Runtime.InteropServices;
using System.Diagnostics;

namespace MinecraftBackendLauncher
{
    public static class JobObject
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? lpName);

        [DllImport("kernel32.dll")]
        private static extern bool SetInformationJobObject(IntPtr hJob, JobObjectInfoType infoType, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

        [DllImport("kernel32.dll")]
        private static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr hObject);

        private static IntPtr _jobHandle;

        static JobObject()
        {
            try
            {
                _jobHandle = CreateJobObject(IntPtr.Zero, null);
                if (_jobHandle == IntPtr.Zero)
                {
                    return;
                }

                var info = new JOBOBJECT_BASIC_LIMIT_INFORMATION
                {
                    LimitFlags = LimitFlags.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                };

                var extendedInfo = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION
                {
                    BasicLimitInformation = info
                };

                int length = Marshal.SizeOf(extendedInfo);
                IntPtr extendedInfoPtr = Marshal.AllocHGlobal(length);
                try
                {
                    Marshal.StructureToPtr(extendedInfo, extendedInfoPtr, false);
                    if (!SetInformationJobObject(_jobHandle, JobObjectInfoType.ExtendedLimitInformation, extendedInfoPtr, (uint)length))
                    {
                        CloseHandle(_jobHandle);
                        _jobHandle = IntPtr.Zero;
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(extendedInfoPtr);
                }
            }
            catch
            {
                _jobHandle = IntPtr.Zero;
            }
        }

        public static void AssociateProcess(Process process)
        {
            if (_jobHandle != IntPtr.Zero && process != null && !process.HasExited)
            {
                try
                {
                    AssignProcessToJobObject(_jobHandle, process.Handle);
                }
                catch
                {
                    // Ignore failures (e.g. process already exited or permission issues)
                }
            }
        }
        
        public static void CleanUp()
        {
            if (_jobHandle != IntPtr.Zero)
            {
                CloseHandle(_jobHandle);
                _jobHandle = IntPtr.Zero;
            }
        }

        #region Structures and Enums
        private enum JobObjectInfoType
        {
            AssociateCompletionPortInformation = 7,
            BasicLimitInformation = 2,
            BasicUuiInformation = 1,
            CpuRateControlInformation = 15,
            EndOfJobTimeInformation = 6,
            ExtendedLimitInformation = 9,
            GroupInformation = 11,
            GroupInformationEx = 14,
            LimitViolationInformation = 13,
            Name = 10,
            NotificationLimitInformation = 12,
            SecurityLimitInformation = 5,
            UiRestrictionsInformation = 4
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public Int64 PerProcessUserTimeLimit;
            public Int64 PerJobUserTimeLimit;
            public LimitFlags LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public UInt32 ActiveProcessLimit;
            public Int64 Affinity;
            public UInt32 PriorityClass;
            public UInt32 SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct IO_COUNTERS
        {
            public UInt64 ReadOperationCount;
            public UInt64 WriteOperationCount;
            public UInt64 OtherOperationCount;
            public UInt64 ReadTransferCount;
            public UInt64 WriteTransferCount;
            public UInt64 OtherTransferCount;
        }

        [Flags]
        private enum LimitFlags : uint
        {
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        }
        #endregion
    }
}
