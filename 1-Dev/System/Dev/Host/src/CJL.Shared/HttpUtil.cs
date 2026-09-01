using System.Diagnostics;
using System.Net.Http.Json;
using System.Text.Json;

namespace CJL.Shared;

public static class HttpUtil
{
    private static readonly HttpClient Client = new() { Timeout = TimeSpan.FromSeconds(4) };

    public static async Task<bool> PingAsync(int port, string token, CancellationToken cancellationToken = default)
    {
        try
        {
            var uri = $"http://127.0.0.1:{port}/api/instance/ping?token={Uri.EscapeDataString(token)}";
            using var response = await Client.GetAsync(uri, cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch { return false; }
    }

    public static async Task ShutdownAsync(int port, string token, CancellationToken cancellationToken = default)
    {
        try
        {
            var uri = $"http://127.0.0.1:{port}/api/instance/shutdown";
            using var response = await Client.PostAsJsonAsync(uri, new { token }, cancellationToken);
            _ = response.IsSuccessStatusCode;
        }
        catch { }
    }

    public static async Task<InstanceRegistry?> WaitForInstanceAsync(string stateRoot, Process process, TimeSpan timeout, CancellationToken cancellationToken = default)
    {
        var registry = Path.Combine(stateRoot, "Instancia", "instance.json");
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline && !cancellationToken.IsCancellationRequested)
        {
            if (process.HasExited) return null;
            try
            {
                if (File.Exists(registry))
                {
                    var value = JsonSerializer.Deserialize<InstanceRegistry>(await File.ReadAllTextAsync(registry, cancellationToken), JsonOptions.Indented);
                    if (value is not null && value.Port > 0 && !string.IsNullOrWhiteSpace(value.Token) && await PingAsync(value.Port, value.Token, cancellationToken))
                        return value;
                }
            }
            catch { }
            await Task.Delay(200, cancellationToken);
        }
        return null;
    }
}

public sealed class InstanceRegistry
{
    public int Pid { get; set; }
    public int Port { get; set; }
    public string Token { get; set; } = "";
    public string State_Root { get; set; } = "";
}
