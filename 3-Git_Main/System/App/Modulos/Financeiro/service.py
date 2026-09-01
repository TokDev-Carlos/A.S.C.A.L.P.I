from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from Core.audit import log
from Core.db import connect
from Core.ids import next_id
from Core.text import upper_text
from Core.validation import money


ADMIN_CHARTS = {"FINANCEIRO_MENSAL", "RESULTADO_POR_OBRA"}
OPERATIONAL_CHARTS = {
    "VALOR_REAL_MENSAL",
    "CAMINHOES_MAIS_USADOS",
    "DIAS_MAIOR_CARREGAMENTO",
    "VIAGENS_MAIORES_CUSTOS",
}
MONTHS = {
    1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ",
}


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _validate_date(value: str, label: str = "Data") -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except Exception as exc:
        raise ValueError(f"{label} inválida. Use AAAA-MM-DD.") from exc


def list_receitas():
    """Lista pagamentos manuais; a rota só os entrega a perfis financeiros."""
    with connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                """SELECT r.*, o.nome obra_nome, o.municipio,
                          u.nome unidade_nome, u.uf
                     FROM receitas r
                     JOIN obras o ON o.id = r.obra_id
                     JOIN unidades u ON u.id = o.unidade_id
                    ORDER BY r.data_competencia DESC, r.id DESC"""
            )
        ]


def create_receita(
    obra_id: str,
    data_competencia: str,
    valor,
    descricao: str = "",
    origem: str = "PAGO_MANUAL",
):
    """Registra um valor efetivamente pago para uma obra."""
    data_competencia = _validate_date(data_competencia, "Data do pagamento")
    value = money(valor, field="VALOR PAGO")
    if value <= 0:
        raise ValueError("O valor pago deve ser maior que zero.")
    now = _now()
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM obras WHERE id=?", (obra_id,)).fetchone():
            raise ValueError("Obra inválida.")
        payment_id = next_id(conn, "receita", "REC")
        conn.execute(
            """INSERT INTO receitas(
                   id,obra_id,data_competencia,descricao,valor,origem,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                payment_id, obra_id, data_competencia,
                upper_text(descricao, multiline=True), value,
                upper_text(origem) or "PAGO_MANUAL", now, now,
            ),
        )
        log("PAGAMENTO_REGISTRADO", id=payment_id, obra=obra_id, data=data_competencia, valor=value)
        return dict(conn.execute("SELECT * FROM receitas WHERE id=?", (payment_id,)).fetchone())


def _normalize_filters(ano=None, mes=None, uf=None) -> tuple[str, str, str]:
    year = str(ano or "").strip()
    if year and (not year.isdigit() or len(year) != 4):
        raise ValueError("ANO INVÁLIDO.")
    month = ""
    if str(mes or "").strip():
        try:
            month_number = int(str(mes).strip())
        except ValueError as exc:
            raise ValueError("MÊS INVÁLIDO.") from exc
        if month_number < 1 or month_number > 12:
            raise ValueError("MÊS INVÁLIDO.")
        month = f"{month_number:02d}"
    state = upper_text(uf)
    if state and (len(state) != 2 or not state.isalpha()):
        raise ValueError("ESTADO INVÁLIDO.")
    return year, month, state


def _filters(ano=None, mes=None, uf=None):
    year, month, state = _normalize_filters(ano, mes, uf)
    where = []
    args = []
    if year:
        where.append("substr(data_ref,1,4)=?")
        args.append(year)
    if month:
        where.append("substr(data_ref,6,2)=?")
        args.append(month)
    if state:
        where.append("uf=?")
        args.append(state)
    return (" WHERE " + " AND ".join(where) if where else ""), args


def _event_query() -> str:
    """Eventos administrativos: gerado, pago e custo reconhecido."""
    return """
        SELECT r.data_competencia data_ref,
               u.uf,u.nome estado,o.id obra_id,o.nome obra_nome,o.municipio,
               0.0 receita_gerada,r.valor receita_paga,0.0 custo
          FROM receitas r
          JOIN obras o ON o.id=r.obra_id
          JOIN unidades u ON u.id=o.unidade_id
         WHERE o.deleted_at=''
        UNION ALL
        SELECT COALESCE(NULLIF(c.data_saida,''),c.data) data_ref,
               u.uf,u.nome estado,o.id obra_id,o.nome obra_nome,o.municipio,
               co.valor_obra receita_gerada,0.0 receita_paga,co.custo_viagem custo
          FROM carregamento_obras co
          JOIN carregamentos c ON c.id=co.carregamento_id
          JOIN obras o ON o.id=co.obra_id
          JOIN unidades u ON u.id=o.unidade_id
         WHERE c.status='EXPEDIDO' AND c.deleted_at='' AND o.deleted_at=''
        UNION ALL
        SELECT COALESCE(NULLIF(c.data_saida,''),c.data) data_ref,
               u.uf,u.nome estado,o.id obra_id,o.nome obra_nome,o.municipio,
               0.0 receita_gerada,0.0 receita_paga,co.custo_viagem custo
          FROM carregamento_obras co
          JOIN carregamentos c ON c.id=co.carregamento_id
          JOIN obras o ON o.id=co.obra_id
          JOIN unidades u ON u.id=o.unidade_id
         WHERE co.custo_viagem>0 AND c.status NOT IN ('EXPEDIDO','CANCELADO')
           AND c.deleted_at='' AND o.deleted_at=''
        UNION ALL
        SELECT v.data_saida data_ref,
               u.uf,u.nome estado,o.id obra_id,o.nome obra_nome,o.municipio,
               0.0 receita_gerada,0.0 receita_paga,v.custo_total custo
          FROM viagens v
          JOIN obras o ON o.id=v.obra_id
          JOIN unidades u ON u.id=o.unidade_id
         WHERE o.deleted_at=''
    """


def _operational_query() -> str:
    """Eventos liberados ao usuário padrão, sem pagamentos administrativos."""
    return """
        SELECT COALESCE(NULLIF(c.data_saida,''),c.data) data_ref,
               u.uf,u.nome estado,o.id obra_id,o.nome obra_nome,o.municipio,
               co.valor_obra valor_carregado,co.custo_viagem custo_viagem
          FROM carregamento_obras co
          JOIN carregamentos c ON c.id=co.carregamento_id
          JOIN obras o ON o.id=co.obra_id
          JOIN unidades u ON u.id=o.unidade_id
         WHERE c.status<>'CANCELADO' AND c.deleted_at='' AND o.deleted_at=''
        UNION ALL
        SELECT v.data_saida data_ref,
               u.uf,u.nome estado,o.id obra_id,o.nome obra_nome,o.municipio,
               0.0 valor_carregado,v.custo_total custo_viagem
          FROM viagens v
          JOIN obras o ON o.id=v.obra_id
          JOIN unidades u ON u.id=o.unidade_id
         WHERE o.deleted_at=''
    """


def _add_admin_fields(row: dict) -> dict:
    generated = round(float(row.get("receita_gerada") or 0), 2)
    paid = round(float(row.get("receita_paga") or 0), 2)
    cost = round(float(row.get("custo") or 0), 2)
    row.update(
        receita_gerada=generated,
        receita_paga=paid,
        custo=cost,
        saldo_receber=round(generated - paid, 2),
        lucro_gerado=round(generated - cost, 2),
        lucro_pago=round(paid - cost, 2),
        receita=generated,
        lucro=round(generated - cost, 2),
    )
    return row


def _add_operational_fields(row: dict) -> dict:
    loaded = round(float(row.get("valor_carregado") or 0), 2)
    cost = round(float(row.get("custo_viagens") or 0), 2)
    row.update(
        valor_carregado=loaded,
        custo_viagens=cost,
        valor_real=round(loaded - cost, 2),
    )
    return row


def _admin_summary(conn, ano=None, mes=None, uf=None) -> dict:
    base = _event_query()
    where, args = _filters(ano, mes, uf)
    works = [
        _add_admin_fields(dict(row))
        for row in conn.execute(
            f"""SELECT uf,estado,obra_id,obra_nome,municipio,
                        SUM(receita_gerada) receita_gerada,
                        SUM(receita_paga) receita_paga,SUM(custo) custo
                   FROM ({base}) x {where}
                  GROUP BY uf,estado,obra_id,obra_nome,municipio
                  ORDER BY estado,obra_nome""",
            args,
        )
    ]
    totals = {
        "receita_gerada": round(sum(row["receita_gerada"] for row in works), 2),
        "receita_paga": round(sum(row["receita_paga"] for row in works), 2),
        "saldo_receber": round(sum(row["saldo_receber"] for row in works), 2),
        "custo": round(sum(row["custo"] for row in works), 2),
        "lucro_gerado": round(sum(row["lucro_gerado"] for row in works), 2),
        "lucro_pago": round(sum(row["lucro_pago"] for row in works), 2),
    }
    totals["margem_gerada"] = round(totals["lucro_gerado"] / totals["receita_gerada"] * 100, 4) if totals["receita_gerada"] else 0.0
    totals["margem_paga"] = round(totals["lucro_pago"] / totals["receita_paga"] * 100, 4) if totals["receita_paga"] else 0.0
    totals.update(receita=totals["receita_gerada"], lucro=totals["lucro_gerado"], margem=totals["margem_gerada"])
    states = [
        _add_admin_fields(dict(row))
        for row in conn.execute(
            f"""SELECT uf,estado,SUM(receita_gerada) receita_gerada,
                        SUM(receita_paga) receita_paga,SUM(custo) custo
                   FROM ({base}) x {where}
                  GROUP BY uf,estado
                  ORDER BY (SUM(receita_gerada)-SUM(custo)) DESC""",
            args,
        )
    ]
    return {
        "modo": "ADMINISTRATIVO",
        "totais": totals,
        "obras": works,
        "estados": states,
        "campos": ["receita_gerada", "receita_paga", "saldo_receber", "custo", "lucro_gerado", "lucro_pago"],
    }


def _operational_summary(conn, ano=None, mes=None, uf=None) -> dict:
    base = _operational_query()
    where, args = _filters(ano, mes, uf)
    works = [
        _add_operational_fields(dict(row))
        for row in conn.execute(
            f"""SELECT uf,estado,obra_id,obra_nome,municipio,
                        SUM(valor_carregado) valor_carregado,
                        SUM(custo_viagem) custo_viagens
                   FROM ({base}) x {where}
                  GROUP BY uf,estado,obra_id,obra_nome,municipio
                  ORDER BY estado,obra_nome""",
            args,
        )
    ]
    totals = _add_operational_fields({
        "valor_carregado": sum(row["valor_carregado"] for row in works),
        "custo_viagens": sum(row["custo_viagens"] for row in works),
    })
    states = [
        _add_operational_fields(dict(row))
        for row in conn.execute(
            f"""SELECT uf,estado,SUM(valor_carregado) valor_carregado,
                        SUM(custo_viagem) custo_viagens
                   FROM ({base}) x {where}
                  GROUP BY uf,estado
                  ORDER BY (SUM(valor_carregado)-SUM(custo_viagem)) DESC""",
            args,
        )
    ]
    return {
        "modo": "OPERACIONAL",
        "totais": totals,
        "obras": works,
        "estados": states,
        "campos": ["valor_carregado", "custo_viagens", "valor_real"],
    }


def resumo(ano=None, mes=None, uf=None, *, administrative: bool = True):
    """Entrega somente os campos financeiros autorizados para o perfil."""
    _normalize_filters(ano, mes, uf)
    with connect() as conn:
        return _admin_summary(conn, ano, mes, uf) if administrative else _operational_summary(conn, ano, mes, uf)


def _monthly_graph(conn, ano, mes, uf, *, administrative: bool) -> dict:
    base = _event_query() if administrative else _operational_query()
    where, args = _filters(ano, mes, uf)
    if administrative:
        rows = [
            _add_admin_fields(dict(row))
            for row in conn.execute(
                f"""SELECT substr(data_ref,1,7) competencia,
                            SUM(receita_gerada) receita_gerada,
                            SUM(receita_paga) receita_paga,SUM(custo) custo
                       FROM ({base}) x {where}
                      GROUP BY substr(data_ref,1,7) ORDER BY competencia""",
                args,
            )
        ]
        return {
            "tipo": "FINANCEIRO_MENSAL",
            "titulo": "GERADO, PAGO E CUSTO POR MÊS",
            "subtitulo": "COMPARAÇÃO ADMINISTRATIVA DOS VALORES EXPEDIDOS E RECEBIDOS.",
            "unidade": "MOEDA",
            "series": [
                {"chave": "receita_gerada", "rotulo": "GERADO", "cor": "#3988cd"},
                {"chave": "receita_paga", "rotulo": "PAGO", "cor": "#41a77d"},
                {"chave": "custo", "rotulo": "CUSTO", "cor": "#ed9b49"},
            ],
            "pontos": [
                {
                    "rotulo": f"{MONTHS[int(row['competencia'][5:7])]}/{row['competencia'][2:4]}",
                    "receita_gerada": row["receita_gerada"],
                    "receita_paga": row["receita_paga"],
                    "custo": row["custo"],
                }
                for row in rows
            ],
        }
    rows = [
        _add_operational_fields(dict(row))
        for row in conn.execute(
            f"""SELECT substr(data_ref,1,7) competencia,
                        SUM(valor_carregado) valor_carregado,
                        SUM(custo_viagem) custo_viagens
                   FROM ({base}) x {where}
                  GROUP BY substr(data_ref,1,7) ORDER BY competencia""",
            args,
        )
    ]
    return {
        "tipo": "VALOR_REAL_MENSAL",
        "titulo": "VALOR CARREGADO, CUSTO E VALOR REAL POR MÊS",
        "subtitulo": "VISÃO OPERACIONAL DOS CARREGAMENTOS NÃO CANCELADOS.",
        "unidade": "MOEDA",
        "series": [
            {"chave": "valor_carregado", "rotulo": "CARREGADO", "cor": "#3988cd"},
            {"chave": "custo_viagens", "rotulo": "CUSTO", "cor": "#ed9b49"},
            {"chave": "valor_real", "rotulo": "VALOR REAL", "cor": "#41a77d"},
        ],
        "pontos": [
            {
                "rotulo": f"{MONTHS[int(row['competencia'][5:7])]}/{row['competencia'][2:4]}",
                "valor_carregado": row["valor_carregado"],
                "custo_viagens": row["custo_viagens"],
                "valor_real": row["valor_real"],
            }
            for row in rows
        ],
    }


def _vehicles_graph(conn, ano, mes, uf) -> dict:
    where, args = _filters(ano, mes, uf)
    rows = conn.execute(
        f"""SELECT veiculo rotulo,COUNT(DISTINCT carregamento_id) quantidade
               FROM (
                    SELECT COALESCE(NULLIF(c.data_saida,''),c.data) data_ref,u.uf,
                           c.id carregamento_id,
                           COALESCE(NULLIF(c.placa,''),NULLIF(c.veiculo,''),'NÃO INFORMADO') veiculo
                      FROM carregamentos c
                      JOIN carregamento_obras co ON co.carregamento_id=c.id
                      JOIN obras o ON o.id=co.obra_id
                      JOIN unidades u ON u.id=o.unidade_id
                     WHERE c.status<>'CANCELADO' AND c.deleted_at='' AND o.deleted_at=''
               ) x {where}
              GROUP BY veiculo ORDER BY quantidade DESC,veiculo LIMIT 12""",
        args,
    ).fetchall()
    return {
        "tipo": "CAMINHOES_MAIS_USADOS",
        "titulo": "CAMINHÕES MAIS USADOS",
        "subtitulo": "QUANTIDADE DE CARREGAMENTOS NÃO CANCELADOS POR VEÍCULO.",
        "unidade": "QUANTIDADE",
        "series": [{"chave": "quantidade", "rotulo": "CARREGAMENTOS", "cor": "#7657b2"}],
        "pontos": [{"rotulo": row["rotulo"], "quantidade": int(row["quantidade"])} for row in rows],
    }


def _busy_days_graph(conn, ano, mes, uf) -> dict:
    where, args = _filters(ano, mes, uf)
    rows = conn.execute(
        f"""SELECT data_ref,COUNT(DISTINCT carregamento_id) quantidade
               FROM (
                    SELECT COALESCE(NULLIF(c.data_saida,''),c.data) data_ref,u.uf,c.id carregamento_id
                      FROM carregamentos c
                      JOIN carregamento_obras co ON co.carregamento_id=c.id
                      JOIN obras o ON o.id=co.obra_id
                      JOIN unidades u ON u.id=o.unidade_id
                     WHERE c.status<>'CANCELADO' AND c.deleted_at='' AND o.deleted_at=''
               ) x {where}
              GROUP BY data_ref ORDER BY quantidade DESC,data_ref DESC LIMIT 15""",
        args,
    ).fetchall()
    points = sorted(
        [
            {"rotulo": f"{row['data_ref'][8:10]}/{row['data_ref'][5:7]}", "ordem": row["data_ref"], "quantidade": int(row["quantidade"])}
            for row in rows
        ],
        key=lambda row: row["ordem"],
    )
    for point in points:
        point.pop("ordem", None)
    return {
        "tipo": "DIAS_MAIOR_CARREGAMENTO",
        "titulo": "DIAS COM MAIS CARREGAMENTOS",
        "subtitulo": "ATÉ 15 DIAS DE MAIOR MOVIMENTO NO PERÍODO SELECIONADO.",
        "unidade": "QUANTIDADE",
        "series": [{"chave": "quantidade", "rotulo": "CARREGAMENTOS", "cor": "#2f9f98"}],
        "pontos": points,
    }


def _costliest_trips_graph(conn, ano, mes, uf) -> dict:
    where, args = _filters(ano, mes, uf)
    rows = conn.execute(
        f"""SELECT carregamento_id,data_ref,SUM(custo_viagem) custo_viagem
               FROM (
                    SELECT COALESCE(NULLIF(c.data_saida,''),c.data) data_ref,u.uf,
                           c.id carregamento_id,co.custo_viagem
                      FROM carregamentos c
                      JOIN carregamento_obras co ON co.carregamento_id=c.id
                      JOIN obras o ON o.id=co.obra_id
                      JOIN unidades u ON u.id=o.unidade_id
                     WHERE c.status<>'CANCELADO' AND c.deleted_at='' AND o.deleted_at=''
               ) x {where}
              GROUP BY carregamento_id,data_ref
              ORDER BY custo_viagem DESC,data_ref DESC LIMIT 10""",
        args,
    ).fetchall()
    return {
        "tipo": "VIAGENS_MAIORES_CUSTOS",
        "titulo": "VIAGENS COM MAIORES CUSTOS",
        "subtitulo": "DEZ CARREGAMENTOS COM MAIOR CUSTO NO PERÍODO.",
        "unidade": "MOEDA",
        "series": [{"chave": "custo_viagem", "rotulo": "CUSTO", "cor": "#ed9b49"}],
        "pontos": [
            {"rotulo": row["carregamento_id"], "custo_viagem": round(float(row["custo_viagem"] or 0), 2)}
            for row in rows
        ],
    }


def _work_result_graph(conn, ano, mes, uf) -> dict:
    base = _event_query()
    where, args = _filters(ano, mes, uf)
    rows = [
        _add_admin_fields(dict(row))
        for row in conn.execute(
            f"""SELECT obra_id,obra_nome,SUM(receita_gerada) receita_gerada,
                        SUM(receita_paga) receita_paga,SUM(custo) custo
                   FROM ({base}) x {where}
                  GROUP BY obra_id,obra_nome
                  ORDER BY (SUM(receita_gerada)-SUM(custo)) DESC LIMIT 10""",
            args,
        )
    ]
    return {
        "tipo": "RESULTADO_POR_OBRA",
        "titulo": "RESULTADO GERADO POR OBRA",
        "subtitulo": "DEZ OBRAS ORDENADAS PELO VALOR EXPEDIDO MENOS O CUSTO.",
        "unidade": "MOEDA",
        "series": [
            {"chave": "receita_gerada", "rotulo": "GERADO", "cor": "#3988cd"},
            {"chave": "custo", "rotulo": "CUSTO", "cor": "#ed9b49"},
            {"chave": "lucro_gerado", "rotulo": "RESULTADO", "cor": "#41a77d"},
        ],
        "pontos": [
            {
                "rotulo": row["obra_nome"], "receita_gerada": row["receita_gerada"],
                "custo": row["custo"], "lucro_gerado": row["lucro_gerado"],
            }
            for row in rows
        ],
    }


def grafico(tipo="", ano=None, mes=None, uf=None, *, administrative: bool = True) -> dict:
    """Retorna um único conjunto de dados para o gráfico selecionado."""
    _normalize_filters(ano, mes, uf)
    selected = upper_text(tipo).replace(" ", "_")
    if not selected:
        selected = "FINANCEIRO_MENSAL" if administrative else "VALOR_REAL_MENSAL"
    allowed = set(OPERATIONAL_CHARTS)
    if administrative:
        allowed |= ADMIN_CHARTS
    if selected not in allowed:
        if selected in ADMIN_CHARTS:
            raise PermissionError("ESTE GRÁFICO CONTÉM INFORMAÇÕES EXCLUSIVAS DO ADMINISTRADOR.")
        raise ValueError("TIPO DE GRÁFICO INVÁLIDO.")
    with connect() as conn:
        if selected == "FINANCEIRO_MENSAL":
            result = _monthly_graph(conn, ano, mes, uf, administrative=True)
        elif selected == "VALOR_REAL_MENSAL":
            result = _monthly_graph(conn, ano, mes, uf, administrative=False)
        elif selected == "CAMINHOES_MAIS_USADOS":
            result = _vehicles_graph(conn, ano, mes, uf)
        elif selected == "DIAS_MAIOR_CARREGAMENTO":
            result = _busy_days_graph(conn, ano, mes, uf)
        elif selected == "VIAGENS_MAIORES_CUSTOS":
            result = _costliest_trips_graph(conn, ano, mes, uf)
        else:
            result = _work_result_graph(conn, ano, mes, uf)
    result["modo"] = "ADMINISTRATIVO" if administrative else "OPERACIONAL"
    return result


def update_receita(receita_id: str, data_competencia: str, valor, descricao: str = ""):
    data_competencia = _validate_date(data_competencia, "Data do pagamento")
    value = money(valor, field="VALOR PAGO")
    if value <= 0:
        raise ValueError("O valor pago deve ser maior que zero.")
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM receitas WHERE id=?", (receita_id,)).fetchone():
            raise ValueError("Pagamento não encontrado.")
        conn.execute(
            """UPDATE receitas SET data_competencia=?,valor=?,descricao=?,
                      origem='PAGO_MANUAL',updated_at=? WHERE id=?""",
            (data_competencia, value, upper_text(descricao, multiline=True), _now(), receita_id),
        )
        log("PAGAMENTO_EDITADO", id=receita_id, data=data_competencia, valor=value)
        return dict(conn.execute("SELECT * FROM receitas WHERE id=?", (receita_id,)).fetchone())
