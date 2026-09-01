using System.Diagnostics;
using System.Text;

namespace CJL.Shared;

public sealed record ProcessResult(int ExitCode, string StdOut, string StdErr);

public static class ProcessUtil
{
    public static async Task<ProcessResult> RunAsync(string file, IEnumerable<string> args, string? cwd = null, IDictionary<string,string?>? env = null, string? stdin = null, bool createWindow = false, CancellationToken token = default)
    {
        var start = new ProcessStartInfo(file)
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = stdin is not null,
            CreateNoWindow = !createWindow,
            WorkingDirectory = cwd ?? Environment.CurrentDirectory,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var arg in args) start.ArgumentList.Add(arg);
        if (env is not null)
            foreach (var item in env) start.Environment[item.Key] = item.Value;

        using var process = new Process { StartInfo = start, EnableRaisingEvents = true };
        if (!process.Start()) throw new InvalidOperationException($"Não foi possível iniciar {file}.");
        if (stdin is not null)
        {
            await process.StandardInput.WriteAsync(stdin.AsMemory(), token);
            await process.StandardInput.FlushAsync(token);
            process.StandardInput.Close();
        }
        var stdoutTask = process.StandardOutput.ReadToEndAsync(token);
        var stderrTask = process.StandardError.ReadToEndAsync(token);
        await process.WaitForExitAsync(token);
        return new ProcessResult(process.ExitCode, await stdoutTask, await stderrTask);
    }

    public static Process StartDetached(string file, IEnumerable<string> args, string? cwd = null)
    {
        var start = new ProcessStartInfo(file) { UseShellExecute = true, WorkingDirectory = cwd ?? Environment.CurrentDirectory };
        foreach (var arg in args) start.ArgumentList.Add(arg);
        return Process.Start(start) ?? throw new InvalidOperationException($"Não foi possível iniciar {file}.");
    }
}
