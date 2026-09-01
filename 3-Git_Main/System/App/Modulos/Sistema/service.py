from __future__ import annotations
import hashlib, json, os, sqlite3, subprocess, tempfile, threading, urllib.parse, uuid, zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from Core.audit import log
from Core.config import local_backups_path, local_logs_path, local_temp_path, network_root
from Core.db import DB_PATH, connect
from Core.repository import status as repository_status
from Core.paths import DATA_ROOT, PROJECT_ROOT
from Core.version import app_version
from Core.storage import GIB, MIB, directory_size, ensure_disk_space, status as storage_status

SYSTEM_DIR=Path(__file__).resolve().parents[2]
BACKUPS_DIR=local_backups_path()
LOG_DIR=local_logs_path()
TEMP_DIR=local_temp_path()
_SHUTDOWN_LOCK=threading.Lock()
_SHUTDOWN_PREPARED=False
MAX_BACKUPS=20
MAX_BACKUP_FILES=100_000
MAX_BACKUP_MANIFEST_BYTES=32*MIB
MAX_BACKUP_UNCOMPRESSED_BYTES=512*GIB
MAX_MASTER_PATCH_BYTES=512*MIB
MAX_MASTER_PATCH_MEMBERS=20_000
MAX_MASTER_PATCH_UNCOMPRESSED_BYTES=2*GIB

def _sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    return digest.hexdigest()

def _zip_member_sha256(archive: zipfile.ZipFile, name: str) -> str:
    digest=hashlib.sha256()
    with archive.open(name,'r') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    return digest.hexdigest()

def _valid_backup_member(name: str) -> bool:
    if not isinstance(name,str) or not name or len(name)>512 or "\\" in name or "\x00" in name:
        return False
    path=PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    if path.as_posix()!=name or name.endswith("/"):
        return False
    return name in {"manifesto.json","Banco/sistema.db"} or (
        len(path.parts)>=2 and path.parts[0]=="Dados"
    )

def status(include_sensitive: bool = True):
    with connect() as c:
        counts={t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['unidades','clientes','obras','pracas','carregamentos','caminhoes','viagens','receitas','equipamentos']}
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        foreign_keys=len(c.execute('PRAGMA foreign_key_check').fetchall())
    healthy=integrity=='ok' and foreign_keys==0
    repository=repository_status()
    payload={'status':'OK' if healthy else 'ERRO','version':app_version(),'environment':'PRODUCAO','integrity':integrity,'foreign_key_errors':foreign_keys,'counts':counts,
             'repository':{key:value for key,value in repository.items() if include_sensitive or key not in {'network_root','repository_root','station_id'}}}
    if include_sensitive:
        payload['paths']={'project_root':str(PROJECT_ROOT),'data_root':str(DATA_ROOT),'database':str(DB_PATH)}
        payload['storage']={'dados':storage_status(DATA_ROOT),'backups':storage_status(BACKUPS_DIR),'data_bytes':directory_size(DATA_ROOT)}
        payload['protected']=['IDs técnicos','caminhos físicos','nomes técnicos de pastas','schema SQLite','timestamps internos','arquivos _sistema.json']
    return payload

def prepare_shutdown():
    global _SHUTDOWN_PREPARED
    with _SHUTDOWN_LOCK:
        if _SHUTDOWN_PREPARED:
            return {'ok':True,'integridade':'OK','ja_preparado':True}
        try:
            with connect() as c:
                integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
                foreign_keys=c.execute('PRAGMA foreign_key_check').fetchall()
                if integrity!='ok': raise RuntimeError(f'Falha de integridade: {integrity}')
                if foreign_keys: raise RuntimeError(f'Falha de referências: {len(foreign_keys)} vínculo(s) inválido(s)')
                checkpoint=c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                if checkpoint and int(checkpoint[0] or 0)>0:
                    raise RuntimeError('Banco ocupado; tente fechar novamente em alguns segundos.')
            log('SISTEMA_ENCERRADO_SEGURO',integridade='OK',referencias='OK',checkpoint='TRUNCATE')
            _SHUTDOWN_PREPARED=True
            return {'ok':True,'integridade':'OK','referencias':'OK','checkpoint':'TRUNCATE'}
        except Exception as exc:
            log('FALHA_ENCERRAMENTO_SEGURO',erro=str(exc))
            raise

def recent_logs(limit=60):
    files=sorted(LOG_DIR.glob('*.jsonl'),reverse=True); out=[]
    for f in files:
        try:
            lines=f.read_text(encoding='utf-8').splitlines()
            for line in reversed(lines):
                try: out.append(json.loads(line))
                except Exception: pass
                if len(out)>=limit: return out
        except OSError: pass
    return out

def validate_backup(path: str | Path) -> dict:
    candidate=Path(path)
    if not candidate.is_file(): raise FileNotFoundError('Arquivo de backup não encontrado.')
    TEMP_DIR.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(candidate,'r') as archive:
        entries=archive.infolist()
        if not entries or len(entries)>MAX_BACKUP_FILES+1:
            raise RuntimeError('A QUANTIDADE DE ARQUIVOS DO BACKUP É INVÁLIDA.')
        names=[entry.filename for entry in entries]
        if len(names)!=len(set(name.casefold() for name in names)):
            raise RuntimeError('O BACKUP POSSUI CAMINHOS DUPLICADOS OU AMBÍGUOS.')
        total=0
        for entry in entries:
            if not _valid_backup_member(entry.filename) or entry.is_dir() or entry.flag_bits&1:
                raise RuntimeError(f'CAMINHO OU COMPONENTE INVÁLIDO NO BACKUP: {entry.filename!r}.')
            if entry.file_size<0 or entry.compress_size<0:
                raise RuntimeError('O BACKUP POSSUI TAMANHO DE COMPONENTE INVÁLIDO.')
            total+=entry.file_size
            if total>MAX_BACKUP_UNCOMPRESSED_BYTES:
                raise RuntimeError('O BACKUP ULTRAPASSA O LIMITE DE SEGURANÇA PARA VALIDAÇÃO.')
        manifest_entry=next((entry for entry in entries if entry.filename=='manifesto.json'),None)
        if manifest_entry is None or manifest_entry.file_size>MAX_BACKUP_MANIFEST_BYTES:
            raise RuntimeError('MANIFESTO DO BACKUP AUSENTE OU EXCESSIVO.')
        if archive.testzip() is not None: raise RuntimeError('O ZIP DO BACKUP ESTÁ CORROMPIDO.')
        try: manifest=json.loads(archive.read('manifesto.json').decode('utf-8'))
        except Exception as exc: raise RuntimeError('MANIFESTO DO BACKUP AUSENTE OU INVÁLIDO.') from exc
        files=manifest.get('files') if isinstance(manifest,dict) else None
        if not isinstance(manifest,dict) or manifest.get('format')!=2 or not isinstance(files,dict) or 'Banco/sistema.db' not in files:
            raise RuntimeError('FORMATO DO BACKUP NÃO É SUPORTADO.')
        if not files or len(files)>MAX_BACKUP_FILES:
            raise RuntimeError('MANIFESTO DO BACKUP POSSUI QUANTIDADE INVÁLIDA DE ARQUIVOS.')
        if any(
            not _valid_backup_member(name) or name=='manifesto.json'
            or not isinstance(expected,str) or len(expected)!=64
            or any(character not in '0123456789abcdef' for character in expected.lower())
            for name,expected in files.items()
        ):
            raise RuntimeError('MANIFESTO DO BACKUP POSSUI CAMINHO OU HASH INVÁLIDO.')
        declared=set(files); present=set(archive.namelist())-{'manifesto.json'}
        if declared!=present: raise RuntimeError('CONJUNTO DE ARQUIVOS DO BACKUP DIVERGE DO MANIFESTO.')
        for name,expected in files.items():
            if _zip_member_sha256(archive,name)!=str(expected):
                raise RuntimeError(f'HASH INVÁLIDO NO BACKUP: {name}.')
        with tempfile.TemporaryDirectory(prefix='validar_backup_',dir=TEMP_DIR) as temp_name:
            database=Path(temp_name)/'sistema.db'
            with archive.open('Banco/sistema.db') as source,database.open('wb') as target:
                for block in iter(lambda:source.read(1024*1024),b''): target.write(block)
            connection=sqlite3.connect(database)
            try:
                integrity=connection.execute('PRAGMA integrity_check').fetchone()[0]
                foreign=connection.execute('PRAGMA foreign_key_check').fetchall()
            finally: connection.close()
            if integrity!='ok' or foreign: raise RuntimeError('BANCO DO BACKUP NÃO PASSOU NA INTEGRIDADE.')
    return {'ok':True,'arquivo':candidate.name,'sha256':_sha256_file(candidate),'files':len(files),'size':candidate.stat().st_size}

def backup():
    BACKUPS_DIR.mkdir(parents=True,exist_ok=True)
    TEMP_DIR.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    dest=BACKUPS_DIR/f'cjl_backup_{stamp}.zip'
    temporary=BACKUPS_DIR/f'.cjl_backup_{stamp}.{os.getpid()}.tmp'
    if not DB_PATH.exists(): raise ValueError('Banco de dados não encontrado.')
    with connect() as checkpoint:
        result=checkpoint.execute('PRAGMA wal_checkpoint(FULL)').fetchone()
        if result and int(result[0] or 0)>0: raise RuntimeError('Banco ocupado; tente o backup novamente.')
    estimate=DB_PATH.stat().st_size+directory_size(DATA_ROOT)
    ensure_disk_space(BACKUPS_DIR,estimate,label='BACKUP COMPLETO')
    try:
        with tempfile.TemporaryDirectory(prefix='backup_',dir=TEMP_DIR) as temp_name:
            temp_db=Path(temp_name)/'sistema.db'
            source=sqlite3.connect(DB_PATH)
            target=sqlite3.connect(temp_db)
            try:
                source.backup(target)
            finally:
                target.close(); source.close()
            files={}
            with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
                archive.write(temp_db,'Banco/sistema.db')
                files['Banco/sistema.db']=_sha256_file(temp_db)
                if DATA_ROOT.exists():
                    for data_file in sorted(path for path in DATA_ROOT.rglob('*') if path.is_file() and not path.is_symlink()):
                        relative=data_file.relative_to(DATA_ROOT)
                        lowered={part.lower() for part in relative.parts}
                        if '.cjlstaging' in lowered or data_file.name.endswith(('.stage','.tmp')): continue
                        member='Dados/'+relative.as_posix()
                        archive.write(data_file,member)
                        files[member]=_sha256_file(data_file)
                archive.writestr('manifesto.json',json.dumps({
                    'format':2,'sistema':'CJL System','versao':app_version(),
                    'criado_em':datetime.now().astimezone().isoformat(timespec='seconds'),
                    'files':files,
                },ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n')
            # O arquivo só recebe o nome definitivo depois de CRC, hashes e
            # integridade SQLite terem sido confirmados.
            validation=validate_backup(temporary)
            os.replace(temporary,dest)
    finally:
        temporary.unlink(missing_ok=True)
    old=sorted(BACKUPS_DIR.glob('cjl_backup_*.zip'),key=lambda item:item.stat().st_mtime,reverse=True)
    for expired in old[MAX_BACKUPS:]:
        try: expired.unlink()
        except OSError: pass
    log('BACKUP_MANUAL',arquivo=dest.name)
    return {'arquivo':dest.name,'path':str(dest),'sha256':validation['sha256'],'files':validation['files'],'validado':True}


# ---------------------------------------------------------------------------
# MASTER PATCH MANAGEMENT - Layout 5 / Patch format 6
# ---------------------------------------------------------------------------

def _assert_direct_master() -> Path:
    root=network_root().resolve()
    mode=str(os.environ.get('CJL_HOST_MODE') or '').strip().upper()
    if mode!='MASTER_DIRECT' or PROJECT_ROOT.resolve()!=root:
        raise PermissionError('PATCHES DO MESTRE SO PODEM SER GERENCIADOS NO CJL System MESTRE.')
    return root


def _master_patch_inbox(root: Path) -> Path:
    inbox=root/'Updates'/'In'
    inbox.mkdir(parents=True,exist_ok=True)
    return inbox


def _safe_patch_filename(value: str) -> str:
    raw=urllib.parse.unquote(str(value or '').strip()).replace('\\','/')
    name=Path(raw).name
    if not name or name!=raw.split('/')[-1] or len(name)>180 or not name.lower().endswith('.zip'):
        raise ValueError('NOME DO PATCH INVALIDO. SELECIONE UM ARQUIVO .ZIP.')
    allowed='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.() '
    if any(ch not in allowed for ch in name):
        raise ValueError('O NOME DO PATCH POSSUI CARACTERES NAO SUPORTADOS.')
    return name


def _zip_patch_manifest(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path,'r') as archive:
            members=archive.infolist()
            if not members or len(members)>MAX_MASTER_PATCH_MEMBERS:
                raise ValueError('QUANTIDADE DE COMPONENTES DO PATCH INVALIDA.')
            total=0
            manifest_members=[]
            seen=set()
            for member in members:
                name=str(member.filename or '').replace('\\','/')
                if not name or '\x00' in name or name.startswith('/'):
                    raise ValueError('PATCH POSSUI CAMINHO INTERNO INVALIDO.')
                pure=PurePosixPath(name)
                if any(part in {'','.','..'} for part in pure.parts):
                    raise ValueError('PATCH POSSUI CAMINHO INTERNO INVALIDO.')
                folded=name.casefold()
                if folded in seen:
                    raise ValueError('PATCH POSSUI CAMINHOS INTERNOS DUPLICADOS.')
                seen.add(folded)
                if member.flag_bits&1:
                    raise ValueError('PATCH CRIPTOGRAFADO NAO E SUPORTADO.')
                # Unix symlink bit in external attributes.
                mode=(member.external_attr>>16)&0xF000
                if mode==0xA000:
                    raise ValueError('PATCH NAO PODE CONTER LINK SIMBOLICO.')
                total+=int(member.file_size or 0)
                if total>MAX_MASTER_PATCH_UNCOMPRESSED_BYTES:
                    raise ValueError('PATCH ULTRAPASSA O LIMITE DE CONTEUDO DESCOMPACTADO.')
                if name=='patch.json' or name.endswith('/patch.json'):
                    manifest_members.append(member)
            if len(manifest_members)!=1:
                raise ValueError('PATCH.JSON NAO FOI ENCONTRADO DE FORMA INEQUIVOCA.')
            if archive.testzip() is not None:
                raise ValueError('ZIP DO PATCH ESTA CORROMPIDO.')
            if manifest_members[0].file_size>2*MIB:
                raise ValueError('PATCH.JSON EXCEDE O LIMITE PERMITIDO.')
            value=json.loads(archive.read(manifest_members[0]).decode('utf-8'))
            if not isinstance(value,dict):
                raise ValueError('PATCH.JSON INVALIDO.')
            if int(value.get('format') or 0)!=6 or value.get('product')!='CJL System' or int(value.get('layout') or 0)!=5:
                raise ValueError('PATCH INCOMPATIVEL. ESPERADO FORMAT 6 / LAYOUT 5.')
            return value
    except zipfile.BadZipFile as exc:
        raise ValueError('ARQUIVO SELECIONADO NAO E UM ZIP VALIDO.') from exc
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise ValueError('PATCH.JSON INVALIDO.') from exc


def _patch_public(path: Path) -> dict:
    manifest=_zip_patch_manifest(path)
    source=manifest.get('source') if isinstance(manifest.get('source'),dict) else {}
    target=manifest.get('target') if isinstance(manifest.get('target'),dict) else {}
    gate=manifest.get('security_gate') if isinstance(manifest.get('security_gate'),dict) else {}
    return {
        'arquivo':path.name,
        'bytes':path.stat().st_size,
        'sha256':_sha256_file(path),
        'patch_id':str(manifest.get('patch_id') or ''),
        'type':str(manifest.get('primary_type') or ''),
        'created_at':str(manifest.get('created_at') or ''),
        'timezone':str(manifest.get('timezone') or ''),
        'source':source,
        'target':target,
        'security_gate':gate,
        'operations':len(manifest.get('operations') or []) if isinstance(manifest.get('operations'),list) else 0,
    }


def master_patch_status() -> dict:
    try:
        root=_assert_direct_master()
    except PermissionError:
        return {'available':False,'direct_master':False,'reason':'STATION'}
    inbox=_master_patch_inbox(root)
    patches=[]
    for path in sorted(inbox.glob('*.zip'),key=lambda item:item.stat().st_mtime,reverse=True):
        try:
            patches.append({**_patch_public(path),'valid_manifest':True})
        except Exception as exc:
            patches.append({'arquivo':path.name,'bytes':path.stat().st_size,'sha256':_sha256_file(path),'valid_manifest':False,'error':str(exc)})
    from Core.release import release_state
    current=release_state(root)
    from Core.sm_repo import ensure_structure
    sm_repo=ensure_structure(root)
    return {
        'available':True,
        'direct_master':True,
        'current':{
            'version':current['version'],'patches':current['patches'],'build':current['build'],
            'compat_sequence':current['compat_sequence'],'layout':current['layout'],
        },
        'inbox':str(inbox),
        'sm_repo':str(sm_repo['root']),
        'patches':patches,
        'count':len(patches),
    }


def import_master_patch(stream, size: int, filename: str) -> dict:
    root=_assert_direct_master()
    if size<=0 or size>MAX_MASTER_PATCH_BYTES:
        raise ValueError('TAMANHO DO PATCH INVALIDO OU ACIMA DE 512 MB.')
    name=_safe_patch_filename(filename)
    inbox=_master_patch_inbox(root)
    existing=[path for path in inbox.glob('*.zip') if path.name.casefold()!=name.casefold()]
    if existing:
        raise ValueError('JA EXISTE OUTRO PATCH EM Updates/In. REMOVA OU APLIQUE O PATCH ATUAL ANTES DE IMPORTAR OUTRO.')
    temporary=inbox/(f'.{name}.{os.getpid()}.{uuid.uuid4().hex}.upload')
    destination=inbox/name
    received=0
    digest=hashlib.sha256()
    try:
        with temporary.open('xb') as target:
            while received<size:
                block=stream.read(min(1024*1024,size-received))
                if not block:
                    raise ValueError('UPLOAD DO PATCH FOI INTERROMPIDO ANTES DO TAMANHO DECLARADO.')
                target.write(block); digest.update(block); received+=len(block)
            target.flush()
            try: os.fsync(target.fileno())
            except OSError: pass
        if received!=size:
            raise ValueError('TAMANHO RECEBIDO DO PATCH DIVERGE DO CONTENT-LENGTH.')
        public=_patch_public(temporary)
        if destination.exists():
            if _sha256_file(destination)==digest.hexdigest():
                temporary.unlink(missing_ok=True)
                public=_patch_public(destination)
                return {'ok':True,'imported':False,'already_present':True,'patch':public}
            raise ValueError('JA EXISTE UM ARQUIVO DE PATCH COM O MESMO NOME E CONTEUDO DIFERENTE.')
        os.replace(temporary,destination)
        log('MASTER_PATCH_IMPORTADO',patch_id=public.get('patch_id'),arquivo=name,sha256=public.get('sha256'))
        return {'ok':True,'imported':True,'patch':_patch_public(destination)}
    finally:
        temporary.unlink(missing_ok=True)


def _selected_master_patch(root: Path, filename: str='') -> Path:
    inbox=_master_patch_inbox(root)
    if filename:
        name=_safe_patch_filename(filename)
        path=inbox/name
        if not path.is_file():
            raise FileNotFoundError('PATCH NAO ENCONTRADO EM Updates/In.')
        return path
    candidates=sorted(inbox.glob('*.zip'))
    if len(candidates)!=1:
        raise ValueError(f'ESPERADO EXATAMENTE 1 PATCH EM Updates/In; ENCONTRADOS {len(candidates)}.')
    return candidates[0]


def _run_patch_validate(root: Path, patch: Path) -> dict:
    python=root/'Runtime'/'Python'/'python.exe'
    engine=root/'Dev'/'Tools'/'apply_patch.py'
    if not python.is_file() or not engine.is_file():
        raise RuntimeError('PATCH ENGINE OU RUNTIME OFICIAL AUSENTE.')
    command=[str(python),'-B','-I','-S',str(engine),'--root',str(root),'--patch',str(patch),'--validate-only']
    creationflags=0
    if os.name=='nt':
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    completed=subprocess.run(command,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=creationflags,timeout=180)
    output=str(completed.stdout or '').strip()
    if completed.returncode:
        raise RuntimeError('VALIDACAO DO PATCH FALHOU: '+output[-4000:])
    start=output.find('{'); end=output.rfind('}')
    if start<0 or end<start:
        raise RuntimeError('PATCH ENGINE NAO RETORNOU RESULTADO DE VALIDACAO ESTRUTURADO.')
    try: result=json.loads(output[start:end+1])
    except json.JSONDecodeError as exc: raise RuntimeError('RESULTADO DE VALIDACAO DO PATCH E INVALIDO.') from exc
    if not result.get('ok'):
        raise RuntimeError('PATCH ENGINE NAO APROVOU O PATCH.')
    return result


def validate_master_patch(filename: str='') -> dict:
    root=_assert_direct_master(); patch=_selected_master_patch(root,filename)
    result=_run_patch_validate(root,patch)
    public=_patch_public(patch)
    log('MASTER_PATCH_VALIDADO',patch_id=public.get('patch_id'),arquivo=patch.name,sha256=public.get('sha256'))
    return {'ok':True,'patch':public,'validation':result}


def remove_master_patch(filename: str='') -> dict:
    root=_assert_direct_master(); patch=_selected_master_patch(root,filename)
    public=_patch_public(patch)
    patch.unlink()
    log('MASTER_PATCH_REMOVIDO_INBOX',patch_id=public.get('patch_id'),arquivo=patch.name,sha256=public.get('sha256'))
    return {'ok':True,'removed':patch.name,'patch_id':public.get('patch_id')}


def prepare_master_patch_apply(filename: str='', *, backend_pid: int | None=None) -> dict:
    root=_assert_direct_master(); patch=_selected_master_patch(root,filename)
    validation=_run_patch_validate(root,patch); public=_patch_public(patch)
    if os.name!='nt':
        raise RuntimeError('APLICACAO AUTOMATICA DO PATCH DO MESTRE EXIGE WINDOWS.')
    worker_source=root/'Updates'/'Apply-Worker.ps1'
    if not worker_source.is_file():
        raise RuntimeError('WORKER EXTERNO DE PATCH AUSENTE.')
    worker_dir=TEMP_DIR/'MasterPatchWorker'
    worker_dir.mkdir(parents=True,exist_ok=True)
    worker=worker_dir/(f'Apply-Worker_{uuid.uuid4().hex}.ps1')
    worker.write_bytes(worker_source.read_bytes())
    host_pid=str(os.environ.get('CJL_HOST_PID') or '').strip()
    args=[
        'powershell.exe','-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',str(worker),
        '-Root',str(root),'-Patch',str(patch),'-WaitPid',str(int(backend_pid or os.getpid())),'-Restart',
    ]
    if host_pid.isdigit() and int(host_pid)>0:
        args.extend(['-WaitHostPid',host_pid])
    flags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'DETACHED_PROCESS',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
    process=subprocess.Popen(args,cwd=str(root.parent),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,creationflags=flags)
    log('MASTER_PATCH_APLICACAO_SOLICITADA',patch_id=public.get('patch_id'),arquivo=patch.name,worker_pid=process.pid)
    return {'ok':True,'restart':True,'patch':public,'validation':validation,'worker_pid':process.pid}
