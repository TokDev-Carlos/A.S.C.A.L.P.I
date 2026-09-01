using System.Security.Cryptography;

namespace CJL.Shared;

public static class FileUtil
{
    public static string Sha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    public static void CopyTree(string source, string destination, Func<string,bool>? excludeRelative = null, Action<string>? progress = null)
    {
        source = ProductPaths.Normalize(source);
        destination = ProductPaths.Normalize(destination);
        if (!Directory.Exists(source)) throw new DirectoryNotFoundException(source);
        Directory.CreateDirectory(destination);
        foreach (var directory in Directory.EnumerateDirectories(source, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(source, directory).Replace('\\','/');
            if (IsExcluded(relative, excludeRelative)) continue;
            Directory.CreateDirectory(Path.Combine(destination, relative.Replace('/', Path.DirectorySeparatorChar)));
        }
        foreach (var file in Directory.EnumerateFiles(source, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(source, file).Replace('\\','/');
            if (IsExcluded(relative, excludeRelative)) continue;
            var dest = Path.Combine(destination, relative.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
            File.Copy(file, dest, true);
            progress?.Invoke(relative);
        }
    }

    private static bool IsExcluded(string relative, Func<string,bool>? predicate)
    {
        var parts = relative.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Any(p => p.Equals("__pycache__", StringComparison.OrdinalIgnoreCase))) return true;
        if (relative.EndsWith(".pyc", StringComparison.OrdinalIgnoreCase) || relative.EndsWith(".pyo", StringComparison.OrdinalIgnoreCase)) return true;
        return predicate?.Invoke(relative) == true;
    }

    public static void DeleteTreeBestEffort(string path)
    {
        if (!Directory.Exists(path)) return;
        foreach (var file in Directory.EnumerateFiles(path, "*", SearchOption.AllDirectories))
        {
            try { File.SetAttributes(file, FileAttributes.Normal); } catch { }
        }
        Directory.Delete(path, true);
    }

    public static void AtomicReplaceDirectory(string prepared, string destination)
    {
        prepared = ProductPaths.Normalize(prepared);
        destination = ProductPaths.Normalize(destination);
        var backup = destination + ".Anterior." + DateTime.Now.ToString("yyyyMMddHHmmss");
        if (Directory.Exists(destination)) Directory.Move(destination, backup);
        try
        {
            Directory.Move(prepared, destination);
            if (Directory.Exists(backup)) DeleteTreeBestEffort(backup);
        }
        catch
        {
            if (!Directory.Exists(destination) && Directory.Exists(backup)) Directory.Move(backup, destination);
            throw;
        }
    }
}
