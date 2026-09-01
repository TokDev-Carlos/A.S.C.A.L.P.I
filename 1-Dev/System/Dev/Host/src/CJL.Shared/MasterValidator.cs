using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace CJL.Shared;

public static class MasterValidator
{
    public static ProductVersion ValidateBasic(string master, bool allowStaleHost = false)
    {
        master = ProductPaths.Normalize(master);
        if (!Directory.Exists(master)) throw new DirectoryNotFoundException("O caminho selecionado nao esta disponivel.");
        var app = ProductPaths.MasterApp(master);
        var required = new[]
        {
            Path.Combine(app,"Config","master.id"),
            Path.Combine(app,"Config","sistema.json"),
            Path.Combine(app,"Config","layout.json"),
            Path.Combine(app,"painel.py"),
            Path.Combine(master,"COPYRIGHT.txt"),
            Path.Combine(master,"LICENSE.txt"),
        };
        var missing = required.Where(x => !File.Exists(x)).ToArray();
        if (missing.Length > 0) throw new InvalidOperationException("Mestre incompleto: " + string.Join("; ", missing));
        _ = ProductPaths.ReadMasterId(master);
        var runtime = ProductPaths.MasterRuntimeRoot(master);
        if (!File.Exists(Path.Combine(runtime,"Python","python.exe"))) throw new InvalidOperationException("Runtime Python oficial ausente.");
        if (!allowStaleHost) ValidateHostBuildIfPresent(master, requireCurrentRelease: true);
        return ProductPaths.ReadVersionFromSystemRoot(app);
    }

    public static string ComputeHostSourceTreeHash(string master)
    {
        var root = ProductPaths.MasterDevHost(master);
        if (!Directory.Exists(root)) throw new InvalidOperationException("Fonte do Host .NET ausente em Dev\\Host.");
        var files = Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories)
            .Where(path =>
            {
                var relative = Path.GetRelativePath(root, path).Replace('\\','/');
                var parts = relative.Split('/');
                return !parts.Any(p => p.Equals("bin", StringComparison.OrdinalIgnoreCase) || p.Equals("obj", StringComparison.OrdinalIgnoreCase))
                    && !Path.GetFileName(path).StartsWith("host-build", StringComparison.OrdinalIgnoreCase)
                    && !relative.Contains("Bin.Novo.", StringComparison.OrdinalIgnoreCase)
                    && !relative.Contains("Bin.Anterior.", StringComparison.OrdinalIgnoreCase);
            })
            .OrderBy(path => Path.GetRelativePath(root, path).Replace('\\','/'), StringComparer.Ordinal)
            .ToArray();
        using var digest = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        foreach (var path in files)
        {
            var relative = Path.GetRelativePath(root, path).Replace('\\','/');
            var fileHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
            var line = Encoding.UTF8.GetBytes(relative + "\n" + fileHash + "\n");
            digest.AppendData(line);
        }
        return Convert.ToHexString(digest.GetHashAndReset()).ToLowerInvariant();
    }

    public static void ValidateHostBuildIfPresent(string master, bool requireCurrentRelease = true)
    {
        var bin = ProductPaths.MasterHostBin(master);
        if (!Directory.Exists(bin)) return;
        ValidateHostBuildDirectory(master, bin, requireCurrentRelease);
    }

    public static void ValidateHostBuildDirectory(string master, string bin, bool requireCurrentRelease = true)
    {
        master = ProductPaths.Normalize(master);
        bin = ProductPaths.Normalize(bin);
        var metadata = Path.Combine(bin,"host-build.json");
        if (!File.Exists(metadata)) throw new InvalidOperationException("Host .NET existe sem manifesto de build.");
        using var document = JsonDocument.Parse(File.ReadAllText(metadata, Encoding.UTF8));
        var root = document.RootElement;
        if (!root.TryGetProperty("format", out var formatElement) || formatElement.GetInt32() != 5 ||
            root.GetProperty("architecture").GetString() != "win-x64" || root.GetProperty("self_contained").ValueKind != JsonValueKind.True)
            throw new InvalidOperationException("Manifesto do Host .NET e invalido.");
        if (!string.Equals(root.GetProperty("product").GetString(), "CJL System", StringComparison.Ordinal))
            throw new InvalidOperationException("Produto invalido no manifesto do Host .NET.");

        if (requireCurrentRelease)
        {
            var contract = root.TryGetProperty("host_contract", out var hc) ? hc.GetString() ?? "" : "";
            if (contract != "1") throw new InvalidOperationException("Host Contract Base 5 invalido.");
            var declaredSourceHash = root.GetProperty("source_tree_sha256").GetString() ?? "";
            var actualSourceHash = ComputeHostSourceTreeHash(master);
            if (!string.Equals(declaredSourceHash, actualSourceHash, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("O Host .NET nao corresponde a arvore fonte Dev\\Host atual; recompilacao obrigatoria.");
        }

        var files = root.GetProperty("files");
        var declared = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in files.EnumerateObject())
        {
            if (item.Name.Contains('/') || item.Name.Contains('\\') || item.Name.Contains("..", StringComparison.Ordinal)) throw new InvalidOperationException("Caminho invalido no manifesto do Host .NET.");
            declared.Add(item.Name);
            var path = Path.Combine(bin,item.Name);
            if (!File.Exists(path) || !string.Equals(FileUtil.Sha256(path), item.Value.GetString(), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Binario .NET ausente ou alterado: " + item.Name);
        }
        var actual = Directory.EnumerateFiles(bin,"*",SearchOption.TopDirectoryOnly)
            .Select(Path.GetFileName)
            .Where(name => !string.Equals(name,"host-build.json",StringComparison.OrdinalIgnoreCase))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        if (!actual.SetEquals(declared)) throw new InvalidOperationException("Conjunto de binarios .NET diverge do manifesto de build.");
    }

    public static async Task ValidateDeepAsync(string master, bool allowStaleHost = false, CancellationToken token = default)
    {
        ValidateBasic(master, allowStaleHost);
        var python = ProductPaths.MasterPython(master);
        var bridge = ProductPaths.MasterHostBridge(master);
        var result = await ProcessUtil.RunAsync(python, new[]{"-B","-I","-S",bridge,"validate-master",master}, master, null, null, false, token);
        if (result.ExitCode != 0) throw new InvalidOperationException((result.StdErr + "\n" + result.StdOut).Trim());
    }
}
