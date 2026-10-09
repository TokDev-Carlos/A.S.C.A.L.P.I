"""Regras de uso do módulo: O.P., saldo dos contratos, documentos e acompanhamento."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from . import documento, pdf
from .banco import Banco, agora
from .imagens import CacheImagens
from .regras import (SALDO_ENCERRADO, SALDO_NEGATIVO, SALDO_NEGATIVO_CONFIRMADO, SALDO_OK, SEM_CONTRATO,
                     SaldoItem, agregar_por_base, codigo_base, detectar_material, formatar_numero,
                     interpretar_prazo, montar_nome_base, numero_br, proximo_numero, simular_saldo, tipo_arquivo)

CONFIG_PADRAO = {
    "senha_arquivos": "",      # vazio = gerada na 1ª execução e guardada só no config.json local
    "motor_pdf": "auto",
    "publicar": True,
    "pasta_xlsx": "",          # vazio = <dados>/Documentos/O.Ps
    "pasta_pdf": "",           # vazio = <dados>/Documentos/PDFs
}
CAMPOS_ACOMPANHAMENTO = ("status_instalacao", "entrega_atualizada", "material_obra", "fotografico", "obs")
ESTADOS = ("ATRASADA", "PROXIMA", "NO_PRAZO", "SEM_DATA", "NA_OBRA", "INSTALADA", "CANCELADA")
EM_PRODUCAO = ("ATRASADA", "PROXIMA", "NO_PRAZO", "SEM_DATA")
DIAS_PROXIMA = 3
MESES = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")


def estado_op(o: dict, hoje: date | None = None) -> dict:
    """Situação da O.P. pelas colunas do Controle: cancelada > instalada > na obra > produção (pelo prazo)."""
    hoje = hoje or date.today()
    st = str(o.get("status_instalacao") or "").strip().upper()
    mo = str(o.get("material_obra") or "").strip().upper()
    ea = str(o.get("entrega_atualizada") or "").strip().upper()
    prazo = None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ea):          # entrega atualizada com nova data vale como prazo
        prazo = date.fromisoformat(ea)
    elif o.get("prazo_data"):
        prazo = date.fromisoformat(o["prazo_data"])
    dias = (prazo - hoje).days if prazo else None
    if o.get("situacao") == "CANCELADA" or st in ("CANCELADO", "CANCELADA", "DUPLICADO") or mo in ("CANCELADO", "DUPLICADO"):
        estado = "CANCELADA"
    elif st == "OK":
        estado = "INSTALADA"
    elif mo == "OK" or ea == "OK":
        estado = "NA_OBRA"
    elif prazo is None:
        estado = "SEM_DATA"
    elif dias < 0:
        estado = "ATRASADA"
    elif dias <= DIAS_PROXIMA:
        estado = "PROXIMA"
    else:
        estado = "NO_PRAZO"
    return {"estado": estado, "dias": dias, "prazo_efetivo": prazo.isoformat() if prazo else None}


class ErroValidacao(ValueError):
    pass


class Servico:
    def __init__(self, pasta_dados: Path):
        self.dados = Path(pasta_dados).resolve()
        self.dados.mkdir(parents=True, exist_ok=True)
        self.banco = Banco(self.dados / "ascalpi_producao.db")
        self.arquivo_config = self.dados / "config.json"
        self.fotos = CacheImagens()
        if not self.arquivo_config.exists():
            self.salvar_config({})
        if not self.config()["senha_arquivos"]:
            import secrets
            self.salvar_config({"senha_arquivos": secrets.token_urlsafe(12)})

    # ------------------------------------------------------------ configuração
    def config(self) -> dict:
        try:
            atual = json.loads(self.arquivo_config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            atual = {}
        return {**CONFIG_PADRAO, **{k: v for k, v in atual.items() if k in CONFIG_PADRAO}}

    def salvar_config(self, novos: dict) -> dict:
        cfg = {**(self.config() if self.arquivo_config.exists() else CONFIG_PADRAO),
               **{k: v for k, v in novos.items() if k in CONFIG_PADRAO}}
        tmp = self.arquivo_config.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.arquivo_config)
        return cfg

    def pastas_publicacao(self) -> tuple[Path, Path]:
        cfg = self.config()
        px = Path(cfg["pasta_xlsx"]) if cfg["pasta_xlsx"] else self.dados / "Documentos" / "O.Ps"
        pp = Path(cfg["pasta_pdf"]) if cfg["pasta_pdf"] else self.dados / "Documentos" / "PDFs"
        return px, pp

    # ------------------------------------------------------------ cadastros
    def prefeituras(self) -> list[dict]:
        lista = self.banco.todos(
            "SELECT p.*, (SELECT COUNT(*) FROM modelos m WHERE m.prefeitura_id = p.id AND m.ativo = 1) AS modelos, "
            "(SELECT COUNT(*) FROM ops o WHERE o.prefeitura_id = p.id) AS ops, "
            "(SELECT COUNT(*) FROM ops o WHERE o.prefeitura_id = p.id AND o.ano = ?) AS ops_ano, "
            "(SELECT COUNT(*) FROM contratos c WHERE c.prefeitura_id = p.id) AS contratos "
            "FROM prefeituras p WHERE p.ativo = 1 ORDER BY p.nome", (date.today().year,))
        for p in lista:
            p["logo"] = self._modelo_com_logo(p["id"]) is not None
        return lista

    # ------------------------------------------------------------ fotos e logos (tiradas do modelo)
    def _arquivo_modelo(self, modelo: dict) -> Path:
        return self.dados / modelo["arquivo"]

    def _chaves_fotos(self, modelo: dict) -> set:
        try:
            return self.fotos.chaves(self._arquivo_modelo(modelo))
        except (OSError, KeyError, ValueError):
            return set()

    def _modelo_com_logo(self, prefeitura_id: int) -> dict | None:
        for m in self.banco.todos("SELECT * FROM modelos WHERE prefeitura_id = ? ORDER BY ativo DESC, aba", (prefeitura_id,)):
            if "logo" in self._chaves_fotos(m):
                return m
        return None

    def foto_modelo(self, modelo_id: int, chave: object) -> tuple[bytes, str, str] | None:
        modelo = self._modelo(modelo_id)
        try:
            return self.fotos.imagem(self._arquivo_modelo(modelo), chave)
        except (OSError, KeyError, ValueError):
            return None

    def logo_prefeitura(self, prefeitura_id: int) -> tuple[bytes, str, str] | None:
        m = self._modelo_com_logo(prefeitura_id)
        return self.fotos.imagem(self._arquivo_modelo(m), "logo") if m else None

    def modelos(self, prefeitura_id: int | None = None, todos: bool = False) -> list[dict]:
        sql = ("SELECT m.id, m.prefeitura_id, p.nome AS prefeitura, m.codename, m.aba, m.titulo, m.tipo_padrao, "
               "m.ativo, m.contrato_id, c.ata, c.descricao AS contrato_descricao, "
               "(SELECT COUNT(*) FROM modelo_linhas l WHERE l.modelo_id = m.id) AS equipamentos "
               "FROM modelos m JOIN prefeituras p ON p.id = m.prefeitura_id LEFT JOIN contratos c ON c.id = m.contrato_id "
               "WHERE (? IS NULL OR m.prefeitura_id = ?) AND (? OR m.ativo = 1) ORDER BY p.nome, m.aba")
        lista = self.banco.todos(sql, (prefeitura_id, prefeitura_id, 1 if todos else 0))
        for m in lista:
            completo = self._modelo(m["id"])
            chaves = self._chaves_fotos(completo)
            m["logo"] = "logo" in chaves
            m["fotos"] = sorted(k for k in chaves if isinstance(k, int))[:4]
            m["com_foto"] = len([k for k in chaves if isinstance(k, int)])
            m["ops"] = self.banco.um("SELECT COUNT(*) n FROM ops WHERE modelo_id = ?", (m["id"],))["n"]
        return lista

    def contratos(self, prefeitura_id: int | None = None) -> list[dict]:
        return self.banco.todos(
            "SELECT c.*, p.nome AS prefeitura, (SELECT COUNT(*) FROM contrato_itens i WHERE i.contrato_id = c.id) AS itens "
            "FROM contratos c JOIN prefeituras p ON p.id = c.prefeitura_id WHERE (? IS NULL OR c.prefeitura_id = ?) "
            "ORDER BY p.nome, c.ata", (prefeitura_id, prefeitura_id))

    def atualizar_modelo(self, modelo_id: int, contrato_id: int | None = None, ativo: bool | None = None) -> dict:
        m = self._modelo(modelo_id)
        with self.banco.transacao() as con:
            if contrato_id is not None:
                cid = int(contrato_id) or None
                if cid:
                    c = con.execute("SELECT prefeitura_id FROM contratos WHERE id = ?", (cid,)).fetchone()
                    if not c or c[0] != m["prefeitura_id"]:
                        raise ErroValidacao("CONTRATO NÃO PERTENCE À MESMA PREFEITURA DO MODELO.")
                con.execute("UPDATE modelos SET contrato_id = ? WHERE id = ?", (cid, modelo_id))
            if ativo is not None:
                con.execute("UPDATE modelos SET ativo = ? WHERE id = ?", (1 if ativo else 0, modelo_id))
            self.banco.evento(con, "MODELO_ALTERADO", {"modelo": modelo_id, "contrato": contrato_id, "ativo": ativo})
        return self._modelo(modelo_id)

    def ajustar_item(self, contrato_id: int, codigo: str, montante: float | None = None, ajuste: float | None = None,
                     motivo: str = "") -> None:
        with self.banco.transacao() as con:
            item = con.execute("SELECT * FROM contrato_itens WHERE contrato_id = ? AND codigo = ?", (contrato_id, codigo)).fetchone()
            if not item:
                raise ErroValidacao(f"ITEM {codigo} NÃO EXISTE NO CONTRATO.")
            if montante is not None:
                con.execute("UPDATE contrato_itens SET montante = ? WHERE id = ?", (float(montante), item["id"]))
            if ajuste is not None:
                con.execute("UPDATE contrato_itens SET ajuste = ? WHERE id = ?", (float(ajuste), item["id"]))
            self.banco.evento(con, "SALDO_AJUSTADO", {"contrato": contrato_id, "codigo": codigo, "montante": montante,
                                                       "ajuste": ajuste, "motivo": motivo,
                                                       "antes": {"montante": item["montante"], "ajuste": item["ajuste"]}})

    def _modelo(self, modelo_id: int) -> dict:
        m = self.banco.um("SELECT m.*, p.nome AS prefeitura FROM modelos m JOIN prefeituras p ON p.id = m.prefeitura_id "
                          "WHERE m.id = ?", (modelo_id,))
        if not m:
            raise ErroValidacao("MODELO NÃO ENCONTRADO.")
        return m

    # ------------------------------------------------------------ saldo
    def _consumo_sistema(self, contrato_id: int, excluir_op: int | None = None) -> dict[str, dict[str, float]]:
        linhas = self.banco.todos(
            "SELECT i.codigo, i.quantidade, o.status_instalacao FROM op_itens i JOIN ops o ON o.id = i.op_id "
            "JOIN modelos m ON m.id = o.modelo_id WHERE o.origem = 'SISTEMA' AND o.situacao = 'ATIVA' "
            "AND m.contrato_id = ? AND (? IS NULL OR o.id <> ?)", (contrato_id, excluir_op, excluir_op))
        total: dict[str, dict[str, float]] = {}
        for l in linhas:
            if not l["codigo"]:
                continue
            base = codigo_base(l["codigo"])
            d = total.setdefault(base, {"instalado": 0.0, "previsao": 0.0})
            d["instalado" if str(l["status_instalacao"] or "").strip().upper() == "OK" else "previsao"] += l["quantidade"]
        return total

    def saldo_contrato(self, contrato_id: int, excluir_op: int | None = None) -> list[dict]:
        itens = self.banco.todos("SELECT * FROM contrato_itens WHERE contrato_id = ?", (contrato_id,))
        sistema = self._consumo_sistema(contrato_id, excluir_op)
        saida = []
        for it in itens:
            s = sistema.get(it["codigo"], {"instalado": 0.0, "previsao": 0.0})
            quant = it["medido_inicial"] + s["instalado"]
            previsao = it["previsao_inicial"] + s["previsao"] + it["ajuste"]
            si = SaldoItem(it["codigo"], it["equipamento"], it["montante"], quant + previsao)
            saida.append({**it, "quant": quant, "previsao": previsao, "sistema_instalado": s["instalado"],
                          "sistema_previsao": s["previsao"], "saldo": si.saldo()})
        saida.sort(key=lambda d: (d["codigo"].startswith("0."), [int(x) for x in d["codigo"].split(".")]))
        return saida

    def _itens_saldo(self, contrato_id: int, excluir_op: int | None) -> dict[str, SaldoItem]:
        return {d["codigo"]: SaldoItem(d["codigo"], d["equipamento"], d["montante"], d["quant"] + d["previsao"])
                for d in self.saldo_contrato(contrato_id, excluir_op)}

    def modelo_completo(self, modelo_id: int, excluir_op: int | None = None) -> dict:
        m = self._modelo(modelo_id)
        linhas = self.banco.todos("SELECT linha, codigo, equipamento FROM modelo_linhas WHERE modelo_id = ? ORDER BY linha",
                                  (modelo_id,))
        itens = {}
        if m["contrato_id"]:
            itens = {d["codigo"]: d for d in self.saldo_contrato(m["contrato_id"], excluir_op)}
        chaves = self._chaves_fotos(m)
        for l in linhas:
            base = codigo_base(l["codigo"]) if l["codigo"] else None
            item = itens.get(base) if base else None
            l["saldo"] = item["saldo"] if item else None
            l["montante"] = item["montante"] if item else None
            l["realizado"] = item["quant"] if item else None
            l["previsao"] = item["previsao"] if item else None
            l["consumido"] = (item["quant"] + item["previsao"]) if item else None
            l["foto"] = l["linha"] in chaves
        m["linhas"] = linhas
        m["logo"] = "logo" in chaves
        return m

    def simular(self, modelo_id: int, quantidades: dict, excluir_op: int | None = None) -> dict:
        m = self._modelo(modelo_id)
        linhas = {l["linha"]: l for l in self.banco.todos("SELECT * FROM modelo_linhas WHERE modelo_id = ?", (modelo_id,))}
        pares = []
        for linha, qtd in quantidades.items():
            l = linhas.get(int(linha))
            if l is not None:
                pares.append((l["codigo"], qtd))
        if not m["contrato_id"]:
            return {"status": SEM_CONTRATO, "negativos": [], "encerrados": [], "erros": [], "exige_confirmacao": False}
        por_base, problemas = agregar_por_base(pares)
        sim = simular_saldo(self._itens_saldo(m["contrato_id"], excluir_op), por_base)
        sim.erros[:0] = problemas
        if problemas and sim.status != "ESTRUTURA_INVALIDA":
            sim.status = "ESTRUTURA_INVALIDA"
        return {"status": sim.status, "exige_confirmacao": sim.exige_confirmacao, "erros": sim.erros,
                "negativos": [vars(a) for a in sim.negativos], "encerrados": [vars(a) for a in sim.encerrados]}

    # ------------------------------------------------------------ O.P.
    def proximo_numero(self, ano: int | None = None) -> str:
        ano = ano or date.today().year
        existentes = [r["numero"] for r in self.banco.todos("SELECT numero FROM ops WHERE ano = ?", (ano,))]
        return formatar_numero(proximo_numero(existentes, ano), ano)

    def listar_ops(self, texto: str = "", ano: int | None = None, prefeitura_id: int | None = None,
                   situacao: str = "", limite: int = 3000, estado: str = "") -> list[dict]:
        sql = ("SELECT o.id, o.numero, o.ano, o.seq, o.origem, o.cliente, o.prefeitura_id, o.obra, o.solicitante, "
               "o.tipo, o.material, o.prazo_data, o.prazo_texto, o.entrega_atualizada, o.solicitado_em, o.rev, "
               "o.situacao, o.status_instalacao, o.material_obra, o.fotografico, o.obs, o.saldo_status, o.modelo_id, "
               "o.atualizado_em, m.aba AS modelo, m.titulo AS ata, "
               "(SELECT COUNT(*) FROM op_itens i WHERE i.op_id = o.id) AS itens, "
               "(SELECT COALESCE(SUM(i.quantidade), 0) FROM op_itens i WHERE i.op_id = o.id) AS pecas "
               "FROM ops o LEFT JOIN modelos m ON m.id = o.modelo_id WHERE 1=1")
        args: list = []
        if texto:
            sql += " AND (o.numero LIKE ? OR o.cliente LIKE ? OR o.obra LIKE ? OR o.solicitante LIKE ?)"
            args += [f"%{texto}%"] * 4
        if ano:
            sql += " AND o.ano = ?"
            args.append(int(ano))
        if prefeitura_id:
            sql += " AND o.prefeitura_id = ?"
            args.append(int(prefeitura_id))
        if situacao:
            sql += " AND o.situacao = ?"
            args.append(situacao)
        sql += " ORDER BY o.ano DESC, o.seq DESC, o.id DESC LIMIT ?"
        args.append(int(limite))
        hoje = date.today()
        lista = []
        filtro = {e.strip().upper() for e in str(estado or "").split(",") if e.strip()}
        for o in self.banco.todos(sql, tuple(args)):
            o.update(estado_op(o, hoje))
            if not filtro or o["estado"] in filtro:
                lista.append(o)
        return lista

    def op(self, op_id: int) -> dict:
        o = self.banco.um("SELECT o.*, m.aba AS modelo, m.contrato_id FROM ops o LEFT JOIN modelos m ON m.id = o.modelo_id "
                          "WHERE o.id = ?", (op_id,))
        if not o:
            raise ErroValidacao("O.P. NÃO ENCONTRADA.")
        o["itens"] = self.banco.todos("SELECT * FROM op_itens WHERE op_id = ? ORDER BY linha", (op_id,))
        o["revisoes"] = self.banco.todos("SELECT rev, momento, usuario, resumo FROM op_revisoes WHERE op_id = ? ORDER BY rev",
                                         (op_id,))
        o["arquivos"] = json.loads(o["arquivos"] or "{}")
        o.update(estado_op(o))
        return o

    def _validar(self, dados: dict, modelo: dict) -> tuple[dict, list[dict]]:
        obra = str(dados.get("obra") or "").strip().upper()
        solicitante = str(dados.get("solicitante") or "").strip().upper()
        if not obra:
            raise ErroValidacao("INFORME A OBRA.")
        if not solicitante:
            raise ErroValidacao("INFORME O SOLICITANTE.")
        try:
            prazo = interpretar_prazo(dados.get("prazo"))
        except ValueError as e:
            raise ErroValidacao(str(e))
        linhas_modelo = {l["linha"]: l for l in self.banco.todos("SELECT * FROM modelo_linhas WHERE modelo_id = ?",
                                                                 (modelo["id"],))}
        itens = []
        for it in dados.get("itens") or []:
            linha = int(it.get("linha"))
            if linha not in linhas_modelo:
                raise ErroValidacao(f"LINHA {linha} NÃO EXISTE NO MODELO.")
            bruto = it.get("quantidade")
            if bruto in (None, ""):
                continue
            qtd = numero_br(bruto)
            if qtd is None or qtd < 0:
                raise ErroValidacao(f"QUANTIDADE INVÁLIDA NA LINHA {linha} ({linhas_modelo[linha]['equipamento']}).")
            if qtd == 0:
                continue
            itens.append({"linha": linha, "codigo": linhas_modelo[linha]["codigo"],
                          "equipamento": linhas_modelo[linha]["equipamento"], "quantidade": qtd,
                          "inauguracao": str(it.get("inauguracao") or "").strip().upper(),
                          "observacao": str(it.get("observacao") or "").strip()})
        if not itens:
            raise ErroValidacao("A O.P. PRECISA DE PELO MENOS 1 EQUIPAMENTO COM QUANTIDADE.")
        tipo = str(dados.get("tipo") or modelo["tipo_padrao"] or "").strip().upper()
        cab = {"obra": obra, "solicitante": solicitante, "prazo": prazo, "tipo": tipo,
               "material": detectar_material([i["equipamento"] for i in itens], tipo)}
        return cab, itens

    def salvar_op(self, dados: dict, op_id: int | None = None, confirmar_negativo: bool = False,
                  usuario: str = "", publicar: bool | None = None) -> dict:
        atual = self.op(op_id) if op_id else None
        if atual and atual["origem"] != "SISTEMA":
            raise ErroValidacao("O.P. DO HISTÓRICO LEGADO: SÓ O ACOMPANHAMENTO PODE SER ALTERADO.")
        if atual and atual["situacao"] != "ATIVA":
            raise ErroValidacao("O.P. CANCELADA NÃO PODE SER ALTERADA.")
        modelo = self._modelo(int(atual["modelo_id"] if atual else dados.get("modelo_id") or 0))
        if not atual and not modelo["ativo"]:
            raise ErroValidacao("MODELO DESATIVADO.")
        cab, itens = self._validar(dados, modelo)
        sim = self.simular(modelo["id"], {i["linha"]: i["quantidade"] for i in itens}, excluir_op=op_id)
        if sim["status"] == "ESTRUTURA_INVALIDA":
            raise ErroValidacao("CONTRATO: " + " ".join(sim["erros"]))
        if sim["exige_confirmacao"] and not confirmar_negativo:
            return {"ok": False, "precisa_confirmacao": True, "simulacao": sim}
        saldo_status = sim["status"]
        if saldo_status == SALDO_NEGATIVO:
            saldo_status = SALDO_NEGATIVO_CONFIRMADO

        prazo = cab["prazo"]
        momento = agora()
        with self.banco.transacao() as con:
            campos = dict(obra=cab["obra"], solicitante=cab["solicitante"], tipo=cab["tipo"],
                          tipo_arquivo=tipo_arquivo(cab["tipo"]), material=cab["material"],
                          prazo_data=prazo.isoformat() if isinstance(prazo, date) else None,
                          prazo_texto=None if isinstance(prazo, date) else prazo,
                          saldo_status=saldo_status, saldo_confirmado=1 if saldo_status == SALDO_NEGATIVO_CONFIRMADO else 0,
                          atualizado_em=momento)
            if atual:
                rev = atual["rev"] + 1
                campos["rev"] = rev
                con.execute("UPDATE ops SET " + ", ".join(f"{k} = ?" for k in campos) + " WHERE id = ?",
                            (*campos.values(), op_id))
                con.execute("DELETE FROM op_itens WHERE op_id = ?", (op_id,))
                novo_id = op_id
            else:
                ano = date.today().year
                existentes = [r[0] for r in con.execute("SELECT numero FROM ops WHERE ano = ?", (ano,)).fetchall()]
                seq = proximo_numero(existentes, ano)
                rev = 0
                cur = con.execute(
                    "INSERT INTO ops (numero, ano, seq, origem, prefeitura_id, cliente, modelo_id, solicitado_em, rev, "
                    "criado_em, " + ", ".join(campos) + ") VALUES (?,?,?,'SISTEMA',?,?,?,?,0,?," +
                    ",".join("?" * len(campos)) + ")",
                    (formatar_numero(seq, ano), ano, seq, modelo["prefeitura_id"], modelo["prefeitura"], modelo["id"],
                     momento, momento, *campos.values()))
                novo_id = cur.lastrowid
            con.executemany("INSERT INTO op_itens (op_id, linha, codigo, equipamento, quantidade, inauguracao, observacao) "
                            "VALUES (?,?,?,?,?,?,?)",
                            [(novo_id, i["linha"], i["codigo"], i["equipamento"], i["quantidade"], i["inauguracao"],
                              i["observacao"]) for i in itens])
            foto = {**campos, "itens": itens, "modelo_id": modelo["id"]}
            con.execute("INSERT INTO op_revisoes (op_id, rev, momento, usuario, resumo, dados) VALUES (?,?,?,?,?,?)",
                        (novo_id, rev, momento, usuario, "CRIADA" if rev == 0 else str(dados.get("motivo") or "EDITADA"),
                         json.dumps(foto, ensure_ascii=False, default=str)))
            self.banco.evento(con, "OP_CRIADA" if rev == 0 else "OP_REVISADA",
                              {"op": novo_id, "rev": rev, "saldo": saldo_status})
        resultado = {"ok": True, "op_id": novo_id, "simulacao": sim}
        if self.config()["publicar"] if publicar is None else publicar:
            resultado["publicacao"] = self.publicar(novo_id)
        resultado["op"] = self.op(novo_id)
        return resultado

    def cancelar_op(self, op_id: int, motivo: str, usuario: str = "") -> dict:
        o = self.op(op_id)
        if o["origem"] != "SISTEMA":
            raise ErroValidacao("O.P. DO HISTÓRICO LEGADO NÃO PODE SER CANCELADA AQUI.")
        if not str(motivo or "").strip():
            raise ErroValidacao("INFORME O MOTIVO DO CANCELAMENTO.")
        with self.banco.transacao() as con:
            con.execute("UPDATE ops SET situacao = 'CANCELADA', atualizado_em = ? WHERE id = ?", (agora(), op_id))
            self.banco.evento(con, "OP_CANCELADA", {"op": op_id, "motivo": motivo, "usuario": usuario})
        return self.op(op_id)

    def acompanhar(self, op_id: int, campos: dict) -> dict:
        self.op(op_id)
        novos = {k: str(v or "").strip().upper() if k != "obs" else str(v or "").strip()
                 for k, v in campos.items() if k in CAMPOS_ACOMPANHAMENTO}
        if not novos:
            return self.op(op_id)
        with self.banco.transacao() as con:
            con.execute("UPDATE ops SET " + ", ".join(f"{k} = ?" for k in novos) + ", atualizado_em = ? WHERE id = ?",
                        (*novos.values(), agora(), op_id))
            self.banco.evento(con, "OP_ACOMPANHAMENTO", {"op": op_id, **novos})
        return self.op(op_id)

    # ------------------------------------------------------------ documentos
    def _dados_documento(self, o: dict) -> documento.DadosOP:
        prazo = date.fromisoformat(o["prazo_data"]) if o["prazo_data"] else (o["prazo_texto"] or "DEFINIR")
        emitido = datetime.fromisoformat(o["atualizado_em"])
        return documento.DadosOP(
            numero=o["numero"], obra=o["obra"], prazo=prazo, solicitante=o["solicitante"], rev=o["rev"],
            tipo=o["tipo"] or None, emitido_em=emitido,
            linhas={i["linha"]: documento.LinhaOP(i["quantidade"], _inaug(i["inauguracao"]), i["observacao"])
                    for i in o["itens"]})

    def nome_base(self, o: dict) -> str:
        return montar_nome_base(o["numero"], o["cliente"], o["obra"], o["tipo_arquivo"] or tipo_arquivo(o["tipo"]),
                                o["material"])

    def gerar_documento(self, op_id: int, formato: str) -> tuple[str, bytes]:
        o = self.op(op_id)
        if o["origem"] != "SISTEMA" or not o["modelo_id"]:
            raise ErroValidacao("O.P. DO HISTÓRICO LEGADO: O DOCUMENTO ORIGINAL FICA NA PASTA ANTIGA.")
        modelo = self._modelo(o["modelo_id"])
        bruto = (self.dados / modelo["arquivo"]).read_bytes()
        xlsx = documento.gerar_xlsx(bruto, self._dados_documento(o), self.config()["senha_arquivos"])
        nome = self.nome_base(o)
        if formato == "xlsx":
            return nome + ".xlsx", xlsx
        if formato == "pdf":
            return nome + ".pdf", pdf.gerar_pdf(xlsx, self.config()["motor_pdf"])
        raise ErroValidacao("FORMATO DEVE SER xlsx OU pdf.")

    def publicar(self, op_id: int) -> dict:
        """Grava .xlsx (bloqueado) e .pdf nas pastas configuradas, substituindo a versão anterior desta O.P."""
        o = self.op(op_id)
        px, pp = self.pastas_publicacao()
        anteriores = o["arquivos"] or {}
        resultado: dict = {}
        nome_x, xlsx = self.gerar_documento(op_id, "xlsx")
        px.mkdir(parents=True, exist_ok=True)
        destino_x = px / nome_x
        _gravar_atomico(destino_x, xlsx)
        resultado["xlsx"] = str(destino_x)
        try:
            conteudo_pdf = pdf.gerar_pdf(xlsx, self.config()["motor_pdf"])
            pp.mkdir(parents=True, exist_ok=True)
            destino_p = pp / (nome_x[:-5] + ".pdf")
            _gravar_atomico(destino_p, conteudo_pdf)
            resultado["pdf"] = str(destino_p)
        except Exception as e:  # PDF falhou: xlsx continua publicado
            resultado["pdf_erro"] = str(e)
        for chave in ("xlsx", "pdf"):
            antigo = anteriores.get(chave)
            if antigo and antigo != resultado.get(chave) and Path(antigo).exists():
                try:
                    Path(antigo).unlink()
                except OSError:
                    pass
        with self.banco.transacao() as con:
            con.execute("UPDATE ops SET arquivos = ? WHERE id = ?", (json.dumps(resultado, ensure_ascii=False), op_id))
            self.banco.evento(con, "OP_PUBLICADA", {"op": op_id, **resultado})
        return resultado

    # ------------------------------------------------------------ painel
    def resumo(self) -> dict:
        ano = date.today().year
        return {
            "ano": ano,
            "proximo_numero": self.proximo_numero(ano),
            "prefeituras": self.banco.um("SELECT COUNT(*) n FROM prefeituras WHERE ativo = 1")["n"],
            "modelos": self.banco.um("SELECT COUNT(*) n FROM modelos WHERE ativo = 1")["n"],
            "ops_ano": self.banco.um("SELECT COUNT(*) n FROM ops WHERE ano = ? AND situacao = 'ATIVA'", (ano,))["n"],
            "ops_sistema": self.banco.um("SELECT COUNT(*) n FROM ops WHERE origem = 'SISTEMA'")["n"],
            "sem_data": self.banco.um("SELECT COUNT(*) n FROM ops WHERE ano = ? AND prazo_data IS NULL AND situacao = 'ATIVA'",
                                      (ano,))["n"],
            "motor_pdf": _motor_ou_erro(self.config()["motor_pdf"]),
            "pastas": [str(p) for p in self.pastas_publicacao()],
        }

    def painel(self) -> dict:
        hoje = date.today()
        ano = hoje.year
        ops = self.listar_ops(ano=ano)
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
        for c in self.contratos():
            for it in self.saldo_contrato(c["id"]):
                s = it["saldo"]
                if s == "ACABOU" or (isinstance(s, (int, float)) and s < 0):
                    if s == "ACABOU":
                        encerrados += 1
                    else:
                        negativos += 1
                    alertas.append({"prefeitura": c["prefeitura"], "prefeitura_id": c["prefeitura_id"],
                                    "contrato_id": c["id"], "ata": c["ata"], "codigo": it["codigo"],
                                    "equipamento": it["equipamento"], "saldo": s, "montante": it["montante"]})
        alertas.sort(key=lambda a: (a["saldo"] == "ACABOU", a["saldo"] if a["saldo"] != "ACABOU" else 0))
        semana = [o for o in producao if o["dias"] is not None and 0 <= o["dias"] <= 7]
        return {
            "ano": ano, "hoje": hoje.isoformat(), "proximo_numero": self.proximo_numero(ano),
            "contagem": {e: contagem.get(e, 0) for e in ESTADOS},
            "total_ano": len(validas), "em_producao": sum(contagem.get(e, 0) for e in EM_PRODUCAO),
            "semana": len(semana),
            "por_mes": [{"mes": MESES[i], "ops": n} for i, n in enumerate(por_mes)],
            "por_prefeitura": topo,
            "proximas": producao[:8],
            "atrasadas": atrasadas[:8],
            "sem_data": sorted((o for o in ops if o["estado"] == "SEM_DATA"), key=lambda o: -o["seq"])[:6],
            "alertas_saldo": alertas[:8], "saldo_negativos": negativos, "saldo_encerrados": encerrados,
            "eventos": self.eventos(10),
        }

    def eventos(self, limite: int = 200) -> list[dict]:
        lista = self.banco.todos("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,))
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
            numeros = {r["id"]: r for r in self.banco.todos(
                f"SELECT id, numero, cliente, obra FROM ops WHERE id IN ({marcas})", tuple(ids))}
            for e in lista:
                o = numeros.get(e["dados"].get("op"))
                if o:
                    e["op"] = o
        return lista


def _inaug(valor: str):
    n = numero_br(valor) if valor else None
    return n if n is not None else (valor or None)


def _motor_ou_erro(motor: str) -> str:
    try:
        return pdf.motor_escolhido(motor)
    except pdf.ErroPDF as e:
        return f"INDISPONÍVEL ({e})"


def _gravar_atomico(destino: Path, conteudo: bytes) -> None:
    tmp = destino.with_name("~" + destino.name + ".tmp")
    tmp.write_bytes(conteudo)
    os.replace(tmp, destino)
