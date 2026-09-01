using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using CJL.Shared;

Console.OutputEncoding = Encoding.UTF8;
Console.InputEncoding = Encoding.UTF8;
Console.Title = "CJL System";

string? explicitMaster = ArgValue(args, "--master");
var master = ProductPaths.FindMasterRoot(explicitMaster ?? args.FirstOrDefault(Directory.Exists));
var logPath = CreateRuntimeLog(master);
var selfTestMode = HasFlag(args, "--self-test");

try
{
    Log(logPath, "INICIO", $"Bootstrap iniciado. Master={master}");
    if (selfTestMode)
    {
        await SelfTestAsync(master, ArgValue(args, "--host-bin"), logPath);
        Console.WriteLine("SELFTEST OK");
        return 0;
    }

    var version = MasterValidator.ValidateBasic(master);
    if (HasFlag(args, "--open-master"))
    {
        Launch(master, "CJL.Host.exe", "--master", master, "--direct-master");
        Log(logPath, "OPEN_MASTER", "CJL.Host solicitado por contrato nao interativo.");
        return 0;
    }
    var recoveryAfterFailure = false;
    while (true)
    {
        var recoveryVisible = recoveryAfterFailure || await RecoveryRequiredAsync(master);
        Console.Clear();
        Console.WriteLine("CJL System");
        Console.WriteLine($"{version.Version}  |  {version.PatchLabel}  |  LAYOUT {ProductPaths.LayoutVersion}");
        Console.WriteLine(new string('-', 56));
        Console.Write(recoveryVisible
            ? "Senha administrativa (ENTER = instalar/reparar usuario | RECUPERAR = recuperar ADMIN): "
            : "Senha administrativa (ENTER = instalar/reparar usuario): ");
        var password = ReadSecret();
        Console.WriteLine();
        if (password is null) return 0;
        if (string.IsNullOrWhiteSpace(password))
        {
            Launch(master, "CJL.Setup.exe", "--master", master);
            return 0;
        }
        if (recoveryVisible && string.Equals(password, "RECUPERAR", StringComparison.OrdinalIgnoreCase))
        {
            await RecoverAdminAsync(master);
            version = MasterValidator.ValidateBasic(master);
            Console.WriteLine("Recuperacao administrativa concluida. Pressione ENTER para continuar.");
            Console.ReadLine();
            continue;
        }

        var auth = await ValidateAdminAsync(master, password);
        if (auth.ExitCode == 0)
        {
            await AdminMenu(master, logPath);
            return 0;
        }
        if (auth.ExitCode is 10 or 11)
        {
            recoveryAfterFailure = true;
            Console.WriteLine(auth.ExitCode == 10 ? "Credencial administrativa invalida." : "Credencial sem autoridade SYSTEM_ADMIN.");
            Console.WriteLine("ENTER = tentar novamente | ESC = sair");
            if (Console.ReadKey(true).Key == ConsoleKey.Escape) return 2;
            continue;
        }
        throw new InvalidOperationException("Falha tecnica na autenticacao: " + CleanResult(auth));
    }
}
catch (Exception ex)
{
    Log(logPath, "FALHA", ex.ToString());
    Console.Error.WriteLine("FALHA: " + ex.Message);
    Console.Error.WriteLine("Log: " + logPath);
    if (!selfTestMode) { Console.WriteLine("Pressione ENTER para sair."); Console.ReadLine(); }
    return 1;
}

static string? ArgValue(string[] argv, string name)
{
    var index = Array.FindIndex(argv, value => value.Equals(name, StringComparison.OrdinalIgnoreCase));
    return index >= 0 && index + 1 < argv.Length ? argv[index + 1] : null;
}

static bool HasFlag(string[] argv, string name) => argv.Any(value => value.Equals(name, StringComparison.OrdinalIgnoreCase));

static string CreateRuntimeLog(string master)
{
    var directory = Path.Combine(master, "Logs", "Bootstrap");
    Directory.CreateDirectory(directory);
    return Path.Combine(directory, $"bootstrap_{DateTime.Now:yyyyMMdd_HHmmss}_{Environment.ProcessId}.log");
}

static void Log(string path, string stage, string message)
{
    try { File.AppendAllText(path, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{stage}] {message}{Environment.NewLine}", new UTF8Encoding(false)); }
    catch { }
}

static string? ReadSecret()
{
    var sb = new StringBuilder();
    while (true)
    {
        var key = Console.ReadKey(true);
        if (key.Key == ConsoleKey.Enter) break;
        if (key.Key == ConsoleKey.Escape) return null;
        if (key.Key == ConsoleKey.Backspace)
        {
            if (sb.Length > 0) { sb.Length--; Console.Write("\b \b"); }
            continue;
        }
        if (!char.IsControl(key.KeyChar)) { sb.Append(key.KeyChar); Console.Write('*'); }
    }
    return sb.ToString();
}

static async Task<ProcessResult> ValidateAdminAsync(string master, string password)
{
    return await ProcessUtil.RunAsync(ProductPaths.MasterPython(master), new[] { "-B", "-I", "-S", ProductPaths.MasterHostBridge(master), "validate-admin", master }, master, null, password + "\n");
}

static async Task<bool> RecoveryRequiredAsync(string master)
{
    var result = await ProcessUtil.RunAsync(ProductPaths.MasterPython(master), new[] { "-B", "-I", "-S", ProductPaths.MasterHostBridge(master), "admin-recovery-status", master }, master);
    if (result.ExitCode != 0) throw new InvalidOperationException("Falha ao consultar estado do recovery: " + CleanResult(result));
    using var document = JsonDocument.Parse(result.StdOut);
    return document.RootElement.TryGetProperty("recovery_required", out var required) && required.GetBoolean();
}

static async Task RecoverAdminAsync(string master)
{
    Console.WriteLine();
    Console.WriteLine("RECUPERACAO ADMIN LOCAL - requer este processo executado como Administrador do Windows.");
    Console.Write("Nova senha ADMIN: ");
    var first = ReadSecret();
    Console.WriteLine();
    if (first is null) throw new InvalidOperationException("Recuperacao cancelada.");
    Console.Write("Confirmar nova senha: ");
    var second = ReadSecret();
    Console.WriteLine();
    if (second is null) throw new InvalidOperationException("Recuperacao cancelada.");
    var result = await ProcessUtil.RunAsync(ProductPaths.MasterPython(master), new[] { "-B", "-I", "-S", ProductPaths.MasterHostBridge(master), "recover-admin", master }, master, null, first + "\n" + second + "\n");
    if (result.ExitCode != 0) throw new InvalidOperationException(CleanResult(result));
    Console.WriteLine(result.StdOut);
}

static string CleanResult(ProcessResult result)
{
    var text = string.Join(" ", new[] { result.StdErr, result.StdOut }.Where(v => !string.IsNullOrWhiteSpace(v)).Select(v => v.Trim()));
    return string.IsNullOrWhiteSpace(text) ? $"Codigo de saida: {result.ExitCode}." : text;
}

static void Launch(string master, string exe, params string[] argv)
{
    var bin = Path.Combine(ProductPaths.MasterHostBin(master), exe);
    if (!File.Exists(bin)) throw new FileNotFoundException("Componente .NET nao preparado.", bin);
    ProcessUtil.StartDetached(bin, argv, master);
}

static async Task AdminMenu(string master, string logPath)
{
    while (true)
    {
        var version = ProductPaths.ReadVersionFromSystemRoot(ProductPaths.MasterApp(master));
        Console.Clear();
        Console.WriteLine("CJL System - ADMINISTRACAO DO MESTRE");
        Console.WriteLine($"Versao {version.Version}  |  {version.PatchLabel}  |  Runtime {version.Runtime:000}  |  Layout 5");
        Console.WriteLine(new string('-', 68));
        Console.WriteLine("1. Abrir CJL System Mestre");
        Console.WriteLine("2. Informacoes do sistema");
        Console.WriteLine("3. Verificar integridade");
        Console.WriteLine("4. Verificar Banco / Repositorio");
        Console.WriteLine("5. Patches e atualizacoes do Mestre");
        Console.WriteLine("6. Estacoes conectadas");
        Console.WriteLine("7. Recursos do sistema");
        Console.WriteLine("8. Logs e diagnostico");
        Console.WriteLine("9. Instalar / Atualizar / Reparar estacao");
        Console.WriteLine("10. Exportar Snapshot de Desenvolvimento");
        Console.WriteLine("0. Sair");
        Console.Write("\nOpcao: ");
        var choice = (Console.ReadLine() ?? "").Trim();
        if (choice == "0") return;
        try
        {
            switch (choice)
            {
                case "1": Launch(master, "CJL.Host.exe", "--master", master, "--direct-master"); break;
                case "2": await RunBridge(master, "info"); break;
                case "3": await RunBridge(master, "integrity"); break;
                case "4": await RunBridge(master, "diagnose"); break;
                case "5": ScheduleUpdate(master, logPath); return;
                case "6": await RunBridge(master, "stations"); break;
                case "7": await RunBridge(master, "resources"); break;
                case "8": await RunBridge(master, "diagnose"); break;
                case "9": Launch(master, "CJL.Setup.exe", "--master", master); break;
                case "10": await ExportSnapshot(master); break;
                default: Console.WriteLine("Opcao invalida."); break;
            }
        }
        catch (Exception ex)
        {
            Log(logPath, "ADMIN_ERRO", ex.ToString());
            Console.WriteLine("FALHA: " + ex.Message);
        }
        Console.WriteLine("\nPressione ENTER para continuar.");
        Console.ReadLine();
    }
}

static async Task RunBridge(string master, string command)
{
    var result = await ProcessUtil.RunAsync(ProductPaths.MasterPython(master), new[] { "-B", "-I", "-S", ProductPaths.MasterHostBridge(master), command, master }, master);
    Console.WriteLine(string.IsNullOrWhiteSpace(result.StdOut) ? result.StdErr : result.StdOut);
    if (result.ExitCode != 0) throw new InvalidOperationException(CleanResult(result));
}

static async Task ExportSnapshot(string master)
{
    var script = Path.Combine(master, "Dev", "Tools", "snapshot_export.py");
    if (!File.Exists(script)) throw new FileNotFoundException("Exportador de Snapshot ausente.", script);
    var result = await ProcessUtil.RunAsync(ProductPaths.MasterPython(master), new[] { "-B", "-I", "-S", script, "--root", master }, master);
    Console.WriteLine(result.StdOut);
    if (result.ExitCode != 0) throw new InvalidOperationException(CleanResult(result));
}

static void ScheduleUpdate(string master, string logPath)
{
    var source=Path.Combine(ProductPaths.MasterUpdates(master),"Apply-Worker.ps1");
    if(!File.Exists(source)) throw new FileNotFoundException("Worker externo de atualizacao ausente.",source);
    var inbox=Path.Combine(ProductPaths.MasterUpdates(master),"In"); Directory.CreateDirectory(inbox);
    var patches=Directory.GetFiles(inbox,"*.zip",SearchOption.TopDirectoryOnly);
    if(patches.Length!=1) throw new InvalidOperationException($"Esperado exatamente 1 patch em Updates\\In; encontrados {patches.Length}.");
    var tempRoot=Path.Combine(Path.GetTempPath(),"CJL","UpdateWorker"); Directory.CreateDirectory(tempRoot);
    var worker=Path.Combine(tempRoot,$"CJL-Update-{Guid.NewGuid():N}.ps1"); File.Copy(source,worker,true);
    var psi=new System.Diagnostics.ProcessStartInfo("powershell.exe")
    {
        WorkingDirectory=Path.GetDirectoryName(master)!, UseShellExecute=false, CreateNoWindow=true,
        Arguments=$"-NoLogo -NoProfile -ExecutionPolicy Bypass -File \"{worker}\" -Root \"{master}\" -Patch \"{patches[0]}\" -Restart"
    };
    var p=System.Diagnostics.Process.Start(psi) ?? throw new InvalidOperationException("Nao foi possivel iniciar o worker externo de atualizacao.");
    Log(logPath,"UPDATE",$"Worker externo iniciado. PID={p.Id}; patch={Path.GetFileName(patches[0])}");
    Console.WriteLine("Atualizacao agendada. O Bootstrap sera encerrado e o worker externo aguardara todos os processos CJL liberarem os arquivos.");
}


static async Task SelfTestAsync(string master, string? hostBin, string logPath)
{
    var version = MasterValidator.ValidateBasic(master, allowStaleHost: true);
    await MasterValidator.ValidateDeepAsync(master, allowStaleHost: true);
    var entry = Path.Combine(ProductPaths.MasterApp(master), "Inicializacao", "iniciar.py");
    if (!File.Exists(ProductPaths.MasterPython(master)) || !File.Exists(ProductPaths.MasterPython(master, true)) || !File.Exists(entry))
        throw new InvalidOperationException("Pre-requisitos do modo Mestre direto estao incompletos.");
    var adminStore = await ProcessUtil.RunAsync(ProductPaths.MasterPython(master), new[] { "-B", "-I", "-S", ProductPaths.MasterHostBridge(master), "validate-admin-store", master }, master);
    if (adminStore.ExitCode != 0) throw new InvalidOperationException("Armazenamento administrativo invalido: " + CleanResult(adminStore));
    if (!string.IsNullOrWhiteSpace(hostBin)) MasterValidator.ValidateHostBuildDirectory(master, hostBin, requireCurrentRelease: true);
    Log(logPath, "SELFTEST", $"OK version={version.Version} {version.StructuralId} {version.IncrementalId} {version.SecurityId} layout=5");
}
