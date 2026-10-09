"""Servidor HTTP local (biblioteca padrão) com a API JSON e a tela web do ASCALPI Produção."""
from __future__ import annotations

import json
import mimetypes
import re
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .servico import ErroConflito, ErroValidacao, Servico

WEB = Path(__file__).with_name("web")
# o registro do Windows às vezes associa .js a text/plain, e o navegador recusa módulo ES assim
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        raise ErroValidacao(f"NÚMERO INVÁLIDO: {v}")


class Rotas:
    def __init__(self, servico: Servico):
        self.s = servico
        self.tabela = [
            ("GET", r"/api/resumo", lambda q, c: self.s.resumo()),
            ("GET", r"/api/painel", lambda q, c: self.s.painel()),
            ("GET", r"/api/prefeituras", lambda q, c: self.s.prefeituras()),
            ("GET", r"/api/modelos", lambda q, c: self.s.modelos(_int(q.get("prefeitura_id")), q.get("todos") == "1")),
            ("GET", r"/api/modelos/(\d+)", lambda q, c, i: self.s.modelo_completo(int(i), _int(q.get("excluir_op")))),
            ("PATCH", r"/api/modelos/(\d+)", lambda q, c, i: self.s.atualizar_modelo(int(i), c.get("contrato_id"), c.get("ativo"))),
            ("GET", r"/api/contratos", lambda q, c: self.s.contratos(_int(q.get("prefeitura_id")))),
            ("GET", r"/api/contratos/(\d+)/saldo", lambda q, c, i: self.s.saldo_contrato(int(i))),
            ("POST", r"/api/contratos/(\d+)/ajuste", self._ajuste),
            ("POST", r"/api/simular", lambda q, c: self.s.simular(
                int(c["modelo_id"]), {int(i["linha"]): i.get("quantidade") for i in c.get("itens", [])
                                      if str(i.get("quantidade") or "").strip() not in ("", "0")}, _int(c.get("op_id")))),
            ("GET", r"/api/ops", lambda q, c: self.s.listar_ops(q.get("texto", ""), _int(q.get("ano")),
                                                                _int(q.get("prefeitura_id")), q.get("situacao", ""),
                                                                estado=q.get("estado", ""))),
            ("GET", r"/api/ops/proximo", lambda q, c: {"numero": self.s.proximo_numero()}),
            ("GET", r"/api/ops/(\d+)", lambda q, c, i: self.s.op(int(i))),
            ("POST", r"/api/ops", lambda q, c: self.s.salvar_op(c, None, bool(c.get("confirmar_negativo")), c.get("usuario", ""))),
            ("PUT", r"/api/ops/(\d+)", lambda q, c, i: self.s.salvar_op(c, int(i), bool(c.get("confirmar_negativo")),
                                                                         c.get("usuario", ""))),
            ("POST", r"/api/ops/(\d+)/cancelar", lambda q, c, i: self.s.cancelar_op(int(i), c.get("motivo", ""))),
            ("POST", r"/api/ops/(\d+)/acompanhamento", lambda q, c, i: self.s.acompanhar(int(i), c)),
            ("POST", r"/api/ops/(\d+)/publicar", lambda q, c, i: self.s.publicar(int(i))),
            ("GET", r"/api/config", lambda q, c: {k: v for k, v in self.s.config().items() if k != "senha_arquivos"}),
            ("PUT", r"/api/config", lambda q, c: {k: v for k, v in self.s.salvar_config(c).items() if k != "senha_arquivos"}),
            ("GET", r"/api/eventos", lambda q, c: self.s.eventos()),
        ]

    def _ajuste(self, q, c, i):
        self.s.ajustar_item(int(i), str(c.get("codigo")), c.get("montante"), c.get("ajuste"), c.get("motivo", ""))
        return self.s.saldo_contrato(int(i))

    def resolver(self, metodo: str, caminho: str):
        for m, padrao, func in self.tabela:
            if m == metodo:
                achado = re.fullmatch(padrao, caminho)
                if achado:
                    return func, achado.groups()
        return None, ()


def criar_handler(servico: Servico):
    rotas = Rotas(servico)

    class Handler(BaseHTTPRequestHandler):
        server_version = "ASCALPI-Producao/1.0"

        def log_message(self, fmt, *args):  # silencioso; eventos ficam no banco
            pass

        def _json(self, status: int, corpo) -> None:
            dados = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)

        def _imagem(self, achado) -> None:
            if not achado:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            conteudo, tipo, etag = achado
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(conteudo)))
            self.send_header("Cache-Control", "private, max-age=86400")
            self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(conteudo)

        def _arquivo(self, nome: str, conteudo: bytes, tipo: str, baixar: bool) -> None:
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(conteudo)))
            disp = "attachment" if baixar else "inline"
            self.send_header("Content-Disposition", f"{disp}; filename*=UTF-8''{quote(nome)}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(conteudo)

        def _corpo(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8"))
            except ValueError:
                raise ErroValidacao("CORPO JSON INVÁLIDO.")

        def _tratar(self, metodo: str) -> None:
            url = urlparse(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            try:
                foto = re.fullmatch(r"/api/modelos/(\d+)/(foto/(\d+)|logo)", url.path)
                if metodo == "GET" and foto:
                    chave = int(foto.group(3)) if foto.group(3) else "logo"
                    return self._imagem(servico.foto_modelo(int(foto.group(1)), chave))
                logo = re.fullmatch(r"/api/prefeituras/(\d+)/logo", url.path)
                if metodo == "GET" and logo:
                    return self._imagem(servico.logo_prefeitura(int(logo.group(1))))
                doc = re.fullmatch(r"/api/ops/(\d+)/documento\.(xlsx|pdf)", url.path)
                if metodo == "GET" and doc:
                    nome, conteudo = servico.gerar_documento(int(doc.group(1)), doc.group(2))
                    tipo = ("application/pdf" if doc.group(2) == "pdf" else
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    return self._arquivo(nome, conteudo, tipo, q.get("baixar") == "1" or doc.group(2) == "xlsx")
                if url.path.startswith("/api/"):
                    func, grupos = rotas.resolver(metodo, url.path)
                    if not func:
                        return self._json(404, {"erro": "ROTA NÃO ENCONTRADA."})
                    corpo = self._corpo() if metodo in ("POST", "PUT", "PATCH") else {}
                    return self._json(200, func(q, corpo, *grupos))
                if metodo != "GET":
                    return self._json(405, {"erro": "MÉTODO NÃO PERMITIDO."})
                return self._estatico(url.path)
            except ErroConflito as e:
                return self._json(409, {"erro": str(e)})
            except ErroValidacao as e:
                return self._json(400, {"erro": str(e)})
            except Exception as e:
                traceback.print_exc()
                return self._json(500, {"erro": f"ERRO INTERNO: {e}"})

        def _estatico(self, caminho: str) -> None:
            rel = caminho.lstrip("/") or "index.html"
            alvo = (WEB / rel).resolve()
            if WEB.resolve() not in alvo.parents or not alvo.is_file():
                alvo = WEB / "index.html"
            tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo.endswith("javascript"):
                tipo += "; charset=utf-8"
            dados = alvo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            self._tratar("GET")

        def do_POST(self):
            self._tratar("POST")

        def do_PUT(self):
            self._tratar("PUT")

        def do_PATCH(self):
            self._tratar("PATCH")

    return Handler


def servir(servico: Servico, host: str = "127.0.0.1", porta: int = 8765) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, porta), criar_handler(servico))
    httpd.daemon_threads = True
    return httpd
