using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using CJL.Shared;

Console.OutputEncoding = Encoding.UTF8;
try
{
    if (HasFlag("--finalize-host")) return await FinalizeHostAsync();

    var master=ProductPaths.Normalize(Arg("--master") ?? throw new InvalidOperationException("Mestre não informado."));
    var install=ProductPaths.Normalize(Arg("--install") ?? throw new InvalidOperationException("Instalação não informada."));
    MasterValidator.ValidateBasic(master);
    Directory.CreateDirectory(Path.Combine(install,".update"));

    await EnsureRuntimeAsync(master,install);

    var remoteApp=ProductPaths.MasterApp(master);
    var localApp=Path.Combine(install,"App");
    var applicationChanged=!Directory.Exists(localApp) || !SameTree(remoteApp,localApp);
    var hostChanged=StageHostIfChanged(master,install);

    if(applicationChanged)
    {
        Console.WriteLine("APP_DIVERGENT: reparando camada App por SHA-256.");
        var staging=Path.Combine(install,".update","App"); FileUtil.DeleteTreeBestEffort(staging); FileUtil.CopyTree(remoteApp,staging);
        await StationInstall.ValidateInstalledAsync(staging,install,master);
        FileUtil.AtomicReplaceDirectory(staging,localApp);
    }

    if(hostChanged)
    {
        PrepareHostFinalizeWorker(master,install);
        Console.WriteLine("HOST_UPDATE_PENDING");
        return 3;
    }

    CopyLegal(master,install);
    await StationInstall.ValidatePythonLocalAsync(install,master);
    Console.WriteLine(applicationChanged ? "APP_REPAIRED" : "UP_TO_DATE");
    return applicationChanged ? 1 : 0;
}
catch(Exception ex){Console.Error.WriteLine("FALHA: "+ex.Message);return 2;}

string? Arg(string name){var i=Array.FindIndex(args,x=>x.Equals(name,StringComparison.OrdinalIgnoreCase));return i>=0&&i+1<args.Length?args[i+1]:null;}
bool HasFlag(string name)=>args.Any(x=>x.Equals(name,StringComparison.OrdinalIgnoreCase));

static async Task EnsureRuntimeAsync(string master,string install)
{
    try{await StationInstall.ValidatePythonAgainstMasterAsync(install,master);return;}catch{}
    var source=Path.Combine(ProductPaths.MasterRuntimeRoot(master),"Python"); if(!Directory.Exists(source))throw new InvalidOperationException("Runtime Python oficial ausente no Mestre.");
    var staging=Path.Combine(install,".update","Python");FileUtil.DeleteTreeBestEffort(staging);FileUtil.CopyTree(source,staging);Directory.CreateDirectory(Path.Combine(install,"Runtime"));FileUtil.AtomicReplaceDirectory(staging,Path.Combine(install,"Runtime","Python"));
    await StationInstall.ValidatePythonAgainstMasterAsync(install,master);
}

static void CopyLegal(string master,string install)
{
    foreach(var name in new[]{"COPYRIGHT.txt","LICENSE.txt"})
    {
        var source=Path.Combine(master,name);if(!File.Exists(source))throw new InvalidOperationException("Arquivo legal ausente no Mestre: "+name);
        File.Copy(source,Path.Combine(install,name),true);
    }
}

static bool StageHostIfChanged(string master,string install)
{
    var source=ProductPaths.MasterHostBin(master);if(!Directory.Exists(source))throw new InvalidOperationException("Host\\Bin ausente no Mestre.");
    var target=Path.Combine(install,"Host");
    if(Directory.Exists(target) && SameTree(source,target)) return false;
    var staging=Path.Combine(install,".update","Host");FileUtil.DeleteTreeBestEffort(staging);FileUtil.CopyTree(source,staging);MasterValidator.ValidateHostBuildDirectory(master,staging,true);return true;
}

static bool SameTree(string a,string b)
{
    if(!Directory.Exists(a)||!Directory.Exists(b))return false;
    var ah=HashTree(a);var bh=HashTree(b);if(ah.Count!=bh.Count)return false;
    foreach(var item in ah)if(!bh.TryGetValue(item.Key,out var value)||!string.Equals(item.Value,value,StringComparison.OrdinalIgnoreCase))return false;
    return true;
}

static Dictionary<string,string> HashTree(string directory)
{
    return Directory.EnumerateFiles(directory,"*",SearchOption.AllDirectories)
        .Where(p=>!p.Split(Path.DirectorySeparatorChar).Any(x=>x.Equals("__pycache__",StringComparison.OrdinalIgnoreCase)) && !p.EndsWith(".pyc",StringComparison.OrdinalIgnoreCase))
        .ToDictionary(p=>Path.GetRelativePath(directory,p).Replace('\\','/'),FileUtil.Sha256,StringComparer.OrdinalIgnoreCase);
}

static void PrepareHostFinalizeWorker(string master,string install)
{
    var sourceUpdater=Environment.ProcessPath??throw new InvalidOperationException("Executável do atualizador não localizado.");
    var worker=Path.Combine(Path.GetTempPath(),"CJL.Updater.Worker."+Guid.NewGuid().ToString("N")+".exe");File.Copy(sourceUpdater,worker,true);
    var marker=Path.Combine(install,".update","host-update.pending.json");Directory.CreateDirectory(Path.GetDirectoryName(marker)!);
    File.WriteAllText(marker,JsonSerializer.Serialize(new{format=2,worker,master,install,prepared_at=DateTimeOffset.Now.ToString("O")},JsonOptions.Indented),new UTF8Encoding(false));
}

async Task<int> FinalizeHostAsync()
{
    var master=ProductPaths.Normalize(Arg("--master")??throw new InvalidOperationException("Mestre não informado."));
    var install=ProductPaths.Normalize(Arg("--install")??throw new InvalidOperationException("Instalação não informada."));
    _=int.TryParse(Arg("--wait-pid")??"0",out var pid);
    if(pid>0){try{using var process=Process.GetProcessById(pid);using var timeout=new CancellationTokenSource(TimeSpan.FromSeconds(30));await process.WaitForExitAsync(timeout.Token);}catch(ArgumentException){}catch(OperationCanceledException){throw new InvalidOperationException("Host anterior não encerrou dentro do prazo.");}}
    var staging=Path.Combine(install,".update","Host");var target=Path.Combine(install,"Host");if(!Directory.Exists(staging))return 0;
    var backup=target+".Anterior";FileUtil.DeleteTreeBestEffort(backup);if(Directory.Exists(target))Directory.Move(target,backup);
    try{Directory.Move(staging,target);FileUtil.DeleteTreeBestEffort(backup);}catch{if(!Directory.Exists(target)&&Directory.Exists(backup))Directory.Move(backup,target);throw;}
    try{File.Delete(Path.Combine(install,".update","host-update.pending.json"));}catch{}
    var host=Path.Combine(target,"CJL.Host.exe");if(HasFlag("--restart")&&File.Exists(host))ProcessUtil.StartDetached(host,new[]{"--master",master,"--install",install},install);
    return 0;
}
