from __future__ import annotations
import math
import sqlite3
from pathlib import Path

from Core.config import local_database_path

SYSTEM_DIR = Path(__file__).resolve().parents[1]
# Cada estação abre exclusivamente seu próprio cache. A pasta compartilhada
# contém revisões imutáveis e nunca um SQLite aberto por vários computadores.
DB_PATH = local_database_path()

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS counters(entity TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offline_drafts(
 id TEXT PRIMARY KEY, tipo TEXT NOT NULL, payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usuarios(
 id TEXT PRIMARY KEY, nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
 perfil TEXT NOT NULL DEFAULT 'USUARIO' CHECK(perfil IN ('ADMIN','USUARIO')),
 senha_hash TEXT NOT NULL DEFAULT '', senha_salt TEXT NOT NULL DEFAULT '',
 permissoes_json TEXT NOT NULL DEFAULT '{}', ativo INTEGER NOT NULL DEFAULT 1,
 trocar_senha INTEGER NOT NULL DEFAULT 0, auth_version INTEGER NOT NULL DEFAULT 1,
 ultimo_acesso TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS auditoria_eventos(
 id TEXT PRIMARY KEY, ocorrido_em TEXT NOT NULL, usuario_id TEXT NOT NULL DEFAULT '',
 usuario_nome TEXT NOT NULL DEFAULT '', estacao_id TEXT NOT NULL DEFAULT '',
 evento TEXT NOT NULL, entidade_tipo TEXT NOT NULL DEFAULT '', entidade_id TEXT NOT NULL DEFAULT '',
 detalhes_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS solicitacoes_exclusao(
 id TEXT PRIMARY KEY, entidade_tipo TEXT NOT NULL CHECK(entidade_tipo IN ('CLIENTE','OBRA','CARREGAMENTO')),
 entidade_id TEXT NOT NULL, entidade_rotulo TEXT NOT NULL DEFAULT '', motivo TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'PENDENTE' CHECK(status IN ('PENDENTE','REVOGADA','APROVADA','EXPIRADA')),
 solicitante_id TEXT NOT NULL DEFAULT '', solicitante_nome TEXT NOT NULL DEFAULT '',
 solicitado_em TEXT NOT NULL, expira_em TEXT NOT NULL, revisor_id TEXT NOT NULL DEFAULT '',
 revisor_nome TEXT NOT NULL DEFAULT '', revisado_em TEXT NOT NULL DEFAULT '',
 purgado_em TEXT NOT NULL DEFAULT '', payload_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS exclusao_tombstones(
 id TEXT PRIMARY KEY, entidade_tipo TEXT NOT NULL, entidade_id TEXT NOT NULL,
 entidade_rotulo TEXT NOT NULL DEFAULT '', motivo TEXT NOT NULL DEFAULT '',
 solicitante_id TEXT NOT NULL DEFAULT '', revisor_id TEXT NOT NULL DEFAULT '',
 removido_em TEXT NOT NULL, detalhes_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS carregamento_anexos(
 id TEXT PRIMARY KEY, carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE,
 obra_id TEXT REFERENCES obras(id), op_numero TEXT NOT NULL DEFAULT '',
 nome_original TEXT NOT NULL, nome_seguro TEXT NOT NULL, extensao TEXT NOT NULL,
 mime TEXT NOT NULL, tamanho INTEGER NOT NULL CHECK(tamanho>0), sha256 TEXT NOT NULL,
 relative_path TEXT NOT NULL, usuario_id TEXT NOT NULL DEFAULT '', usuario_nome TEXT NOT NULL DEFAULT '',
 estacao_id TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, deleted_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS carregamento_documentos(
 id TEXT PRIMARY KEY, carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE,
 revisao INTEGER NOT NULL CHECK(revisao>0), tipo TEXT NOT NULL CHECK(tipo IN ('PACOTE')),
 workbook_nome TEXT NOT NULL, workbook_path TEXT NOT NULL, workbook_sha256 TEXT NOT NULL,
 template_sha256 TEXT NOT NULL, conteudo_sha256 TEXT NOT NULL, arquivos_json TEXT NOT NULL DEFAULT '[]',
 usuario_id TEXT NOT NULL DEFAULT '', usuario_nome TEXT NOT NULL DEFAULT '', estacao_id TEXT NOT NULL DEFAULT '',
 gerado_em TEXT NOT NULL, UNIQUE(carregamento_id,revisao));
CREATE TABLE IF NOT EXISTS carregamento_evidencias(
 id TEXT PRIMARY KEY, carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE,
 etapa TEXT NOT NULL CHECK(etapa IN ('CARREGAMENTO','DESCARREGAMENTO')),
 nome_original TEXT NOT NULL, nome_seguro TEXT NOT NULL, mime TEXT NOT NULL,
 tamanho INTEGER NOT NULL CHECK(tamanho>0), sha256 TEXT NOT NULL, relative_path TEXT NOT NULL,
 usuario_id TEXT NOT NULL DEFAULT '', usuario_nome TEXT NOT NULL DEFAULT '', estacao_id TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, deleted_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS unidades(
 id TEXT PRIMARY KEY, nome TEXT NOT NULL, uf TEXT NOT NULL UNIQUE, ativo INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clientes(
 id TEXT PRIMARY KEY, nome TEXT NOT NULL COLLATE NOCASE UNIQUE, documento TEXT NOT NULL DEFAULT '', contato TEXT NOT NULL DEFAULT '', telefone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', observacao TEXT NOT NULL DEFAULT '', ativo INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS obras(
 id TEXT PRIMARY KEY, unidade_id TEXT NOT NULL REFERENCES unidades(id), cliente_id TEXT REFERENCES clientes(id), nome TEXT NOT NULL, municipio TEXT NOT NULL DEFAULT '', codigo TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ATIVA', folder_name TEXT NOT NULL, localizacao_original TEXT NOT NULL DEFAULT '', localizacao_formato TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pracas(
 id TEXT PRIMARY KEY, obra_id TEXT NOT NULL REFERENCES obras(id) ON DELETE CASCADE, nome TEXT NOT NULL DEFAULT '', op_numero TEXT NOT NULL DEFAULT '', endereco TEXT NOT NULL DEFAULT '', observacao TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ATIVA', folder_name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(length(trim(nome))>0 OR length(trim(op_numero))>0));
CREATE TABLE IF NOT EXISTS carregamentos(
 id TEXT PRIMARY KEY, obra_id TEXT NOT NULL REFERENCES obras(id), data TEXT NOT NULL, hora TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'PLANEJADO', observacao TEXT NOT NULL DEFAULT '',
 caminhao_id TEXT REFERENCES caminhoes(id),
 motorista TEXT NOT NULL DEFAULT '', veiculo TEXT NOT NULL DEFAULT '', placa TEXT NOT NULL DEFAULT '', propriedade TEXT NOT NULL DEFAULT 'PROPRIO', transportadora TEXT NOT NULL DEFAULT '',
 data_saida TEXT NOT NULL DEFAULT '', hora_saida TEXT NOT NULL DEFAULT '', funcionarios INTEGER NOT NULL DEFAULT 0,
 dias_viagem REAL NOT NULL DEFAULT 0, distancia_km REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS carregamento_pracas(
 carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE, praca_id TEXT NOT NULL REFERENCES pracas(id), PRIMARY KEY(carregamento_id, praca_id));
CREATE TABLE IF NOT EXISTS carregamento_obras(
 carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE,
 obra_id TEXT NOT NULL REFERENCES obras(id),
 op_numero TEXT NOT NULL DEFAULT '',
 municipio TEXT NOT NULL DEFAULT '',
 endereco TEXT NOT NULL DEFAULT '',
 latitude REAL,
 longitude REAL,
 distancia_km REAL NOT NULL DEFAULT 0,
 custo_pessoal REAL NOT NULL DEFAULT 0,
 custo_frete REAL NOT NULL DEFAULT 0,
 custo_viagem REAL NOT NULL DEFAULT 0,
 valor_obra REAL NOT NULL DEFAULT 0,
 percentual_rateio REAL NOT NULL DEFAULT 0,
 observacao TEXT NOT NULL DEFAULT '',
 ordem INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(carregamento_id, obra_id));
CREATE TABLE IF NOT EXISTS carregamento_custos(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE,
 grupo TEXT NOT NULL CHECK(grupo IN ('PESSOAL','FRETE')),
 descricao TEXT NOT NULL,
 modo TEXT NOT NULL DEFAULT 'FIXO' CHECK(modo IN ('FIXO','POR_FUNCIONARIO','POR_DIA','POR_HORA','POR_UNIDADE')),
 valor_unitario REAL NOT NULL DEFAULT 0 CHECK(valor_unitario>=0),
 quantidade REAL NOT NULL DEFAULT 1 CHECK(quantidade>=0),
 total REAL NOT NULL DEFAULT 0 CHECK(total>=0),
 ativo INTEGER NOT NULL DEFAULT 1,
 ordem INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS equipamentos(
 codigo TEXT PRIMARY KEY, grupo TEXT NOT NULL DEFAULT '', nome TEXT NOT NULL, valor_unit REAL, origem_linha INTEGER, observacao TEXT NOT NULL DEFAULT '', ativo INTEGER NOT NULL DEFAULT 1,
 imagem_arquivo TEXT NOT NULL DEFAULT '', imagem_mime TEXT NOT NULL DEFAULT '', imagem_atualizada_em TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS carregamento_itens(
 id INTEGER PRIMARY KEY AUTOINCREMENT, carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE, praca_id TEXT REFERENCES pracas(id), equipamento_codigo TEXT NOT NULL REFERENCES equipamentos(codigo), quantidade REAL NOT NULL CHECK(quantidade>=0), valor_unitario REAL CHECK(valor_unitario>=0));
CREATE TABLE IF NOT EXISTS receitas(
 id TEXT PRIMARY KEY, obra_id TEXT NOT NULL REFERENCES obras(id), data_competencia TEXT NOT NULL, descricao TEXT NOT NULL DEFAULT '', valor REAL NOT NULL CHECK(valor>=0), origem TEXT NOT NULL DEFAULT 'MANUAL', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS viagens(
 id TEXT PRIMARY KEY, obra_id TEXT NOT NULL REFERENCES obras(id), data_saida TEXT NOT NULL, municipio TEXT NOT NULL DEFAULT '', local_obra TEXT NOT NULL DEFAULT '', veiculo TEXT NOT NULL DEFAULT '', motorista TEXT NOT NULL DEFAULT '', funcionarios INTEGER NOT NULL DEFAULT 0, dias REAL NOT NULL DEFAULT 0, distancia_km REAL NOT NULL DEFAULT 0, custo_pessoal REAL NOT NULL DEFAULT 0, custo_frete REAL NOT NULL DEFAULT 0, custo_total REAL NOT NULL DEFAULT 0, observacao TEXT NOT NULL DEFAULT '', origem TEXT NOT NULL DEFAULT 'MANUAL', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS viagem_pracas(
 viagem_id TEXT NOT NULL REFERENCES viagens(id) ON DELETE CASCADE, praca_id TEXT NOT NULL REFERENCES pracas(id), PRIMARY KEY(viagem_id, praca_id));
CREATE TABLE IF NOT EXISTS equipamento_valores_historico(
 id INTEGER PRIMARY KEY AUTOINCREMENT, equipamento_codigo TEXT NOT NULL REFERENCES equipamentos(codigo), valor_anterior REAL, valor_novo REAL, alterado_em TEXT NOT NULL, motivo TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS caminhoes(
 id TEXT PRIMARY KEY, tipo TEXT NOT NULL DEFAULT 'CAMINHAO_TRANSPORTE' CHECK(tipo IN ('CARRO_PASSEIO','CAMINHAO_TRANSPORTE')),
 placa TEXT NOT NULL COLLATE NOCASE UNIQUE, modelo TEXT NOT NULL, propriedade TEXT NOT NULL DEFAULT 'PROPRIO' CHECK(propriedade IN ('PROPRIO','ALUGADO')),
 transportadora TEXT NOT NULL DEFAULT '', motorista_padrao TEXT NOT NULL DEFAULT '', capacidade TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'DISPONIVEL' CHECK(status IN ('DISPONIVEL','EM_ROTA','MANUTENCAO','INATIVO')),
 porte TEXT NOT NULL DEFAULT 'MEDIO' CHECK(porte IN ('LEVE','MEDIO','PESADO','EXTRAPESADO')),
 eixos INTEGER NOT NULL DEFAULT 2 CHECK(eixos BETWEEN 2 AND 9),
 combustivel TEXT NOT NULL DEFAULT 'DIESEL' CHECK(combustivel IN ('GASOLINA','ETANOL','DIESEL','FLEX','ELETRICO','HIBRIDO')),
 consumo_km_l REAL NOT NULL DEFAULT 0 CHECK(consumo_km_l>=0), tanque_litros REAL NOT NULL DEFAULT 0 CHECK(tanque_litros>=0),
 tarifa_pedagio_eixo REAL NOT NULL DEFAULT 0 CHECK(tarifa_pedagio_eixo>=0),
 apelido TEXT NOT NULL DEFAULT '', perfil_codigo TEXT NOT NULL DEFAULT '', carroceria TEXT NOT NULL DEFAULT '', parametros_estimados_json TEXT NOT NULL DEFAULT '{}',
 latitude REAL, longitude REAL, observacao TEXT NOT NULL DEFAULT '', ativo INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS locais_rota(
 id TEXT PRIMARY KEY, tipo TEXT NOT NULL CHECK(tipo IN ('FABRICA')), origem_tipo TEXT NOT NULL DEFAULT 'FABRICA' CHECK(origem_tipo IN ('EMPRESA','FABRICA','UNIDADE')), nome TEXT NOT NULL, endereco TEXT NOT NULL DEFAULT '', latitude REAL, longitude REAL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS planejamentos_rota(
 id TEXT PRIMARY KEY, carregamento_id TEXT NOT NULL REFERENCES carregamentos(id) ON DELETE CASCADE,
 revisao INTEGER NOT NULL CHECK(revisao>0), caminhao_id TEXT NOT NULL REFERENCES caminhoes(id),
 ordem_modo TEXT NOT NULL CHECK(ordem_modo IN ('OTIMIZADA','CADASTRO','MANUAL')),
 retorno_origem INTEGER NOT NULL DEFAULT 0, distancia_modo TEXT NOT NULL CHECK(distancia_modo IN ('ESTIMADA','MANUAL')),
 distancia_reta_km REAL NOT NULL DEFAULT 0, fator_rodoviario REAL NOT NULL DEFAULT 1.2,
 distancia_adotada_km REAL NOT NULL DEFAULT 0,
 combustivel_modo TEXT NOT NULL CHECK(combustivel_modo IN ('ESTIMADO','MANUAL')),
 preco_combustivel REAL NOT NULL DEFAULT 0, litros_estimados REAL NOT NULL DEFAULT 0,
 custo_combustivel REAL NOT NULL DEFAULT 0,
 pedagio_modo TEXT NOT NULL CHECK(pedagio_modo IN ('ESTIMADO','MANUAL')),
 pracas_pedagio INTEGER NOT NULL DEFAULT 0, tarifa_pedagio_eixo REAL NOT NULL DEFAULT 0,
 custo_pedagio REAL NOT NULL DEFAULT 0, custo_total REAL NOT NULL DEFAULT 0,
 tempo_estimado_min REAL NOT NULL DEFAULT 0, motor_rota TEXT NOT NULL DEFAULT 'FALLBACK_LOCAL',
 distancia_fonte TEXT NOT NULL DEFAULT 'ESTIMADA', rota_geometria_json TEXT NOT NULL DEFAULT '[]',
 pedagios_json TEXT NOT NULL DEFAULT '[]', base_rodoviaria_versao TEXT NOT NULL DEFAULT '',
 base_pedagios_versao TEXT NOT NULL DEFAULT '',
 veiculo_json TEXT NOT NULL DEFAULT '{}', paradas_json TEXT NOT NULL DEFAULT '[]', trechos_json TEXT NOT NULL DEFAULT '[]',
 usuario_id TEXT NOT NULL DEFAULT '', usuario_nome TEXT NOT NULL DEFAULT '', estacao_id TEXT NOT NULL DEFAULT '',
 criado_em TEXT NOT NULL, UNIQUE(carregamento_id,revisao));
CREATE INDEX IF NOT EXISTS idx_pracas_obra ON pracas(obra_id);
CREATE INDEX IF NOT EXISTS idx_carregamentos_data ON carregamentos(data);
CREATE INDEX IF NOT EXISTS idx_carregamentos_obra ON carregamentos(obra_id);
CREATE INDEX IF NOT EXISTS idx_carregamento_obras_carga ON carregamento_obras(carregamento_id,ordem);
CREATE INDEX IF NOT EXISTS idx_carregamento_obras_obra ON carregamento_obras(obra_id);
CREATE INDEX IF NOT EXISTS idx_carregamento_custos_carga ON carregamento_custos(carregamento_id,grupo,ordem);
CREATE INDEX IF NOT EXISTS idx_carregamentos_status ON carregamentos(status);
CREATE INDEX IF NOT EXISTS idx_receitas_data ON receitas(data_competencia);
CREATE INDEX IF NOT EXISTS idx_receitas_obra ON receitas(obra_id);
CREATE INDEX IF NOT EXISTS idx_viagens_data ON viagens(data_saida);
CREATE INDEX IF NOT EXISTS idx_viagens_obra ON viagens(obra_id);
CREATE INDEX IF NOT EXISTS idx_caminhoes_status ON caminhoes(status,ativo);
CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria_eventos(ocorrido_em);
CREATE INDEX IF NOT EXISTS idx_exclusao_status ON solicitacoes_exclusao(status,expira_em);
CREATE INDEX IF NOT EXISTS idx_anexos_carga ON carregamento_anexos(carregamento_id,deleted_at);
CREATE INDEX IF NOT EXISTS idx_documentos_carga ON carregamento_documentos(carregamento_id,revisao DESC);
CREATE INDEX IF NOT EXISTS idx_evidencias_carga ON carregamento_evidencias(carregamento_id,etapa,created_at);
CREATE INDEX IF NOT EXISTS idx_planejamentos_rota_carga ON planejamentos_rota(carregamento_id,revisao DESC);
'''

def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level='IMMEDIATE')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA recursive_triggers=ON')
    conn.execute('PRAGMA trusted_schema=OFF')
    return conn

def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}

def _add_column(conn: sqlite3.Connection, table: str, declaration: str) -> None:
    name = declaration.split()[0]
    if name not in _columns(conn, table):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {declaration}')


def _sanitize_non_finite(conn: sqlite3.Connection) -> None:
    """Remove valores IEEE especiais deixados por versões anteriores.

    JSON estrito e cálculos financeiros não aceitam NaN/Infinity. A lista é
    deliberadamente fechada para nunca interpolar identificadores externos.
    """
    zero_columns = {
        'carregamentos': ('dias_viagem', 'distancia_km'),
        'carregamento_obras': (
            'distancia_km', 'custo_pessoal', 'custo_frete', 'custo_viagem',
            'valor_obra', 'percentual_rateio',
        ),
        'carregamento_custos': ('valor_unitario', 'quantidade', 'total'),
        'carregamento_itens': ('quantidade', 'valor_unitario'),
        'equipamentos': ('valor_unit',),
        'receitas': ('valor',),
        'viagens': ('dias', 'distancia_km', 'custo_pessoal', 'custo_frete', 'custo_total'),
        'caminhoes': ('consumo_km_l', 'tanque_litros', 'tarifa_pedagio_eixo'),
        'planejamentos_rota': (
            'distancia_reta_km', 'fator_rodoviario', 'distancia_adotada_km',
            'preco_combustivel', 'litros_estimados', 'custo_combustivel',
            'tarifa_pedagio_eixo', 'custo_pedagio', 'custo_total', 'tempo_estimado_min',
        ),
    }
    nullable_columns = {
        'obras': ('latitude', 'longitude'),
        'caminhoes': ('latitude', 'longitude'),
        'locais_rota': ('latitude', 'longitude'),
    }
    for table, columns in zero_columns.items():
        for column in columns:
            if column not in _columns(conn, table):
                continue
            for row in conn.execute(f'SELECT rowid,{column} value FROM {table} WHERE {column} IS NOT NULL').fetchall():
                try:
                    valid = math.isfinite(float(row['value']))
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    conn.execute(f'UPDATE {table} SET {column}=0 WHERE rowid=?', (row['rowid'],))
    for table, columns in nullable_columns.items():
        for column in columns:
            if column not in _columns(conn, table):
                continue
            for row in conn.execute(f'SELECT rowid,{column} value FROM {table} WHERE {column} IS NOT NULL').fetchall():
                try:
                    valid = math.isfinite(float(row['value']))
                except (TypeError, ValueError):
                    valid = False
                if not valid:
                    conn.execute(f'UPDATE {table} SET {column}=NULL WHERE rowid=?', (row['rowid'],))

def initialize() -> None:
    with connect() as conn:
        # O schema-base e as migrações incrementais são executados em fases
        # transacionais explícitas. Assim uma falha não deixa meia migração de
        # dados aplicada em uma base existente.
        try:
            conn.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + '\nCOMMIT;')
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        conn.execute('BEGIN IMMEDIATE')
        # Migrações incrementais para bancos V0.001/V0.002 já existentes.
        _add_column(conn, 'obras', "endereco TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'obras', 'latitude REAL')
        _add_column(conn, 'obras', 'longitude REAL')
        _add_column(conn, 'obras', "op_padrao TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'obras', 'cliente_id TEXT REFERENCES clientes(id)')
        _add_column(conn, 'carregamento_itens', 'obra_id TEXT REFERENCES obras(id)')
        _add_column(conn, 'carregamento_itens', 'valor_unitario REAL')
        _add_column(conn, 'carregamentos', "motorista TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "veiculo TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "placa TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "propriedade TEXT NOT NULL DEFAULT 'PROPRIO'")
        _add_column(conn, 'carregamentos', "transportadora TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "data_saida TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "hora_saida TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', 'funcionarios INTEGER NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamentos', 'dias_viagem REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamentos', 'distancia_km REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamentos', 'caminhao_id TEXT REFERENCES caminhoes(id)')
        _add_column(conn, "caminhoes", "porte TEXT NOT NULL DEFAULT 'MEDIO'")
        _add_column(conn, 'caminhoes', 'eixos INTEGER NOT NULL DEFAULT 2')
        _add_column(conn, "caminhoes", "combustivel TEXT NOT NULL DEFAULT 'DIESEL'")
        _add_column(conn, 'caminhoes', 'consumo_km_l REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'caminhoes', 'tanque_litros REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'caminhoes', 'tarifa_pedagio_eixo REAL NOT NULL DEFAULT 0')
        _add_column(conn, "planejamentos_rota", "veiculo_json TEXT NOT NULL DEFAULT '{}'")
        _add_column(conn, 'carregamento_obras', 'distancia_km REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_obras', 'custo_pessoal REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_obras', 'custo_frete REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_obras', 'custo_viagem REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_obras', 'valor_obra REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_obras', 'percentual_rateio REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_obras', "observacao TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamento_custos', 'ativo INTEGER NOT NULL DEFAULT 1')
        _add_column(conn, 'equipamentos', "imagem_arquivo TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'equipamentos', "imagem_mime TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'equipamentos', "imagem_atualizada_em TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'clientes', "deleted_at TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'clientes', "deletion_request_id TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'obras', "deleted_at TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'obras', "deletion_request_id TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "deleted_at TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "deletion_request_id TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "data_retorno TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "solicitante TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', 'revisao_operacional INTEGER NOT NULL DEFAULT 1')
        _add_column(conn, 'carregamentos', "criador_usuario_id TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamentos', "criador_usuario_nome TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'obras', "localizacao_original TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'obras', "localizacao_formato TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'caminhoes', "apelido TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'caminhoes', "perfil_codigo TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'caminhoes', "carroceria TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'caminhoes', "parametros_estimados_json TEXT NOT NULL DEFAULT '{}'")
        _add_column(conn, 'locais_rota', "origem_tipo TEXT NOT NULL DEFAULT 'FABRICA'")
        _add_column(conn, 'carregamento_obras', "previsao_entrega TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamento_obras', "referencia_contrato TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamento_itens', "unidade TEXT NOT NULL DEFAULT 'UN'")
        _add_column(conn, 'carregamento_itens', "observacao TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'carregamento_custos', 'funcionarios_aplicados INTEGER NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_custos', "quantidade_tipo TEXT NOT NULL DEFAULT 'FIXO'")
        _add_column(conn, 'carregamento_custos', 'ajuste_manual INTEGER NOT NULL DEFAULT 0')
        _add_column(conn, 'carregamento_custos', 'calculo_versao INTEGER NOT NULL DEFAULT 0')
        _add_column(conn, 'usuarios', 'auth_version INTEGER NOT NULL DEFAULT 1')
        # PATCH 000003 / schema 15: resultado observável do motor de rota.
        _add_column(conn, 'planejamentos_rota', 'tempo_estimado_min REAL NOT NULL DEFAULT 0')
        _add_column(conn, 'planejamentos_rota', "motor_rota TEXT NOT NULL DEFAULT 'FALLBACK_LOCAL'")
        _add_column(conn, 'planejamentos_rota', "distancia_fonte TEXT NOT NULL DEFAULT 'ESTIMADA'")
        _add_column(conn, 'planejamentos_rota', "rota_geometria_json TEXT NOT NULL DEFAULT '[]'")
        _add_column(conn, 'planejamentos_rota', "pedagios_json TEXT NOT NULL DEFAULT '[]'")
        _add_column(conn, 'planejamentos_rota', "base_rodoviaria_versao TEXT NOT NULL DEFAULT ''")
        _add_column(conn, 'planejamentos_rota', "base_pedagios_versao TEXT NOT NULL DEFAULT ''")
        # Contas sem credencial não são contas operacionais ativas. Permanecem
        # cadastradas para que um administrador possa definir a primeira senha.
        conn.execute("UPDATE usuarios SET ativo=0 WHERE COALESCE(senha_hash,'')='' AND ativo<>0")
        # V1.006: pessoal passa a ser valor unitário × funcionários × dias.
        # A conversão ocorre uma única vez e usa os números já registrados na
        # própria carga, preservando a rastreabilidade da regra anterior.
        conn.execute('''UPDATE carregamento_custos
                           SET funcionarios_aplicados=COALESCE((
                                   SELECT c.funcionarios FROM carregamentos c
                                    WHERE c.id=carregamento_custos.carregamento_id),0),
                               quantidade=COALESCE((
                                   SELECT c.dias_viagem FROM carregamentos c
                                    WHERE c.id=carregamento_custos.carregamento_id),0),
                               quantidade_tipo='DIAS',
                               total=CASE WHEN ativo=1 THEN ROUND(valor_unitario *
                                   COALESCE((SELECT c.funcionarios FROM carregamentos c
                                              WHERE c.id=carregamento_custos.carregamento_id),0) *
                                   COALESCE((SELECT c.dias_viagem FROM carregamentos c
                                              WHERE c.id=carregamento_custos.carregamento_id),0),2)
                                   ELSE 0 END,
                               calculo_versao=2
                         WHERE grupo='PESSOAL' AND modo='POR_FUNCIONARIO'
                           AND calculo_versao<2''')
        conn.execute('''UPDATE carregamento_custos
                           SET quantidade_tipo=CASE modo WHEN 'POR_DIA' THEN 'DIAS'
                                                         WHEN 'POR_HORA' THEN 'HORAS'
                                                         ELSE 'FIXO' END,
                               calculo_versao=2
                         WHERE grupo='FRETE' AND calculo_versao<2''')
        conn.execute('''UPDATE carregamento_custos
                           SET quantidade_tipo='FIXO',calculo_versao=2
                         WHERE grupo='PESSOAL' AND modo<>'POR_FUNCIONARIO'
                           AND calculo_versao<2''')
        _sanitize_non_finite(conn)
        conn.execute("INSERT INTO app_meta(key,value) VALUES('schema_version','15') ON CONFLICT(key) DO UPDATE SET value='15'")
        conn.execute("UPDATE carregamentos SET criador_usuario_id='USR-000001',criador_usuario_nome='ADMIN' WHERE criador_usuario_id='' AND criador_usuario_nome=''")
        # Índices que dependem de colunas adicionadas pelas migrações precisam
        # ser criados somente depois dos ALTER TABLE em bancos antigos.
        conn.execute('CREATE INDEX IF NOT EXISTS idx_obras_cliente ON obras(cliente_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_carregamento_itens_carga_obra ON carregamento_itens(carregamento_id,obra_id)')
        # Preços de carregamentos antigos recebem uma fotografia do valor atual
        # somente na primeira migração. A partir da V1.003 cada item novo já é
        # gravado com seu valor unitário histórico.
        conn.execute('''UPDATE carregamento_itens
                           SET valor_unitario=(SELECT e.valor_unit FROM equipamentos e
                                                WHERE e.codigo=carregamento_itens.equipamento_codigo)
                         WHERE valor_unitario IS NULL''')
        conn.execute("INSERT OR IGNORE INTO locais_rota(id,tipo,nome,endereco,updated_at) VALUES('FABRICA','FABRICA','FÁBRICA / ORIGEM','','')")
        # Cada obra recebe um cliente. Em bancos anteriores, o Município é o
        # nome do cliente, conforme a regra operacional desta versão.
        client_counter_row = conn.execute("SELECT value FROM counters WHERE entity='cliente'").fetchone()
        client_counter = int(client_counter_row['value']) if client_counter_row else 0
        for row in conn.execute("SELECT DISTINCT TRIM(municipio) nome FROM obras WHERE TRIM(municipio)<>'' ORDER BY nome").fetchall():
            existing = conn.execute("SELECT id FROM clientes WHERE UPPER(TRIM(nome))=UPPER(TRIM(?))",(row['nome'],)).fetchone()
            if not existing:
                client_counter += 1
                cid = f'CLI-{client_counter:06d}'
                conn.execute("INSERT INTO clientes(id,nome,created_at,updated_at) VALUES(?,?,datetime('now'),datetime('now'))",(cid,row['nome']))
        conn.execute("INSERT INTO counters(entity,value) VALUES('cliente',?) ON CONFLICT(entity) DO UPDATE SET value=MAX(value,excluded.value)",(client_counter,))
        conn.execute('''UPDATE obras SET cliente_id=(
            SELECT c.id FROM clientes c WHERE UPPER(TRIM(c.nome))=UPPER(TRIM(obras.municipio)) LIMIT 1
        ) WHERE cliente_id IS NULL AND TRIM(municipio)<>'' ''')
        # Compatibilidade: todo carregamento antigo passa a ter sua obra antiga
        # registrada também na nova relação N:N.
        conn.execute('''
            INSERT OR IGNORE INTO carregamento_obras
            (carregamento_id,obra_id,op_numero,municipio,endereco,latitude,longitude,ordem)
            SELECT c.id,o.id,COALESCE(o.op_padrao,''),COALESCE(o.municipio,''),COALESCE(o.endereco,''),o.latitude,o.longitude,0
            FROM carregamentos c JOIN obras o ON o.id=c.obra_id
        ''')
        conn.execute('''UPDATE carregamento_itens
                           SET obra_id=(SELECT co.obra_id FROM carregamento_obras co
                                        WHERE co.carregamento_id=carregamento_itens.carregamento_id
                                        ORDER BY co.ordem,co.obra_id LIMIT 1)
                         WHERE obra_id IS NULL
                           AND (SELECT COUNT(*) FROM carregamento_obras co
                                WHERE co.carregamento_id=carregamento_itens.carregamento_id)=1''')
        conn.execute('''UPDATE carregamento_obras
                           SET valor_obra=ROUND((
                               SELECT SUM(ci.quantidade*COALESCE(ci.valor_unitario,e.valor_unit,0))
                                 FROM carregamento_itens ci
                                 JOIN equipamentos e ON e.codigo=ci.equipamento_codigo
                                WHERE ci.carregamento_id=carregamento_obras.carregamento_id
                                  AND ci.obra_id=carregamento_obras.obra_id
                           ),2)
                         WHERE COALESCE((
                               SELECT SUM(ci.quantidade*COALESCE(ci.valor_unitario,e.valor_unit,0))
                                 FROM carregamento_itens ci
                                 JOIN equipamentos e ON e.codigo=ci.equipamento_codigo
                                WHERE ci.carregamento_id=carregamento_obras.carregamento_id
                                  AND ci.obra_id=carregamento_obras.obra_id
                           ),0)>0''')
        # Converte totais antigos em linhas fixas, preservando o histórico sem
        # duplicar custos em bancos já migrados.
        conn.execute('''
            INSERT INTO carregamento_custos(
                carregamento_id,grupo,descricao,modo,valor_unitario,quantidade,total,ordem
            )
            SELECT co.carregamento_id,'PESSOAL','CUSTO PESSOAL ANTERIOR','FIXO',
                   SUM(co.custo_pessoal),1,SUM(co.custo_pessoal),0
              FROM carregamento_obras co
             WHERE NOT EXISTS(
                   SELECT 1 FROM carregamento_custos cc
                    WHERE cc.carregamento_id=co.carregamento_id)
             GROUP BY co.carregamento_id
            HAVING SUM(co.custo_pessoal)>0
        ''')
        conn.execute('''
            INSERT INTO carregamento_custos(
                carregamento_id,grupo,descricao,modo,valor_unitario,quantidade,total,ordem
            )
            SELECT co.carregamento_id,'FRETE','CUSTO DE FRETE ANTERIOR','FIXO',
                   CASE WHEN SUM(co.custo_viagem)-SUM(co.custo_pessoal)>0
                        THEN SUM(co.custo_viagem)-SUM(co.custo_pessoal)
                        ELSE SUM(co.custo_frete) END,
                   1,
                   CASE WHEN SUM(co.custo_viagem)-SUM(co.custo_pessoal)>0
                        THEN SUM(co.custo_viagem)-SUM(co.custo_pessoal)
                        ELSE SUM(co.custo_frete) END,
                   0
              FROM carregamento_obras co
             WHERE NOT EXISTS(
                   SELECT 1 FROM carregamento_custos cc
                    WHERE cc.carregamento_id=co.carregamento_id AND cc.grupo='FRETE')
             GROUP BY co.carregamento_id
            HAVING SUM(co.custo_frete)>0 OR SUM(co.custo_viagem)-SUM(co.custo_pessoal)>0
        ''')
        conn.execute('''
            UPDATE carregamentos
               SET distancia_km=COALESCE((
                   SELECT MAX(co.distancia_km) FROM carregamento_obras co
                    WHERE co.carregamento_id=carregamentos.id
               ),0)
             WHERE distancia_km=0
        ''')
        # Recalcula o rateio pela soma dos itens sempre que todas as Obras já
        # possuem valor. Bases sem preços mantêm o rateio histórico anterior.
        loads = conn.execute('SELECT id FROM carregamentos').fetchall()
        for load in loads:
            works = conn.execute('''
                SELECT obra_id,valor_obra,custo_pessoal,custo_frete,custo_viagem
                  FROM carregamento_obras
                 WHERE carregamento_id=? ORDER BY ordem,obra_id
            ''',(load['id'],)).fetchall()
            if not works:
                continue
            values = [float(row['valor_obra'] or 0) for row in works]
            if all(value>0 for value in values):
                cost_row = conn.execute('''SELECT COUNT(*) linhas,
                    COALESCE(SUM(CASE WHEN grupo='PESSOAL' THEN total ELSE 0 END),0) pessoal,
                    COALESCE(SUM(CASE WHEN grupo='FRETE' THEN total ELSE 0 END),0) frete
                    FROM carregamento_custos WHERE carregamento_id=?''',(load['id'],)).fetchone()
                personnel_total = float(cost_row['pessoal'] or 0) if cost_row['linhas'] else sum(float(row['custo_pessoal'] or 0) for row in works)
                freight_total = float(cost_row['frete'] or 0) if cost_row['linhas'] else sum(float(row['custo_frete'] or 0) for row in works)
                value_total = sum(values)
                shares=[]; used_share=0.0
                for index,value in enumerate(values):
                    share=round(100.0-used_share,6) if index==len(values)-1 else round(value/value_total*100,6)
                    shares.append(share); used_share+=share
                def split_amount(total):
                    parts=[]; used=0.0
                    for index,share in enumerate(shares):
                        amount=round(total-used,2) if index==len(shares)-1 else round(total*share/100,2)
                        parts.append(amount); used=round(used+amount,2)
                    return parts
                personnel_parts=split_amount(personnel_total)
                freight_parts=split_amount(freight_total)
                for index,row in enumerate(works):
                    conn.execute('''UPDATE carregamento_obras
                        SET percentual_rateio=?,custo_pessoal=?,custo_frete=?,custo_viagem=?
                        WHERE carregamento_id=? AND obra_id=?''',(
                        shares[index],personnel_parts[index],freight_parts[index],
                        round(personnel_parts[index]+freight_parts[index],2),load['id'],row['obra_id']))
                continue
            if any(float(row['percentual_rateio'] or 0)>0 for row in conn.execute(
                'SELECT percentual_rateio FROM carregamento_obras WHERE carregamento_id=?',(load['id'],)
            )):
                continue
            total = sum(float(row['custo_viagem'] or 0) for row in works)
            allocated = 0.0
            for index,row in enumerate(works):
                if index == len(works)-1:
                    share = round(100.0-allocated,6)
                elif total>0:
                    share = round(float(row['custo_viagem'] or 0)/total*100,6)
                    allocated += share
                else:
                    share = round(100.0/len(works),6)
                    allocated += share
                conn.execute('''UPDATE carregamento_obras SET percentual_rateio=?
                                 WHERE carregamento_id=? AND obra_id=?''',(share,load['id'],row['obra_id']))
