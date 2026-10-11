"""Regras de uso do módulo: O.P., saldo dos contratos, documentos e acompanhamento."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

from . import consultas, documento, pdf
from .banco import Banco, agora
from .configuracao import Configuracao
from .imagens import CacheImagens
from .modelos_edicao import EdicaoModelos
from .publicacao import Publicacao
from .validacao import (ErroValidacao, data_legada, itens_op, motivo_obrigatorio, numero_finito,
                        valor_acompanhamento)
from .regras import (SALDO_NEGATIVO, SALDO_NEGATIVO_CONFIRMADO, SEM_CONTRATO,
                     SaldoItem, agregar_por_base, codigo_base, normalizar_codigo, detectar_material, formatar_numero,
                     interpretar_prazo, montar_nome_base, numero_br, proximo_numero, simular_saldo, tipo_arquivo)

from .configuracao import CONFIG_PADRAO  # noqa: F401  (reexportado para quem importava daqui)
CAMPOS_ACOMPANHAMENTO = ("status_instalacao", "entrega_atualizada", "material_obra", "fotografico", "obs")
DIAS_PROXIMA = 3


def estado_op(o: dict, hoje: date | None = None) -> dict:
    """Situação da O.P. pelas colunas do Controle: cancelada > instalada > na obra > produção (pelo prazo)."""
    hoje = hoje or date.today()
    st = str(o.get("status_instalacao") or "").strip().upper()
    mo = str(o.get("material_obra") or "").strip().upper()
    ea = str(o.get("entrega_atualizada") or "").strip().upper()
    prazo = None
    invalida = False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ea):          # entrega atualizada com nova data vale como prazo
        prazo = data_legada(ea)
        invalida = prazo is None
    if prazo is None and o.get("prazo_data"):
        prazo = data_legada(o["prazo_data"])
        invalida = invalida or prazo is None
    # dado antigo com data impossível não derruba a lista: fica como SEM DATA e marcado para correção (R06)
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
    return {"estado": estado, "dias": dias, "prazo_efetivo": prazo.isoformat() if prazo else None, "data_invalida": invalida}


class ErroConflito(ValueError):
    """Pedido coerente, mas em conflito com o estado gravado (HTTP 409)."""


CHAVE_VALIDA = re.compile(r"[A-Za-z0-9_-]{8,100}")


class Servico:
    def __init__(self, pasta_dados: Path):
        self.dados = Path(pasta_dados).resolve()
        self.dados.mkdir(parents=True, exist_ok=True)
        self.banco = Banco(self.dados / "ascalpi_producao.db")
        self._configuracao = Configuracao(self.dados)
        self.arquivo_config = self._configuracao.arquivo
        self.fotos = CacheImagens()
        self._publicacao = Publicacao(self)
        self.edicao = EdicaoModelos(self)
        self._linhas_cache: dict[tuple, list] = {}

    # ------------------------------------------------------------ configuração
    def config(self) -> dict:
        return self._configuracao.ler()

    def salvar_config(self, novos: dict) -> dict:
        return self._configuracao.salvar(novos)

    def pastas_publicacao(self) -> tuple[Path, Path]:
        return self._configuracao.pastas()

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
               "m.ativo, m.editado_sistema, m.contrato_id, c.ata, c.descricao AS contrato_descricao, "
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
        """Trocar o contrato do modelo vale só para as próximas O.P.: cada O.P. guarda o contrato da emissão (R05)."""
        with self.banco.transacao() as con:
            m = self._modelo(modelo_id)
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
        motivo = motivo_obrigatorio(motivo, "MOTIVO DO AJUSTE")
        if montante is None and ajuste is None:
            raise ErroValidacao("INFORME O MONTANTE OU O AJUSTE.")
        montante = None if montante is None else numero_finito(montante, "MONTANTE")
        ajuste = None if ajuste is None else numero_finito(ajuste, "AJUSTE", negativo=True)
        with self.banco.transacao() as con:
            item = con.execute("SELECT * FROM contrato_itens WHERE contrato_id = ? AND codigo = ?", (contrato_id, codigo)).fetchone()
            if not item:
                raise ErroValidacao(f"ITEM {codigo} NÃO EXISTE NO CONTRATO.")
            if montante is not None:
                con.execute("UPDATE contrato_itens SET montante = ?, editado_sistema = 1 WHERE id = ?", (float(montante), item["id"]))
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
            "WHERE o.origem = 'SISTEMA' AND o.situacao = 'ATIVA' "
            "AND o.contrato_id = ? AND (? IS NULL OR o.id <> ?)", (contrato_id, excluir_op, excluir_op))
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
                          "sistema_previsao": s["previsao"], "saldo": si.saldo(),
                          "extra": it["codigo"].startswith("0.")})   # 0.x = extra: conta, mas não tem saldo
        saida.sort(key=lambda d: (d["codigo"].startswith("0."), [int(x) for x in d["codigo"].split(".")]))
        return saida

    def _itens_saldo(self, contrato_id: int, excluir_op: int | None) -> dict[str, SaldoItem]:
        return {d["codigo"]: SaldoItem(d["codigo"], d["equipamento"], d["montante"], d["quant"] + d["previsao"])
                for d in self.saldo_contrato(contrato_id, excluir_op)}

    def _contrato_para(self, modelo: dict, op_id: int | None) -> int | None:
        if op_id:
            o = self.banco.um("SELECT contrato_id FROM ops WHERE id = ? AND origem = 'SISTEMA'", (op_id,))
            if o:
                return o["contrato_id"]
        return modelo["contrato_id"]

    def _modelo_da_op(self, modelo: dict, op_id: int | None) -> dict:
        """Ao editar, a O.P. continua no arquivo de modelo da emissão (R07: reimportar não muda O.P. emitida)."""
        if op_id:
            o = self.banco.um("SELECT modelo_arquivo FROM ops WHERE id = ? AND origem = 'SISTEMA'", (op_id,))
            if o and o["modelo_arquivo"] and o["modelo_arquivo"] != modelo["arquivo"]:
                return {**modelo, "arquivo": o["modelo_arquivo"], "congelado": True}
        return modelo

    def _linhas_modelo(self, modelo: dict) -> list[dict]:
        if modelo.get("congelado"):
            caminho = self.dados / modelo["arquivo"]
            chave = (str(caminho), caminho.stat().st_mtime_ns)
            if chave not in self._linhas_cache:
                self._linhas_cache[chave] = [{"linha": l["linha"], "codigo": normalizar_codigo(l["codigo"]),
                                              "equipamento": l["equipamento"]}
                                             for l in documento.linhas_do_modelo(caminho.read_bytes())]
            return [dict(l) for l in self._linhas_cache[chave]]
        return self.banco.todos("SELECT linha, codigo, equipamento FROM modelo_linhas WHERE modelo_id = ? ORDER BY linha",
                                (modelo["id"],))

    def modelo_completo(self, modelo_id: int, excluir_op: int | None = None) -> dict:
        m = self._modelo_da_op(self._modelo(modelo_id), excluir_op)
        m["contrato_id"] = self._contrato_para(m, excluir_op)
        linhas = self._linhas_modelo(m)
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
        m = self._modelo_da_op(self._modelo(modelo_id), excluir_op)
        linhas = {l["linha"]: l for l in self._linhas_modelo(m)}
        pares = []
        for linha, qtd in quantidades.items():
            l = linhas.get(int(linha))
            if l is not None:
                pares.append((l["codigo"], qtd))
        cid = self._contrato_para(m, excluir_op)
        if not cid:
            return {"status": SEM_CONTRATO, "negativos": [], "encerrados": [], "erros": [], "exige_confirmacao": False}
        por_base, problemas = agregar_por_base(pares)
        sim = simular_saldo(self._itens_saldo(cid, excluir_op), por_base)
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
        o = self.banco.um("SELECT o.*, m.aba AS modelo FROM ops o LEFT JOIN modelos m ON m.id = o.modelo_id "
                          "WHERE o.id = ?", (op_id,))
        if not o:
            raise ErroValidacao("O.P. NÃO ENCONTRADA.")
        o["itens"] = self.banco.todos("SELECT * FROM op_itens WHERE op_id = ? ORDER BY linha", (op_id,))
        o["revisoes"] = self.banco.todos("SELECT rev, momento, usuario, resumo FROM op_revisoes WHERE op_id = ? ORDER BY rev",
                                         (op_id,))
        o["arquivos"] = json.loads(o["arquivos"] or "{}")
        o.update(estado_op(o))
        o["contrato_a_conferir"] = o["id"] in self._pendencia("migracao_contrato_ambiguas")
        return o

    def _pendencia(self, chave: str) -> list:
        return consultas.pendencia(self, chave)

    def pendencias(self) -> dict:
        return consultas.pendencias(self)

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
        linhas_modelo = {l["linha"]: l for l in self._linhas_modelo(modelo)}
        itens = []
        for it in itens_op(dados.get("itens") if dados.get("itens") is not None else []):
            linha = it["linha"]
            if linha not in linhas_modelo:
                raise ErroValidacao(f"LINHA {linha} NÃO EXISTE NO MODELO.")
            itens.append({"linha": linha, "codigo": linhas_modelo[linha]["codigo"],
                          "equipamento": linhas_modelo[linha]["equipamento"], "quantidade": it["quantidade"],
                          "inauguracao": it["inauguracao"].upper(), "observacao": it["observacao"]})
        if not itens:
            raise ErroValidacao("A O.P. PRECISA DE PELO MENOS 1 EQUIPAMENTO COM QUANTIDADE.")
        tipo = str(dados.get("tipo") or modelo["tipo_padrao"] or "").strip().upper()
        cab = {"obra": obra, "solicitante": solicitante, "prazo": prazo, "tipo": tipo,
               "material": detectar_material([i["equipamento"] for i in itens], tipo)}
        return cab, itens

    def salvar_op(self, dados: dict, op_id: int | None = None, confirmar_negativo: bool = False,
                  usuario: str = "", publicar: bool | None = None) -> dict:
        chave = None if op_id else self._chave(dados)
        momento = agora()
        # leitura, validação, conferência definitiva do saldo, número e gravação na MESMA transação (R03/R04);
        # a simulação da tela é só informativa. Publicação (Excel/LibreOffice) fica fora da trava.
        with self.banco.transacao() as con:
            atual = self.op(op_id) if op_id else None
            if atual:
                if atual["origem"] != "SISTEMA":
                    raise ErroValidacao("O.P. DO HISTÓRICO LEGADO: SÓ O ACOMPANHAMENTO PODE SER ALTERADO.")
                if atual["situacao"] != "ATIVA":
                    raise ErroValidacao("O.P. CANCELADA NÃO PODE SER ALTERADA.")
                esperada = dados.get("rev_esperada")
                if isinstance(esperada, bool) or not isinstance(esperada, int):
                    raise ErroValidacao("INFORME A REVISÃO QUE ESTÁ SENDO EDITADA (rev_esperada).")
                if esperada != atual["rev"]:
                    raise ErroConflito(f"A O.P. {atual['numero']} JÁ ESTÁ NA REV {atual['rev']} (FOI ALTERADA EM OUTRA TELA). "
                                       "RECARREGUE A O.P. ANTES DE SALVAR.")
            modelo = self._modelo(int(atual["modelo_id"] if atual else dados.get("modelo_id") or 0))
            modelo = self._modelo_da_op(modelo, op_id)
            if not atual and not modelo["ativo"]:
                raise ErroValidacao("MODELO DESATIVADO.")
            cab, itens = self._validar(dados, modelo)
            assinatura = _assinatura(modelo["id"], cab, itens) if chave else None
            if chave:
                repetida = self._op_da_chave(con.execute("SELECT op_id, assinatura FROM op_chaves WHERE chave = ?",
                                                         (chave,)).fetchone(), assinatura)
                if repetida:
                    return repetida
            contrato_id = atual["contrato_id"] if atual else modelo["contrato_id"]
            sim = self.simular(modelo["id"], {i["linha"]: i["quantidade"] for i in itens}, excluir_op=op_id)
            if sim["status"] == "ESTRUTURA_INVALIDA":
                raise ErroValidacao("CONTRATO: " + " ".join(sim["erros"]))
            if sim["exige_confirmacao"] and not confirmar_negativo:
                return {"ok": False, "precisa_confirmacao": True, "simulacao": sim}
            saldo_status = sim["status"]
            if saldo_status == SALDO_NEGATIVO:
                saldo_status = SALDO_NEGATIVO_CONFIRMADO
            prazo = cab["prazo"]
            campos = dict(obra=cab["obra"], solicitante=cab["solicitante"], tipo=cab["tipo"],
                          tipo_arquivo=tipo_arquivo(cab["tipo"]), material=cab["material"],
                          prazo_data=prazo.isoformat() if isinstance(prazo, date) else None,
                          prazo_texto=None if isinstance(prazo, date) else prazo,
                          saldo_status=saldo_status, saldo_confirmado=1 if saldo_status == SALDO_NEGATIVO_CONFIRMADO else 0,
                          atualizado_em=momento, revisado_em=momento)   # criado_em/solicitado_em nunca mudam
            if atual:
                rev = atual["rev"] + 1
                campos["rev"] = rev
                con.execute("UPDATE ops SET " + ", ".join(f"{k} = ?" for k in campos) + " WHERE id = ? AND rev = ?",
                            (*campos.values(), op_id, atual["rev"]))
                con.execute("DELETE FROM op_itens WHERE op_id = ?", (op_id,))
                novo_id = op_id
            else:
                ano = date.today().year
                existentes = [r[0] for r in con.execute("SELECT numero FROM ops WHERE ano = ?", (ano,)).fetchall()]
                seq = proximo_numero(existentes, ano)
                rev = 0
                cur = con.execute(
                    "INSERT INTO ops (numero, ano, seq, origem, prefeitura_id, cliente, modelo_id, modelo_arquivo, contrato_id, "
                    "solicitado_em, rev, criado_em, " + ", ".join(campos) + ") VALUES (?,?,?,'SISTEMA',?,?,?,?,?,?,0,?," +
                    ",".join("?" * len(campos)) + ")",
                    (formatar_numero(seq, ano), ano, seq, modelo["prefeitura_id"], modelo["prefeitura"], modelo["id"],
                     modelo["arquivo"], contrato_id, momento, momento, *campos.values()))
                novo_id = cur.lastrowid
                if chave:
                    con.execute("INSERT INTO op_chaves (chave, op_id, assinatura, criado_em) VALUES (?,?,?,?)",
                                (chave, novo_id, assinatura, momento))
            con.executemany("INSERT INTO op_itens (op_id, linha, codigo, equipamento, quantidade, inauguracao, observacao) "
                            "VALUES (?,?,?,?,?,?,?)",
                            [(novo_id, i["linha"], i["codigo"], i["equipamento"], i["quantidade"], i["inauguracao"],
                              i["observacao"]) for i in itens])
            foto = {**campos, "itens": itens, "modelo_id": modelo["id"], "contrato_id": contrato_id}
            con.execute("INSERT INTO op_revisoes (op_id, rev, momento, usuario, resumo, dados) VALUES (?,?,?,?,?,?)",
                        (novo_id, rev, momento, usuario, "CRIADA" if rev == 0 else str(dados.get("motivo") or "EDITADA"),
                         json.dumps(foto, ensure_ascii=False, default=str)))
            self.banco.evento(con, "OP_CRIADA" if rev == 0 else "OP_REVISADA",
                              {"op": novo_id, "rev": rev, "saldo": saldo_status})
        resultado = {"ok": True, "op_id": novo_id, "simulacao": sim}
        # a O.P. já está gravada: falha ao publicar nunca vira "erro de criação" (R02)
        if self.config()["publicar"] if publicar is None else publicar:
            try:
                resultado["publicacao"] = self.publicar(novo_id)
            except Exception as e:  # noqa: BLE001 - registrado e devolvido como pendência
                resultado["publicacao"] = {"estado": "PENDENTE", "xlsx_erro": str(e), "pdf_erro": "NÃO GERADO"}
        resultado["op"] = self.op(novo_id)
        return resultado

    @staticmethod
    def _chave(dados: dict) -> str | None:
        chave = dados.get("chave")
        if chave in (None, ""):
            return None
        if not isinstance(chave, str) or not CHAVE_VALIDA.fullmatch(chave):
            raise ErroValidacao("CHAVE DO PEDIDO INVÁLIDA.")
        return chave

    def _op_da_chave(self, r, assinatura: str) -> dict | None:
        if r is None:
            return None
        r = dict(r)
        o = self.op(r["op_id"])
        if r["assinatura"] != assinatura:
            raise ErroConflito(f"CHAVE DO RASCUNHO JÁ USADA NA O.P. {o['numero']} COM OUTROS DADOS. "
                               "LIMPE O RASCUNHO PARA GERAR OUTRA O.P.")
        return {"ok": True, "op_id": o["id"], "op": o, "repetida": True, "simulacao": None,
                "publicacao": o["arquivos"] or None}

    def cancelar_op(self, op_id: int, motivo: str, usuario: str = "") -> dict:
        motivo = motivo_obrigatorio(motivo if isinstance(motivo, str) else "", "MOTIVO DO CANCELAMENTO")
        with self.banco.transacao() as con:
            o = self.op(op_id)
            if o["origem"] != "SISTEMA":
                raise ErroValidacao("O.P. DO HISTÓRICO LEGADO NÃO PODE SER CANCELADA AQUI.")
            if o["situacao"] != "ATIVA":
                return o
            con.execute("UPDATE ops SET situacao = 'CANCELADA', atualizado_em = ? WHERE id = ?", (agora(), op_id))
            self.banco.evento(con, "OP_CANCELADA", {"op": op_id, "motivo": motivo, "usuario": usuario})
        return self.op(op_id)

    def acompanhar(self, op_id: int, campos: dict) -> dict:
        # tudo validado antes de gravar: data impossível ou valor fora da lista não entra no banco (R06)
        novos = {k: valor_acompanhamento(k, v) for k, v in campos.items()}
        with self.banco.transacao() as con:
            o = self.op(op_id)
            if not novos:
                return o
            sets = dict(novos)
            if o["origem"] == "LEGADO":   # o que foi editado aqui vence numa reimportação do Controle (R07)
                try:
                    antes = set(json.loads(o.get("editado_sistema") or "[]"))
                except ValueError:
                    antes = set()
                sets["editado_sistema"] = json.dumps(sorted(antes | set(novos)))
            con.execute("UPDATE ops SET " + ", ".join(f"{k} = ?" for k in sets) + ", atualizado_em = ? WHERE id = ?",
                        (*sets.values(), agora(), op_id))
            self.banco.evento(con, "OP_ACOMPANHAMENTO", {"op": op_id, **novos})
        return self.op(op_id)

    # ------------------------------------------------------------ documentos
    def _dados_documento(self, o: dict) -> documento.DadosOP:
        prazo = date.fromisoformat(o["prazo_data"]) if o["prazo_data"] else (o["prazo_texto"] or "DEFINIR")
        # "Hoje" = criação da O.P. (imutável); a partir da REV 1 o documento mostra também a data da revisão
        criada = datetime.fromisoformat(o["criado_em"])
        revisada = datetime.fromisoformat(o["revisado_em"]) if o.get("revisado_em") and o["rev"] else None
        return documento.DadosOP(
            numero=o["numero"], obra=o["obra"], prazo=prazo, solicitante=o["solicitante"], rev=o["rev"],
            tipo=o["tipo"] or None, emitido_em=criada, revisado_em=revisada,
            linhas={i["linha"]: documento.LinhaOP(i["quantidade"], _inaug(i["inauguracao"]), i["observacao"])
                    for i in o["itens"]})

    def nome_base(self, o: dict) -> str:
        return montar_nome_base(o["numero"], o["cliente"], o["obra"], o["tipo_arquivo"] or tipo_arquivo(o["tipo"]),
                                o["material"])

    def gerar_documento(self, op_id: int, formato: str, retrato: dict | None = None) -> tuple[str, bytes]:
        """Gera o documento da O.P.; `retrato` fixa a versão usada (a publicação passa o mesmo que registra)."""
        o = retrato if retrato is not None else self.op(op_id)
        if o["origem"] != "SISTEMA" or not o["modelo_id"]:
            raise ErroValidacao("O.P. DO HISTÓRICO LEGADO: O DOCUMENTO ORIGINAL FICA NA PASTA ANTIGA.")
        modelo = self._modelo(o["modelo_id"])
        bruto = (self.dados / (o.get("modelo_arquivo") or modelo["arquivo"])).read_bytes()   # modelo da emissão
        xlsx = documento.gerar_xlsx(bruto, self._dados_documento(o), self.config()["senha_arquivos"])
        nome = self.nome_base(o)
        if formato == "xlsx":
            return nome + ".xlsx", xlsx
        if formato == "pdf":
            return nome + ".pdf", pdf.gerar_pdf(xlsx, self.config()["motor_pdf"])
        raise ErroValidacao("FORMATO DEVE SER xlsx OU pdf.")

    def publicar(self, op_id: int) -> dict:
        return self._publicacao.publicar(op_id)

    # ------------------------------------------------------------ painel
    def resumo(self) -> dict:
        return consultas.resumo(self)

    def painel(self) -> dict:
        return consultas.painel(self)

    def eventos(self, limite: int = 200) -> list[dict]:
        return consultas.eventos(self, limite)


def _inaug(valor: str):
    n = numero_br(valor) if valor else None
    return n if n is not None else (valor or None)


def _assinatura(modelo_id: int, cab: dict, itens: list[dict]) -> str:
    corpo = {"modelo": modelo_id, **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in cab.items()},
             "itens": sorted(([i["linha"], i["quantidade"], i["inauguracao"], i["observacao"]] for i in itens))}
    return hashlib.sha256(json.dumps(corpo, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
