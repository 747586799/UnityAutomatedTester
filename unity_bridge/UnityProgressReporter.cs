using System.Threading.Tasks;

namespace UnityAutomatedTester
{
    public sealed class UnityProgressReporter
    {
        private readonly UnityTesterClient client;

        public UnityProgressReporter(UnityTesterClient client)
        {
            this.client = client;
        }

        public Task ReportAsync(int current, int total, string message)
        {
            return client.SendProgressAsync(current, total, message);
        }

        public Task LogInfoAsync(string message)
        {
            return client.SendLogAsync("info", message);
        }

        public Task LogErrorAsync(string message)
        {
            return client.SendLogAsync("error", message);
        }
    }
}
