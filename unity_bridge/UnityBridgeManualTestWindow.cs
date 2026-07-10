#if UNITY_EDITOR
using System;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

namespace UnityAutomatedTester
{
    public sealed class UnityBridgeManualTestWindow : EditorWindow
    {
        private string instanceId = "manual-unity-001";
        private string serverUrl = "ws://127.0.0.1:5100/ws/unity";
        private string logMessage = "Hello from Unity Editor";
        private string progressMessage = "Manual progress";
        private int progressCurrent = 1;
        private int progressTotal = 10;
        private bool connected;

        [MenuItem("Tools/Unity Automated Tester/Manual Test Window")]
        public static void Open()
        {
            GetWindow<UnityBridgeManualTestWindow>("UAT Manual Test");
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Connection", EditorStyles.boldLabel);
            instanceId = EditorGUILayout.TextField("Instance Id", instanceId);
            serverUrl = EditorGUILayout.TextField("Server Url", serverUrl);

            EditorGUILayout.BeginHorizontal();
            GUI.enabled = !connected;
            if (GUILayout.Button("Connect"))
            {
                RunAsync(ConnectAsync);
            }

            GUI.enabled = connected;
            if (GUILayout.Button("Disconnect"))
            {
                RunAsync(DisconnectAsync);
            }
            GUI.enabled = true;
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Messages", EditorStyles.boldLabel);
            GUI.enabled = connected;

            logMessage = EditorGUILayout.TextField("Log Message", logMessage);
            if (GUILayout.Button("Send Log"))
            {
                RunAsync(async () =>
                {
                    await UnityAutomatedTestContext.LogInfoAsync(logMessage);
                    Debug.Log("UnityAutomatedTester manual test sent log: " + logMessage);
                });
            }

            progressCurrent = EditorGUILayout.IntField("Progress Current", progressCurrent);
            progressTotal = EditorGUILayout.IntField("Progress Total", progressTotal);
            progressMessage = EditorGUILayout.TextField("Progress Message", progressMessage);
            if (GUILayout.Button("Send Progress"))
            {
                RunAsync(async () =>
                {
                    await UnityAutomatedTestContext.ReportProgressAsync(progressCurrent, progressTotal, progressMessage);
                    Debug.Log("UnityAutomatedTester manual test sent progress: " + progressCurrent + "/" + progressTotal + " " + progressMessage);
                });
            }

            if (GUILayout.Button("Send Heartbeat"))
            {
                RunAsync(async () =>
                {
                    await UnityAutomatedTestContext.SendHeartbeatAsync();
                    Debug.Log("UnityAutomatedTester manual test sent heartbeat.");
                });
            }

            if (GUILayout.Button("Send Test Started"))
            {
                RunAsync(() => UnityAutomatedTestContext.SendTestStartedAsync("ManualEditorTest"));
            }

            if (GUILayout.Button("Send Test Completed"))
            {
                RunAsync(() => UnityAutomatedTestContext.SendTestCompletedAsync(true, 1, 0, 0));
            }

            if (GUILayout.Button("Send Test Failed"))
            {
                RunAsync(() => UnityAutomatedTestContext.SendTestFailedAsync("Manual failure", "Triggered from Unity editor"));
            }

            GUI.enabled = true;
            EditorGUILayout.Space();
            EditorGUILayout.HelpBox(
                connected
                    ? "Connected. You can send messages to the Python server."
                    : "Before connecting, create or register the same instance_id on the Python server.",
                connected ? MessageType.Info : MessageType.Warning);
        }

        private async Task ConnectAsync()
        {
            if (connected)
            {
                return;
            }

            var options = CommandLineOptions.CreateManualTest(instanceId, serverUrl);
            await UnityAutomatedTestContext.ConnectAsync(options);
            connected = true;
            Debug.Log("UnityAutomatedTester manual test connected: " + instanceId);
            Repaint();
        }

        private async Task DisconnectAsync()
        {
            if (!connected || !UnityAutomatedTestContext.IsConnected)
            {
                return;
            }

            await UnityAutomatedTestContext.DisconnectAsync();
            connected = false;
            Debug.Log("UnityAutomatedTester manual test disconnected: " + instanceId);
            Repaint();
        }

        private void OnDisable()
        {
            if (UnityAutomatedTestContext.IsConnected)
            {
                _ = DisconnectAsync();
            }
        }

        private async void RunAsync(Func<Task> action)
        {
            try
            {
                await action();
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
        }
    }
}
#endif
