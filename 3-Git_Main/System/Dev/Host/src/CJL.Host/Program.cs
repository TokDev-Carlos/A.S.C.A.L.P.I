using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;
using CJL.Shared;

namespace CJL.Host;

public sealed class HostApp : Application
{
    [STAThread]
    public static int Main(string[] args)
    {
        var selfTest = HasFlag(args, "--self-test");
        try
        {
            var directMaster = HasFlag(args, "--direct-master");
            var master = Arg(args, "--master") ?? (directMaster ? ProductPaths.FindMasterRoot() : LoadMasterFromInstall(Arg(args, "--install")));
            var install = directMaster
                ? ProductPaths.Normalize(master)
                : Arg(args, "--install") ?? Directory.GetParent(AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar))!.FullName;

            if (selfTest)
                return SelfTestAsync(master, install, directMaster).GetAwaiter().GetResult();

            var app = new HostApp();
            app.DispatcherUnhandledException += (_, e) =>
            {
                MessageBox.Show(e.Exception.Message, "CJL System", MessageBoxButton.OK, MessageBoxImage.Error);
                e.Handled = true;
            };
            app.Run(new HostWindow(master, install, directMaster));
            return 0;
        }
        catch (Exception ex)
        {
            if (selfTest) Console.Error.WriteLine("SELFTEST FALHOU: " + ex);
            else MessageBox.Show(ex.Message, "CJL System — Falha do Host", MessageBoxButton.OK, MessageBoxImage.Error);
            return 1;
        }
    }

    static string? Arg(string[] args, string name)
    {
        var i = Array.FindIndex(args, x => x.Equals(name, StringComparison.OrdinalIgnoreCase));
        return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
    }

    static bool HasFlag(string[] args, string name)
        => args.Any(x => x.Equals(name, StringComparison.OrdinalIgnoreCase));

    static string LoadMasterFromInstall(string? install)
    {
        var root = install ?? Directory.GetParent(AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar))!.FullName;
        return File.ReadAllText(Path.Combine(root, "Config", "master.path"), Encoding.UTF8).Trim();
    }

    static async Task<int> SelfTestAsync(string master, string install, bool directMaster)
    {
        master = ProductPaths.Normalize(master);
        await MasterValidator.ValidateDeepAsync(master, allowStaleHost: true);
        if (directMaster)
        {
            var python = ProductPaths.MasterPython(master, true);
            var entry = Path.Combine(ProductPaths.MasterApp(master), "Inicializacao", "iniciar.py");
            if (!File.Exists(python) || !File.Exists(entry))
                throw new InvalidOperationException("Modo Mestre direto não possui Runtime Python ou inicializador oficial.");
        }
        else
        {
            _ = ProductPaths.InstalledPython(install, true);
            var entry = Path.Combine(ProductPaths.InstalledApp(install), "Inicializacao", "iniciar.py");
            if (!File.Exists(entry)) throw new InvalidOperationException("Instalação local não possui inicializador Python oficial.");
        }
        Console.WriteLine("SELFTEST OK");
        return 0;
    }
}

public sealed class HostWindow : Window
{
    readonly string masterRoot;
    readonly string installRoot;
    readonly string stateRoot;
    readonly bool directMaster;
    readonly string hostLog;
    readonly WebView2 web = new();
    readonly Grid loadingLayer = new();
    readonly TextBlock loadingStatus = new();
    Process? backend;
    InstanceRegistry? instance;
    bool closing;
    readonly DispatcherTimer restartTimer = new() { Interval = TimeSpan.FromSeconds(1) };

    public HostWindow(string master, string install, bool direct)
    {
        masterRoot = ProductPaths.Normalize(master);
        installRoot = ProductPaths.Normalize(install);
        directMaster = direct;
        stateRoot = ProductPaths.LocalStateRoot(masterRoot);
        Directory.CreateDirectory(Path.Combine(stateRoot, "Logs"));
        hostLog = Path.Combine(stateRoot, "Logs", $"host_{DateTime.Now:yyyyMMdd_HHmmss}_{Environment.ProcessId}.log");

        Title = directMaster ? "CJL System — MESTRE" : "CJL System";
        Width = 1440;
        Height = 900;
        MinWidth = 1024;
        MinHeight = 700;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        WindowState = WindowState.Maximized;
        WindowStyle = WindowStyle.SingleBorderWindow;
        ResizeMode = ResizeMode.CanResizeWithGrip;
        ShowInTaskbar = true;
        Background = new SolidColorBrush(Color.FromRgb(14,47,76));
        UseLayoutRounding = true;
        ApplyIcon();
        Content = BuildShell();
        web.NavigationCompleted += (_, e) =>
        {
            if (e.IsSuccess)
            {
                loadingLayer.Visibility = Visibility.Collapsed;
                Log("UI_PRONTA", "Interface WebView2 carregada.");
            }
            else
            {
                loadingStatus.Text = "NÃO FOI POSSÍVEL CARREGAR A INTERFACE";
                Log("UI_FALHA", $"WebErrorStatus={e.WebErrorStatus}");
            }
        };
        Loaded += async (_, __) => await StartAsync();
        Closing += OnClosing;
        restartTimer.Tick += async (_, __) => await CheckRestartAsync();
    }

    void ApplyIcon()
    {
        try
        {
            var iconPath = directMaster
                ? Path.Combine(ProductPaths.MasterApp(masterRoot), "Recursos", "CJL.ico")
                : Path.Combine(ProductPaths.InstalledApp(installRoot), "Recursos", "CJL.ico");
            if (File.Exists(iconPath)) Icon = BitmapFrame.Create(new Uri(iconPath, UriKind.Absolute));
        }
        catch { }
    }

    UIElement BuildShell()
    {
        var root = new Grid();
        web.Visibility = Visibility.Visible;
        root.Children.Add(web);

        loadingLayer.Background = new SolidColorBrush(Color.FromRgb(14,47,76));
        var card = new Border
        {
            Width = 430,
            Padding = new Thickness(34,30,34,28),
            CornerRadius = new CornerRadius(18),
            Background = new SolidColorBrush(Color.FromRgb(247,250,252)),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        var stack = new StackPanel();
        stack.Children.Add(new TextBlock
        {
            Text = "CJL System",
            FontSize = 30,
            FontWeight = FontWeights.Bold,
            Foreground = new SolidColorBrush(Color.FromRgb(9,43,72)),
            HorizontalAlignment = HorizontalAlignment.Center,
        });
        stack.Children.Add(new TextBlock
        {
            Text = directMaster ? "MODO MESTRE" : "ESTAÇÃO LOCAL",
            FontSize = 11,
            FontWeight = FontWeights.Bold,
            Foreground = new SolidColorBrush(Color.FromRgb(24,107,190)),
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(0,4,0,22),
        });
        var bar = new ProgressBar { Height = 8, IsIndeterminate = true };
        stack.Children.Add(bar);
        loadingStatus.Text = "INICIANDO SISTEMA...";
        loadingStatus.FontSize = 11;
        loadingStatus.FontWeight = FontWeights.SemiBold;
        loadingStatus.Foreground = new SolidColorBrush(Color.FromRgb(70,91,108));
        loadingStatus.HorizontalAlignment = HorizontalAlignment.Center;
        loadingStatus.Margin = new Thickness(0,14,0,0);
        stack.Children.Add(loadingStatus);
        card.Child = stack;
        loadingLayer.Children.Add(card);
        root.Children.Add(loadingLayer);
        return root;
    }

    void Log(string stage, string message)
    {
        try
        {
            File.AppendAllText(hostLog, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{stage}] {message}{Environment.NewLine}", new UTF8Encoding(false));
        }
        catch { }
    }

    async Task StartAsync()
    {
        try
        {
            loadingStatus.Text = "VALIDANDO SISTEMA...";
            Log("INICIO", $"Master={masterRoot}; DirectMaster={directMaster}; Install={installRoot}");
            await MasterValidator.ValidateDeepAsync(masterRoot);
            if (!directMaster)
            {
                loadingStatus.Text = "VERIFICANDO ATUALIZAÇÕES...";
                await RunUpdaterAsync();
            }

            loadingStatus.Text = "PREPARANDO INTERFACE...";
            Directory.CreateDirectory(Path.Combine(stateRoot, "WebView"));
            var environment = await CoreWebView2Environment.CreateAsync(null, Path.Combine(stateRoot, "WebView"));
            await web.EnsureCoreWebView2Async(environment);
            web.CoreWebView2.Settings.AreDevToolsEnabled = false;
            web.CoreWebView2.Settings.IsStatusBarEnabled = false;
            web.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;

            loadingStatus.Text = "INICIANDO NÚCLEO DO CJL System...";
            await StartBackendAsync();
            loadingStatus.Text = "CARREGANDO PAINEL...";
            restartTimer.Start();
            Log("PRONTO", "Backend iniciado; aguardando conclusão da navegação WebView2.");
        }
        catch (OperationCanceledException) when (closing) { }
        catch (Exception ex)
        {
            Log("FALHA_INICIALIZACAO", ex.ToString());
            MessageBox.Show(this, $"{ex.Message}\n\nLog: {hostLog}", "CJL System — Falha de inicialização", MessageBoxButton.OK, MessageBoxImage.Error);
            closing = true;
            Close();
        }
    }

    async Task RunUpdaterAsync()
    {
        var updater = Path.Combine(installRoot, "Host", "CJL.Updater.exe");
        if (!File.Exists(updater)) return;
        var result = await ProcessUtil.RunAsync(updater, new[] { "--master", masterRoot, "--install", installRoot, "--prelaunch" }, installRoot);
        if (result.ExitCode == 3)
        {
            var marker = Path.Combine(installRoot, ".update", "host-update.pending.json");
            if (!File.Exists(marker)) throw new InvalidOperationException("Atualizador solicitou troca do Host sem publicar o worker.");
            using var document = System.Text.Json.JsonDocument.Parse(File.ReadAllText(marker));
            var worker = document.RootElement.GetProperty("worker").GetString() ?? throw new InvalidOperationException("Worker do Host inválido.");
            ProcessUtil.StartDetached(worker, new[] { "--finalize-host", "--master", masterRoot, "--install", installRoot, "--wait-pid", Environment.ProcessId.ToString(), "--restart" }, Path.GetTempPath());
            closing = true;
            Dispatcher.BeginInvoke(new Action(Close));
            throw new OperationCanceledException("Host será atualizado e reiniciado.");
        }
        if (result.ExitCode > 1) throw new InvalidOperationException("Atualização local falhou: " + (result.StdErr + result.StdOut).Trim());
    }

    async Task StartBackendAsync()
    {
        string python;
        string entry;
        string workingDirectory;

        if (directMaster)
        {
            python = ProductPaths.MasterPython(masterRoot, true);
            entry = Path.Combine(ProductPaths.MasterApp(masterRoot), "Inicializacao", "iniciar.py");
            workingDirectory = masterRoot;
        }
        else
        {
            python = ProductPaths.InstalledPython(installRoot, true);
            entry = Path.Combine(ProductPaths.InstalledApp(installRoot), "Inicializacao", "iniciar.py");
            workingDirectory = installRoot;
        }

        if (!File.Exists(entry)) throw new FileNotFoundException("Inicializador Python oficial não encontrado.", entry);

        var token = Convert.ToBase64String(RandomNumberGenerator.GetBytes(36));
        var env = new Dictionary<string, string?>
        {
            ["CJL_NETWORK_ROOT"] = masterRoot,
            ["CJL_STATE_ROOT"] = stateRoot,
            ["CJL_INSTANCE_ID"] = ProductPaths.InstanceId(masterRoot),
            ["CJL_LIFECYCLE_TOKEN"] = token,
            ["CJL_BROWSER_MANAGED"] = "1",
            ["CJL_HOST_MODE"] = directMaster ? "MASTER_DIRECT" : "STATION",
            ["CJL_HOST_PID"] = Environment.ProcessId.ToString(),
        };
        if (!directMaster) env["CJL_INSTALL_ROOT"] = installRoot;

        var start = new ProcessStartInfo(python)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = workingDirectory,
        };
        start.ArgumentList.Add("-B");
        start.ArgumentList.Add("-I");
        start.ArgumentList.Add("-S");
        start.ArgumentList.Add(entry);
        foreach (var kv in env) start.Environment[kv.Key] = kv.Value;

        backend = new Process { StartInfo = start, EnableRaisingEvents = true };
        backend.Exited += (_, __) => Dispatcher.Invoke(async () => await BackendExitedAsync());
        if (!backend.Start()) throw new InvalidOperationException("Não foi possível iniciar o núcleo Python.");
        Log("PYTHON", $"PID={backend.Id}; Executable={python}; Entry={entry}");

        instance = await HttpUtil.WaitForInstanceAsync(stateRoot, backend, TimeSpan.FromSeconds(30))
            ?? throw new InvalidOperationException("O núcleo Python não publicou a porta local dentro do tempo esperado.");
        Log("HTTP", $"Port={instance.Port}");
        web.Source = new Uri($"http://127.0.0.1:{instance.Port}/");
    }

    async Task BackendExitedAsync()
    {
        if (closing) return;
        restartTimer.Stop();
        Log("PYTHON_EXIT", backend is null ? "Backend encerrado." : $"PID={backend.Id}; ExitCode={(backend.HasExited ? backend.ExitCode : -1)}");

        var request = Path.Combine(stateRoot, "Instancia", "restart-update.request");
        if (!directMaster && File.Exists(request))
        {
            try
            {
                File.Delete(request);
                await RunUpdaterAsync();
                await StartBackendAsync();
                restartTimer.Start();
                return;
            }
            catch (OperationCanceledException) when (closing) { return; }
            catch (Exception ex)
            {
                Log("UPDATE_ERRO", ex.ToString());
                MessageBox.Show(this, ex.Message, "Falha na atualização", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
        closing = true;
        Close();
    }

    async Task CheckRestartAsync()
    {
        if (directMaster) return;
        var request = Path.Combine(stateRoot, "Instancia", "restart-update.request");
        if (!File.Exists(request) || backend is null || backend.HasExited) return;
        restartTimer.Stop();
        await ShutdownBackendAsync();
    }

    async void OnClosing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        if (closing) return;
        e.Cancel = true;
        closing = true;
        restartTimer.Stop();
        Log("ENCERRAMENTO", "Fechamento solicitado pela janela Host.");
        await ShutdownBackendAsync();
        Close();
    }

    async Task ShutdownBackendAsync()
    {
        if (backend is null || backend.HasExited) return;
        if (instance is not null) await HttpUtil.ShutdownAsync(instance.Port, instance.Token);
        var deadline = DateTime.UtcNow.AddSeconds(12);
        while (!backend.HasExited && DateTime.UtcNow < deadline) await Task.Delay(200);
        if (!backend.HasExited)
        {
            try
            {
                Log("KILL", $"Finalização graciosa excedeu limite; encerrando árvore PID={backend.Id}.");
                backend.Kill(true);
            }
            catch (Exception ex) { Log("KILL_ERRO", ex.Message); }
        }
        try { await backend.WaitForExitAsync(); } catch { }
        Log("ENCERRADO", "Núcleo Python finalizado.");
    }
}
