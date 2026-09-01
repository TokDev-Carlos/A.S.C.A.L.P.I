using System.Security.Cryptography;
using System.Text;

namespace CJL.Shared;

public static class StationInstall
{
    public static string DefaultInstallRoot => @"C:\CJL";

    public static async Task ValidateInstalledAsync(string candidateRoot, string installRoot, string masterRoot, CancellationToken token = default)
    {
        candidateRoot = ProductPaths.Normalize(candidateRoot);
        var app = Directory.Exists(Path.Combine(candidateRoot, "App")) ? Path.Combine(candidateRoot, "App") : candidateRoot;
        var python = ProductPaths.InstalledPython(installRoot);
        var bridge = ProductPaths.MasterHostBridge(masterRoot);
        var result = await ProcessUtil.RunAsync(python, new[]{"-B","-I","-S",bridge,"validate-installed",app,masterRoot,installRoot}, installRoot, null, null, false, token);
        if (result.ExitCode != 0) throw new InvalidOperationException((result.StdErr + "\n" + result.StdOut).Trim());
    }

    public static Task ValidatePythonAgainstMasterAsync(string installRoot, string masterRoot, CancellationToken token = default)
        => ValidateInstalledAsync(ProductPaths.MasterApp(masterRoot), installRoot, masterRoot, token);

    public static Task ValidatePythonLocalAsync(string installRoot, string masterRoot, CancellationToken token = default)
        => ValidateInstalledAsync(Path.Combine(installRoot, "App"), installRoot, masterRoot, token);

    public static void EnsureTransientLayout(string masterRoot)
    {
        var local = ProductPaths.LocalStateRoot(masterRoot);
        foreach (var name in new[]{"Sessao","Cache","Temp","Outbox","DownloadsTemporarios","WebView","Instancia","Logs","Recursos\\Temp"})
            Directory.CreateDirectory(Path.Combine(local,name));
        Directory.CreateDirectory(ProductPaths.ProgramDataRoot(masterRoot));
    }

    public static string InstallId(string installRoot)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(ProductPaths.Normalize(installRoot).ToUpperInvariant()));
        return Convert.ToHexString(bytes)[..16];
    }
}
