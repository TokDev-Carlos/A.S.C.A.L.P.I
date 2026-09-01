from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

RULE_RE = re.compile(r"^(R-\d{4})\s*\|\s*(.*)$")

@dataclass(frozen=True)
class Rule:
    rule_id: str
    text: str
    line: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rules_paths(root: Path) -> tuple[Path, Path]:
    base = Path(root) / "Docs" / "Rules"
    return base / "SIS_LOGIS_REGRAS_VOLUME_001.md", base / "SIS_LOGIS_REGRAS_INDICE_MESTRE.md"


def parse_volume(path: Path) -> list[Rule]:
    rules: list[Rule] = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        match = RULE_RE.match(raw)
        if match:
            rules.append(Rule(match.group(1), match.group(2), f"{match.group(1)} | {match.group(2)}"))
    if not rules:
        raise RuntimeError(f"Volume de Regras sem regras: {path}")
    for index, rule in enumerate(rules, start=1):
        expected = f"R-{index:04d}"
        if rule.rule_id != expected:
            raise RuntimeError(f"Sequência de regras inválida: esperado {expected}, encontrado {rule.rule_id}.")
    if len({r.rule_id for r in rules}) != len(rules):
        raise RuntimeError("IDs de regras duplicados.")
    return rules


def logical_sha256(rules: list[Rule]) -> str:
    payload = "".join(rule.line + "\n" for rule in rules).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def metadata(root: Path) -> dict:
    root = Path(root)
    volume, index = rules_paths(root)
    if not volume.is_file() or not index.is_file():
        raise RuntimeError("Regra Mestra/Índice ausente em Docs/Rules.")
    rules = parse_volume(volume)
    return {
        "format": 1,
        "count": len(rules),
        "first_rule": rules[0].rule_id,
        "last_rule": rules[-1].rule_id,
        "volume": volume.relative_to(root).as_posix(),
        "index": index.relative_to(root).as_posix(),
        "volume_sha256": sha256_file(volume),
        "logical_sha256": logical_sha256(rules),
    }


def validate_repository(root: Path, expected: dict | None = None) -> dict:
    root = Path(root)
    info = metadata(root)
    if info["first_rule"] != "R-0001":
        raise RuntimeError("Regra Mestra não começa em R-0001.")
    if expected:
        for key in ("count", "last_rule", "volume_sha256", "logical_sha256"):
            value = expected.get(key)
            if value not in (None, "") and str(info[key]) != str(value):
                raise RuntimeError(f"Contrato de regras diverge em {key}: {info[key]!r} != {value!r}")
    index_text = (root / info["index"]).read_text(encoding="utf-8-sig")
    for marker in (info["last_rule"], str(info["count"]), info["volume_sha256"], info["logical_sha256"]):
        if marker not in index_text:
            raise RuntimeError(f"Índice Mestre não reflete o contrato corrente: {marker}")
    return info


def validate_append_only(base_root: Path, target_root: Path) -> dict:
    base_rules = parse_volume(rules_paths(base_root)[0])
    target_rules = parse_volume(rules_paths(target_root)[0])
    if len(target_rules) < len(base_rules):
        raise RuntimeError("Release candidata reduziu o Volume de Regras.")
    for index, source in enumerate(base_rules):
        target = target_rules[index]
        if source.line != target.line:
            raise RuntimeError(f"Regra histórica reescrita/reordenada em {source.rule_id}.")
    added = target_rules[len(base_rules):]
    return {"source": metadata(base_root), "target": metadata(target_root), "added_rules": [r.rule_id for r in added]}


def _text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def _python_surface(path: Path) -> set[str]:
    text = _text(path)
    try:
        tree = ast.parse(text)
    except Exception:
        return set()
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            out.add(f"SYMBOL:{node.name}")
    for route in re.findall(r'["\'](/api/[A-Za-z0-9_./{}:-]+)["\']', text):
        out.add(f"API:{route}")
    return out


def _html_surface(path: Path) -> set[str]:
    text = _text(path)
    out = {f"ID:{x}" for x in re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', text, flags=re.I)}
    for tag, attrs in re.findall(r'<(input|select|textarea|button|form)\b([^>]*)>', text, flags=re.I):
        m = re.search(r'\bname\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.I)
        if m: out.add(f"FIELD:{tag.lower()}:{m.group(1)}")
    return out


def _js_surface(path: Path) -> set[str]:
    text = _text(path)
    out = {f"FUNCTION:{x}" for x in re.findall(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(', text)}
    out.update(f"FUNCTION:{x}" for x in re.findall(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', text))
    out.update(f"API:{x}" for x in re.findall(r'["\'](/api/[A-Za-z0-9_./${}:-]+)["\']', text))
    return out


def _strip_css_comments(text: str) -> str:
    return re.sub(r'/\*.*?\*/', '', text, flags=re.S)


def _split_css_blocks(text: str):
    i=0; n=len(text)
    while i<n:
        while i<n and text[i].isspace(): i+=1
        if i>=n: break
        start=i
        while i<n and text[i] != '{': i+=1
        if i>=n: break
        head=text[start:i].strip(); i+=1; body_start=i; depth=1
        quote=None; escape=False
        while i<n and depth:
            ch=text[i]
            if quote:
                if escape: escape=False
                elif ch=='\\': escape=True
                elif ch==quote: quote=None
            else:
                if ch in ('"',"'"): quote=ch
                elif ch=='{': depth+=1
                elif ch=='}': depth-=1
            i+=1
        body=text[body_start:i-1] if depth==0 else text[body_start:]
        yield head, body


def _parse_declarations(body: str) -> dict[str,str]:
    out={}
    # Rule bodies considered here contain declarations, not nested rules.
    for part in body.split(';'):
        if ':' not in part: continue
        prop,val=part.split(':',1)
        prop=prop.strip().casefold(); val=' '.join(val.strip().split())
        if prop and val: out[prop]=val
    return out


def _css_surface(path: Path) -> dict[str,dict[str,str]]:
    result={}
    def walk(text:str, context:str=''):
        for head,body in _split_css_blocks(text):
            h=' '.join(head.split())
            if not h: continue
            if h.startswith('@'):
                if h.lower().startswith(('@media','@supports','@layer','@container')):
                    walk(body, context + h + ' || ')
                # @font-face/@keyframes are intentionally not used as protected selectors here.
                continue
            decls=_parse_declarations(body)
            for selector in h.split(','):
                s=' '.join(selector.split())
                if not s: continue
                key=context+s
                merged=result.setdefault(key,{})
                merged.update(decls)  # later occurrence is effective
    walk(_strip_css_comments(_text(path)))
    return result


def _json_flat(value, prefix='$') -> dict[str,object]:
    out={}
    if isinstance(value,dict):
        for key,item in value.items():
            path=f'{prefix}.{key}'
            out[path]='__OBJECT__' if isinstance(item,dict) else ('__LIST__' if isinstance(item,list) else item)
            out.update(_json_flat(item,path))
    elif isinstance(value,list):
        # Preserve member semantics without making order changes look like key removal.
        scalars=[x for x in value if not isinstance(x,(dict,list))]
        if len(scalars)==len(value): out[prefix+'[]']=sorted(map(lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True),scalars))
    return out


def semantic_changes(base_file: Path, target_file: Path) -> list[str]:
    base_file=Path(base_file); target_file=Path(target_file)
    suffix=base_file.suffix.casefold()
    if suffix=='.py':
        a,b=_python_surface(base_file),_python_surface(target_file)
        return [f"PY_REMOVED:{x}" for x in sorted(a-b)]
    if suffix in {'.html','.htm'}:
        a,b=_html_surface(base_file),_html_surface(target_file)
        return [f"HTML_REMOVED:{x}" for x in sorted(a-b)]
    if suffix=='.js':
        a,b=_js_surface(base_file),_js_surface(target_file)
        return [f"JS_REMOVED:{x}" for x in sorted(a-b)]
    if suffix=='.css':
        a,b=_css_surface(base_file),_css_surface(target_file); out=[]
        for selector in sorted(a):
            if selector not in b:
                out.append(f"CSS_SELECTOR_REMOVED:{selector}"); continue
            for prop,val in sorted(a[selector].items()):
                if prop not in b[selector]: out.append(f"CSS_PROPERTY_REMOVED:{selector}:{prop}")
                elif b[selector][prop] != val: out.append(f"CSS_PROPERTY_CHANGED:{selector}:{prop}:{val}=>{b[selector][prop]}")
        return out
    if suffix=='.json':
        try: a=_json_flat(json.loads(_text(base_file))); b=_json_flat(json.loads(_text(target_file)))
        except Exception: return []
        out=[]
        for key,val in a.items():
            if key not in b: out.append(f"JSON_KEY_REMOVED:{key}")
            elif b[key] != val: out.append(f"JSON_VALUE_CHANGED:{key}:{json.dumps(val,ensure_ascii=False,sort_keys=True)}=>{json.dumps(b[key],ensure_ascii=False,sort_keys=True)}")
        return out
    return []


def audit_release_pair(base_root: Path, target_root: Path, *, files: list[str] | None = None) -> dict:
    base_root=Path(base_root); target_root=Path(target_root)
    rules = validate_append_only(base_root, target_root)
    findings=[]
    for rel in files or []:
        a=base_root/rel; b=target_root/rel
        if a.is_file() and b.is_file():
            items=semantic_changes(a,b)
            if items: findings.append({"path":rel,"classification":"SEMANTIC_CHANGE","items":items})
        elif a.is_file() and not b.exists():
            findings.append({"path":rel,"classification":"FILE_REMOVAL","items":[rel]})
    return {"ok": not findings, "rules": rules, "findings": findings}
