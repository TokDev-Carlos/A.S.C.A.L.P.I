"""Configuração local (config.json na pasta de dados): gravação atômica; a senha dos .xlsx nunca sai daqui."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

CONFIG_PADRAO = {
    "senha_arquivos": "",      # vazio = gerada na 1ª execução e guardada só no config.json local
    "motor_pdf": "auto",
    "publicar": True,
    "pasta_xlsx": "",          # vazio = <dados>/Documentos/O.Ps
    "pasta_pdf": "",           # vazio = <dados>/Documentos/PDFs
}


class Configuracao:
    def __init__(self, pasta_dados: Path):
        self.dados = Path(pasta_dados)
        self.arquivo = self.dados / "config.json"
        if not self.arquivo.exists():
            self.salvar({})
        if not self.ler()["senha_arquivos"]:
            self.salvar({"senha_arquivos": secrets.token_urlsafe(12)})

    def ler(self) -> dict:
        try:
            atual = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            atual = {}
        return {**CONFIG_PADRAO, **{k: v for k, v in atual.items() if k in CONFIG_PADRAO}}

    def salvar(self, novos: dict) -> dict:
        cfg = {**(self.ler() if self.arquivo.exists() else CONFIG_PADRAO),
               **{k: v for k, v in novos.items() if k in CONFIG_PADRAO}}
        tmp = self.arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.arquivo)
        return cfg

    def pastas(self) -> tuple[Path, Path]:
        cfg = self.ler()
        px = Path(cfg["pasta_xlsx"]) if cfg["pasta_xlsx"] else self.dados / "Documentos" / "O.Ps"
        pp = Path(cfg["pasta_pdf"]) if cfg["pasta_pdf"] else self.dados / "Documentos" / "PDFs"
        return px, pp
