"""PDF da O.P. a partir do .xlsx gerado.

- "excel": Microsoft Excel no Windows (mesmo motor do VBA = PDF idêntico ao atual).
- "libreoffice": LibreOffice sem tela (para testes fora do Windows; aparência muito próxima).
- "auto": Excel quando existir, senão LibreOffice.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_PS = r"""
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
try {
  $xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.ScreenUpdating = $false
  $wb = $xl.Workbooks.Open($args[0], 0, $true)
  try { $wb.ExportAsFixedFormat(0, $args[1], 0, $true, $false) } finally { $wb.Close($false) }
} finally { $xl.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
"""

_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooSetupSystemLocale" oor:op="fuse"><value>pt-BR</value></prop></item>
<item oor:path="/org.openoffice.Setup/L10N"><prop oor:name="ooLocale" oor:op="fuse"><value>pt-BR</value></prop></item>
</oor:items>
"""


class ErroPDF(RuntimeError):
    pass


def excel_disponivel() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application"))
        return True
    except OSError:
        return False


def libreoffice() -> str | None:
    for nome in ("soffice", "libreoffice"):
        achado = shutil.which(nome)
        if achado:
            return achado
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.exists(p):
            return p
    return None


def motor_escolhido(motor: str = "auto") -> str:
    if motor == "auto":
        if excel_disponivel():
            return "excel"
        if libreoffice():
            return "libreoffice"
        raise ErroPDF("NENHUM MOTOR DE PDF DISPONÍVEL (INSTALE O EXCEL OU O LIBREOFFICE).")
    return motor


def gerar_pdf(xlsx: bytes, motor: str = "auto", timeout: int = 180) -> bytes:
    motor = motor_escolhido(motor)
    with tempfile.TemporaryDirectory(prefix="ascalpi_pdf_") as tmp:
        tmp = Path(tmp)
        entrada = tmp / "op.xlsx"
        saida = tmp / "op.pdf"
        entrada.write_bytes(xlsx)
        if motor == "excel":
            script = tmp / "exportar.ps1"
            script.write_text(_PS, encoding="utf-8-sig")
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                                str(entrada), str(saida)], capture_output=True, text=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif motor == "libreoffice":
            exe = libreoffice()
            if not exe:
                raise ErroPDF("LIBREOFFICE NÃO ENCONTRADO.")
            perfil = tmp / "perfil"
            (perfil / "user").mkdir(parents=True)
            (perfil / "user" / "registrymodifications.xcu").write_text(_XCU, encoding="utf-8")
            r = subprocess.run([exe, f"-env:UserInstallation={perfil.as_uri()}", "--headless", "--norestore",
                                "--convert-to", "pdf", "--outdir", str(tmp), str(entrada)],
                               capture_output=True, text=True, timeout=timeout)
        else:
            raise ErroPDF(f"MOTOR DE PDF DESCONHECIDO: {motor}")
        if not saida.exists() or saida.stat().st_size == 0:
            raise ErroPDF(f"FALHA AO GERAR PDF ({motor}): {(r.stderr or r.stdout).strip()[:500]}")
        return saida.read_bytes()
