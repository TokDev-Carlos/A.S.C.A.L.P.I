"""Banco SQLite do módulo ASCALPI Produção."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

VERSAO_ESQUEMA = 1

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);

CREATE TABLE IF NOT EXISTS prefeituras (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,            -- cliente oficial (TAB_CLIENTE / B3)
    arquivo_origem TEXT DEFAULT '',
    cores_aparelhos TEXT DEFAULT '',
    cores_canoplas TEXT DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY,
    prefeitura_id INTEGER NOT NULL REFERENCES prefeituras(id),
    ata TEXT NOT NULL,                    -- identificador (CIMASP, CIOP, GYM...)
    nome TEXT DEFAULT '',                 -- nome da aba / título
    descricao TEXT DEFAULT '',            -- ex.: Contrato: FOR-29/2025
    importado_em TEXT,
    UNIQUE (prefeitura_id, ata)
);

CREATE TABLE IF NOT EXISTS contrato_itens (
    id INTEGER PRIMARY KEY,
    contrato_id INTEGER NOT NULL REFERENCES contratos(id) ON DELETE CASCADE,
    codigo TEXT NOT NULL,
    equipamento TEXT NOT NULL DEFAULT '',
    valor_un REAL DEFAULT 0,
    montante REAL NOT NULL DEFAULT 0,
    medido_inicial REAL NOT NULL DEFAULT 0,     -- QUANT. da planilha na importação (medições + instalados)
    previsao_inicial REAL NOT NULL DEFAULT 0,   -- PREVISÃO da planilha na importação
    ajuste REAL NOT NULL DEFAULT 0,             -- correção manual feita no sistema (+ consome / - devolve)
    UNIQUE (contrato_id, codigo)
);

CREATE TABLE IF NOT EXISTS modelos (
    id INTEGER PRIMARY KEY,
    prefeitura_id INTEGER NOT NULL REFERENCES prefeituras(id),
    contrato_id INTEGER REFERENCES contratos(id),
    codename TEXT NOT NULL,
    aba TEXT NOT NULL,
    titulo TEXT DEFAULT '',               -- ex.: ATA CIMASP
    tipo_padrao TEXT DEFAULT '',          -- B8 do modelo
    arquivo TEXT NOT NULL,                -- caminho relativo do .xlsx do modelo
    ativo INTEGER NOT NULL DEFAULT 1,
    UNIQUE (prefeitura_id, codename)
);

CREATE TABLE IF NOT EXISTS modelo_linhas (
    modelo_id INTEGER NOT NULL REFERENCES modelos(id) ON DELETE CASCADE,
    linha INTEGER NOT NULL,
    codigo TEXT DEFAULT '',
    equipamento TEXT NOT NULL,
    PRIMARY KEY (modelo_id, linha)
);

CREATE TABLE IF NOT EXISTS ops (
    id INTEGER PRIMARY KEY,
    numero TEXT NOT NULL,                 -- NNN-AA
    ano INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    origem TEXT NOT NULL DEFAULT 'SISTEMA',   -- SISTEMA | LEGADO
    prefeitura_id INTEGER REFERENCES prefeituras(id),
    cliente TEXT DEFAULT '',
    modelo_id INTEGER REFERENCES modelos(id),
    obra TEXT DEFAULT '',
    solicitante TEXT DEFAULT '',
    tipo TEXT DEFAULT '',                 -- B8 (MOB, ABRIGO...)
    tipo_arquivo TEXT DEFAULT '',
    material TEXT DEFAULT '',
    prazo_data TEXT,                      -- aaaa-mm-dd
    prazo_texto TEXT,                     -- ex.: DEFINIR
    entrega_atualizada TEXT DEFAULT '',
    solicitado_em TEXT,
    rev INTEGER NOT NULL DEFAULT 0,
    situacao TEXT NOT NULL DEFAULT 'ATIVA',   -- ATIVA | CANCELADA
    status_instalacao TEXT DEFAULT '',
    material_obra TEXT DEFAULT '',
    fotografico TEXT DEFAULT '',
    obs TEXT DEFAULT '',
    saldo_status TEXT DEFAULT '',
    saldo_confirmado INTEGER NOT NULL DEFAULT 0,
    arquivos TEXT DEFAULT '{}',           -- json com caminhos publicados
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_ops_sistema ON ops(ano, seq) WHERE origem = 'SISTEMA';
CREATE INDEX IF NOT EXISTS ix_ops_numero ON ops(numero);

CREATE TABLE IF NOT EXISTS op_itens (
    op_id INTEGER NOT NULL REFERENCES ops(id) ON DELETE CASCADE,
    linha INTEGER NOT NULL,
    codigo TEXT DEFAULT '',
    equipamento TEXT DEFAULT '',
    quantidade REAL NOT NULL,
    inauguracao TEXT DEFAULT '',
    observacao TEXT DEFAULT '',
    PRIMARY KEY (op_id, linha)
);

CREATE TABLE IF NOT EXISTS op_revisoes (
    id INTEGER PRIMARY KEY,
    op_id INTEGER NOT NULL REFERENCES ops(id) ON DELETE CASCADE,
    rev INTEGER NOT NULL,
    momento TEXT NOT NULL,
    usuario TEXT DEFAULT '',
    resumo TEXT DEFAULT '',
    dados TEXT NOT NULL                   -- json completo da O.P. nesta revisão
);

CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY,
    momento TEXT NOT NULL,
    acao TEXT NOT NULL,
    detalhe TEXT DEFAULT ''
);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.RLock()
        self._con = sqlite3.connect(str(self.caminho), check_same_thread=False, isolation_level=None)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.executescript(ESQUEMA)
        self._con.execute("INSERT OR IGNORE INTO meta VALUES ('versao_esquema', ?)", (str(VERSAO_ESQUEMA),))

    @contextmanager
    def transacao(self):
        with self._trava:
            self._con.execute("BEGIN IMMEDIATE")
            try:
                yield self._con
            except BaseException:
                self._con.execute("ROLLBACK")
                raise
            else:
                self._con.execute("COMMIT")

    def todos(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._trava:
            return [dict(r) for r in self._con.execute(sql, args).fetchall()]

    def um(self, sql: str, args: tuple = ()) -> dict | None:
        with self._trava:
            r = self._con.execute(sql, args).fetchone()
            return dict(r) if r else None

    def evento(self, con, acao: str, detalhe: object = "") -> None:
        if not isinstance(detalhe, str):
            detalhe = json.dumps(detalhe, ensure_ascii=False, default=str)
        con.execute("INSERT INTO eventos (momento, acao, detalhe) VALUES (?,?,?)", (agora(), acao, detalhe))

    def fechar(self) -> None:
        with self._trava:
            self._con.close()
