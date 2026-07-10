using System;
using System.Threading.Tasks;
using UnityEngine;

namespace UnityAutomatedTester
{
    public static class UnityAutomatedTestContext
    {
        public static CommandLineOptions Options { get; private set; }
        public static UnityTesterClient Client { get; private set; }
        public static UnityProgressReporter Reporter { get; private set; }
        public static bool IsConnected => Client != null;

        public static event Action<string, string> OnServerMessage;

        public static string GetArg(string key, string defaultValue = "")
        {
            return Options != null ? Options.GetArg(key, defaultValue) : defaultValue;
        }

        public static bool TryGetArg(string key, out string value)
        {
            if (Options != null)
            {
                return Options.TryGetArg(key, out value);
            }

            value = null;
            return false;
        }

        public static int GetIntArg(string key, int defaultValue = 0)
        {
            return Options != null ? Options.GetIntArg(key, defaultValue) : defaultValue;
        }

        public static float GetFloatArg(string key, float defaultValue = 0)
        {
            return Options != null ? Options.GetFloatArg(key, defaultValue) : defaultValue;
        }

        public static bool GetBoolArg(string key, bool defaultValue = false)
        {
            return Options != null ? Options.GetBoolArg(key, defaultValue) : defaultValue;
        }

        public static async Task ConnectAsync(CommandLineOptions options)
        {
            if (Client != null)
            {
                await DisconnectAsync();
            }

            Options = options ?? throw new ArgumentNullException(nameof(options));
            Client = new UnityTesterClient(Options);
            Client.OnServerMessage += OnClientMessage;
            Reporter = new UnityProgressReporter(Client);
            await Client.ConnectAsync();
        }

        public static async Task DisconnectAsync()
        {
            if (Client == null)
            {
                return;
            }

            Client.OnServerMessage -= OnClientMessage;
            await Client.CloseAsync();
            Client.Dispose();
            Client = null;
            Reporter = null;
            Options = null;
        }

        /// <summary>
        /// Handles server messages received by the client.
        /// </summary>
        private static void OnClientMessage(string type, string payload)
        {
            // Forward to external subscribers
            OnServerMessage?.Invoke(type, payload);

            // Built-in handlers
            switch (type)
            {
                case "shutdown":
                    Debug.Log("UnityAutomatedTestContext received shutdown command, exiting...");
                    Exit(0);
                    break;
            }
        }

        public static Task ReportProgressAsync(int current, int total, string message)
        {
            EnsureConnected();
            return Reporter.ReportAsync(current, total, message);
        }

        public static Task LogInfoAsync(string message)
        {
            EnsureConnected();
            return Reporter.LogInfoAsync(message);
        }

        public static Task LogErrorAsync(string message)
        {
            EnsureConnected();
            return Reporter.LogErrorAsync(message);
        }

        public static Task SendHeartbeatAsync()
        {
            EnsureConnected();
            return Client.SendHeartbeatAsync();
        }

        public static Task SendTestStartedAsync(string testName)
        {
            EnsureConnected();
            return Client.SendTestStartedAsync(testName);
        }

        public static Task SendTestCompletedAsync(bool success, int passed, int failed, double durationSeconds, string report = null)
        {
            EnsureConnected();
            return Client.SendTestCompletedAsync(success, passed, failed, durationSeconds, report);
        }

        public static Task SendTestFailedAsync(string error, string stackTrace)
        {
            EnsureConnected();
            return Client.SendTestFailedAsync(error, stackTrace);
        }

        /// <summary>
        /// Tell the server this instance is ready with the given ready_id.
        /// The server will wait for all group members before broadcasting the start command.
        /// </summary>
        public static Task SendReadyAsync(int readyId)
        {
            EnsureConnected();
            return Client.SendReadyAsync(readyId);
        }

        private static void EnsureConnected()
        {
            if (Client == null || Reporter == null)
            {
                throw new InvalidOperationException("UnityAutomatedTestContext is not connected.");
            }
        }

        public static void Exit(int code)
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.Exit(code);
#else
            Application.Quit(code);
#endif
        }
    }
}
