from __future__ import annotations
import json
from pathlib import Path

APP_DIR=Path(__file__).resolve().parents[1]
PROJECT_ROOT=APP_DIR.parent


def verify_release_signature(root: Path=PROJECT_ROOT)->dict:
    root=Path(root).resolve()
    if root.name.casefold()=="app": root=root.parent
    path=root/"App"/"Config"/"provenance.json"
    try: prov=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: raise RuntimeError("PROVENIENCIA BASE 5 AUSENTE OU INVALIDA.") from exc
    required={"format":1,"product":"CJL System","product_code":"CJL","business_id":"BA-01","migration":"ES-05"}
    for key,value in required.items():
        if prov.get(key)!=value: raise RuntimeError(f"PROVENIENCIA BASE 5 DIVERGE EM {key}.")
    if str(prov.get("master_id") or "").upper()!=(root/"App"/"Config"/"master.id").read_text(encoding="utf-8").strip().upper():
        raise RuntimeError("PROVENIENCIA BASE 5 DIVERGE DO MASTER.ID.")
    cfg=json.loads((root/"App"/"Config"/"sistema.json").read_text(encoding="utf-8"))
    current_core=str(cfg.get("version") or ""); current_full=str(cfg.get("version_full") or "")
    declared_core=str(prov.get("current_version") or prov.get("version") or "")
    declared_full=str(prov.get("current_version_full") or ("1.05.00.005" if declared_core=="5.00.005" else ""))
    if declared_core!=current_core or declared_full!=current_full:
        raise RuntimeError("PROVENIENCIA CORRENTE DIVERGE DA RELEASE ATIVA.")
    return {"ok":True,"scope":"CJL_BASE5_MIGRATION_CHECKPOINT","current_release_signed":False,"trust_mode":str(prov.get("trust_mode") or "SHA256_MIGRATION_CHECKPOINT"),"historical_evidence_archived":bool(prov.get("historical_evidence_archived")),"checkpoint_version":str(prov.get("version") or ""),"current_version":current_core,"current_version_full":current_full,"note":"A proveniencia preserva o checkpoint Base 5 e declara separadamente a release corrente."}
