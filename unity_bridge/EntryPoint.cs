using System;
using System.Diagnostics;
using System.Threading.Tasks;
using UnityEngine;

namespace UnityAutomatedTester
{
    public static class EntryPoint
    {
        public static void Run()
        {
            RunAsync().GetAwaiter().GetResult();
        }

        private static async Task RunAsync()
        {
            var options = CommandLineOptions.Parse();
            if (string.IsNullOrWhiteSpace(options.InstanceId))
            {
                UnityEngine.Debug.LogError("UnityAutomatedTester instanceId is required.");
                Exit(1);
                return;
            }

            var stopwatch = Stopwatch.StartNew();

            try
            {
                await UnityAutomatedTestContext.ConnectAsync(options);
                await UnityAutomatedTestContext.LogInfoAsync("UnityAutomatedTester bridge connected.");
                await UnityAutomatedTestContext.LogInfoAsync("UnityAutomatedTester custom args: " + string.Join(", ", options.Args));
                await UnityAutomatedTestContext.SendTestStartedAsync(GetTestName(options));
                await UnityAutomatedTestContext.ReportProgressAsync(1, 3, "Bridge initialized");
                await UnityAutomatedTestContext.ReportProgressAsync(2, 3, "Waiting for test implementation");
                await UnityAutomatedTestContext.ReportProgressAsync(3, 3, "MVP bridge completed");
                await UnityAutomatedTestContext.SendTestCompletedAsync(true, 1, 0, stopwatch.Elapsed.TotalSeconds);
                await UnityAutomatedTestContext.DisconnectAsync();
                Exit(0);
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogException(ex);
                if (UnityAutomatedTestContext.IsConnected)
                {
                    await UnityAutomatedTestContext.SendTestFailedAsync(ex.Message, ex.ToString());
                    await UnityAutomatedTestContext.DisconnectAsync();
                }
                Exit(1);
            }
        }

        private static string GetTestName(CommandLineOptions options)
        {
            return options.Args.TryGetValue("test_name", out var testName) ? testName : "MvpBridgeTest";
        }

        private static void Exit(int code)
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.Exit(code);
#else
            Application.Quit(code);
#endif
        }
    }
}
