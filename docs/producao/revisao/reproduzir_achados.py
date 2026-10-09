"""Diagnóstico sintético da revisão Codex; não é teste de aceite.

Execute da raiz: python docs/producao/revisao/reproduzir_achados.py
Só usa diretórios temporários e livros fictícios; não inicia Excel/LibreOffice.
Cada resultado descreve o comportamento observado, sem exigir que o defeito continue existindo.
Após corrigir, converter os cenários relevantes em testes de regressão com expectativas corretas.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Modulos" / "ASCALPI_Producao"))

from ascalpi_producao import legado, pacote, imagens
from ascalpi_producao.servico import Servico
from tests.apoio import criar_livro, criar_controle


@contextmanager
def cenario():
    with tempfile.TemporaryDirectory(prefix="ascalpi_revisao_") as tmp:
        root = Path(tmp)
        origem = root / "origem"
        origem.mkdir()
        criar_livro(origem)
        controle = criar_controle(origem)
        s = Servico(root / "dados")
        s.salvar_config({"publicar": False})
        legado.importar_pasta(s.banco, origem, root / "dados")
        modelo = s.modelos()[0]
        dados = dict(modelo_id=modelo["id"], obra="OBRA FICTÍCIA", solicitante="TESTE",
                     prazo="DEFINIR", itens=[dict(linha=10, quantidade=1)])
        try:
            yield s, modelo, dados, root, controle
        finally:
            s.banco.fechar()


def saldo(s, cid):
    return next(i["saldo"] for i in s.saldo_contrato(cid) if i["codigo"] == "1")


def observar(nome, func):
    try:
        print(json.dumps({"cenario": nome, "resultado": func()}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"cenario": nome, "erro_do_cenario": type(e).__name__ + ": " + str(e)}, ensure_ascii=False))
        raise


def pdf_anterior():
    with cenario() as (s, m, dados, root, controle):
        oid = s.salvar_op(dados)["op_id"]
        with patch("ascalpi_producao.servico.pdf.gerar_pdf", return_value=b"%PDF-1.4\nTESTE"):
            anterior = s.publicar(oid)
        with patch("ascalpi_producao.servico.pdf.gerar_pdf", side_effect=RuntimeError("FALHA SINTÉTICA")):
            resultado = s.publicar(oid)
        return dict(pdf_anterior_preservado=Path(anterior["pdf"]).exists(),
                    erro_reportado="pdf_erro" in resultado)


def falha_xlsx():
    with cenario() as (s, m, dados, root, controle):
        erro = None
        with patch("ascalpi_producao.servico._gravar_atomico", side_effect=PermissionError("FALHA SINTÉTICA")):
            try:
                s.salvar_op(dados, publicar=True)
            except PermissionError:
                erro = "PermissionError"
        antes = s.banco.um("SELECT COUNT(*) n FROM ops WHERE origem='SISTEMA'")["n"]
        s.salvar_op(dados)
        depois = s.banco.um("SELECT COUNT(*) n FROM ops WHERE origem='SISTEMA'")["n"]
        return dict(erro=erro, ops_gravadas_apos_erro=antes, ops_apos_repetir=depois)


def saldo_concorrente():
    with cenario() as (s, m, dados, root, controle):
        dados["itens"][0]["quantidade"] = 4
        barreira = threading.Barrier(2, timeout=5)
        original = s.simular
        def simular(*args, **kwargs):
            resultado = original(*args, **kwargs)
            barreira.wait()
            return resultado
        with patch.object(s, "simular", side_effect=simular):
            with ThreadPoolExecutor(max_workers=2) as pool:
                respostas = list(pool.map(lambda _: s.salvar_op(dados), range(2)))
        return dict(confirmacao_solicitada=[r.get("precisa_confirmacao", False) for r in respostas],
                    numeros=[r.get("op", {}).get("numero") for r in respostas],
                    saldo_final=saldo(s, m["contrato_id"]))


def revisao_concorrente():
    with cenario() as (s, m, dados, root, controle):
        oid = s.salvar_op(dados)["op_id"]
        barreira = threading.Barrier(2, timeout=5)
        original = s._validar
        def validar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            barreira.wait()
            return resultado
        with patch.object(s, "_validar", side_effect=validar):
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda i: s.salvar_op({**dados, "obra": "EDIÇÃO " + str(i)}, op_id=oid), range(2)))
        return dict(revisoes=[r["rev"] for r in s.op(oid)["revisoes"]])


def trocar_contrato():
    with cenario() as (s, m, dados, root, controle):
        dados["itens"][0]["quantidade"] = 4
        oid = s.salvar_op(dados)["op_id"]
        antes = saldo(s, m["contrato_id"])
        with s.banco.transacao() as con:
            cid = con.execute("INSERT INTO contratos(prefeitura_id, ata) VALUES (?, 'OUTRA')", (m["prefeitura_id"],)).lastrowid
            con.execute("INSERT INTO contrato_itens(contrato_id,codigo,montante) VALUES (?, '1', 10)", (cid,))
        s.atualizar_modelo(m["id"], contrato_id=cid)
        return dict(saldo_original_antes=antes, saldo_original_depois=saldo(s, m["contrato_id"]),
                    saldo_novo_contrato=saldo(s, cid), revisao_op=s.op(oid)["rev"])


def data_invalida():
    with cenario() as (s, m, dados, root, controle):
        oid = s.salvar_op(dados)["op_id"]
        try:
            s.acompanhar(oid, {"entrega_atualizada": "2026-02-31"})
        except ValueError:
            pass
        persistida = s.banco.um("SELECT entrega_atualizada FROM ops WHERE id=?", (oid,))["entrega_atualizada"]
        try:
            s.listar_ops()
            lista = "OK"
        except ValueError:
            lista = "ValueError"
        return dict(data_persistida=persistida, listar_ops=lista)


def reimportar_acompanhamento():
    with cenario() as (s, m, dados, root, controle):
        oid = s.banco.um("SELECT id FROM ops WHERE origem='LEGADO' ORDER BY id LIMIT 1")["id"]
        s.acompanhar(oid, {"obs": "NOTA ADICIONADA NO SISTEMA"})
        legado.importar_controle(s.banco, controle, [])
        restantes = s.banco.um("SELECT COUNT(*) n FROM ops WHERE obs='NOTA ADICIONADA NO SISTEMA'")["n"]
        return dict(anotacoes_preservadas=restantes)


def controle_sem_tabela():
    with cenario() as (s, m, dados, root, controle):
        antes = s.banco.um("SELECT COUNT(*) n FROM ops WHERE origem='LEGADO'")["n"]
        legado.importar_controle(s.banco, root / "origem" / "OK-TESTE_O.P.xlsx", [])
        depois = s.banco.um("SELECT COUNT(*) n FROM ops WHERE origem='LEGADO'")["n"]
        return dict(historico_antes=antes, historico_depois=depois)


def motivo_vazio():
    with cenario() as (s, m, dados, root, controle):
        s.ajustar_item(m["contrato_id"], "1", ajuste=2, motivo="")
        return dict(saldo_apos_ajuste_sem_motivo=saldo(s, m["contrato_id"]))


def imagem_namespace():
    import openpyxl
    from openpyxl.drawing.image import Image
    from PIL import Image as PILImage
    with tempfile.TemporaryDirectory(prefix="ascalpi_imagem_") as tmp:
        root = Path(tmp)
        foto = root / "foto.png"
        PILImage.new("RGB", (8, 8), "red").save(foto)
        wb = openpyxl.Workbook()
        wb.active.add_image(Image(str(foto)), "C10")
        caminho = root / "imagem.xlsx"
        wb.save(caminho)
        partes = pacote.carregar(caminho)
        return dict(midias_presentes=sum(n.startswith("xl/media/") for n in partes),
                    imagens_reconhecidas=len(imagens.mapa_imagens(partes)))


if __name__ == "__main__":
    for nome, func in [
        ("R01_pdf_anterior", pdf_anterior), ("R02_falha_xlsx", falha_xlsx),
        ("R03_saldo_concorrente", saldo_concorrente), ("R04_revisao_concorrente", revisao_concorrente),
        ("R05_trocar_contrato", trocar_contrato), ("R06_data_invalida", data_invalida),
        ("R07_reimportar_acompanhamento", reimportar_acompanhamento),
        ("R07_controle_sem_tabela", controle_sem_tabela), ("R08_motivo_vazio", motivo_vazio),
        ("R09_imagem_namespace", imagem_namespace),
    ]:
        observar(nome, func)
