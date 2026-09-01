using System;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.Win32;
using CJL.Shared;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace CJL.Setup;

public sealed class SetupApp : Application
{
    [STAThread] public static int Main(string[] args)
    {
        var app = new SetupApp();
        app.Run(new SetupWindow(Arg(args,"--master") ?? SafeMaster()));
        return 0;
    }
    static string? Arg(string[] args,string name) { var i=Array.FindIndex(args,x=>x.Equals(name,StringComparison.OrdinalIgnoreCase)); return i>=0&&i+1<args.Length?args[i+1]:null; }
    static string SafeMaster() { try { return ProductPaths.FindMasterRoot(); } catch { return ""; } }
}

public sealed class SetupWindow : Window
{
    readonly TextBox master = new(){MinWidth=520,Height=36,VerticalContentAlignment=VerticalAlignment.Center};
    readonly TextBox install = new(){MinWidth=520,Height=36,VerticalContentAlignment=VerticalAlignment.Center,Text=StationInstall.DefaultInstallRoot};
    readonly TextBlock status = new(){Text="PRONTO",TextWrapping=TextWrapping.Wrap,Margin=new Thickness(0,10,0,0),FontWeight=FontWeights.SemiBold,Foreground=new SolidColorBrush(Color.FromRgb(47,72,92))};
    readonly ProgressBar progress = new(){Minimum=0,Maximum=100,Height=10,Margin=new Thickness(0,10,0,0)};
    readonly Button installButton = new(){Content="INSTALAR / ATUALIZAR / REPARAR",Height=46,Margin=new Thickness(0,18,0,0),FontWeight=FontWeights.Bold};

    public SetupWindow(string proposedMaster)
    {
        Title="CJL System — Instalar / Atualizar / Reparar Estação";
        Width=900; Height=600; MinWidth=760; MinHeight=520;
        WindowStartupLocation=WindowStartupLocation.CenterScreen;
        WindowStyle=WindowStyle.SingleBorderWindow;
        ResizeMode=ResizeMode.CanResizeWithGrip;
        ShowInTaskbar=true;
        Background=new SolidColorBrush(Color.FromRgb(244,247,250));
        master.Text=proposedMaster;
        ApplyIcon(proposedMaster);
        Content=Build();
        installButton.Click += async (_,__) => await InstallAsync();
    }

    void ApplyIcon(string proposedMaster)
    {
        try
        {
            if(string.IsNullOrWhiteSpace(proposedMaster)) return;
            var iconPath=Path.Combine(ProductPaths.MasterApp(ProductPaths.Normalize(proposedMaster)),"Recursos","CJL.ico");
            if(File.Exists(iconPath)) Icon=BitmapFrame.Create(new Uri(iconPath,UriKind.Absolute));
        }
        catch { }
    }

    UIElement Build()
    {
        var root=new Grid();
        root.RowDefinitions.Add(new RowDefinition{Height=GridLength.Auto});
        root.RowDefinitions.Add(new RowDefinition{Height=new GridLength(1,GridUnitType.Star)});
        var header=new Border{Background=new SolidColorBrush(Color.FromRgb(15,93,168)),Padding=new Thickness(34,24,34,22)};
        var hs=new StackPanel();
        hs.Children.Add(new TextBlock{Text="CJL System",Foreground=Brushes.White,FontSize=30,FontWeight=FontWeights.Bold});
        hs.Children.Add(new TextBlock{Text="ESTAÇÃO · INSTALL / UPDATE / REPAIR",Foreground=new SolidColorBrush(Color.FromRgb(220,235,249)),FontSize=14,FontWeight=FontWeights.SemiBold,Margin=new Thickness(0,2,0,0)});
        header.Child=hs; Grid.SetRow(header,0); root.Children.Add(header);
        var panel=new StackPanel{Margin=new Thickness(38,30,38,32)};
        panel.Children.Add(StepTitle("1","SISTEMA MESTRE")); panel.Children.Add(Row(master,"LOCALIZAR...",()=>Browse(master)));
        panel.Children.Add(StepTitle("2","PASTA LOCAL",22)); panel.Children.Add(Row(install,"ALTERAR...",()=>Browse(install)));
        panel.Children.Add(StepTitle("3","PROCESSO",22)); panel.Children.Add(progress); panel.Children.Add(status);
        StylePrimary(installButton); panel.Children.Add(installButton);
        var scroll=new ScrollViewer{Content=panel,VerticalScrollBarVisibility=ScrollBarVisibility.Auto}; Grid.SetRow(scroll,1); root.Children.Add(scroll);
        return root;
    }

    static TextBlock StepTitle(string number,string title,double top=0) => new(){Text=$"{number}. {title}",FontSize=13,FontWeight=FontWeights.Bold,Foreground=new SolidColorBrush(Color.FromRgb(12,55,91)),Margin=new Thickness(0,top,0,8)};
    static void StylePrimary(Button button){button.Background=new SolidColorBrush(Color.FromRgb(24,107,190));button.Foreground=Brushes.White;button.BorderBrush=new SolidColorBrush(Color.FromRgb(18,83,147));button.BorderThickness=new Thickness(1);}
    static UIElement Row(TextBox box,string caption,Action click){var g=new Grid();g.ColumnDefinitions.Add(new ColumnDefinition{Width=new GridLength(1,GridUnitType.Star)});g.ColumnDefinitions.Add(new ColumnDefinition{Width=GridLength.Auto});Grid.SetColumn(box,0);g.Children.Add(box);var b=new Button{Content=caption,Margin=new Thickness(10,0,0,0),Padding=new Thickness(15,7,15,7),MinWidth=112,Height=36,FontWeight=FontWeights.SemiBold};b.Click+=(_,__)=>click();Grid.SetColumn(b,1);g.Children.Add(b);return g;}
    void Browse(TextBox target){var d=new OpenFolderDialog{Title=target==master?"Selecione a raiz do Mestre CJL System":"Selecione a pasta local",InitialDirectory=Directory.Exists(target.Text)?target.Text:null};if(d.ShowDialog(this)==true)target.Text=d.FolderName;}
    void Stage(int n,int total,string text,double value){status.Text=$"ETAPA {n}/{total} · {text}";progress.Value=value;}

    async Task InstallAsync()
    {
        installButton.IsEnabled=false; master.IsEnabled=false; install.IsEnabled=false;
        string? work=null;
        try
        {
            Stage(1,8,"VALIDANDO MESTRE",7);
            var masterRoot=ProductPaths.Normalize(master.Text); var remote=MasterValidator.ValidateBasic(masterRoot); await MasterValidator.ValidateDeepAsync(masterRoot);
            Stage(2,8,"PREPARANDO ESTAÇÃO",15);
            var installRoot=ProductPaths.Normalize(install.Text); ValidateInstallRoot(installRoot,masterRoot); Directory.CreateDirectory(installRoot); StationInstall.EnsureTransientLayout(masterRoot);
            Stage(3,8,"VALIDANDO WINDOWS / WEBVIEW2",23); await EnsureWebView2Async(masterRoot);
            Stage(4,8,"PRESERVANDO OU REPARANDO RUNTIME",36); await EnsurePythonAsync(masterRoot,installRoot);
            Stage(5,8,"PREPARANDO APP + HOST",52); work=StagePayload(masterRoot,installRoot);
            Stage(6,8,"VALIDANDO STAGING",68); await StationInstall.ValidateInstalledAsync(Path.Combine(work,"App"),installRoot,masterRoot); MasterValidator.ValidateHostBuildDirectory(masterRoot,Path.Combine(work,"Host"),true);
            Stage(7,8,"COMMIT ATÔMICO",82); Commit(work,installRoot); work=null; await StationInstall.ValidatePythonLocalAsync(installRoot,masterRoot);
            Stage(8,8,"ESTADO E ATALHOS",94); CopyLegal(masterRoot,installRoot); SaveState(masterRoot,installRoot); CreateShortcuts(masterRoot,installRoot); ArchiveLegacyStation(masterRoot,installRoot);
            progress.Value=100; status.Text=$"CONCLUÍDO · {remote} · {installRoot}";
            MessageBox.Show(this,"CJL System instalado/atualizado/reparado e validado. Runtime e configurações locais foram preservados quando íntegros.","CJL System",MessageBoxButton.OK,MessageBoxImage.Information);
        }
        catch(Exception ex){status.Text="FALHA · "+ex.Message;MessageBox.Show(this,ex.Message,"Falha na instalação/reparo",MessageBoxButton.OK,MessageBoxImage.Error);}
        finally{if(work is not null)FileUtil.DeleteTreeBestEffort(work);installButton.IsEnabled=true;master.IsEnabled=true;install.IsEnabled=true;}
    }

    static void ValidateInstallRoot(string installRoot,string masterRoot)
    {
        if(!Path.IsPathFullyQualified(installRoot)) throw new InvalidOperationException("A pasta local deve ser caminho absoluto.");
        if(installRoot.StartsWith(@"\\",StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("A estação deve ficar em disco local.");
        if(installRoot.StartsWith(ProductPaths.Normalize(masterRoot)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("A estação não pode ficar dentro do Mestre.");
        var drive=new DriveInfo(Path.GetPathRoot(installRoot)!); if(drive.IsReady && drive.AvailableFreeSpace<1_000_000_000L) throw new InvalidOperationException("Espaço livre insuficiente.");
    }

    static string StagePayload(string masterRoot,string installRoot)
    {
        var root=Path.Combine(installRoot,".staging","Install."+Guid.NewGuid().ToString("N")); FileUtil.DeleteTreeBestEffort(root); Directory.CreateDirectory(root);
        FileUtil.CopyTree(ProductPaths.MasterApp(masterRoot),Path.Combine(root,"App"));
        var host=ProductPaths.MasterHostBin(masterRoot); if(!Directory.Exists(host))throw new InvalidOperationException("Host\\Bin não preparado no Mestre.");
        FileUtil.CopyTree(host,Path.Combine(root,"Host"));
        return root;
    }

    static void Commit(string staging,string installRoot)
    {
        var app=Path.Combine(staging,"App"); var host=Path.Combine(staging,"Host");
        FileUtil.AtomicReplaceDirectory(app,Path.Combine(installRoot,"App"));
        FileUtil.AtomicReplaceDirectory(host,Path.Combine(installRoot,"Host"));
        FileUtil.DeleteTreeBestEffort(staging);
    }

    static async Task EnsurePythonAsync(string masterRoot,string installRoot)
    {
        var target=Path.Combine(installRoot,"Runtime","Python");
        if(Directory.Exists(target)&&File.Exists(Path.Combine(target,"python.exe")))
        {
            try{await StationInstall.ValidatePythonAgainstMasterAsync(installRoot,masterRoot);return;}catch{}
        }
        var source=Path.Combine(ProductPaths.MasterRuntimeRoot(masterRoot),"Python"); if(!Directory.Exists(source))throw new InvalidOperationException("Runtime Python oficial ausente no Mestre.");
        var stage=Path.Combine(installRoot,".staging","Python."+Guid.NewGuid().ToString("N")); try{FileUtil.CopyTree(source,stage);Directory.CreateDirectory(Path.Combine(installRoot,"Runtime"));FileUtil.AtomicReplaceDirectory(stage,target);await StationInstall.ValidatePythonAgainstMasterAsync(installRoot,masterRoot);}finally{if(Directory.Exists(stage))FileUtil.DeleteTreeBestEffort(stage);}
    }


    static void CopyLegal(string masterRoot,string installRoot)
    {
        foreach(var name in new[]{"COPYRIGHT.txt","LICENSE.txt"})
        {
            var source=Path.Combine(masterRoot,name);if(!File.Exists(source))throw new InvalidOperationException("Arquivo legal ausente no Mestre: "+name);
            File.Copy(source,Path.Combine(installRoot,name),true);
        }
    }
    static void SaveState(string masterRoot,string installRoot)
    {
        new InstallationState{MasterRoot=masterRoot,MasterId=ProductPaths.ReadMasterId(masterRoot),InstanceId=ProductPaths.InstanceId(masterRoot),InstallRoot=installRoot,InstalledAt=DateTimeOffset.Now.ToString("O")}.Save();
        var cfg=Path.Combine(installRoot,"Config");Directory.CreateDirectory(cfg);File.WriteAllText(Path.Combine(cfg,"master.path"),masterRoot,new System.Text.UTF8Encoding(false));
    }

    static void CreateShortcuts(string masterRoot,string installRoot)
    {
        var host=Path.Combine(installRoot,"Host","CJL.Host.exe");var uninstaller=Path.Combine(installRoot,"Host","CJL.Uninstall.exe");var icon=Path.Combine(installRoot,"App","Recursos","CJL.ico");
        var desktop=Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);var menu=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu),"Programs","CJL System");
        ShortcutUtil.Create(Path.Combine(desktop,"CJL System.lnk"),host,"--master \""+masterRoot+"\" --install \""+installRoot+"\"",installRoot,icon);
        ShortcutUtil.Create(Path.Combine(menu,"CJL System.lnk"),host,"--master \""+masterRoot+"\" --install \""+installRoot+"\"",installRoot,icon);
        ShortcutUtil.Create(Path.Combine(menu,"Desinstalar CJL System.lnk"),uninstaller,"--master \""+masterRoot+"\" --install \""+installRoot+"\"",installRoot,icon);
    }

    static void ArchiveLegacyStation(string masterRoot,string installRoot)
    {
        var legacy=Path.Combine(installRoot,"Aplicacao"); if(!Directory.Exists(legacy))return;
        var archiveRoot=Path.Combine(ProductPaths.LocalStateRoot(masterRoot),"Archive","LegacyStation");
        Directory.CreateDirectory(archiveRoot);
        var destination=Path.Combine(archiveRoot,"LegacyApplication_"+DateTimeOffset.Now.ToString("yyyyMMdd_HHmmss"));
        Directory.Move(legacy,destination);
    }

    static async Task EnsureWebView2Async(string masterRoot)
    {
        var probe=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),"Microsoft","EdgeWebView","Application"); if(Directory.Exists(probe))return;
        var published=Path.Combine(masterRoot,"Host","Dependencies","MicrosoftEdgeWebview2Setup.exe");var installer=published;var downloaded=false;
        if(!File.Exists(installer))
        {
            installer=Path.Combine(Path.GetTempPath(),"MicrosoftEdgeWebview2Setup.exe");
            try{using var client=new HttpClient{Timeout=TimeSpan.FromMinutes(3)};var bytes=await client.GetByteArrayAsync("https://go.microsoft.com/fwlink/p/?LinkId=2124703");await File.WriteAllBytesAsync(installer,bytes);downloaded=true;var cert=new System.Security.Cryptography.X509Certificates.X509Certificate2(System.Security.Cryptography.X509Certificates.X509Certificate.CreateFromSignedFile(installer));if(!cert.Subject.Contains("Microsoft",StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Assinatura Microsoft do WebView2 não reconhecida.");}
            catch(Exception ex){throw new InvalidOperationException("WebView2 ausente e não foi possível obter o instalador oficial. Publique-o em Host\\Dependencies ou conecte a máquina à internet.",ex);}
        }
        try{var result=await ProcessUtil.RunAsync(installer,new[]{"/silent","/install"},masterRoot);if(result.ExitCode!=0)throw new InvalidOperationException("Falha ao instalar WebView2 Runtime.");}
        finally{if(downloaded)try{File.Delete(installer);}catch{}}
    }
}
