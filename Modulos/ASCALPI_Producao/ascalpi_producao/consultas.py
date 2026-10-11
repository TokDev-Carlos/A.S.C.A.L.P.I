"""Consultas e agregações (painel, resumo, eventos, pendências): só leitura, nunca alteram O.P."""
from __future__ import annotations

import json
from collections import Counter
from datetime import date

from . import pdf

ESTADOS = ("ATRASADA", "PROXIMA", "NO_PRAZO", "SEM_DATA", "NA_OBRA", "INSTALADA", "CANCELADA")
EM_PRODUCAO = ("ATRASADA", "PROXIMA", "NO_PRAZO", "SEM_DATA")
MESES = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")


def pendencia(s, chave: str) -> list:
    """Listas guardadas pelas migrações (nada é corrigido sozinho; o Carlos confere e decide)."""
    r = s.banco.um("SELECT valor FROM meta WHERE chave = ?", (chave,))
    try:
        return json.loads(r["valor"]) if r else []
    except ValueError:
        return []

def pendencias(s) -> dict:
    ids = pendencia(s, "migracao_contrato_ambiguas")
    ops = s.banco.todos("SELECT id, numero, cliente, obra FROM ops WHERE id IN (%s) ORDER BY ano, seq"
                           % ",".join("?" * len(ids)), tuple(ids)) if ids else []
    return {"contrato_a_conferir": ops, "revisoes_duplicadas": pendencia(s, "revisoes_duplicadas"),
            "saldo_a_conferir": pendencia(s, "saldo_a_conferir")}

def resumo(s) -> dict:
    ano = date.today().year
    return {
        "ano": ano,
        "proximo_numero": s.proximo_numero(ano),
        "prefeituras": s.banco.um("SELECT COUNT(*) n FROM prefeituras WHERE ativo = 1")["n"],
        "modelos": s.banco.um("SELECT COUNT(*) n FROM modelos WHERE ativo = 1")["n"],
        "ops_ano": s.banco.um("SELECT COUNT(*) n FROM ops WHERE ano = ? AND situacao = 'ATIVA'", (ano,))["n"],
        "ops_sistema": s.banco.um("SELECT COUNT(*) n FROM ops WHERE origem = 'SISTEMA'")["n"],
        "sem_data": s.banco.um("SELECT COUNT(*) n FROM ops WHERE ano = ? AND prazo_data IS NULL AND situacao = 'ATIVA'",
                                  (ano,))["n"],
        "motor_pdf": motor_ou_erro(s.config()["motor_pdf"]),
        "pastas": [str(p) for p in s.pastas_publicacao()],
        "pendencias": s.pendencias(),
    }

def painel(s) -> dict:
    hoje = date.today()
    ano = hoje.year
    ops = s.listar_ops(ano=ano)
    validas = [o for o in ops if o["estado"] != "CANCELADA"]
    contagem = Counter(o["estado"] for o in ops)
    por_mes = [0] * 12
    for o in validas:
        if o["solicitado_em"]:
            por_mes[int(o["solicitado_em"][5:7]) - 1] += 1
    por_prefeitura = Counter(o["cliente"] or "SEM CLIENTE" for o in validas).most_common()
    topo = [{"nome": n, "ops": q} for n, q in por_prefeitura[:8]]
    resto = sum(q for _, q in por_prefeitura[8:])
    if resto:
        topo.append({"nome": f"OUTRAS ({len(por_prefeitura) - 8})", "ops": resto, "outras": True})
    producao = [o for o in ops if o["estado"] in ("PROXIMA", "NO_PRAZO")]
    producao.sort(key=lambda o: (o["dias"], o["seq"]))
    atrasadas = sorted((o for o in ops if o["estado"] == "ATRASADA"), key=lambda o: (-o["dias"], -o["seq"]))
    alertas, negativos, encerrados = [], 0, 0
    for c in s.contratos():
        for it in s.saldo_contrato(c["id"]):
            if it["extra"]:
                continue
            saldo = it["saldo"]
            if saldo == "ACABOU" or (isinstance(saldo, (int, float)) and saldo < 0):
                if saldo == "ACABOU":
                    encerrados += 1
                else:
                    negativos += 1
                alertas.append({"prefeitura": c["prefeitura"], "prefeitura_id": c["prefeitura_id"],
                                "contrato_id": c["id"], "ata": c["ata"], "codigo": it["codigo"],
                                "equipamento": it["equipamento"], "saldo": saldo, "montante": it["montante"]})
    alertas.sort(key=lambda a: (a["saldo"] == "ACABOU", a["saldo"] if a["saldo"] != "ACABOU" else 0))
    semana = [o for o in producao if o["dias"] is not None and 0 <= o["dias"] <= 7]
    return {
        "ano": ano, "hoje": hoje.isoformat(), "proximo_numero": s.proximo_numero(ano),
        "contagem": {e: contagem.get(e, 0) for e in ESTADOS},
        "total_ano": len(validas), "em_producao": sum(contagem.get(e, 0) for e in EM_PRODUCAO),
        "semana": len(semana),
        "por_mes": [{"mes": MESES[i], "ops": n} for i, n in enumerate(por_mes)],
        "por_prefeitura": topo,
        "proximas": producao[:8],
        "atrasadas": atrasadas[:8],
        "sem_data": sorted((o for o in ops if o["estado"] == "SEM_DATA"), key=lambda o: -o["seq"])[:6],
        "alertas_saldo": alertas[:8], "saldo_negativos": negativos, "saldo_encerrados": encerrados,
        "eventos": s.eventos(10),
    }

def eventos(s, limite: int = 200) -> list[dict]:
    lista = s.banco.todos("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,))
    ids = set()
    for e in lista:
        try:
            e["dados"] = json.loads(e["detalhe"]) if e["detalhe"].startswith("{") else {}
        except ValueError:
            e["dados"] = {}
        if isinstance(e["dados"].get("op"), int):
            ids.add(e["dados"]["op"])
    if ids:
        marcas = ",".join("?" * len(ids))
        numeros = {r["id"]: r for r in s.banco.todos(
            f"SELECT id, numero, cliente, obra FROM ops WHERE id IN ({marcas})", tuple(ids))}
        for e in lista:
            o = numeros.get(e["dados"].get("op"))
            if o:
                e["op"] = o
    return lista


def motor_ou_erro(motor: str) -> str:
    try:
        return pdf.motor_escolhido(motor)
    except pdf.ErroPDF as e:
        return f"INDISPONÍVEL ({e})"
