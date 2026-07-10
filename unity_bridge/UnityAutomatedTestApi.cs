using System.Threading.Tasks;

namespace UnityAutomatedTester
{
    public static class UnityAutomatedTestApi
    {
        public static string GetArg(string key, string defaultValue = "")
        {
            return UnityAutomatedTestContext.GetArg(key, defaultValue);
        }

        public static bool TryGetArg(string key, out string value)
        {
            return UnityAutomatedTestContext.TryGetArg(key, out value);
        }

        public static int GetIntArg(string key, int defaultValue = 0)
        {
            return UnityAutomatedTestContext.GetIntArg(key, defaultValue);
        }

        public static float GetFloatArg(string key, float defaultValue = 0)
        {
            return UnityAutomatedTestContext.GetFloatArg(key, defaultValue);
        }

        public static bool GetBoolArg(string key, bool defaultValue = false)
        {
            return UnityAutomatedTestContext.GetBoolArg(key, defaultValue);
        }

        public static Task ProgressAsync(int current, int total, string message)
        {
            return UnityAutomatedTestContext.ReportProgressAsync(current, total, message);
        }

        public static Task LogInfoAsync(string message)
        {
            return UnityAutomatedTestContext.LogInfoAsync(message);
        }

        public static Task LogErrorAsync(string message)
        {
            return UnityAutomatedTestContext.LogErrorAsync(message);
        }

        public static Task HeartbeatAsync()
        {
            return UnityAutomatedTestContext.SendHeartbeatAsync();
        }

        public static Task TestStartedAsync(string testName)
        {
            return UnityAutomatedTestContext.SendTestStartedAsync(testName);
        }

        public static Task TestCompletedAsync(bool success, int passed, int failed, double durationSeconds, string report = null)
        {
            return UnityAutomatedTestContext.SendTestCompletedAsync(success, passed, failed, durationSeconds, report);
        }

        public static Task TestFailedAsync(string error, string stackTrace)
        {
            return UnityAutomatedTestContext.SendTestFailedAsync(error, stackTrace);
        }
    }
}
