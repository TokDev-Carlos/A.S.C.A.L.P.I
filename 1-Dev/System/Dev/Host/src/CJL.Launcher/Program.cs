using System.Diagnostics;
using CJL.Shared;

try
{
    var root=ProductPaths.FindMasterRoot(AppContext.BaseDirectory);
    var bootstrap=Path.Combine(ProductPaths.MasterHostBin(root),"CJL.Bootstrap.exe");
    if(!File.Exists(bootstrap)) throw new FileNotFoundException("CJL.Bootstrap.exe ausente. Execute a preparacao da Base 5.",bootstrap);
    var psi=new ProcessStartInfo{FileName=bootstrap,WorkingDirectory=root,UseShellExecute=false};
    foreach(var arg in args) psi.ArgumentList.Add(arg);
    using var process=Process.Start(psi) ?? throw new InvalidOperationException("Falha ao iniciar o Bootstrap CJL.");
    process.WaitForExit(); return process.ExitCode;
}
catch(Exception ex)
{
    Console.Error.WriteLine("[CJL] FALHA DE INICIALIZACAO: "+ex.Message);
    Console.WriteLine("Pressione ENTER para sair."); Console.ReadLine(); return 1;
}
