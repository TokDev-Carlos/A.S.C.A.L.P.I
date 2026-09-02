[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "Selecionar Patch ASCALPI"
$dialog.Filter = "Patch ZIP (*.zip)|*.zip"
$dialog.Multiselect = $false
$dialog.CheckFileExists = $true
$dialog.CheckPathExists = $true
$dialog.RestoreDirectory = $true

try {
    $downloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads"
    if (Test-Path -LiteralPath $downloads -PathType Container) {
        $dialog.InitialDirectory = $downloads
    }
}
catch {}

$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    Write-Output $dialog.FileName
    exit 0
}

exit 1
