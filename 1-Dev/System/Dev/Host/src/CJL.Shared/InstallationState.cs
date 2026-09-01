using System.Text;
using System.Text.Json;

namespace CJL.Shared;

public sealed class InstallationState
{
    public string Product { get; set; } = "CJL System";
    public int Format { get; set; } = 1;
    public string MasterRoot { get; set; } = "";
    public string MasterId { get; set; } = "";
    public string InstanceId { get; set; } = "";
    public string InstallRoot { get; set; } = "";
    public string InstalledAt { get; set; } = "";
    public string Architecture { get; set; } = "DOTNET10_WPF_WEBVIEW2";

    public static string StateFile(string master) => Path.Combine(ProductPaths.ProgramDataRoot(master), "installation.json");

    public static InstallationState? LoadByMaster(string master)
    {
        var path = StateFile(master);
        if (!File.Exists(path)) return null;
        try { return JsonSerializer.Deserialize<InstallationState>(File.ReadAllText(path, Encoding.UTF8)); }
        catch { return null; }
    }

    public void Save()
    {
        Directory.CreateDirectory(ProductPaths.ProgramDataRoot(MasterRoot));
        var path = StateFile(MasterRoot);
        var temp = path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(this, JsonOptions.Indented), new UTF8Encoding(false));
        File.Move(temp, path, true);
    }
}

public static class JsonOptions
{
    public static readonly JsonSerializerOptions Indented = new() { WriteIndented = true, PropertyNameCaseInsensitive = true };
}
