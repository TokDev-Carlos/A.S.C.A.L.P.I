from __future__ import annotations
import re, unicodedata
from datetime import date
from pathlib import Path
from Core.config import network_root, shared_data_root
SYSTEM_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SYSTEM_DIR.parent
NETWORK_ROOT = network_root()
DATA_ROOT = shared_data_root()
MONTHS = {1:'JANEIRO',2:'FEVEREIRO',3:'MARCO',4:'ABRIL',5:'MAIO',6:'JUNHO',7:'JULHO',8:'AGOSTO',9:'SETEMBRO',10:'OUTUBRO',11:'NOVEMBRO',12:'DEZEMBRO'}

def slug(value: str, fallback: str='SEM_NOME') -> str:
    text = unicodedata.normalize('NFKD', value or '').encode('ascii','ignore').decode('ascii')
    text = re.sub(r'[^A-Za-z0-9]+','_',text).strip('_').upper()
    return text[:70] or fallback

def unit_folder(uf: str, nome: str) -> str:
    return f'{slug(uf, "UF")} - {slug(nome)}'

def obra_folder(obra_id: str, nome: str) -> str:
    return f'{obra_id}__{slug(nome, "OBRA")}'

def praca_folder(praca_id: str, nome: str, op: str='') -> str:
    label = nome.strip() or f'OP_{op.strip()}'
    tail = f'__{slug(op)}' if op.strip() else ''
    return f'{praca_id}__{slug(label, "PRACA")}{tail}'

def cadastro_obra_path(uf: str, unidade: str, obra_folder_name: str) -> Path:
    return DATA_ROOT / 'Cadastros' / unit_folder(uf, unidade) / 'Obras' / obra_folder_name

def cadastro_praca_path(uf: str, unidade: str, obra_folder_name: str, praca_folder_name: str) -> Path:
    return cadastro_obra_path(uf, unidade, obra_folder_name) / 'Pracas' / praca_folder_name

def operation_month_base(d: date) -> Path:
    return DATA_ROOT / 'Operacao' / str(d.year) / f'{d.month:02d} - {MONTHS[d.month]}'

def operation_month_root(d: date, uf: str, unidade: str) -> Path:
    return operation_month_base(d) / unit_folder(uf, unidade)

def carregamento_path(d: date, uf: str, unidade: str, obra_folder_name: str, carregamento_id: str) -> Path:
    # Mantido para compatibilidade com registros antigos de uma única Obra.
    return operation_month_root(d, uf, unidade) / obra_folder_name / 'Carregamentos' / f'{d.isoformat()}__{carregamento_id}'

def carregamento_global_path(d: date, carregamento_id: str) -> Path:
    # Novo padrão: Carregamento é um evento independente e pode conter várias Obras/Estados.
    return operation_month_base(d) / '_CARREGAMENTOS' / f'{d.isoformat()}__{carregamento_id}'

def ensure_under_data(path: Path) -> Path:
    resolved = path.resolve()
    root = DATA_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError('Caminho fora da raiz de dados protegida.')
    return resolved
