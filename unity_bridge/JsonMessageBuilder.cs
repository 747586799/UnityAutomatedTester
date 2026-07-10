using System;

namespace UnityAutomatedTester
{
    public static class JsonMessageBuilder
    {
        public static string Create(string instanceId, string type, string payloadJson = "{}")
        {
            return "{"
                + "\"id\":\"" + Guid.NewGuid().ToString("N") + "\","
                + "\"instance_id\":\"" + Escape(instanceId) + "\","
                + "\"type\":\"" + Escape(type) + "\","
                + "\"timestamp\":\"" + DateTime.UtcNow.ToString("O") + "\","
                + "\"payload\":" + payloadJson
                + "}";
        }

        public static string ProgressPayload(int current, int total, string message)
        {
            var percent = total <= 0 ? 0.0f : (float)current / total;
            return "{"
                + "\"current\":" + current + ","
                + "\"total\":" + total + ","
                + "\"percent\":" + percent.ToString(System.Globalization.CultureInfo.InvariantCulture) + ","
                + "\"message\":\"" + Escape(message) + "\""
                + "}";
        }

        public static string LogPayload(string level, string message)
        {
            return "{"
                + "\"level\":\"" + Escape(level) + "\","
                + "\"message\":\"" + Escape(message) + "\""
                + "}";
        }

        public static string TestCompletedPayload(bool success, int passed, int failed, double durationSeconds, string report = null)
        {
            if (report == null)
            {
                return "{"
                    + "\"success\":" + (success ? "true" : "false") + ","
                    + "\"passed\":" + passed + ","
                    + "\"failed\":" + failed + ","
                    + "\"duration_seconds\":" + durationSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture)
                    + "}";
            }

            return "{"
                + "\"success\":" + (success ? "true" : "false") + ","
                + "\"passed\":" + passed + ","
                + "\"failed\":" + failed + ","
                + "\"duration_seconds\":" + durationSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture) + ","
                + "\"report\":\"" + Escape(report) + "\""
                + "}";
        }

        public static string TestFailedPayload(string error, string stackTrace)
        {
            return "{"
                + "\"error\":\"" + Escape(error) + "\","
                + "\"stack_trace\":\"" + Escape(stackTrace) + "\""
                + "}";
        }

        private static string Escape(string value)
        {
            return (value ?? string.Empty)
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n")
                .Replace("\t", "\\t");
        }
    }
}
