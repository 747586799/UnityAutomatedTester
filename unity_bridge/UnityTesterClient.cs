using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace UnityAutomatedTester
{
    public sealed class UnityTesterClient : IDisposable
    {
        /// <summary>
        /// Fired when a complete server message is received.
        /// Parameters: (messageType, payloadJson)
        /// </summary>
        public event Action<string, string> OnServerMessage;

        private readonly CommandLineOptions options;
        private readonly ClientWebSocket socket = new ClientWebSocket();
        private readonly CancellationTokenSource cancellation = new CancellationTokenSource();

        public UnityTesterClient(CommandLineOptions options)
        {
            this.options = options;
        }

        public async Task ConnectAsync()
        {
            await socket.ConnectAsync(new Uri(options.ServerUrl), cancellation.Token);
            await SendAsync(JsonMessageBuilder.Create(options.InstanceId, "hello", CreateHelloPayload()));
            await SendAsync(JsonMessageBuilder.Create(options.InstanceId, "ready"));
            _ = Task.Run(ReceiveLoopAsync);
        }

        public Task SendProgressAsync(int current, int total, string message)
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "progress", JsonMessageBuilder.ProgressPayload(current, total, message)));
        }

        public Task SendLogAsync(string level, string message)
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "log", JsonMessageBuilder.LogPayload(level, message)));
        }

        public Task SendTestStartedAsync(string testName)
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "test_started", "{\"test_name\":\"" + testName + "\"}"));
        }

        public Task SendTestCompletedAsync(bool success, int passed, int failed, double durationSeconds, string report = null)
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "test_completed", JsonMessageBuilder.TestCompletedPayload(success, passed, failed, durationSeconds, report)));
        }

        public Task SendTestFailedAsync(string error, string stackTrace)
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "test_failed", JsonMessageBuilder.TestFailedPayload(error, stackTrace)));
        }

        /// <summary>
        /// Send a ready signal to the server with a ready_id.
        /// The server waits for all group instances to be ready before sending the start command.
        /// </summary>
        public Task SendReadyAsync(int readyId)
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "ready", "{\"ready_id\":" + readyId + "}"));
        }

        public Task SendHeartbeatAsync()
        {
            return SendAsync(JsonMessageBuilder.Create(options.InstanceId, "heartbeat"));
        }

        public async Task CloseAsync()
        {
            cancellation.Cancel();
            if (socket.State == WebSocketState.Open)
            {
                await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "closed", CancellationToken.None);
            }
        }

        public void Dispose()
        {
            cancellation.Cancel();
            socket.Dispose();
            cancellation.Dispose();
        }

        private async Task SendAsync(string json)
        {
            if (socket.State != WebSocketState.Open)
            {
                Debug.LogWarning("UnityAutomatedTester send skipped because socket is not open. State: " + socket.State);
                return;
            }

            var bytes = Encoding.UTF8.GetBytes(json);
            await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cancellation.Token);
            var truncated = json.Length <= 300 ? json : json.Substring(0, 300) + "...(" + json.Length + " bytes)";
            Debug.Log("UnityAutomatedTester sent message: " + truncated);
        }

        private const int ReceiveBufferSize = 64 * 1024; // 64 KB chunk

        private async Task ReceiveLoopAsync()
        {
            var buffer = new byte[ReceiveBufferSize];

            while (!cancellation.IsCancellationRequested && socket.State == WebSocketState.Open)
            {
                var messageBuilder = new StringBuilder();
                WebSocketReceiveResult result;

                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellation.Token);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        return;
                    }

                    messageBuilder.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                } while (!result.EndOfMessage);

                var message = messageBuilder.ToString();
                var truncated = message.Length <= 200 ? message : message.Substring(0, 200) + "...";
                Debug.Log("UnityAutomatedTester received command (" + message.Length + " bytes): " + truncated);

                // Fire event for subscribers to handle
                var type = ExtractMessageType(message);
                var payload = ExtractMessagePayload(message);
                OnServerMessage?.Invoke(type, payload);
            }
        }

        /// <summary>
        /// Extract the "type" field from a server message JSON string.
        /// </summary>
        private static string ExtractMessageType(string json)
        {
            var search = "\"type\":\"";
            var start = json.IndexOf(search, StringComparison.Ordinal);
            if (start < 0)
            {
                // Try with space: "type": "
                search = "\"type\": \"";
                start = json.IndexOf(search, StringComparison.Ordinal);
            }
            if (start < 0)
                return string.Empty;

            start += search.Length;
            var end = json.IndexOf('"', start);
            return end > start ? json.Substring(start, end - start) : string.Empty;
        }

        /// <summary>
        /// Extract the "payload" field as a raw JSON string from a server message.
        /// </summary>
        private static string ExtractMessagePayload(string json)
        {
            var search = "\"payload\":";
            var start = json.IndexOf(search, StringComparison.Ordinal);
            if (start < 0)
            {
                search = "\"payload\" :";
                start = json.IndexOf(search, StringComparison.Ordinal);
            }
            if (start < 0)
                return string.Empty;

            start += search.Length;
            // Skip whitespace
            while (start < json.Length && (json[start] == ' ' || json[start] == '\t'))
                start++;

            if (start >= json.Length)
                return string.Empty;

            // Find matching brace
            if (json[start] == '{')
            {
                var depth = 0;
                for (var i = start; i < json.Length; i++)
                {
                    if (json[i] == '{') depth++;
                    else if (json[i] == '}') depth--;
                    if (depth == 0)
                        return json.Substring(start, i - start + 1);
                }
            }

            return string.Empty;
        }

        private string CreateHelloPayload()
        {
            return "{"
                + "\"unity_version\":\"" + Application.unityVersion + "\","
                + "\"project_path\":\"" + Application.dataPath.Replace("\\", "\\\\") + "\""
                + "}";
        }
    }
}
