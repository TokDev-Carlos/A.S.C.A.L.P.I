param([Parameter(Mandatory=$true)][string]$Root,[string]$Patch="",[switch]$ValidateOnly)
Set-StrictMode -Version 2.0;$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($Root)).TrimEnd('\')
$Python=Join-Path $Root 'Runtime\Python\python.exe';$Engine=Join-Path $Root 'Dev\Tools\apply_patch.py'
if(-not(Test-Path -LiteralPath $Python -PathType Leaf)){throw 'Runtime Python ausente.'};if(-not(Test-Path -LiteralPath $Engine -PathType Leaf)){throw 'Patch Engine ausente.'}
$args=@('-B','-I','-S',$Engine,'--root',$Root);if($Patch){$args+=@('--patch',$Patch)};if($ValidateOnly){$args+='--validate-only'}
& $Python @args;exit [int]$LASTEXITCODE
