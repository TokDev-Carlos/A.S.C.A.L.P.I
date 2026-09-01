namespace CJL.Shared;

public static class ShortcutUtil
{
    public static void Create(string shortcutPath, string target, string arguments, string workingDirectory, string icon)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(shortcutPath)!);
        var type = Type.GetTypeFromProgID("WScript.Shell") ?? throw new InvalidOperationException("WScript.Shell indisponível.");
        dynamic shell = Activator.CreateInstance(type)!;
        dynamic shortcut = shell.CreateShortcut(shortcutPath);
        shortcut.TargetPath = target;
        shortcut.Arguments = arguments;
        shortcut.WorkingDirectory = workingDirectory;
        shortcut.IconLocation = icon;
        shortcut.Description = "CJL System";
        shortcut.Save();
    }
}
