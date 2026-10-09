"""Importação única dos arquivos legados (OK-<CIDADE>_O.P.xlsm e Controle) para o banco do ASCALPI Produção.

Nada é gravado nos arquivos de origem: eles são apenas lidos.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from . import documento, pacote
from .banco import Banco, agora
from .regras import (codigo_valido, normalizar_cabecalho, normalizar_chave, normalizar_codigo, numero_br,
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
        itens.append({
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

def importar_livro(banco: Banco, caminho: Path, pasta_modelos: Path, relatorio: list[str]) -> None:
    info = ler_livro(caminho)
    pasta = pasta_modelos / sanitizar_nome(info["cliente"])
    pasta.mkdir(parents=True, exist_ok=True)
    modelos_xlsx = {}
    for m in info["modelos"]:
        conteudo = pacote.extrair_aba(caminho, m["aba"])
        destino = pasta / f"{sanitizar_nome(m['codename'])}.xlsx"
        destino.write_bytes(conteudo)
        modelos_xlsx[m["codename"]] = (destino, documento.linhas_do_modelo(conteudo))

    with banco.transacao() as con:
        con.execute("INSERT INTO prefeituras (nome, arquivo_origem) VALUES (?, ?) "
                    "ON CONFLICT(nome) DO UPDATE SET arquivo_origem = excluded.arquivo_origem",
                    (info["cliente"], info["arquivo"]))
        pid = con.execute("SELECT id FROM prefeituras WHERE nome = ?", (info["cliente"],)).fetchone()[0]
        ids_contrato = {}
        for ata, c in info["contratos"].items():
            con.execute("INSERT INTO contratos (prefeitura_id, ata, nome, descricao, importado_em) VALUES (?,?,?,?,?) "
                        "ON CONFLICT(prefeitura_id, ata) DO UPDATE SET nome = excluded.nome, "
                        "descricao = excluded.descricao, importado_em = excluded.importado_em",
                        (pid, ata, c["nome"], c["descricao"], agora()))
            cid = con.execute("SELECT id FROM contratos WHERE prefeitura_id = ? AND ata = ?", (pid, ata)).fetchone()[0]
            ids_contrato[ata] = cid
            for it in c["itens"]:
                con.execute("INSERT INTO contrato_itens (contrato_id, codigo, equipamento, valor_un, montante, "
                            "medido_inicial, previsao_inicial) VALUES (?,?,?,?,?,?,?) "
                            "ON CONFLICT(contrato_id, codigo) DO UPDATE SET equipamento = excluded.equipamento, "
                            "valor_un = excluded.valor_un, montante = excluded.montante, "
                            "medido_inicial = excluded.medido_inicial, previsao_inicial = excluded.previsao_inicial",
                            (cid, it["codigo"], it["equipamento"], it["valor_un"], it["montante"],
                             it["medido"], it["previsao"]))
            relatorio.append(f"  CONTRATO {ata}: {len(c['itens'])} ITENS")
        for m in info["modelos"]:
            destino, linhas = modelos_xlsx[m["codename"]]
            rel = destino.relative_to(pasta_modelos.parent).as_posix()
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
        banco.evento(con, "IMPORTAR_LIVRO", {"arquivo": info["arquivo"], "cliente": info["cliente"]})
    relatorio.insert(len(relatorio) - len(info["contratos"]) - len(info["modelos"]),
                     f"{info['arquivo']} → {info['cliente']}")


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


def importar_controle(banco: Banco, caminho: Path, relatorio: list[str]) -> None:
    partes = pacote.carregar(caminho)
    ss = pacote.strings_compartilhadas(partes)
    linhas_op, cores = [], []
    for a in pacote.abas(partes):
        for t in pacote.tabelas(partes, a["parte"]):
            vals = None
            if t["nome"] == "Controle_OP":
                vals = pacote.ler_valores(partes, a["parte"], ss)
                c1, r1, c2, r2 = _faixa(t["ref"])
                mapa = {}
                for c in range(c1, c2 + 1):
                    h = normalizar_cabecalho(_texto(_v(vals, c, r1)))
                    campo = COLUNAS_CONTROLE.get(h) or ("numero" if h.startswith("N") and h.endswith(" OP") else None)
                    if campo and campo not in mapa.values():
                        mapa[c] = campo
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
    with banco.transacao() as con:
        prefeituras = [dict(r) for r in con.execute("SELECT id, nome FROM prefeituras").fetchall()]
        for nome, ap, cn in cores:
            pid = _achar_prefeitura(prefeituras, nome)
            if pid:
                con.execute("UPDATE prefeituras SET cores_aparelhos = ?, cores_canoplas = ? WHERE id = ?", (ap.strip(), cn.strip(), pid))
        con.execute("DELETE FROM ops WHERE origem = 'LEGADO'")
        for d in linhas_op:
            numero = _texto(d.get("numero"))
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
            con.execute(
                "INSERT INTO ops (numero, ano, seq, origem, prefeitura_id, cliente, obra, solicitante, tipo, tipo_arquivo, "
                "material, prazo_data, prazo_texto, entrega_atualizada, solicitado_em, status_instalacao, material_obra, "
                "fotografico, obs, criado_em, atualizado_em) VALUES (?,?,?,'LEGADO',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (numero, ano, seq, _achar_prefeitura(prefeituras, cliente), cliente, _texto(d.get("obra")),
                 _texto(d.get("solicitante")), tipo, tipo_arquivo(tipo), _texto(d.get("material")),
                 prazo_data.isoformat() if prazo_data else None,
                 None if prazo_data else (_texto(prazo).upper() or None),
                 _data_ou_texto(d.get("entrega_atualizada")),
                 solicitado, _texto(d.get("status_instalacao")), _texto(d.get("material_obra")),
                 _texto(d.get("fotografico")), _texto(d.get("obs")), agora(), agora()))
        banco.evento(con, "IMPORTAR_CONTROLE", {"arquivo": caminho.name, "ops": len(linhas_op)})
    relatorio.append(f"{caminho.name} → {len(linhas_op)} O.P. NO HISTÓRICO, {len(cores)} PREFEITURAS COM CORES")


def importar_pasta(banco: Banco, origem: Path, pasta_dados: Path) -> list[str]:
    origem = Path(origem)
    relatorio: list[str] = []
    livros = sorted(p for p in origem.glob("*.xls[mx]") if not p.name.startswith("~$"))
    controle = [p for p in livros if "CONTROLE" in p.name.upper()]
    for p in livros:
        if p in controle:
            continue
        try:
            importar_livro(banco, p, pasta_dados / "Modelos", relatorio)
        except Exception as e:  # um livro com problema não impede os demais
            relatorio.append(f"ERRO EM {p.name}: {e}")
    for p in controle:
        importar_controle(banco, p, relatorio)
    return relatorio
