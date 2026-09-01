from __future__ import annotations
import json
from datetime import datetime
from Core.audit import log
from Core.db import connect
from Core.filetx import stage_bytes, stage_mkdir, stage_move
from Core.ids import next_id
from Core.paths import DATA_ROOT, cadastro_obra_path, cadastro_praca_path, obra_folder, praca_folder, ensure_under_data, unit_folder, slug
from Core.text import upper_code, upper_text
from Core.validation import coordinates

WORK_STATUSES = {"ATIVA", "PAUSADA", "CONCLUÍDA"}
SQUARE_STATUSES = {"ATIVA", "INATIVA"}

def _now(): return datetime.now().isoformat(timespec='seconds')

def _float_or_none(v):
    if v in (None,''): return None
    try: return float(str(v).replace(',','.'))
    except Exception as exc: raise ValueError('Latitude/longitude inválida.') from exc

def _stage_json(path, payload):
    stage_bytes(path,(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))

def list_unidades():
    with connect() as c: return [dict(r) for r in c.execute('SELECT * FROM unidades WHERE ativo=1 ORDER BY nome')]

def create_unidade(nome: str, uf: str):
    nome=upper_text(nome,max_length=120); uf=upper_code(uf)
    if not nome: raise ValueError('Informe o nome do Estado/Unidade.')
    if len(uf)!=2 or not uf.isalpha(): raise ValueError('Informe uma UF válida com duas letras.')
    now=_now()
    with connect() as c:
        old=c.execute('SELECT * FROM unidades WHERE uf=?',(uf,)).fetchone()
        if old: return dict(old)
        base=f'UNI-{slug(uf,"UF")}'
        uid=base
        n=1
        while c.execute('SELECT 1 FROM unidades WHERE id=?',(uid,)).fetchone():
            n+=1; uid=f'{base}-{n}'
        c.execute('INSERT INTO unidades(id,nome,uf,created_at,updated_at) VALUES(?,?,?,?,?)',(uid,nome,uf,now,now))
        log('UNIDADE_CRIADA',id=uid,nome=nome,uf=uf)
        return dict(c.execute('SELECT * FROM unidades WHERE id=?',(uid,)).fetchone())

def get_or_create_unidade(uf: str, nome: str=''):
    uf=upper_code(uf); nome=upper_text(nome,max_length=120)
    if len(uf)!=2 or not uf.isalpha(): raise ValueError('Estado/UF deve ter duas letras.')
    with connect() as c:
        row=c.execute('SELECT * FROM unidades WHERE uf=?',(uf,)).fetchone()
        if row: return dict(row)
    return create_unidade(nome or uf,uf)

def list_obras():
    with connect() as c:
        return [dict(r) for r in c.execute('''SELECT o.*,u.nome unidade_nome,u.uf,cl.nome cliente_nome
            FROM obras o JOIN unidades u ON u.id=o.unidade_id
            LEFT JOIN clientes cl ON cl.id=o.cliente_id
            WHERE o.deleted_at='' ORDER BY u.nome,o.nome''')]

def _resolve_cliente(c, cliente_id, cliente_nome: str, municipio: str, now: str) -> str:
    requested_id=str(cliente_id or '').strip()
    if requested_id:
        row=c.execute("SELECT id FROM clientes WHERE id=? AND ativo=1 AND deleted_at=''",(requested_id,)).fetchone()
        if not row: raise ValueError('Cliente inválido ou inativo.')
        return row['id']
    name=upper_text(cliente_nome,max_length=200) or upper_text(municipio,max_length=200)
    if not name: raise ValueError('Informe o Cliente ou o Município da obra.')
    row=c.execute("SELECT id,ativo FROM clientes WHERE deleted_at='' AND UPPER(TRIM(nome))=UPPER(TRIM(?)) LIMIT 1",(name,)).fetchone()
    if row:
        if not row['ativo']: raise ValueError('Cliente encontrado, mas está inativo.')
        return row['id']
    cid=next_id(c,'cliente','CLI')
    c.execute('INSERT INTO clientes(id,nome,created_at,updated_at) VALUES(?,?,?,?)',(cid,name,now,now))
    return cid

def create_obra(unidade_id: str, nome: str, municipio: str='', codigo: str='', endereco: str='', latitude=None, longitude=None, op_padrao: str='', cliente_id: str='', cliente_nome: str=''):
    nome=upper_text(nome,max_length=240); municipio=upper_text(municipio,max_length=160); codigo=upper_code(codigo)
    if not nome: raise ValueError('Nome da obra é obrigatório.')
    lat,lng=coordinates(latitude,longitude,optional=True); now=_now()
    with connect() as c:
        u=c.execute('SELECT * FROM unidades WHERE id=?',(unidade_id,)).fetchone()
        if not u: raise ValueError('Unidade inválida.')
        resolved_client=_resolve_cliente(c,cliente_id,cliente_nome,municipio,now)
        oid=next_id(c,'obra','OBR'); folder=obra_folder(oid,nome)
        c.execute('''INSERT INTO obras(id,unidade_id,cliente_id,nome,municipio,codigo,folder_name,created_at,updated_at,endereco,latitude,longitude,op_padrao)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(oid,unidade_id,resolved_client,nome,municipio,codigo,folder,now,now,upper_text(endereco),lat,lng,upper_code(op_padrao)))
        p=ensure_under_data(cadastro_obra_path(u['uf'],u['nome'],folder)); stage_mkdir(p); stage_mkdir(p/'Pracas')
        _stage_json(p/'_sistema.json',{'tipo':'OBRA','id':oid,'unidade_id':unidade_id,'folder_name':folder,'created_at':now})
        log('OBRA_CRIADA', id=oid, unidade=unidade_id, nome=nome)
        return dict(c.execute('SELECT * FROM obras WHERE id=?',(oid,)).fetchone())

def find_matching_obra(unidade_id: str, nome: str, municipio: str=''):
    nome=upper_text(nome); municipio=upper_text(municipio)
    if not nome: return None
    with connect() as c:
        row=c.execute('''SELECT * FROM obras WHERE deleted_at='' AND unidade_id=? AND UPPER(TRIM(nome))=UPPER(TRIM(?))
                         AND (TRIM(?)='' OR UPPER(TRIM(municipio))=UPPER(TRIM(?))) ORDER BY id LIMIT 1''',(unidade_id,nome,municipio,municipio)).fetchone()
        return dict(row) if row else None

def update_obra(obra_id: str, nome: str, municipio: str='', codigo: str='', status: str='ATIVA', endereco=None, latitude=None, longitude=None, op_padrao=None, cliente_id=None, cliente_nome=None):
    nome=upper_text(nome,max_length=240)
    if not nome: raise ValueError('Nome da obra é obrigatório.')
    normalized_status=upper_text(status or 'ATIVA',max_length=20)
    if normalized_status not in WORK_STATUSES: raise ValueError('Status da obra inválido.')
    now=_now()
    with connect() as c:
        old=c.execute("""SELECT o.*,u.nome unidade_nome,u.uf FROM obras o JOIN unidades u ON u.id=o.unidade_id WHERE o.id=? AND o.deleted_at=''""",(obra_id,)).fetchone()
        if not old: raise ValueError('Obra não encontrada.')
        newfolder=obra_folder(obra_id,nome)
        oldpath=ensure_under_data(cadastro_obra_path(old['uf'],old['unidade_nome'],old['folder_name']))
        newpath=ensure_under_data(cadastro_obra_path(old['uf'],old['unidade_nome'],newfolder))
        operation_moves=[]
        unit=unit_folder(old['uf'],old['unidade_nome']); op_root=DATA_ROOT/'Operacao'
        if oldpath != newpath:
            if newpath.exists(): raise ValueError('Destino interno já existe; renomeação cancelada.')
            if op_root.exists():
                for unit_dir in op_root.glob(f'*/*/{unit}'):
                    src=unit_dir/old['folder_name']; dst=unit_dir/newfolder
                    if src.exists():
                        if dst.exists(): raise ValueError('Existe pasta operacional de destino; renomeação cancelada.')
                        operation_moves.append((src,dst))
            if oldpath.exists():
                stage_move(oldpath,newpath)
            for src,dst in operation_moves:
                stage_move(src,dst)
        if latitude is None and longitude is None:
            lat,lng=old['latitude'],old['longitude']
        else:
            lat,lng=coordinates(
                old['latitude'] if latitude in (None,'') else latitude,
                old['longitude'] if longitude in (None,'') else longitude,
                optional=True,
            )
        end=old['endereco'] if endereco is None else upper_text(endereco)
        op=old['op_padrao'] if op_padrao is None else upper_code(op_padrao)
        requested_client=str(cliente_id or '').strip()
        if requested_client and requested_client==str(old['cliente_id'] or ''):
            resolved_client=old['cliente_id']
        else:
            resolved_client=old['cliente_id'] if cliente_id is None and cliente_nome is None else _resolve_cliente(c,cliente_id,cliente_nome,municipio,now)
        c.execute('''UPDATE obras SET nome=?,municipio=?,codigo=?,status=?,folder_name=?,updated_at=?,endereco=?,latitude=?,longitude=?,op_padrao=?,cliente_id=? WHERE id=?''',
                  (nome,upper_text(municipio,max_length=160),upper_code(codigo),normalized_status,newfolder,now,end,lat,lng,op,resolved_client,obra_id))
        stage_mkdir(newpath)
        _stage_json(newpath/'_sistema.json',{'tipo':'OBRA','id':obra_id,'unidade_id':old['unidade_id'],'folder_name':newfolder,'updated_at':now})
        log('OBRA_EDITADA', id=obra_id, nome=nome)
        return dict(c.execute('SELECT * FROM obras WHERE id=?',(obra_id,)).fetchone())

def list_pracas(obra_id: str | None=None):
    sql="""SELECT p.*,o.nome obra_nome,o.unidade_id FROM pracas p JOIN obras o ON o.id=p.obra_id WHERE o.deleted_at=''"""; args=()
    if obra_id: sql+=' AND p.obra_id=?'; args=(obra_id,)
    sql += " ORDER BY o.nome, COALESCE(NULLIF(p.nome,''),p.op_numero)"
    with connect() as c: return [dict(r) for r in c.execute(sql,args)]

def create_praca(obra_id: str, nome: str='', op_numero: str='', endereco: str='', observacao: str=''):
    nome=upper_text(nome,max_length=200); op=upper_code(op_numero)
    if not nome and not op: raise ValueError('Informe o nome da Praça, o número da OP ou ambos.')
    now=_now()
    with connect() as c:
        o=c.execute("""SELECT o.*,u.nome unidade_nome,u.uf FROM obras o JOIN unidades u ON u.id=o.unidade_id WHERE o.id=? AND o.deleted_at=''""",(obra_id,)).fetchone()
        if not o: raise ValueError('Obra inválida.')
        pid=next_id(c,'praca','PRC'); folder=praca_folder(pid,nome,op)
        c.execute('''INSERT INTO pracas(id,obra_id,nome,op_numero,endereco,observacao,folder_name,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)''',(pid,obra_id,nome,op,upper_text(endereco),upper_text(observacao,multiline=True),folder,now,now))
        p=ensure_under_data(cadastro_praca_path(o['uf'],o['unidade_nome'],o['folder_name'],folder)); stage_mkdir(p)
        _stage_json(p/'_sistema.json',{'tipo':'PRACA','id':pid,'obra_id':obra_id,'folder_name':folder,'created_at':now})
        log('PRACA_CRIADA', id=pid, obra=obra_id, nome=nome, op=op)
        return dict(c.execute('SELECT * FROM pracas WHERE id=?',(pid,)).fetchone())

def update_praca(praca_id: str, nome: str='', op_numero: str='', endereco: str='', observacao: str='', status: str='ATIVA'):
    nome=upper_text(nome,max_length=200); op=upper_code(op_numero)
    if not nome and not op: raise ValueError('Informe o nome da Praça, o número da OP ou ambos.')
    normalized_status=upper_text(status or 'ATIVA',max_length=20)
    if normalized_status not in SQUARE_STATUSES: raise ValueError('Status da Praça inválido.')
    now=_now()
    with connect() as c:
        old=c.execute('''SELECT p.*,o.folder_name obra_folder,u.nome unidade_nome,u.uf FROM pracas p JOIN obras o ON o.id=p.obra_id JOIN unidades u ON u.id=o.unidade_id WHERE p.id=?''',(praca_id,)).fetchone()
        if not old: raise ValueError('Praça não encontrada.')
        newfolder=praca_folder(praca_id,nome,op)
        oldpath=ensure_under_data(cadastro_praca_path(old['uf'],old['unidade_nome'],old['obra_folder'],old['folder_name']))
        newpath=ensure_under_data(cadastro_praca_path(old['uf'],old['unidade_nome'],old['obra_folder'],newfolder))
        if oldpath!=newpath and oldpath.exists():
            if newpath.exists(): raise ValueError('Destino interno já existe; renomeação cancelada.')
            stage_move(oldpath,newpath)
        c.execute('UPDATE pracas SET nome=?,op_numero=?,endereco=?,observacao=?,status=?,folder_name=?,updated_at=? WHERE id=?',(nome,op,upper_text(endereco),upper_text(observacao,multiline=True),normalized_status,newfolder,now,praca_id))
        stage_mkdir(newpath)
        _stage_json(newpath/'_sistema.json',{'tipo':'PRACA','id':praca_id,'obra_id':old['obra_id'],'folder_name':newfolder,'updated_at':now})
        log('PRACA_EDITADA', id=praca_id, nome=nome, op=op)
        return dict(c.execute('SELECT * FROM pracas WHERE id=?',(praca_id,)).fetchone())
