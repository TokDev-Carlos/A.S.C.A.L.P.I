"""Publicação dos arquivos da O.P. (.xlsx bloqueado e .pdf) nas pastas configuradas.

Isolada do commit do banco: a O.P. já está gravada quando a publicação começa. Cada formato só substitui o arquivo
anterior depois que o novo foi gravado; a mesma O.P. nunca é publicada por duas chamadas ao mesmo tempo.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import threading
from pathlib import Path

from . import pdf
from .banco import agora
from .validacao import ErroValidacao


class Publicacao:
    def __init__(self, servico):
        self.s = servico
        self._travas: dict[int, threading.Lock] = {}
        self._mapa = threading.Lock()

    def _trava(self, op_id: int) -> threading.Lock:
        with self._mapa:
            return self._travas.setdefault(op_id, threading.Lock())

    def publicar(self, op_id: int) -> dict:
        """Grava .xlsx (bloqueado) e .pdf nas pastas configuradas.

        Cada formato só substitui o arquivo anterior depois que o novo foi gravado (R01). Se um formato falha,
        o anterior continua publicado e o resultado diz de qual revisão ele é. Nunca lança por falha de arquivo
        ou de motor: devolve estado PUBLICADA, PARCIAL ou PENDENTE com o erro de cada formato.
        """
        s = self.s
        o = s.op(op_id)
        if o["origem"] != "SISTEMA" or not o["modelo_id"]:
            raise ErroValidacao("O.P. DO HISTÓRICO LEGADO: O DOCUMENTO ORIGINAL FICA NA PASTA ANTIGA.")
        with self._trava(op_id):
            o = s.op(op_id)
            px, pp = s.pastas_publicacao()
            ant = o["arquivos"] or {}
            res = {"rev": o["rev"], "tentativa_em": agora(), "paginacao": s.config()["paginacao"],   # motor usado (G2)
                   "xlsx": ant.get("xlsx"), "xlsx_rev": ant.get("xlsx_rev"),
                   "pdf": ant.get("pdf"), "pdf_rev": ant.get("pdf_rev")}
            xlsx = nome_x = None
            try:
                nome_x, xlsx = s.gerar_documento(op_id, "xlsx", o)   # mesmo retrato da REV registrada
                px.mkdir(parents=True, exist_ok=True)
                destino_x = px / nome_x
                gravar_atomico(destino_x, xlsx)
                remover_substituido(ant.get("xlsx"), destino_x)
                res.update(xlsx=str(destino_x), xlsx_rev=o["rev"])
            except ErroValidacao:
                raise
            except Exception as e:  # noqa: BLE001
                res["xlsx_erro"] = str(e) or type(e).__name__
            if xlsx is None:
                res["pdf_erro"] = "PDF NÃO GERADO: O XLSX DESTA REVISÃO FALHOU."
            else:
                try:
                    conteudo_pdf = pdf.gerar_pdf(xlsx, s.config()["motor_pdf"])
                    res["paginas"] = _conferir_paginas(xlsx, conteudo_pdf)
                    pp.mkdir(parents=True, exist_ok=True)
                    destino_p = pp / (nome_x[:-5] + ".pdf")
                    gravar_atomico(destino_p, conteudo_pdf)
                    remover_substituido(ant.get("pdf"), destino_p)
                    res.update(pdf=str(destino_p), pdf_rev=o["rev"])
                except Exception as e:  # noqa: BLE001
                    res["pdf_erro"] = str(e) or type(e).__name__
            atuais = [res.get(f + "_rev") == o["rev"] and not res.get(f + "_erro") for f in ("xlsx", "pdf")]
            res["estado"] = "PUBLICADA" if all(atuais) else "PARCIAL" if any(atuais) else "PENDENTE"
            with s.banco.transacao() as con:
                con.execute("UPDATE ops SET arquivos = ? WHERE id = ?", (json.dumps(res, ensure_ascii=False), op_id))
                s.banco.evento(con, "OP_PUBLICADA" if res["estado"] == "PUBLICADA" else "OP_PUBLICACAO_PENDENTE",
                                  {"op": op_id, **res})
            return res


def _conferir_paginas(xlsx: bytes, conteudo_pdf: bytes) -> dict:
    """G2: páginas previstas pelas quebras x páginas do PDF real (Excel/LibreOffice). Divergência vira aviso."""
    from . import pacote, paginacao
    partes = pacote.carregar(io.BytesIO(xlsx))
    aba = pacote.abas(partes)[0]["parte"]
    previstas, reais = paginacao.paginas_previstas(partes[aba].decode("utf-8")), paginacao.paginas_pdf(conteudo_pdf)
    saida = {"previstas": previstas, "pdf": reais}
    if reais != previstas:
        saida["aviso"] = (f"PAGINAÇÃO: PREVISTAS {previstas} PÁGINA(S), O PDF SAIU COM {reais}. "
                          "CONFIRA O DOCUMENTO E AVISE (AJUSTE DO CÁLCULO DE ALTURA).")
    return saida


def gravar_atomico(destino: Path, conteudo: bytes) -> None:
    """Grava num temporário exclusivo da mesma pasta e troca de uma vez (nunca deixa arquivo pela metade)."""
    fd, nome = tempfile.mkstemp(prefix="~" + destino.stem[:40] + ".", suffix=".tmp", dir=destino.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(conteudo)
        os.replace(nome, destino)
    except BaseException:
        try:
            os.unlink(nome)
        except OSError:
            pass
        raise


def remover_substituido(antigo: str | None, novo: Path) -> None:
    """Apaga o arquivo da publicação anterior só quando ele foi substituído por outro nome já gravado."""
    if not antigo or Path(antigo) == novo:
        return
    try:
        Path(antigo).unlink(missing_ok=True)
    except OSError:
        pass
