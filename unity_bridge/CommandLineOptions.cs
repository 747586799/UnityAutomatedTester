using System;
using System.Collections.Generic;
using System.Globalization;

namespace UnityAutomatedTester
{
    public sealed class CommandLineOptions
    {
        public string InstanceId { get; private set; } = string.Empty;
        public string ServerUrl { get; private set; } = "ws://127.0.0.1:5100/ws/unity";
        public string TaskId { get; private set; } = string.Empty;
        public Dictionary<string, string> Args { get; } = new Dictionary<string, string>();

        public string GetArg(string key, string defaultValue = "")
        {
            return Args.TryGetValue(key, out var value) ? value : defaultValue;
        }

        public bool TryGetArg(string key, out string value)
        {
            return Args.TryGetValue(key, out value);
        }

        public int GetIntArg(string key, int defaultValue = 0)
        {
            return Args.TryGetValue(key, out var value) && int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var result)
                ? result
                : defaultValue;
        }

        public float GetFloatArg(string key, float defaultValue = 0)
        {
            return Args.TryGetValue(key, out var value) && float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var result)
                ? result
                : defaultValue;
        }

        public bool GetBoolArg(string key, bool defaultValue = false)
        {
            return Args.TryGetValue(key, out var value) && bool.TryParse(value, out var result)
                ? result
                : defaultValue;
        }

        public static CommandLineOptions CreateManualTest(string instanceId, string serverUrl)
        {
            return new CommandLineOptions
            {
                InstanceId = instanceId,
                ServerUrl = serverUrl,
            };
        }

        public static CommandLineOptions Parse()
        {
            var options = new CommandLineOptions();
            var args = Environment.GetCommandLineArgs();

            for (var i = 0; i < args.Length; i++)
            {
                var key = args[i];
                if (!key.StartsWith("-automatedTester.", StringComparison.Ordinal))
                {
                    continue;
                }

                var value = i + 1 < args.Length ? args[i + 1] : string.Empty;
                var name = key.Substring("-automatedTester.".Length);
                options.Args[name] = value;

                if (name == "instanceId")
                {
                    options.InstanceId = value;
                }
                else if (name == "serverUrl")
                {
                    options.ServerUrl = value;
                }
                else if (name == "taskId")
                {
                    options.TaskId = value;
                }
            }

            return options;
        }
    }
}
