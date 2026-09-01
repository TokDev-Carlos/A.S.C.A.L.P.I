from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path


def _add_runtime_site_packages(root: Path) -> None:
    site_packages = root / "Runtime" / "Python" / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise RuntimeError(f"Runtime site-packages ausente: {site_packages}")
    value = str(site_packages)
    if value not in sys.path:
        sys.path.insert(0, value)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def host_source_hash(root: Path) -> str:
    source = root / "Dev" / "Host"
    rows: list[bytes] = []
    for path in sorted(source.rglob("*"), key=lambda p: p.relative_to(source).as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(source).as_posix()
        parts = rel.split("/")
        if any(p.casefold() in {"bin", "obj"} for p in parts):
            continue
        if path.name.casefold().startswith("host-build") or "Bin.Novo." in rel or "Bin.Anterior." in rel:
            continue
        rows.append((rel + "\n" + sha256(path) + "\n").encode("utf-8"))
    h = hashlib.sha256()
    for row in rows:
        h.update(row)
    return h.hexdigest()


def validate_python_sources(root: Path) -> dict:
    checked = 0
    roots = [root / "App", root / "Host" / "Bridge", root / "Dev" / "Tools"]
    errors: list[str] = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in {p.casefold() for p in path.parts}:
                continue
            try:
                compile(path.read_text(encoding="utf-8-sig"), str(path), "exec", dont_inherit=True)
                checked += 1
            except Exception as exc:
                errors.append(f"{path.relative_to(root).as_posix()}: {exc}")
    if errors:
        raise RuntimeError("FALHA DE SINTAXE PYTHON: " + " | ".join(errors[:8]))
    return {"checked": checked, "ok": True}


def validate_active_secret_policy(root: Path) -> dict:
    roots = [root / "App", root / "Host" / "Bridge", root / "Dev" / "Host", root / "Dev" / "Tools"]
    suffixes = {".py", ".ps1", ".cs", ".cmd", ".json"}
    forbidden = [
        re.compile(r"\bMASTER_ADMIN_PIN\s*=\s*[\"']", re.I),
        re.compile(r"\bMASTER_(?:PASSWORD|PIN)\s*=\s*[\"']", re.I),
        re.compile(r"\bADMIN_(?:PASSWORD|PIN)\s*=\s*[\"']\d{4,}[\"']", re.I),
        re.compile(r"senha\s*(?:mestre|master)\s*=\s*[\"'][^\"']+[\"']", re.I),
    ]
    checked = 0
    hits: list[str] = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink() or path.suffix.casefold() not in suffixes:
                continue
            if any(part.casefold() in {"vendor", "bin", "obj", "__pycache__"} for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError):
                continue
            checked += 1
            for pattern in forbidden:
                if pattern.search(text):
                    hits.append(path.relative_to(root).as_posix() + ":" + pattern.pattern)
    if hits:
        raise RuntimeError("SEGREDO/CREDENCIAL HARDCODED EM FONTE ATIVA: " + " | ".join(hits[:8]))
    return {"checked": checked, "ok": True, "hardcoded_admin_secret": False}


def validate_launcher_binding(root: Path, config: dict) -> dict:
    manifest=read_json(root/"Host"/"launcher-build.json")
    if int(manifest.get("format") or 0)!=2 or manifest.get("product")!="CJL System": raise RuntimeError("Host/launcher-build.json ausente ou invalido.")
    binary=root/str(manifest.get("binary") or "")
    if not binary.is_file(): raise RuntimeError("Launcher CJL.exe ausente.")
    if sha256(binary)!=str(manifest.get("binary_sha256") or "").casefold(): raise RuntimeError("CJL.exe divergiu do binding SHA-256.")
    if str(manifest.get("host_contract") or "")!=str((read_json(root/"App"/"Config"/"host.json")).get("host_contract") or "1"): raise RuntimeError("Launcher pertence a outro Host Contract.")
    return {"ok":True,"binary_sha256":manifest["binary_sha256"],"host_contract":str(manifest.get("host_contract") or "")}


def validate(root: Path) -> dict:
    root=root.resolve(); app=root/"App"; _add_runtime_site_packages(root); sys.path.insert(0,str(app))
    from Core.release import verify_manifest,verify_runtime_integrity,version_key
    from Core.signature import verify_release_signature
    from Core.version import versioning, app_version_full
    from Core.branch import read_branch
    required_dirs=["App","Host","Runtime","Data","Shared","Repo","Updates","Logs","Temp","Docs","Dev","Export"]
    missing=[n for n in required_dirs if not (root/n).is_dir()]
    if missing: raise RuntimeError("DIRETORIOS OBRIGATORIOS AUSENTES: "+", ".join(missing))
    required_files={"COPYRIGHT.txt","LICENSE.txt","CJL.exe","CJL.root.json","CJL.branch.json","VERSION"}
    for name in sorted(required_files):
        if not (root/name).is_file(): raise RuntimeError(f"ARQUIVO OBRIGATORIO AUSENTE: {name}")
    allowed_dirs=set(required_dirs); allowed_files=set(required_files)
    unknown=[]
    for entry in root.iterdir():
        if entry.is_dir() and entry.name not in allowed_dirs: unknown.append(entry.name+"/")
        elif entry.is_file() and entry.name not in allowed_files: unknown.append(entry.name)
    if unknown: raise RuntimeError("RAIZ CJL SYSTEM POSSUI ITEM NAO DECLARADO: "+", ".join(sorted(unknown,key=str.casefold)))
    layout=read_json(app/"Config"/"layout.json")
    expected={"format":5,"product":"CJL System","app":"App","host":"Host","runtime":"Runtime","seed_database":"Data/sistema.db","shared_data":"Shared","repository":"Repo","updates":"Updates","logs":"Logs","temp":"Temp","docs":"Docs","dev":"Dev","export":"Export"}
    for key,value in expected.items():
        if layout.get(key)!=value: raise RuntimeError(f"LAYOUT 5 INVALIDO: {key}={layout.get(key)!r}; esperado {value!r}")
    sm=layout.get("sm_repo") if isinstance(layout.get("sm_repo"),dict) else {}
    if sm.get("mode")!="SIBLING_OF_SYSTEM" or sm.get("folder")!="SM_Repo": raise RuntimeError("LAYOUT 5 NAO DECLARA O SM_REPO OFICIAL.")
    config=read_json(app/"Config"/"sistema.json"); ids=versioning(); branch=read_branch(root)
    branch_name=str(branch.get("branch") or "").upper(); is_dev=branch_name=="DEV"
    if str(config.get("version_full") or "")!=app_version_full(): raise RuntimeError("VERSION_FULL DIVERGE DA IDENTIDADE BA/ES/IN/SE.")
    if int(config.get("layout_version") or 0)!=5 or int(ids.get("business") or 0)<1: raise RuntimeError("sistema.json nao declara Base 5/BA valida.")
    if version_key(str(config.get("version") or ""))!=(int(ids["structural"]),int(ids["incremental"]),int(ids["security"])): raise RuntimeError("Version nao corresponde a ES/IN/SE.")
    from Core.updates import read_state
    state=read_state(root)
    if state["business_id"]!=ids["business_id"] or state["compat_sequence"]!=int(ids["compat_sequence"]): raise RuntimeError("Updates/State diverge da identidade Base 5.")
    root_marker=read_json(root/"CJL.root.json")
    if int(root_marker.get("root_contract") or 0)!=5 or root_marker.get("product")!="CJL System" or root_marker.get("business_id")!=ids["business_id"] or root_marker.get("version")!=config.get("version"): raise RuntimeError("CJL.root.json diverge da identidade atual.")
    if branch_name=="MAIN" and str(root_marker.get("role") or "MASTER").upper() not in {"MASTER","PRODUCTION"}: raise RuntimeError("CJL.root.json MAIN com role invalida.")
    if branch_name=="DEV" and str(root_marker.get("role") or "").upper()!="DEVELOPMENT": raise RuntimeError("CJL.root.json DEV deve declarar role DEVELOPMENT.")
    old_keys=[app/"Config"/"release_public_key.json",app/"Config"/"release_delivery_public_key.json"]
    if any(x.exists() for x in old_keys): raise RuntimeError("CHAVES PUBLICAS DA LINHAGEM ANTERIOR NAO PODEM FICAR NA CAMADA ATIVA BASE 5.")
    host_config=read_json(app/"Config"/"host.json")
    if "legacy" in host_config or int(host_config.get("host_contract") or 0)!=1 or int(host_config.get("update_contract") or 0)!=1 or int(host_config.get("remote_contract") or 0)!=1: raise RuntimeError("host.json nao corresponde ao contrato Base 5.")
    manifest=verify_manifest(root,exact_file_set=True); runtime=verify_runtime_integrity(root,exact_file_set=True,quick=False); lineage=verify_release_signature(root)
    if lineage.get("current_release_signed") is not False or lineage.get("trust_mode")!="SHA256_MIGRATION_CHECKPOINT": raise RuntimeError("PROVENIENCIA BASE 5 DEVE SER CHECKPOINT SHA-256 NAO ASSINADO.")
    if not is_dev:
        db=root/"Data"/"sistema.db"
        if not db.is_file(): raise RuntimeError("Banco Data/sistema.db ausente.")
        wal=db.with_name(db.name+"-wal"); journal=db.with_name(db.name+"-journal")
        if (wal.is_file() and wal.stat().st_size>0) or (journal.is_file() and journal.stat().st_size>0): raise RuntimeError("BANCO SQLITE POSSUI WAL/JOURNAL NAO VAZIO DURANTE VALIDACAO.")
        uri=db.as_uri()+"?mode=ro&immutable=1"
        with sqlite3.connect(uri,uri=True,timeout=15) as conn:
            integrity=str(conn.execute("PRAGMA integrity_check").fetchone()[0]); admin=conn.execute("SELECT nome,perfil,senha_hash,senha_salt,ativo FROM usuarios WHERE nome='ADMIN' COLLATE NOCASE LIMIT 1").fetchone()
        if integrity.casefold()!="ok": raise RuntimeError("PRAGMA integrity_check falhou: "+integrity)
        if not admin or str(admin[1]).upper()!="ADMIN" or not int(admin[4]) or not admin[2] or not admin[3]: raise RuntimeError("ADMIN principal precisa permanecer ativo e com hash/salt configurado.")
        if not (root/"Repo"/"HEAD.json").is_file(): raise RuntimeError("Repo/HEAD.json ausente.")
        from Core.repository import _validate_head_chain
        repo_head=read_json(root/"Repo"/"HEAD.json")
        repo_transaction_sha256=_validate_head_chain(repo_head,{})
        anchor=read_json(app/"Config"/"repository.anchor.json")
        anchor_revision=int(anchor.get("revision") or 0); head_revision=int(repo_head.get("revision") or 0)
        if int(anchor.get("format") or 0)!=2 or anchor.get("product")!="CJL System" or anchor_revision<=0 or anchor_revision>head_revision: raise RuntimeError("Anchor CJL do Repo invalido.")
    else:
        integrity="DEV_TECHNICAL_ONLY"; repo_head={"revision":0}; repo_transaction_sha256="DEV_TECHNICAL_ONLY"
        for protected_name in ("Data","Shared","Repo"):
            protected_path=root/protected_name
            if protected_path.is_symlink(): raise RuntimeError(f"BRANCH DEV NAO PODE APONTAR {protected_name} POR LINK/JUNCTION PARA OUTRA RAIZ.")
        # O laboratório nasce sem dados de produção. Dados de teste futuros ficam isolados nesta raiz.
        if (root/"Data"/"PRODUCTION_DATA_IMPORTED.flag").exists(): raise RuntimeError("BRANCH DEV MARCADA COM DADOS DE PRODUCAO IMPORTADOS.")
    host_manifest=read_json(root/"Host"/"Bin"/"host-build.json")
    if int(host_manifest.get("format") or 0)!=5 or host_manifest.get("product")!="CJL System" or host_manifest.get("architecture")!="win-x64" or host_manifest.get("self_contained") is not True: raise RuntimeError("Manifesto Host Base 5 invalido.")
    declared_source=str(host_manifest.get("source_tree_sha256") or "").casefold(); actual_source=host_source_hash(root)
    if declared_source!=actual_source: raise RuntimeError("Host/Bin nao corresponde a arvore Dev/Host atual.")
    expected_bins={"CJL.Bootstrap.exe","CJL.Setup.exe","CJL.Host.exe","CJL.Updater.exe","CJL.Uninstall.exe"}
    files=host_manifest.get("files")
    if not isinstance(files,dict) or set(files)!=expected_bins: raise RuntimeError("Conjunto declarado do Host Base 5 diverge do contrato.")
    for name,digest in files.items():
        p=root/"Host"/"Bin"/name
        if not p.is_file() or sha256(p)!=str(digest).casefold(): raise RuntimeError("Binario Host ausente/alterado: "+name)
    residues=[p.name for p in (root/"Host").iterdir() if p.name.startswith("Bin.Novo.") or p.name.startswith("Bin.Anterior.")]
    if residues: raise RuntimeError("RESIDUOS DE BUILD HOST PRESENTES: "+", ".join(residues))
    for required in (root/"Dev"/"Tools"/"snapshot_export.py",root/"Dev"/"Tools"/"create_patch.py",root/"Dev"/"Tools"/"apply_patch.py",root/"Updates"/"Apply-Master.ps1",root/"Updates"/"Apply-Worker.ps1",root/"App"/"Core"/"sm_repo.py"):
        if not required.is_file(): raise RuntimeError("Ferramenta Base 5 ausente: "+str(required.relative_to(root)))
    forbidden=[root/"Updates"/"Legacy",root/"Updates"/"Lineage",root/"Updates"/"History"]
    if any(p.exists() for p in forbidden): raise RuntimeError("HISTORICO/LINEAGE NAO PODE FICAR NO CAMINHO OPERACIONAL BASE 5.")
    expected_projects={"CJL.Shared","CJL.Bootstrap","CJL.Host","CJL.Setup","CJL.Updater","CJL.Uninstall","CJL.Launcher"}
    source_projects={p.name for p in (root/"Dev"/"Host"/"src").iterdir() if p.is_dir()}
    if source_projects!=expected_projects: raise RuntimeError("CONJUNTO DE PROJETOS HOST DIVERGE DO CONTRATO BASE 5: "+", ".join(sorted(source_projects)))
    pycache=[]
    for base in (root/"App",root/"Dev"):
        if base.is_dir(): pycache.extend(p for p in base.rglob("*") if p.is_dir() and p.name=="__pycache__"); pycache.extend(p for p in base.rglob("*.pyc") if p.is_file())
    if pycache: raise RuntimeError("ARTEFATOS PYTHON NAO DEVEM SER PUBLICADOS: "+", ".join(str(p.relative_to(root)) for p in pycache[:8]))
    launcher=validate_launcher_binding(root,config); secret=validate_active_secret_policy(root); python_sources=validate_python_sources(root)
    from Core.cumulativity import validate_repository as validate_rules
    rules=validate_rules(root, config.get("rules_contract") if isinstance(config.get("rules_contract"),dict) else None)
    from Core.data_policy import read_policy as validate_data_policy, schema_contract
    data_policy=validate_data_policy(root); schema_info=schema_contract(root)
    return {"ok":True,"root":str(root),"product":"CJL System","branch":branch_name,"validation_profile":"DEV_TECHNICAL" if is_dev else "MAIN_PRODUCTION","business":ids["business_id"],"version":config.get("version"),"version_full":config.get("version_full"),"structural":ids["structural_id"],"incremental":ids["incremental_id"],"security":ids["security_id"],"compat_sequence":int(ids["compat_sequence"]),"build":int(config.get("build") or 0),"layout":5,"app_files":len(manifest.get("files") or {}),"runtime_declared_files":len(runtime.get("files") or {}),"database_integrity":integrity,"repo_revision":int(repo_head.get("revision") or 0),"repo_transaction_sha256":repo_transaction_sha256,"host_source_tree_sha256":actual_source,"host_binaries":len(files),"launcher":launcher,"provenance":lineage,"security_policy":secret,"python_sources":python_sources,"rules":rules,"data_policy":data_policy.get("policy_id"),"schema_contract":schema_info}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    result = validate(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        raise SystemExit(1)
