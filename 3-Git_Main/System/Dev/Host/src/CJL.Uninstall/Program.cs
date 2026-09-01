using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using CJL.Shared;
using System.Windows;

namespace CJL.Uninstall;
public sealed class UninstallApp:Application
{
    [STAThread] public static int Main(string[] args)
    {
        try
        {
            var master=Arg(args,"--master")??throw new InvalidOperationException("Mestre não informado."); var install=Arg(args,"--install")??throw new InvalidOperationException("Instalação não informada.");
            install=ProductPaths.Normalize(install); if(!File.Exists(Path.Combine(install,"Config","master.path"))) throw new InvalidOperationException("A pasta selecionada não possui identidade de instalação CJL System.");
            var answer=MessageBox.Show("Remover o CJL System desta máquina? O Mestre, Banco, dados, documentos e backups oficiais não serão alterados.","Desinstalar CJL System",MessageBoxButton.YesNo,MessageBoxImage.Question); if(answer!=MessageBoxResult.Yes)return 0;
            RemoveShortcuts(); var state=ProductPaths.LocalStateRoot(master); var program=ProductPaths.ProgramDataRoot(master); FileUtil.DeleteTreeBestEffort(state); FileUtil.DeleteTreeBestEffort(program);
            var worker=Path.Combine(Path.GetTempPath(),"cjl-uninstall-"+Guid.NewGuid().ToString("N")+".cmd"); File.WriteAllText(worker,$"@echo off\r\nping 127.0.0.1 -n 3 >nul\r\nrmdir /s /q \"{install}\"\r\ndel /q \"%~f0\"\r\n",System.Text.Encoding.ASCII); ProcessUtil.StartDetached("cmd.exe",new[]{"/c",worker},Path.GetTempPath());
            MessageBox.Show("Desinstalação iniciada. A pasta local será removida após o encerramento desta janela.","CJL System",MessageBoxButton.OK,MessageBoxImage.Information); return 0;
        }
        catch(Exception ex){MessageBox.Show(ex.Message,"Falha na desinstalação",MessageBoxButton.OK,MessageBoxImage.Error);return 1;}
    }
    static string? Arg(string[] args,string name){var i=Array.FindIndex(args,x=>x.Equals(name,StringComparison.OrdinalIgnoreCase));return i>=0&&i+1<args.Length?args[i+1]:null;}
    static void RemoveShortcuts(){var desktop=Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);foreach(var p in new[]{Path.Combine(desktop,"CJL System.lnk"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu),"Programs","CJL System")})try{if(File.Exists(p))File.Delete(p);else if(Directory.Exists(p))Directory.Delete(p,true);}catch{}}
}
