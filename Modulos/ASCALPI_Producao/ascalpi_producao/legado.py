"""Importação única dos arquivos legados (OK-<CIDADE>_O.P.xlsm e Controle) para o banco do ASCALPI Produção.

Nada é gravado nos arquivos de origem: eles são apenas lidos.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import documento, pacote
import json

from .banco import Banco, agora
from .validacao import ErroValidacao
from .regras import (codigo_valido, formatar_quantidade, normalizar_cabecalho, normalizar_chave, normalizar_codigo, numero_br,
                     sanitizar_nome, tipo_arquivo)

PREFIXO_OP = "OP_"
PREFIXO_SALDO = "SALDO_"


def _col_row(ref: str) -> tuple[int, int]:
    col, row = documento.separar_ref(ref)
    return documento.col_num(col), row


def _faixa(ref: str) -> tuple[int, int, int, int]:
    a, b = ref.split(":")
    c1, r1 = _col_row(a)
    c2, r2 = _col_row(b)
    return c1, r1, c2, r2


def _v(valores: dict, col: int, row: int):
    return valores.get(f"{documento.col_letras(col)}{row}")


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def data_excel(v) -> date | None:
    if isinstance(v, (int, float)) and v > 0:
        return date(1899, 12, 30) + timedelta(days=int(v))
    if isinstance(v, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                return datetime.strptime(v.strip()[:10], fmt).date()
            except ValueError:
                pass
    return None


def _data_ou_texto(v) -> str:
    d = data_excel(v)
    return d.isoformat() if d else _texto(v).upper()


def momento_excel(v) -> str | None:
    if isinstance(v, (int, float)) and v > 0:
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).replace(microsecond=0).isoformat()
    d = data_excel(v)
    return d.isoformat() if d else None


# ---------------------------------------------------------------- leitura de um livro de O.P.

def aba_modelo_valida(nome: str) -> bool:
    """Aba de modelo de O.P. = nome com o padrão "OP-" (ignorando pontos: "O.P-ATA-CIMASP")."""
    return "OP-" in nome.replace(".", "").upper()


def ata_pelo_nome(nome: str) -> str:
    resto = nome.replace(".", "").upper().split("OP-", 1)[1]
    resto = resto[4:] if resto.startswith("ATA-") else resto
    return re.sub(r"[^A-Z0-9]", "", sanitizar_nome(resto).upper()) or "MODELO"

def ler_saldo(partes: dict, aba: dict, ss: list[str]) -> dict | None:
    tabs = pacote.tabelas(partes, aba["parte"])
    if not tabs:
        return None
    alvo = next((t for t in tabs if t["nome"].upper().startswith("TAB_SALDO_")), tabs[0])
    valores = pacote.ler_valores(partes, aba["parte"], ss)
    c1, r1, c2, r2 = _faixa(alvo["ref"])
    cab = {}
    for c in range(c1, c2 + 1):
        h = normalizar_cabecalho(_texto(_v(valores, c, r1)))
        if h and h not in cab:
            cab[h] = c
    col_prev = next((c for h, c in cab.items() if h.startswith("PREVISAO")), None)
    obrig = {"COD": cab.get("COD"), "EQUIPAMENTOS": cab.get("EQUIPAMENTOS"), "MONTANTE": cab.get("MONTANTE")}
    if None in obrig.values():
        raise ValueError(f"TABELA {alvo['nome']} SEM COLUNAS OBRIGATÓRIAS (COD/EQUIPAMENTOS/MONTANTE).")
    descricao = ""
    for c in range(c1, c2 + 1):
        t = _texto(_v(valores, c, r1 - 1))
        if t.upper().startswith("CONTRATO"):
            descricao = re.sub(r"\s+", " ", t)
            break
    itens = []
    for r in range(r1 + 1, r2 + 1):
        cod = normalizar_codigo(_v(valores, obrig["COD"], r))
        if not codigo_valido(cod):
            continue
        ausentes = [rot for rot, col in (("MONTANTE", obrig["MONTANTE"]), ("QUANT.", cab.get("QUANT")),
                                         ("PREVISÃO", col_prev)) if col and _v(valores, col, r) in (None, "")]
        itens.append({
            "ausentes": ausentes,
            "codigo": cod,
            "equipamento": _texto(_v(valores, obrig["EQUIPAMENTOS"], r)),
            "valor_un": numero_br(_v(valores, cab["VALOR UN"], r)) or 0 if "VALOR UN" in cab else 0,
            "montante": numero_br(_v(valores, obrig["MONTANTE"], r)) or 0,
            "medido": numero_br(_v(valores, cab["QUANT"], r)) or 0 if "QUANT" in cab else 0,
            "previsao": numero_br(_v(valores, col_prev, r)) or 0 if col_prev else 0,
            "saldo_planilha": _v(valores, cab["SALDO"], r) if "SALDO" in cab else None,
        })
    return {"tabela": alvo["nome"], "descricao": descricao, "itens": itens}


def ler_livro(caminho: Path) -> dict:
    partes = pacote.carregar(caminho)
    ss = pacote.strings_compartilhadas(partes)
    lista = pacote.abas(partes)
    cliente = ""
    for a in lista:
        if a["codename"].upper() == "DB_" or a["nome"].upper() == "DB":
            for t in pacote.tabelas(partes, a["parte"]):
                if t["nome"].upper() == "TAB_CLIENTE":
                    vals = pacote.ler_valores(partes, a["parte"], ss)
                    c1, r1, _, r2 = _faixa(t["ref"])
                    for r in range(r1 + 1, r2 + 1):
                        cliente = _texto(_v(vals, c1, r))
                        if cliente:
                            break
    contratos, modelos = {}, []
    for a in lista:
        cn = a["codename"].upper()
        if cn.startswith(PREFIXO_SALDO):
            saldo = ler_saldo(partes, a, ss)
            if saldo:
                saldo["nome"] = a["nome"]
                contratos[cn[len(PREFIXO_SALDO):]] = saldo
        elif aba_modelo_valida(a["nome"]):
            vals = pacote.ler_valores(partes, a["parte"], ss)
            ata = cn[len(PREFIXO_OP):] if cn.startswith(PREFIXO_OP) else ata_pelo_nome(a["nome"])
            modelos.append({"codename": a["codename"] or "OP_" + ata, "ata": ata, "aba": a["nome"],
                            "oculta": a["estado"] != "visible",
                            "cliente_b3": _texto(vals.get("B3")), "titulo": _texto(vals.get("S4")),
                            "tipo": _texto(vals.get("B8"))})
    if not cliente:
        cliente = next((m["cliente_b3"] for m in modelos if m["cliente_b3"]), caminho.stem)
    return {"arquivo": caminho.name, "cliente": cliente, "contratos": contratos, "modelos": modelos}


# ---------------------------------------------------------------- importação para o banco

class _Previa(Exception):
    """Desfaz a transação da prévia: nada é gravado."""


def _q(v) -> str:
    return formatar_quantidade(v or 0)


def _conferir_saldo(ata: str, it: dict) -> list[str]:
    """Compara o SALDO salvo na planilha com MONTANTE − (QUANT. + PREVISÃO); valor ausente é aviso, não zero."""
    avisos = [f"  ITEM {it['codigo']} ({ata}): {campo} SEM VALOR NA PLANILHA (FÓRMULA SEM VALOR SALVO?), CONSIDERADO 0"
              for campo in it.get("ausentes", [])]
    if it["codigo"].startswith("0.") or not it["montante"] or it["montante"] <= 0:
        return avisos
    bruto = it.get("saldo_planilha")
    planilha = 0.0 if str(bruto or "").strip().upper() == "ACABOU" else numero_br(bruto)
    calculado = it["montante"] - (it["medido"] + it["previsao"])
    if planilha is not None and abs(planilha - calculado) > 1e-6:
        avisos.append(f"  CONFERIR SALDO ITEM {it['codigo']} ({ata}): PLANILHA {_q(planilha)}, CALCULADO {_q(calculado)}")
    return avisos


def importar_livro(banco: Banco, caminho: Path, pasta_modelos: Path, relatorio: list[str], previa: bool = False) -> None:
    info = ler_livro(caminho)
    pasta = pasta_modelos / sanitizar_nome(info["cliente"])
    raiz = pasta_modelos.parent
    escritos: list[Path] = []          # arquivos novos desta importação (apagados se o banco falhar)
    modelos_xlsx = {}
    for m in info["modelos"]:
        conteudo = pacote.extrair_aba(caminho, m["aba"])
        atual = banco.um("SELECT m.arquivo FROM modelos m JOIN prefeituras p ON p.id = m.prefeitura_id "
                         "WHERE p.nome = ? AND m.codename = ?", (info["cliente"], m["codename"]))
        base = pasta / f"{sanitizar_nome(m['codename'])}.xlsx"
        destino, mudou = base, True
        if atual and (raiz / atual["arquivo"]).exists():
            destino = raiz / atual["arquivo"]
            mudou = destino.read_bytes() != conteudo
            if mudou:   # nunca sobrescreve: O.P. já emitidas continuam apontando para o arquivo anterior
                destino = pasta / f"{sanitizar_nome(m['codename'])}.{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx"
        elif base.exists() and base.read_bytes() != conteudo:
            destino = pasta / f"{sanitizar_nome(m['codename'])}.{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx"
        modelos_xlsx[m["codename"]] = (destino, documento.linhas_do_modelo(conteudo), mudou and atual is not None)
        if not previa and (mudou or not destino.exists()):
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
            escritos.append(destino)
    avisos: list[str] = []
    try:
        with banco.transacao() as con:
            con.execute("INSERT INTO prefeituras (nome, arquivo_origem) VALUES (?, ?) "
                        "ON CONFLICT(nome) DO UPDATE SET arquivo_origem = excluded.arquivo_origem",
                        (info["cliente"], info["arquivo"]))
            pid = con.execute("SELECT id FROM prefeituras WHERE nome = ?", (info["cliente"],)).fetchone()[0]
            ids_contrato = {}
            pendentes = []
            for ata, c in info["contratos"].items():
                cid_antigo = con.execute("SELECT id FROM contratos WHERE prefeitura_id = ? AND ata = ?", (pid, ata)).fetchone()
                antigos = {r["codigo"]: dict(r) for r in con.execute(
                    "SELECT codigo, montante, medido_inicial, previsao_inicial, editado_sistema FROM contrato_itens "
                    "WHERE contrato_id = ?",
                    (cid_antigo[0],)).fetchall()} if cid_antigo else {}
                con.execute("INSERT INTO contratos (prefeitura_id, ata, nome, descricao, importado_em) VALUES (?,?,?,?,?) "
                            "ON CONFLICT(prefeitura_id, ata) DO UPDATE SET nome = excluded.nome, "
                            "descricao = excluded.descricao, importado_em = excluded.importado_em",
                            (pid, ata, c["nome"], c["descricao"], agora()))
                cid = con.execute("SELECT id FROM contratos WHERE prefeitura_id = ? AND ata = ?", (pid, ata)).fetchone()[0]
                ids_contrato[ata] = cid
                for it in c["itens"]:
                    velho = antigos.get(it["codigo"])
                    if cid_antigo and velho is None:
                        avisos.append(f"  NOVO ITEM {it['codigo']} ({ata}): {it['equipamento']}")
                    elif velho:
                        if velho["editado_sistema"] and abs((velho["montante"] or 0) - (it["montante"] or 0)) > 1e-9:
                            avisos.append(f"  ITEM {it['codigo']} ({ata}): MONTANTE EDITADO NO SISTEMA ({_q(velho['montante'])}) "
                                          f"MANTIDO; PLANILHA {_q(it['montante'])}")
                        for campo, chave in (("MONTANTE", "montante"), ("QUANT.", "medido_inicial"), ("PREVISÃO", "previsao_inicial")):
                            novo = it["montante" if chave == "montante" else "medido" if chave == "medido_inicial" else "previsao"]
                            if chave == "montante" and velho["editado_sistema"]:
                                continue
                            if abs((velho[chave] or 0) - (novo or 0)) > 1e-9:
                                avisos.append(f"  ITEM {it['codigo']} ({ata}): {campo} {_q(velho[chave])} → {_q(novo)}")
                    conferencia = _conferir_saldo(ata, it)
                    avisos.extend(conferencia)
                    pendentes += [{"prefeitura": info["cliente"], "ata": ata, "codigo": it["codigo"], "aviso": a.strip()}
                                  for a in conferencia]
                    con.execute("INSERT INTO contrato_itens (contrato_id, codigo, equipamento, valor_un, montante, "
                                "medido_inicial, previsao_inicial) VALUES (?,?,?,?,?,?,?) "
                                "ON CONFLICT(contrato_id, codigo) DO UPDATE SET equipamento = excluded.equipamento, "
                                "valor_un = excluded.valor_un, montante = CASE WHEN contrato_itens.editado_sistema "
                                "THEN contrato_itens.montante ELSE excluded.montante END, "
                                "medido_inicial = excluded.medido_inicial, previsao_inicial = excluded.previsao_inicial",
                                (cid, it["codigo"], it["equipamento"], it["valor_un"], it["montante"],
                                 it["medido"], it["previsao"]))
                relatorio.append(f"  CONTRATO {ata}: {len(c['itens'])} ITENS")
            # pendências de conferência do saldo: substitui só as desta prefeitura
            r = con.execute("SELECT valor FROM meta WHERE chave = 'saldo_a_conferir'").fetchone()
            try:
                todas = [x for x in json.loads(r[0]) if x.get("prefeitura") != info["cliente"]] if r else []
            except ValueError:
                todas = []
            con.execute("INSERT OR REPLACE INTO meta VALUES ('saldo_a_conferir', ?)",
                        (json.dumps(todas + pendentes, ensure_ascii=False),))
            for m in info["modelos"]:
                destino, linhas, trocou = modelos_xlsx[m["codename"]]
                rel = destino.relative_to(raiz).as_posix()
                ata_contrato = m["ata"] if m["ata"] in ids_contrato else re.sub(r"\d+$", "", m["ata"])
                cid = ids_contrato.get(ata_contrato)
                con.execute("INSERT INTO modelos (prefeitura_id, contrato_id, codename, aba, titulo, tipo_padrao, arquivo, ativo) "
                            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(prefeitura_id, codename) DO UPDATE SET "
                            "contrato_id = COALESCE(modelos.contrato_id, excluded.contrato_id), aba = excluded.aba, "
                            "titulo = excluded.titulo, tipo_padrao = excluded.tipo_padrao, arquivo = excluded.arquivo",
                            (pid, cid, m["codename"], m["aba"], m["titulo"], m["tipo"], rel, 1))
                mid = con.execute("SELECT id FROM modelos WHERE prefeitura_id = ? AND codename = ?",
                                  (pid, m["codename"])).fetchone()[0]
                con.execute("DELETE FROM modelo_linhas WHERE modelo_id = ?", (mid,))
                con.executemany("INSERT INTO modelo_linhas (modelo_id, linha, codigo, equipamento) VALUES (?,?,?,?)",
                                [(mid, l["linha"], normalizar_codigo(l["codigo"]), l["equipamento"]) for l in linhas])
                if trocou:
                    usadas = con.execute("SELECT COUNT(*) FROM ops WHERE modelo_id = ?", (mid,)).fetchone()[0]
                    avisos.append(f"  MODELO {m['aba']}: ARQUIVO ATUALIZADO" +
                                  (f" ({usadas} O.P. JÁ EMITIDAS CONTINUAM NO MODELO ANTERIOR)" if usadas else ""))
                relatorio.append(f"  MODELO {m['aba']} ({m['codename']}): {len(linhas)} EQUIPAMENTOS, "
                                 f"CONTRATO {'—' if cid is None else ata_contrato}")
            # abas que deixaram de ser modelo válido: apaga se nunca usada, senão só desativa
            validos = [m["codename"] for m in info["modelos"]]
            marcas = ",".join("?" * len(validos)) or "''"
            for (mid,) in con.execute(f"SELECT id FROM modelos WHERE prefeitura_id = ? AND codename NOT IN ({marcas})",
                                      (pid, *validos)).fetchall():
                if con.execute("SELECT 1 FROM ops WHERE modelo_id = ? LIMIT 1", (mid,)).fetchone():
                    con.execute("UPDATE modelos SET ativo = 0 WHERE id = ?", (mid,))
                else:
                    con.execute("DELETE FROM modelos WHERE id = ?", (mid,))
            banco.evento(con, "IMPORTAR_LIVRO", {"arquivo": info["arquivo"], "cliente": info["cliente"], "avisos": len(avisos)})
            if previa:
                raise _Previa()
    except _Previa:
        pass
    except BaseException:
        for arq in escritos:              # banco não gravou: os arquivos novos não podem ficar órfãos
            arq.unlink(missing_ok=True)
        raise
    if not previa:
        _limpar_modelos_sem_uso(banco, raiz, pasta)
    relatorio.insert(len(relatorio) - len(info["contratos"]) - len(info["modelos"]),
                     f"{info['arquivo']} → {info['cliente']}")
    relatorio.extend(avisos)


def _limpar_modelos_sem_uso(banco: Banco, raiz: Path, pasta: Path) -> None:
    """Remove versões antigas de modelo que nenhum modelo nem O.P. referencia mais."""
    usados = {r["a"] for r in banco.todos("SELECT arquivo a FROM modelos UNION SELECT modelo_arquivo FROM ops "
                                          "WHERE modelo_arquivo IS NOT NULL")}
    for arq in pasta.glob("*.xlsx"):
        if arq.relative_to(raiz).as_posix() not in usados:
            try:
                arq.unlink()
            except OSError:
                pass


COLUNAS_CONTROLE = {
    "Nº OP": "numero", "N OP": "numero", "NO OP": "numero", "CLIENTE": "cliente", "OBRA": "obra",
    "SOLICITANTE": "solicitante", "EQUIPAMENTOS": "tipo", "TIPO DE MATERIAL": "material",
    "SOLICITACAO": "solicitado_em", "DATA ENTREGA": "prazo", "DATA ENTREGA ATUALIZADA": "entrega_atualizada",
    "MATERIAL OBRA": "material_obra", "STATUS INSTALACAO": "status_instalacao", "FOTOGRAFICO": "fotografico",
    "OBS:": "obs", "OBS": "obs",
}


def _achar_prefeitura(prefeituras: list[dict], cliente: str) -> int | None:
    chave = normalizar_chave(cliente)
    if not chave:
        return None
    for p in prefeituras:
        if normalizar_chave(p["nome"]) == chave:
            return p["id"]
    candidatos = [p for p in prefeituras if normalizar_chave(p["nome"]).startswith(chave) or chave.startswith(normalizar_chave(p["nome"]))]
    return candidatos[0]["id"] if len(candidatos) == 1 else None


def importar_controle(banco: Banco, caminho: Path, relatorio: list[str], previa: bool = False) -> None:
    partes = pacote.carregar(caminho)
    ss = pacote.strings_compartilhadas(partes)
    linhas_op, cores = [], []
    achou_tabela = achou_numero = False
    for a in pacote.abas(partes):
        for t in pacote.tabelas(partes, a["parte"]):
            vals = None
            if t["nome"] == "Controle_OP":
                achou_tabela = True
                vals = pacote.ler_valores(partes, a["parte"], ss)
                c1, r1, c2, r2 = _faixa(t["ref"])
                mapa = {}
                for c in range(c1, c2 + 1):
                    h = normalizar_cabecalho(_texto(_v(vals, c, r1)))
                    campo = COLUNAS_CONTROLE.get(h) or ("numero" if h.startswith("N") and h.endswith(" OP") else None)
                    if campo and campo not in mapa.values():
                        mapa[c] = campo
                achou_numero = achou_numero or "numero" in mapa.values()
                for r in range(r1 + 1, r2 + 1):
                    d = {campo: _v(vals, c, r) for c, campo in mapa.items()}
                    if _texto(d.get("numero")):
                        linhas_op.append(d)
            elif "MODELOS" in a["nome"].upper() and t["ref"]:
                vals = pacote.ler_valores(partes, a["parte"], ss)
                c1, r1, c2, r2 = _faixa(t["ref"])
                cab = {normalizar_cabecalho(_texto(_v(vals, c, r1))): c for c in range(c1, c2 + 1)}
                cp = cab.get("PREFEITURA")
                ca = next((c for h, c in cab.items() if h.startswith("CORES DOS APARELHOS")), None)
                cc = next((c for h, c in cab.items() if h.startswith("CORES CANOPLAS")), None)
                for r in range(r1 + 1, r2 + 1):
                    nome = _texto(_v(vals, cp, r)) if cp else ""
                    if nome:
                        cores.append((nome, re.sub(r"\s{2,}", "\n", _texto(_v(vals, ca, r))) if ca else "",
                                      re.sub(r"\s{2,}", "\n", _texto(_v(vals, cc, r))) if cc else ""))
    # conferir ANTES de mexer no banco: arquivo errado nunca apaga o histórico (R07)
    if not achou_tabela:
        raise ErroValidacao(f"{caminho.name}: TABELA Controle_OP NÃO ENCONTRADA. NADA FOI ALTERADO.")
    if not achou_numero:
        raise ErroValidacao(f"{caminho.name}: A TABELA Controle_OP NÃO TEM A COLUNA Nº O.P. NADA FOI ALTERADO.")
    ja_tem = banco.um("SELECT COUNT(*) n FROM ops WHERE origem = 'LEGADO'")["n"]
    if not linhas_op and ja_tem:
        raise ErroValidacao(f"{caminho.name}: TABELA Controle_OP SEM NENHUMA O.P. E O SISTEMA JÁ TEM {ja_tem} "
                            "NO HISTÓRICO. NADA FOI ALTERADO.")
    novas = atualizadas = preservados = 0
    try:
        _gravar_controle(banco, caminho, linhas_op, cores, previa, contagem := {})
    except _Previa:
        pass
    novas, atualizadas, fora, preservados = (contagem.get(k, 0) for k in ("novas", "atualizadas", "fora", "preservados"))
    relatorio.append(f"{caminho.name} → {len(linhas_op)} O.P. NO HISTÓRICO, {len(cores)} PREFEITURAS COM CORES "
                     f"({novas} NOVAS, {atualizadas} ATUALIZADAS, {fora} MANTIDAS FORA DO ARQUIVO, "
                     f"{preservados} CAMPOS EDITADOS NO SISTEMA PRESERVADOS)")


def _gravar_controle(banco: Banco, caminho: Path, linhas_op: list, cores: list, previa: bool, contagem: dict) -> None:
    novas = atualizadas = preservados = 0
    with banco.transacao() as con:
        prefeituras = [dict(r) for r in con.execute("SELECT id, nome FROM prefeituras").fetchall()]
        for nome, ap, cn in cores:
            pid = _achar_prefeitura(prefeituras, nome)
            if pid:
                con.execute("UPDATE prefeituras SET cores_aparelhos = ?, cores_canoplas = ? WHERE id = ?", (ap.strip(), cn.strip(), pid))
        # identidade estável: número + ocorrência no arquivo (o Controle admite números repetidos)
        existentes = {r["chave_origem"]: dict(r) for r in con.execute(
            "SELECT id, chave_origem, editado_sistema FROM ops WHERE origem = 'LEGADO'").fetchall()}
        vistos: dict[str, int] = {}
        chaves_arquivo = set()
        for d in linhas_op:
            numero = _texto(d.get("numero"))
            vistos[numero] = vistos.get(numero, 0) + 1
            chave = f"{numero}#{vistos[numero]}"
            chaves_arquivo.add(chave)
            solicitado = momento_excel(d.get("solicitado_em"))
            m = re.fullmatch(r"(\d+)\s*-\s*(\d{2})", numero)
            if m:
                seq, ano = int(m.group(1)), 2000 + int(m.group(2))
            else:
                digitos = re.sub(r"\D", "", numero)
                seq = int(digitos) if digitos else 0
                ano = int(solicitado[:4]) if solicitado else datetime.now().year
            prazo = d.get("prazo")
            prazo_data = data_excel(prazo)
            cliente = _texto(d.get("cliente"))
            tipo = _texto(d.get("tipo"))
            campos = {
                "numero": numero, "ano": ano, "seq": seq, "prefeitura_id": _achar_prefeitura(prefeituras, cliente),
                "cliente": cliente, "obra": _texto(d.get("obra")), "solicitante": _texto(d.get("solicitante")),
                "tipo": tipo, "tipo_arquivo": tipo_arquivo(tipo), "material": _texto(d.get("material")),
                "prazo_data": prazo_data.isoformat() if prazo_data else None,
                "prazo_texto": None if prazo_data else (_texto(prazo).upper() or None),
                "entrega_atualizada": _data_ou_texto(d.get("entrega_atualizada")), "solicitado_em": solicitado,
                "status_instalacao": _texto(d.get("status_instalacao")), "material_obra": _texto(d.get("material_obra")),
                "fotografico": _texto(d.get("fotografico")), "obs": _texto(d.get("obs")),
            }
            atual = existentes.get(chave)
            if atual:
                try:
                    protegidos = set(json.loads(atual["editado_sistema"] or "[]"))
                except ValueError:
                    protegidos = set()
                preservados += len(protegidos & set(campos))
                sets = {k: v for k, v in campos.items() if k not in protegidos}
                con.execute("UPDATE ops SET " + ", ".join(f"{k} = ?" for k in sets) + ", atualizado_em = ? WHERE id = ?",
                            (*sets.values(), agora(), atual["id"]))
                atualizadas += 1
            else:
                con.execute("INSERT INTO ops (origem, chave_origem, criado_em, atualizado_em, " + ", ".join(campos) +
                            ") VALUES ('LEGADO', ?, ?, ?, " + ",".join("?" * len(campos)) + ")",
                            (chave, agora(), agora(), *campos.values()))
                novas += 1
        fora = len(set(existentes) - chaves_arquivo)   # não estão mais no arquivo: ficam (nada é apagado)
        banco.evento(con, "IMPORTAR_CONTROLE", {"arquivo": caminho.name, "ops": len(linhas_op), "novas": novas,
                                                "atualizadas": atualizadas, "fora_do_arquivo": fora,
                                                "campos_preservados": preservados})
        contagem.update(novas=novas, atualizadas=atualizadas, fora=fora, preservados=preservados)
        if previa:
            raise _Previa()


def importar_pasta(banco: Banco, origem: Path, pasta_dados: Path, previa: bool = False) -> list[str]:
    """Importa livros e Controle. Com `previa=True` mostra o que mudaria e não grava nada (banco e arquivos)."""
    origem = Path(origem)
    relatorio: list[str] = ["PRÉVIA DA IMPORTAÇÃO: NADA FOI GRAVADO. CONFIRA AS DIFERENÇAS ABAIXO."] if previa else []
    livros = sorted(p for p in origem.glob("*.xls[mx]") if not p.name.startswith("~$"))
    controle = [p for p in livros if "CONTROLE" in p.name.upper()]
    for p in livros:
        if p in controle:
            continue
        try:
            importar_livro(banco, p, pasta_dados / "Modelos", relatorio, previa)
        except Exception as e:  # um livro com problema não impede os demais
            relatorio.append(f"ERRO EM {p.name}: {e}")
    for p in controle:
        try:
            importar_controle(banco, p, relatorio, previa)
        except ErroValidacao as e:   # arquivo inválido: avisa e não mexe no histórico
            relatorio.append(f"ERRO EM {p.name}: {e}")
    return relatorio
