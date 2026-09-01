using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace CJL.Shared;

public static class ProductPaths
{
    public const string ProductName = "CJL System";
    public const int LayoutVersion = 5;

    public static string Normalize(string path) => Path.GetFullPath(Environment.ExpandEnvironmentVariables(path.Trim().Trim('"'))).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

    public static string FindMasterRoot(string? start = null)
    {
        var current = new DirectoryInfo(Normalize(start ?? AppContext.BaseDirectory));
        for (var i = 0; i < 10 && current is not null; i++, current = current.Parent)
        {
            if (File.Exists(Path.Combine(current.FullName, "App", "Config", "master.id"))) return current.FullName;
        }
        throw new InvalidOperationException("A raiz do Mestre CJL System nao pode ser identificada.");
    }

    public static string MasterApp(string master) => Path.Combine(master, "App");
    public static string MasterHost(string master) => Path.Combine(master, "Host");
    public static string MasterHostBin(string master) => Path.Combine(master, "Host", "Bin");
    public static string MasterHostBridge(string master) => Path.Combine(master, "Host", "Bridge", "host_bridge.py");
    public static string MasterUpdates(string master) => Path.Combine(master, "Updates");
    public static string MasterDevHost(string master) => Path.Combine(master, "Dev", "Host");

    public static string ReadMasterId(string master)
    {
        var path = Path.Combine(MasterApp(master), "Config", "master.id");
        var value = File.ReadAllText(path, Encoding.UTF8).Trim().ToUpperInvariant();
        if (!value.StartsWith("CJL-MST-", StringComparison.Ordinal)) throw new InvalidOperationException("MASTER.ID invalido.");
        return value;
    }

    public static string InstanceId(string master)
    {
        var normalized = Normalize(master).ToUpperInvariant();
        var digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(normalized)));
        return $"{ReadMasterId(master)}-{digest[..12]}";
    }

    public static string ProgramDataRoot(string master) => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "CJL", "Instancias", InstanceId(master));
    public static string LocalStateRoot(string master) => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CJL", "Instancias", InstanceId(master));

    public static string MasterRuntimeRoot(string master) => Path.Combine(master, "Runtime");
    public static string MasterSeedDatabase(string master) => Path.Combine(master, "Data", "sistema.db");
    public static string MasterSharedData(string master) => Path.Combine(master, "Shared");
    public static string MasterRepository(string master) => Path.Combine(master, "Repo");

    public static string MasterPython(string master, bool windowless = false)
    {
        var root = Path.Combine(MasterRuntimeRoot(master), "Python");
        var preferred = Path.Combine(root, windowless ? "pythonw.exe" : "python.exe");
        if (File.Exists(preferred)) return preferred;
        var fallback = Path.Combine(root, "python.exe");
        if (File.Exists(fallback)) return fallback;
        throw new FileNotFoundException("Runtime Python oficial nao encontrado no Mestre.", preferred);
    }

    public static string InstalledPython(string installRoot, bool windowless = false)
    {
        var root = Path.Combine(installRoot, "Runtime", "Python");
        var preferred = Path.Combine(root, windowless ? "pythonw.exe" : "python.exe");
        if (File.Exists(preferred)) return preferred;
        var fallback = Path.Combine(root, "python.exe");
        if (File.Exists(fallback)) return fallback;
        throw new FileNotFoundException("Runtime Python local nao encontrado.", preferred);
    }

    public static string InstalledApp(string installRoot) => Path.Combine(installRoot, "App");

    public static ProductVersion ReadVersionFromSystemRoot(string appRoot)
    {
        var path=Path.Combine(appRoot,"Config","sistema.json"); using var doc=JsonDocument.Parse(File.ReadAllText(path,Encoding.UTF8)); var root=doc.RootElement;
        var version=root.GetProperty("version").GetString()??"0.00.000"; var v=root.GetProperty("versioning");
        return new ProductVersion(version,v.GetProperty("business").GetInt32(),v.GetProperty("structural").GetInt32(),v.GetProperty("incremental").GetInt32(),v.GetProperty("security").GetInt32(),v.GetProperty("compat_sequence").GetInt32(),root.GetProperty("build").GetInt64(),root.GetProperty("schema_version").GetInt32(),root.GetProperty("runtime_version").GetInt32());
    }


}

public sealed record ProductVersion(string Version, int Business, int Structural, int Incremental, int Security, int CompatSequence, long Build, int Schema, int Runtime)
{
    public string BusinessId => $"BA-{Business:00}";
    public string StructuralId => $"ES-{Structural:00}";
    public string IncrementalId => $"IN-{Incremental:00}";
    public string SecurityId => $"SE-{Security:000}";
    public string PatchLabel => $"{BusinessId}  |  {StructuralId}  |  {IncrementalId}  |  {SecurityId}";
    public override string ToString() => $"{Version}  |  {PatchLabel}  |  BUILD {Build}";
}
