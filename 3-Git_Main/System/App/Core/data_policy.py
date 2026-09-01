from __future__ import annotations
import ast,hashlib,json
from pathlib import Path

def _sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def read_policy(root:Path)->dict:
    path=Path(root)/"App"/"Config"/"data.policy.json";value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict) or int(value.get("format") or 0)!=1 or value.get("product")!="CJL System" or value.get("policy_id")!="CJL_DATA_POLICY_V1":raise RuntimeError("POLÍTICA DE DADOS CJL AUSENTE/INVÁLIDA.")
    return value

def schema_contract(root:Path)->dict:
    root=Path(root);source=root/"App"/"Core"/"db.py";tree=ast.parse(source.read_text(encoding="utf-8"));schema=None
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SCHEMA" for t in node.targets):
            try:schema=ast.literal_eval(node.value)
            except Exception:schema=None
            break
    if not isinstance(schema,str) or not schema.strip():raise RuntimeError("CONTRATO SCHEMA NÃO LOCALIZADO EM App/Core/db.py.")
    cfg=json.loads((root/"App"/"Config"/"sistema.json").read_text(encoding="utf-8"))
    normalized="\n".join(line.rstrip() for line in schema.replace("\r\n","\n").split("\n")).strip()+"\n"
    return {"schema_version":int(cfg.get("schema_version") or 0),"schema_sha256":_sha_bytes(normalized.encode("utf-8")),"authority":"App/Core/db.py::SCHEMA","database_rows_included":False}

def snapshot_policy_metadata(root:Path)->dict:
    policy=read_policy(root);return {"policy_id":policy["policy_id"],"system_data_included":True,"operational_user_data_included":False,"system_technical_logs_included":True,"database_rows_included":False,"schema":schema_contract(root),"excluded_roots":policy["operational_user_data"]["roots"]+policy["generated_or_heavy_system_components"]["roots"],"included_technical_logs":policy["logs"]["snapshot_include"]}
