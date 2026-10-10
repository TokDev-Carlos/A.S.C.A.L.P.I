"""G1 — editar o modelo da O.P. no Excel com segurança.

Fluxo: iniciar (cópia de trabalho) → abrir no Excel (só Windows, ação do usuário) → validar (prévia das
diferenças) → publicar nova versão (arquivo novo, ponteiro trocado numa transação) ou descartar.

Garantias:
- o arquivo publicado do modelo e os arquivos das O.P. já emitidas nunca são alterados no lugar;
- O.P. emitidas continuam no modelo da emissão (ops.modelo_arquivo);
- uma edição aberta por modelo; publicar sobre uma versão que mudou desde o início → conflito (409);
- o que é publicado é exatamente o que foi validado (hash da última validação gravada, conferido com a cópia);
- nada é apagado: cópias descartadas ficam na pasta de edição.
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

from . import documento, pacote
from .banco import agora
from .imagens import mapa_imagens
from .legado import aba_modelo_valida
from .regras import codigo_base, normalizar_codigo, sanitizar_nome
from .validacao import ErroValidacao, motivo_obrigatorio

PASTA_EDICAO = "_edicao"          # dentro de <dados>/Modelos (fora das pastas varridas pela limpeza do legado)
_ROW = re.compile(r"<row\b([^>]*)>|<row\b([^>]*)/>")


class ErroConflitoEdicao(ValueError):
    """Estado mudou desde o início da edição (HTTP 409)."""


def _hash(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _sem_protecao(conteudo: bytes) -> bytes:
    """Cópia de trabalho editável: tira a proteção só da cópia (o modelo publicado não muda)."""
    partes = pacote.carregar(io.BytesIO(conteudo))
    for nome in list(partes):
        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", nome):
            xml = partes[nome].decode("utf-8")
            partes[nome] = re.sub(r"<sheetProtection\b[^>]*/>", "", xml).encode("utf-8")
    wb = partes["xl/workbook.xml"].decode("utf-8")
    partes["xl/workbook.xml"] = re.sub(r"<workbookProtection\b[^>]*/>", "", wb).encode("utf-8")
    return pacote.salvar(partes)


def _alturas(partes: dict, parte: str) -> dict[int, str | None]:
    xml = partes[parte].decode("utf-8")
    saida: dict[int, str | None] = {}
    for m in _ROW.finditer(xml):
        attrs = m.group(1) or m.group(2) or ""
        r = re.search(r'\br="(\d+)"', attrs)
        if not r:
            continue
        ht = re.search(r'\bht="([^"]+)"', attrs)
        saida[int(r.group(1))] = ht.group(1) if ht else None
    return saida


def _fotos(partes: dict) -> dict[object, str]:
    return {k: _hash(partes[v]) for k, v in mapa_imagens(partes).items() if v in partes}


def analisar(original: bytes, novo: bytes, codigos_contrato: set[str] | None) -> dict:
    """Valida a cópia de trabalho e lista as diferenças em relação ao modelo publicado."""
    erros: list[str] = []
    avisos: list[str] = []
    dif: list[dict] = []
    try:
        partes = pacote.carregar(io.BytesIO(novo))
        abas = pacote.abas(partes)
    except Exception as e:  # zip corrompido, XML ilegível
        return {"ok": False, "hash": _hash(novo), "erros": [f"ARQUIVO ILEGÍVEL: {e}"], "avisos": [], "diferencas": []}
    tipos = partes.get("[Content_Types].xml", b"").decode("utf-8", "ignore")
    if any(n.lower().endswith("vbaproject.bin") for n in partes) or "macroEnabled" in tipos:
        erros.append("O MODELO NÃO PODE TER MACROS. SALVE COMO .XLSX (PASTA DE TRABALHO DO EXCEL).")
    if len(abas) != 1:
        erros.append(f"O MODELO PRECISA TER EXATAMENTE 1 ABA (TEM {len(abas)}).")
    if erros:
        return {"ok": False, "hash": _hash(novo), "erros": erros, "avisos": avisos, "diferencas": dif}

    p_orig = pacote.carregar(io.BytesIO(original))
    aba_orig, aba_nova = pacote.abas(p_orig)[0], abas[0]
    if not aba_modelo_valida(aba_nova["nome"]):
        erros.append(f"O NOME DA ABA PRECISA CONTER \"OP-\" (ESTÁ \"{aba_nova['nome']}\").")
    elif aba_nova["nome"] != aba_orig["nome"]:
        dif.append({"tipo": "CABECALHO", "linha": None, "campo": "ABA", "antes": aba_orig["nome"], "depois": aba_nova["nome"]})
        avisos.append("O NOME DA ABA MUDOU: AS PRÓXIMAS O.P. USAM O NOME NOVO.")
    l_orig = {l["linha"]: l for l in documento.linhas_do_modelo(original)}
    l_nova = {l["linha"]: l for l in documento.linhas_do_modelo(novo)}
    if not l_nova:
        erros.append("NENHUM EQUIPAMENTO NAS LINHAS 10 A 100 (COLUNA B).")

    # códigos repetidos: erro só se a repetição é nova
    def repetidos(linhas: dict) -> set[str]:
        vistos, rep = set(), set()
        for l in linhas.values():
            c = normalizar_codigo(l["codigo"])
            if c:
                (rep if c in vistos else vistos).add(c)
        return rep
    novos_rep = repetidos(l_nova) - repetidos(l_orig)
    if novos_rep:
        erros.append("CÓDIGO REPETIDO NO MODELO: " + ", ".join(sorted(novos_rep)))

    # cabeçalho
    c_orig, c_novo = documento.cabecalho_do_modelo(original), documento.cabecalho_do_modelo(novo)
    for campo, rotulo in (("cliente", "CLIENTE (B3)"), ("tipo", "TIPO (B8)"), ("titulo", "TÍTULO (D2)"), ("ata", "ATA (S4)"),
                          ("empresa", "EMPRESA (L2)")):
        if c_orig[campo] != c_novo[campo]:
            dif.append({"tipo": "CABECALHO", "linha": None, "campo": rotulo, "antes": c_orig[campo], "depois": c_novo[campo]})
    if c_orig["cliente"] != c_novo["cliente"]:
        avisos.append("O CLIENTE (B3) MUDOU: CONFIRA SE É O MODELO CERTO.")

    # equipamentos
    for r in sorted(set(l_orig) | set(l_nova)):
        a, b = l_orig.get(r), l_nova.get(r)
        if a and not b:
            dif.append({"tipo": "REMOVIDO", "linha": r, "antes": f"{a['codigo']} {a['equipamento']}".strip(), "depois": ""})
        elif b and not a:
            dif.append({"tipo": "ADICIONADO", "linha": r, "antes": "", "depois": f"{b['codigo']} {b['equipamento']}".strip()})
        else:
            if normalizar_codigo(a["codigo"]) != normalizar_codigo(b["codigo"]):
                dif.append({"tipo": "CODIGO", "linha": r, "antes": a["codigo"], "depois": b["codigo"]})
            if a["equipamento"] != b["equipamento"]:
                dif.append({"tipo": "NOME", "linha": r, "antes": a["equipamento"], "depois": b["equipamento"]})

    # alturas originais das linhas (nunca recalculadas pelo sistema; só registradas)
    h_orig, h_nova = _alturas(p_orig, aba_orig["parte"]), _alturas(partes, aba_nova["parte"])
    for r in range(1, documento.LINHA_FIM + 1):
        if h_orig.get(r) != h_nova.get(r) and (r in l_orig or r in l_nova or r < documento.LINHA_INICIO):
            dif.append({"tipo": "ALTURA", "linha": r, "antes": h_orig.get(r) or "PADRÃO", "depois": h_nova.get(r) or "PADRÃO"})

    # fotos e logo
    f_orig, f_nova = _fotos(p_orig), _fotos(partes)
    for k in sorted(set(f_orig) | set(f_nova), key=lambda x: (isinstance(x, int), x if isinstance(x, int) else 0)):
        if f_orig.get(k) != f_nova.get(k):
            antes = "COM FOTO" if k in f_orig else "SEM FOTO"
            depois = "COM FOTO" if k in f_nova else "SEM FOTO"
            if antes == depois:
                antes, depois = "FOTO ANTERIOR", "FOTO NOVA"
            dif.append({"tipo": "LOGO" if k == "logo" else "FOTO", "linha": None if k == "logo" else k,
                        "antes": antes, "depois": depois})

    # contrato: código sem item (0.x são extras e não precisam estar no contrato)
    if codigos_contrato is not None:
        faltam = sorted({normalizar_codigo(l["codigo"]) for l in l_nova.values()
                         if normalizar_codigo(l["codigo"]) and not normalizar_codigo(l["codigo"]).startswith("0.")
                         and codigo_base(normalizar_codigo(l["codigo"])) not in codigos_contrato})
        if faltam:
            avisos.append("CÓDIGO SEM ITEM NO CONTRATO (NÃO TERÁ SALDO): " + ", ".join(faltam))

    # o modelo ainda gera O.P.? (prova com 1 equipamento, sem gravar nada)
    if l_nova and not erros:
        try:
            primeira = min(l_nova)
            documento.gerar_xlsx(novo, documento.DadosOP(numero="000-00", obra="VALIDAÇÃO", prazo="DEFINIR",
                                                         solicitante="", linhas={primeira: documento.LinhaOP(1)}),
                                 secrets.token_hex(4))
        except Exception as e:
            erros.append(f"O MODELO NÃO GERA O.P.: {e}")

    if not dif and not erros:
        avisos.append("NENHUMA ALTERAÇÃO EM RELAÇÃO AO MODELO PUBLICADO.")
    return {"ok": not erros, "hash": _hash(novo), "erros": erros, "avisos": avisos, "diferencas": dif,
            "equipamentos": {"antes": len(l_orig), "depois": len(l_nova)}}


class EdicaoModelos:
    def __init__(self, servico):
        self.s = servico

    # ------------------------------------------------------------ apoio
    def _ativa(self) -> None:
        if self.s.config().get("edicao_modelo_excel") is not True:
            raise ErroValidacao("EDIÇÃO DE MODELO NO EXCEL DESATIVADA (CONFIGURAÇÃO).")

    def _sessao(self, sessao_id: int) -> dict:
        e = self.s.banco.um("SELECT * FROM modelo_edicoes WHERE id = ?", (sessao_id,))
        if not e:
            raise ErroValidacao("EDIÇÃO NÃO ENCONTRADA.")
        return e

    def _aberta(self, sessao_id: int) -> dict:
        e = self._sessao(sessao_id)
        if e["estado"] != "ABERTA":
            raise ErroConflitoEdicao(f"ESTA EDIÇÃO JÁ FOI {e['estado']}.")
        return e

    def _caminho_trabalho(self, e: dict) -> Path:
        alvo = (self.s.dados / e["arquivo_trabalho"]).resolve()
        raiz = (self.s.dados / "Modelos" / PASTA_EDICAO).resolve()
        if raiz not in alvo.parents:                       # nunca abre caminho fora da pasta de edição
            raise ErroValidacao("CAMINHO DA CÓPIA DE TRABALHO INVÁLIDO.")
        return alvo

    def _origem(self, e: dict, modelo: dict) -> bytes:
        """Conteúdo do modelo de quando a edição começou; se o modelo mudou desde então, é conflito."""
        if modelo["arquivo"] != e["arquivo_origem"]:
            raise ErroConflitoEdicao("O MODELO FOI ATUALIZADO DEPOIS QUE ESTA EDIÇÃO COMEÇOU. DESCARTE E COMECE OUTRA.")
        try:
            return (self.s.dados / e["arquivo_origem"]).read_bytes()
        except FileNotFoundError:
            raise ErroConflitoEdicao("O ARQUIVO DO MODELO NÃO EXISTE MAIS. DESCARTE E COMECE OUTRA.")

    def _codigos_contrato(self, modelo: dict) -> set[str] | None:
        if not modelo.get("contrato_id"):
            return None
        return {codigo_base(normalizar_codigo(r["codigo"])) for r in self.s.banco.todos(
            "SELECT codigo FROM contrato_itens WHERE contrato_id = ?", (modelo["contrato_id"],))}

    def _publico(self, e: dict) -> dict:
        saida = {k: e[k] for k in ("id", "modelo_id", "estado", "criado_em", "finalizado_em", "arquivo_publicado", "motivo")}
        saida["arquivo"] = Path(e["arquivo_trabalho"]).name
        try:
            saida["validacao"] = json.loads(e["validacao"]) if e["validacao"] else None
        except ValueError:
            saida["validacao"] = None
        return saida

    # ------------------------------------------------------------ fluxo
    def situacao(self, modelo_id: int) -> dict:
        self._ativa()
        m = self.s._modelo(modelo_id)
        e = self.s.banco.um("SELECT * FROM modelo_edicoes WHERE modelo_id = ? AND estado = 'ABERTA'", (modelo_id,))
        versoes = self.s.banco.todos("SELECT id, estado, criado_em, finalizado_em, motivo FROM modelo_edicoes "
                                     "WHERE modelo_id = ? AND estado = 'PUBLICADA' ORDER BY id DESC", (modelo_id,))
        return {"modelo_id": modelo_id, "aba": m["aba"], "edicao": self._publico(e) if e else None,
                "versoes_publicadas": versoes, "windows": os.name == "nt"}

    def iniciar(self, modelo_id: int) -> dict:
        self._ativa()
        m = self.s._modelo(modelo_id)
        existente = self.s.banco.um("SELECT * FROM modelo_edicoes WHERE modelo_id = ? AND estado = 'ABERTA'", (modelo_id,))
        if existente:
            return self._publico(existente)
        origem = self.s.dados / m["arquivo"]
        conteudo = origem.read_bytes()
        token = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
        rel = Path("Modelos") / PASTA_EDICAO / f"{modelo_id}-{token}" / f"{sanitizar_nome(m['codename'])}.xlsx"
        destino = self.s.dados / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(_sem_protecao(conteudo))
        try:
            with self.s.banco.transacao() as con:
                cur = con.execute("INSERT INTO modelo_edicoes (modelo_id, arquivo_origem, hash_origem, arquivo_trabalho, "
                                  "estado, criado_em) VALUES (?,?,?,?, 'ABERTA', ?)",
                                  (modelo_id, m["arquivo"], _hash(conteudo), rel.as_posix(), agora()))
                self.s.banco.evento(con, "MODELO_EDICAO_INICIADA", {"modelo": modelo_id, "edicao": cur.lastrowid})
        except sqlite3.IntegrityError:
            # outra requisição abriu a edição ao mesmo tempo (índice único): devolve a que ficou valendo
            destino.unlink(missing_ok=True)
            existente = self.s.banco.um("SELECT * FROM modelo_edicoes WHERE modelo_id = ? AND estado = 'ABERTA'",
                                        (modelo_id,))
            if not existente:
                raise
            return self._publico(existente)
        except Exception:
            destino.unlink(missing_ok=True)
            raise
        return self._publico(self._sessao(cur.lastrowid))

    def abrir(self, sessao_id: int) -> dict:
        """Abre a cópia de trabalho no programa padrão do .xlsx (Excel) — só no Windows, por ação do usuário."""
        self._ativa()
        e = self._aberta(sessao_id)
        alvo = self._caminho_trabalho(e)
        if not alvo.is_file():
            raise ErroValidacao("CÓPIA DE TRABALHO NÃO ENCONTRADA.")
        if os.name != "nt":
            raise ErroValidacao(f"ABRIR NO EXCEL SÓ FUNCIONA NO WINDOWS. CÓPIA: {e['arquivo_trabalho']}")
        os.startfile(str(alvo))  # type: ignore[attr-defined]  # caminho gerado pelo sistema, sem argumentos
        return {"ok": True, "arquivo": alvo.name}

    def validar(self, sessao_id: int) -> dict:
        self._ativa()
        e = self._aberta(sessao_id)
        m = self.s._modelo(e["modelo_id"])
        alvo = self._caminho_trabalho(e)
        try:
            novo = alvo.read_bytes()
        except OSError as erro:
            raise ErroValidacao(f"NÃO FOI POSSÍVEL LER A CÓPIA (FECHE O EXCEL E TENTE DE NOVO): {erro}")
        r = analisar(self._origem(e, m), novo, self._codigos_contrato(m))
        r["usada_em_ops"] = self.s.banco.um("SELECT COUNT(*) n FROM ops WHERE modelo_id = ?", (m["id"],))["n"]
        with self.s.banco.transacao() as con:
            con.execute("UPDATE modelo_edicoes SET validacao = ? WHERE id = ?", (json.dumps(r, ensure_ascii=False), sessao_id))
        return r

    def publicar(self, sessao_id: int, motivo: object, hash_validado: object) -> dict:
        self._ativa()
        motivo = motivo_obrigatorio(motivo)
        e = self._aberta(sessao_id)
        m = self.s._modelo(e["modelo_id"])
        original = self._origem(e, m)
        alvo = self._caminho_trabalho(e)
        try:
            novo = alvo.read_bytes()
        except OSError as erro:
            raise ErroValidacao(f"NÃO FOI POSSÍVEL LER A CÓPIA (FECHE O EXCEL E TENTE DE NOVO): {erro}")
        try:
            gravada = json.loads(e["validacao"]) if e["validacao"] else {}
        except ValueError:
            gravada = {}
        if not isinstance(hash_validado, str) or gravada.get("hash") != hash_validado or hash_validado != _hash(novo):
            raise ErroConflitoEdicao("A CÓPIA MUDOU DEPOIS DA VALIDAÇÃO. VALIDE DE NOVO ANTES DE PUBLICAR.")
        if not gravada.get("ok"):
            raise ErroValidacao("CORRIJA ANTES DE PUBLICAR: " + " | ".join(gravada.get("erros") or []))
        r = analisar(original, novo, self._codigos_contrato(m))
        if not r["ok"]:
            raise ErroValidacao("CORRIJA ANTES DE PUBLICAR: " + " | ".join(r["erros"]))
        if not r["diferencas"]:
            raise ErroValidacao("NENHUMA ALTERAÇÃO PARA PUBLICAR.")
        pasta = (self.s.dados / e["arquivo_origem"]).parent
        destino = pasta / f"{sanitizar_nome(m['codename'])}.{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx"
        tmp = destino.with_name(destino.name + f".{secrets.token_hex(4)}.tmp")
        tmp.write_bytes(novo)
        os.replace(tmp, destino)                            # arquivo novo; nenhum existente é sobrescrito
        rel = destino.relative_to(self.s.dados).as_posix()
        linhas = documento.linhas_do_modelo(novo)
        cab = documento.cabecalho_do_modelo(novo)
        try:
            with self.s.banco.transacao() as con:
                atual = con.execute("SELECT arquivo FROM modelos WHERE id = ?", (m["id"],)).fetchone()[0]
                if atual != e["arquivo_origem"]:
                    raise ErroConflitoEdicao("O MODELO FOI ATUALIZADO DEPOIS QUE ESTA EDIÇÃO COMEÇOU. DESCARTE E COMECE OUTRA.")
                estado = con.execute("SELECT estado FROM modelo_edicoes WHERE id = ?", (sessao_id,)).fetchone()[0]
                if estado != "ABERTA":
                    raise ErroConflitoEdicao(f"ESTA EDIÇÃO JÁ FOI {estado}.")
                con.execute("UPDATE modelos SET arquivo = ?, aba = ?, titulo = ?, tipo_padrao = ?, editado_sistema = 1 "
                            "WHERE id = ?", (rel, cab["aba"] or m["aba"], cab["ata"] or m["titulo"],
                                             cab["tipo"] or m["tipo_padrao"], m["id"]))
                con.execute("DELETE FROM modelo_linhas WHERE modelo_id = ?", (m["id"],))
                con.executemany("INSERT INTO modelo_linhas (modelo_id, linha, codigo, equipamento) VALUES (?,?,?,?)",
                                [(m["id"], l["linha"], normalizar_codigo(l["codigo"]), l["equipamento"]) for l in linhas])
                con.execute("UPDATE modelo_edicoes SET estado = 'PUBLICADA', finalizado_em = ?, arquivo_publicado = ?, "
                            "motivo = ?, validacao = ? WHERE id = ?",
                            (agora(), rel, motivo, json.dumps(r, ensure_ascii=False), sessao_id))
                self.s.banco.evento(con, "MODELO_VERSAO_PUBLICADA", {
                    "modelo": m["id"], "edicao": sessao_id, "antes": e["arquivo_origem"], "depois": rel,
                    "hash": r["hash"], "motivo": motivo, "diferencas": len(r["diferencas"])})
        except BaseException:
            destino.unlink(missing_ok=True)                 # banco não gravou: o arquivo novo não fica órfão
            raise
        self.s._linhas_cache.clear()
        return {"ok": True, "modelo": self.s._modelo(m["id"]), "edicao": self._publico(self._sessao(sessao_id)),
                "diferencas": len(r["diferencas"])}

    def descartar(self, sessao_id: int, motivo: object = "") -> dict:
        self._ativa()
        e = self._aberta(sessao_id)
        with self.s.banco.transacao() as con:
            n = con.execute("UPDATE modelo_edicoes SET estado = 'DESCARTADA', finalizado_em = ?, motivo = ? "
                            "WHERE id = ? AND estado = 'ABERTA'",
                            (agora(), str(motivo or "").strip()[:500], sessao_id)).rowcount
            if not n:
                raise ErroConflitoEdicao("ESTA EDIÇÃO JÁ FOI FINALIZADA.")
            self.s.banco.evento(con, "MODELO_EDICAO_DESCARTADA", {"modelo": e["modelo_id"], "edicao": sessao_id})
        return self._publico(self._sessao(sessao_id))     # a cópia fica guardada na pasta de edição
