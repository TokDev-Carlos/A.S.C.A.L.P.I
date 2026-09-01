from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from Core.atomic import atomic_write_bytes, atomic_write_json
from Core.config import (
    ensure_local_layout,
    local_database_path,
    local_state_root,
    network_root,
    repository_root,
    seed_database_path,
    station_id,
)
from Core.context import current_identity
from Core.filetx import begin as begin_file_transaction
from Core.filetx import reset as reset_file_transaction
from Core.storage import ensure_disk_space


REPOSITORY_FORMAT = 2
LOCK_TIMEOUT_SECONDS = float(os.environ.get("CJL_LOCK_TIMEOUT", "25"))
STALE_LOCK_SECONDS = max(300.0, float(os.environ.get("CJL_STALE_LOCK", "900")))
_PROCESS_LOCK = threading.RLock()


class RepositoryOfflineError(RuntimeError):
    pass


class RepositoryConflictError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _read_required_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{label} AUSENTE OU INVÁLIDO: {path.name}.") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} INVÁLIDO: {path.name}.")
    return value


def _sync_file() -> Path:
    return local_state_root() / "sync.json"


def _pending_local_write_file() -> Path:
    return local_state_root() / "Temp" / "pending_write.json"


def _local_sync() -> dict:
    return _read_json(_sync_file())


def _head_file() -> Path:
    return repository_root() / "HEAD.json"


def _revision_file(revision: int) -> Path:
    return repository_root() / "Revisoes" / f"{revision:09d}.sqlite.gz"


def _transaction_file(revision: int) -> Path:
    return repository_root() / "Transacoes" / f"{revision:09d}.json"


def _lock_file() -> Path:
    return repository_root() / "Bloqueios" / "ESCRITA_GLOBAL.lock"


def _file_journal_dir() -> Path:
    return repository_root() / "Pendentes"


def _file_journals_exist() -> bool:
    try:
        return any(_file_journal_dir().glob("*.json"))
    except OSError:
        return False


def _journal_member(relative: str) -> Path | None:
    value = str(relative or "").strip().replace("\\", "/")
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RepositoryConflictError("CAMINHO INVÁLIDO EM DIÁRIO DE ARQUIVOS.")
    root = network_root().resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RepositoryConflictError("DIÁRIO DE ARQUIVOS ESCAPA DO MESTRE.") from exc
    return resolved


def _recover_file_journals_locked() -> None:
    directory = _file_journal_dir()
    if not directory.is_dir():
        return
    head = _read_required_json(_head_file(), "HEAD OFICIAL") if _head_file().is_file() else {}
    head_revision = int(head.get("revision") or 0)
    head_operation = str(head.get("operation_id") or "")
    for journal_path in sorted(directory.glob("*.json")):
        journal = _read_required_json(journal_path, "DIÁRIO DE ARQUIVOS")
        if int(journal.get("format") or 0) != 1:
            raise RepositoryConflictError(f"FORMATO DE DIÁRIO INVÁLIDO: {journal_path.name}.")
        operation_id = str(journal.get("operation_id") or "")
        base_revision = int(journal.get("base_revision") or -1)
        target_revision = int(journal.get("target_revision") or -1)
        operations = journal.get("operations")
        if (
            len(operation_id) != 32
            or target_revision != base_revision + 1
            or not isinstance(operations, list)
        ):
            raise RepositoryConflictError(f"DIÁRIO DE ARQUIVOS INCOMPLETO: {journal_path.name}.")
        published = head_revision == target_revision and head_operation == operation_id
        if not published and head_revision != base_revision:
            raise RepositoryConflictError(
                f"NÃO É SEGURO RECUPERAR {journal_path.name}: O HEAD NÃO CORRESPONDE À OPERAÇÃO."
            )
        errors: list[str] = []
        if published:
            # O banco já referencia o estado novo. Restam apenas resíduos de
            # staging/rollback que podem ser eliminados idempotentemente.
            for entry in operations:
                try:
                    staged = _journal_member(entry.get("staged", ""))
                    backup = _journal_member(entry.get("backup", ""))
                    if staged and staged.is_file():
                        staged.unlink()
                    if backup and backup.is_file():
                        backup.unlink()
                except (OSError, AttributeError, TypeError, ValueError) as exc:
                    errors.append(str(exc))
        else:
            # O HEAD ainda é o anterior: desfaz as trocas externas inferindo o
            # ponto exato da interrupção pelos caminhos e hashes registrados.
            for entry in reversed(operations):
                try:
                    if not isinstance(entry, dict):
                        raise ValueError("OPERAÇÃO DE DIÁRIO INVÁLIDA.")
                    kind = str(entry.get("kind") or "")
                    source = _journal_member(entry.get("source", ""))
                    destination = _journal_member(entry.get("destination", ""))
                    staged = _journal_member(entry.get("staged", ""))
                    backup = _journal_member(entry.get("backup", ""))
                    if destination is None:
                        raise ValueError("DESTINO AUSENTE NO DIÁRIO.")
                    if kind == "replace":
                        if backup and backup.exists():
                            destination.unlink(missing_ok=True)
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(backup, destination)
                        elif not bool(entry.get("original_exists")) and destination.is_file():
                            expected = str(entry.get("staged_sha256") or "")
                            if len(expected) != 64 or _sha256(destination.read_bytes()) != expected:
                                raise RuntimeError(f"DESTINO NOVO DIVERGE DO DIÁRIO: {destination}.")
                            destination.unlink()
                    elif kind in {"move", "directory"}:
                        if source is None:
                            raise ValueError("ORIGEM AUSENTE NO DIÁRIO.")
                        if not source.exists() and destination.exists():
                            source.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(destination, source)
                    elif kind == "mkdir":
                        if not bool(entry.get("original_exists")) and destination.is_dir():
                            destination.rmdir()
                    else:
                        raise ValueError(f"TIPO DE OPERAÇÃO INVÁLIDO: {kind}.")
                    if staged and staged.is_file():
                        staged.unlink()
                except (OSError, AttributeError, TypeError, ValueError, RuntimeError) as exc:
                    errors.append(str(exc))
        if errors:
            raise RepositoryConflictError(
                "A RECUPERAÇÃO AUTOMÁTICA DE ARQUIVOS NÃO FOI CONCLUÍDA: "
                + "; ".join(errors[:3])
            )
        journal_path.unlink()


def _anchor_file() -> Path:
    # O anchor é parte da aplicação assinada e não acompanha fisicamente o Repositório.
    return Path(__file__).resolve().parents[1] / "Config" / "repository.anchor.json"


def _network_available(create: bool = False) -> bool:
    root = repository_root()
    try:
        if create:
            if not root.is_dir() and int(_local_sync().get("revision") or 0) > 0:
                return False
            root.mkdir(parents=True, exist_ok=True)
        return root.is_dir()
    except OSError:
        return False


def _copy_seed_if_needed() -> None:
    ensure_local_layout()
    destination = local_database_path()
    if destination.is_file():
        return
    seed = seed_database_path()
    if not seed.is_file():
        raise RuntimeError("BANCO INICIAL DO CJL System NÃO FOI ENCONTRADO.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".seed.tmp")
    shutil.copy2(seed, temporary)
    os.replace(temporary, destination)


def _checkpoint_database() -> None:
    database = local_database_path()
    if not database.is_file():
        return
    connection = sqlite3.connect(database, timeout=20)
    try:
        connection.execute("PRAGMA busy_timeout=20000")
        result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if result and int(result[0] or 0) > 0:
            raise RuntimeError("O CACHE LOCAL ESTÁ OCUPADO; TENTE NOVAMENTE.")
    finally:
        connection.close()


def _sqlite_copy(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(source_path, timeout=20)
    target = sqlite3.connect(destination_path, timeout=20)
    try:
        target.execute("PRAGMA busy_timeout=20000")
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()


def _database_preimage() -> Path:
    _checkpoint_database()
    fd, name = tempfile.mkstemp(prefix="sistema.preimage-", suffix=".sqlite", dir=local_state_root() / "Temp")
    os.close(fd)
    path = Path(name)
    path.unlink(missing_ok=True)
    _sqlite_copy(local_database_path(), path)
    return path


def _restore_preimage(path: Path) -> None:
    _checkpoint_database()
    _sqlite_copy(path, local_database_path())
    _validate_database(local_database_path())


def _database_snapshot() -> tuple[bytes, str]:
    _checkpoint_database()
    with tempfile.TemporaryDirectory(prefix="cjl-snapshot-", dir=str(local_state_root() / "Temp")) as name:
        copy_path = Path(name) / "sistema.db"
        _sqlite_copy(local_database_path(), copy_path)
        raw = copy_path.read_bytes()
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    return compressed, _sha256(compressed)


def _validate_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError("A REVISÃO COMPARTILHADA NÃO PASSOU NA VALIDAÇÃO DE INTEGRIDADE.")
    finally:
        connection.close()


def _transaction_file_sha256(revision: int) -> str:
    path = _transaction_file(revision)
    try:
        return _sha256(path.read_bytes())
    except OSError as exc:
        raise RuntimeError(f"TRANSAÇÃO OFICIAL {revision} AUSENTE.") from exc


def _validate_anchor(head_revision: int) -> tuple[int, str]:
    anchor = _read_required_json(_anchor_file(), "ÂNCORA DO REPOSITÓRIO")
    revision = int(anchor.get("revision") or 0)
    transaction_digest = str(anchor.get("transaction_file_sha256") or "").lower()
    snapshot_digest = str(anchor.get("snapshot_sha256") or "").lower()
    if revision <= 0 or len(transaction_digest) != 64 or len(snapshot_digest) != 64:
        raise RuntimeError("ÂNCORA DO REPOSITÓRIO ESTÁ INCOMPLETA.")
    if head_revision < revision:
        raise RepositoryConflictError("O HEAD OFICIAL FOI REBAIXADO PARA UMA REVISÃO ANTERIOR À ÂNCORA.")
    if _transaction_file_sha256(revision) != transaction_digest:
        raise RepositoryConflictError("A TRANSAÇÃO ÂNCORA DO REPOSITÓRIO FOI ALTERADA.")
    snapshot = _revision_file(revision)
    if not snapshot.is_file() or _sha256(snapshot.read_bytes()) != snapshot_digest:
        raise RepositoryConflictError("O SNAPSHOT ÂNCORA DO REPOSITÓRIO FOI ALTERADO.")
    return revision, transaction_digest


def _validate_transaction(revision: int, expected_previous_hash: str = "") -> tuple[dict, str]:
    path = _transaction_file(revision)
    transaction = _read_required_json(path, "TRANSAÇÃO OFICIAL")
    if int(transaction.get("revision") or 0) != revision:
        raise RepositoryConflictError(f"NUMERAÇÃO INVÁLIDA NA TRANSAÇÃO {revision}.")
    file_digest = _sha256(path.read_bytes())
    if int(transaction.get("format") or 1) >= 2:
        declared = str(transaction.get("transaction_sha256") or "").lower()
        content = dict(transaction)
        content.pop("transaction_sha256", None)
        if declared != _sha256(_canonical_json(content)):
            raise RepositoryConflictError(f"CONTEÚDO DA TRANSAÇÃO {revision} FOI ALTERADO.")
        if str(transaction.get("previous_transaction_sha256") or "").lower() != expected_previous_hash.lower():
            raise RepositoryConflictError(f"CADEIA DE TRANSAÇÕES ROMPIDA NA REVISÃO {revision}.")
    return transaction, file_digest


def _validate_head_chain(head: dict, local: dict) -> str:
    revision = int(head.get("revision") or 0)
    if revision <= 0 or int(head.get("format") or 1) not in {1, 2}:
        raise RuntimeError("HEAD OFICIAL AUSENTE OU INVÁLIDO.")
    local_revision = int(local.get("revision") or 0)
    if revision < local_revision:
        raise RepositoryConflictError(
            f"REGRESSÃO BLOQUEADA: A ESTAÇÃO CONHECE A REVISÃO {local_revision}, MAS A REDE OFERECE {revision}."
        )
    if local_revision == revision and local.get("snapshot_sha256") and (
        str(local.get("snapshot_sha256")).lower() != str(head.get("snapshot_sha256") or "").lower()
    ):
        raise RepositoryConflictError("O HEAD FOI REESCRITO SEM AVANÇO DE REVISÃO.")
    anchor_revision, anchor_hash = _validate_anchor(revision)
    start = anchor_revision + 1
    previous_hash = anchor_hash
    if local_revision >= anchor_revision:
        local_hash = str(local.get("transaction_file_sha256") or "").lower()
        if local_hash:
            actual_local = _transaction_file_sha256(local_revision)
            if actual_local != local_hash:
                raise RepositoryConflictError("A TRANSAÇÃO JÁ CONHECIDA PELA ESTAÇÃO FOI ALTERADA.")
            start = local_revision + 1
            previous_hash = local_hash
    current_hash = previous_hash
    if revision == anchor_revision:
        current_hash = anchor_hash
    for number in range(start, revision + 1):
        _transaction, current_hash = _validate_transaction(number, current_hash)
    if int(head.get("format") or 1) >= 2 and str(head.get("transaction_file_sha256") or "").lower() != current_hash:
        raise RepositoryConflictError("O HEAD NÃO CORRESPONDE À ÚLTIMA TRANSAÇÃO OFICIAL.")
    return current_hash


def _pull_head_locked(head: dict | None = None) -> bool:
    if not _head_file().is_file():
        return False
    head = head or _read_required_json(_head_file(), "HEAD OFICIAL")
    revision = int(head.get("revision") or 0)
    local = _local_sync()
    interrupted_local_write = _pending_local_write_file().is_file()
    transaction_hash = _validate_head_chain(head, local)
    if (
        int(local.get("revision") or 0) == revision
        and local_database_path().is_file()
        and not interrupted_local_write
    ):
        return False
    try:
        compressed = _revision_file(revision).read_bytes()
    except OSError as exc:
        raise RepositoryOfflineError("A REVISÃO OFICIAL NÃO ESTÁ ACESSÍVEL NA REDE.") from exc
    expected = str(head.get("snapshot_sha256") or "").lower()
    if len(expected) != 64 or _sha256(compressed) != expected:
        raise RuntimeError("HASH DA REVISÃO OFICIAL INVÁLIDO.")
    try:
        raw = gzip.decompress(compressed)
    except OSError as exc:
        raise RuntimeError("REVISÃO OFICIAL COMPACTADA INVÁLIDA.") from exc
    destination = local_database_path()
    fd, name = tempfile.mkstemp(prefix="sistema.", suffix=".pull.tmp", dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_bytes(raw)
        _validate_database(temporary)
        _sqlite_copy(temporary, destination)
        _validate_database(destination)
    finally:
        temporary.unlink(missing_ok=True)
    atomic_write_json(_sync_file(), {
        "revision": revision,
        "snapshot_sha256": expected,
        "transaction_file_sha256": transaction_hash,
        "synced_at": _now(),
        "station_id": station_id(),
    })
    if interrupted_local_write:
        _pending_local_write_file().unlink(missing_ok=True)
    return True


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _reclaim_stale_lock(lock: Path) -> bool:
    try:
        original = lock.read_bytes()
        age = max(0.0, time.time() - lock.stat().st_mtime)
    except OSError:
        return False
    owner = _read_json(lock)
    same_station = str(owner.get("station_id") or "") == station_id()
    dead_local_process = same_station and not _pid_alive(int(owner.get("pid") or 0))
    if not dead_local_process and age < STALE_LOCK_SECONDS:
        return False
    try:
        if lock.read_bytes() != original:
            return False
        quarantine = repository_root() / "Quarentena" / "Bloqueios"
        quarantine.mkdir(parents=True, exist_ok=True)
        os.replace(lock, quarantine / f"lock-{int(time.time())}-{uuid.uuid4().hex[:8]}.json")
        return True
    except OSError:
        return False


@contextmanager
def _exclusive_network_lock(action: str):
    if not _network_available(create=True):
        raise RepositoryOfflineError("A PASTA OFICIAL DE REDE ESTÁ INDISPONÍVEL.")
    lock = _lock_file()
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    nonce = uuid.uuid4().hex
    payload = json.dumps({
        "format": 1,
        "nonce": nonce,
        "station_id": station_id(),
        "pid": os.getpid(),
        "action": action,
        "started_at": _now(),
        "started_epoch": time.time(),
    }, ensure_ascii=False, indent=2).encode("utf-8")
    while descriptor is None:
        try:
            descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            if _reclaim_stale_lock(lock):
                continue
            if time.monotonic() >= deadline:
                owner = _read_json(lock)
                label = owner.get("station_id") or "OUTRA ESTAÇÃO"
                raise RepositoryConflictError(f"A ESCRITA OFICIAL ESTÁ EM USO POR {label}. TENTE NOVAMENTE.")
            time.sleep(0.12)
        except OSError as exc:
            raise RepositoryOfflineError("NÃO FOI POSSÍVEL CRIAR O BLOQUEIO EXCLUSIVO NA REDE.") from exc
    heartbeat_stop = threading.Event()

    def heartbeat() -> None:
        while not heartbeat_stop.wait(30):
            try:
                if _read_json(lock).get("nonce") != nonce:
                    return
                os.utime(lock, None)
            except OSError:
                return

    heartbeat_thread: threading.Thread | None = None
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        heartbeat_thread = threading.Thread(
            target=heartbeat,
            name="CJLLockHeartbeat",
            daemon=True,
        )
        heartbeat_thread.start()
        yield
    finally:
        heartbeat_stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        if descriptor is not None:
            os.close(descriptor)
        try:
            if _read_json(lock).get("nonce") == nonce:
                lock.unlink()
        except OSError:
            pass


def _quarantine_orphan(revision: int) -> None:
    existing = [path for path in (_revision_file(revision), _transaction_file(revision)) if path.exists()]
    if not existing:
        return
    quarantine = repository_root() / "Quarentena" / f"Revisao-{revision:09d}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    quarantine.mkdir(parents=True, exist_ok=False)
    for path in existing:
        os.replace(path, quarantine / path.name)


def _prune_revision_snapshots(current: int) -> None:
    keep_recent = max(100, int(os.environ.get("CJL_REVISION_SNAPSHOTS", "500")))
    cutoff = max(1, current - keep_recent + 1)
    anchor_revision = int(_read_json(_anchor_file()).get("revision") or 0)
    for path in (repository_root() / "Revisoes").glob("*.sqlite.gz"):
        try:
            revision = int(path.name.split(".", 1)[0])
        except ValueError:
            continue
        if revision >= cutoff or revision == anchor_revision or revision % 100 == 0:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def _publish_locked(
    action: str,
    *,
    app_version: str,
    schema_version: int,
    operation_id: str = "",
) -> dict:
    head = _read_required_json(_head_file(), "HEAD OFICIAL") if _head_file().is_file() else {}
    previous = int(head.get("revision") or 0)
    local = _local_sync()
    if previous:
        _validate_head_chain(head, local)
    if previous and int(local.get("revision") or 0) != previous:
        raise RepositoryConflictError(
            f"A ESTAÇÃO ESTÁ NA REVISÃO {int(local.get('revision') or 0)} E A REDE NA {previous}. ATUALIZE E REPITA."
        )
    revision = previous + 1
    _quarantine_orphan(revision)
    compressed, digest = _database_snapshot()
    ensure_disk_space(_revision_file(revision), len(compressed), label="NOVA REVISÃO OFICIAL")
    atomic_write_bytes(_revision_file(revision), compressed)
    identity = current_identity()
    transaction = {
        "format": REPOSITORY_FORMAT,
        "revision": revision,
        "previous_revision": previous,
        "previous_transaction_sha256": _transaction_file_sha256(previous) if previous else "",
        "action": action,
        "snapshot_sha256": digest,
        "app_version": app_version,
        "schema_version": int(schema_version),
        "user_id": identity.user_id,
        "user_name": identity.user_name,
        "station_id": identity.station_id or station_id(),
        "published_at": _now(),
        "operation_id": operation_id,
    }
    transaction["transaction_sha256"] = _sha256(_canonical_json(transaction))
    atomic_write_json(_transaction_file(revision), transaction)
    transaction_file_hash = _transaction_file_sha256(revision)
    head_payload = {
        "format": REPOSITORY_FORMAT,
        "revision": revision,
        "snapshot_sha256": digest,
        "transaction_file_sha256": transaction_file_hash,
        "app_version": app_version,
        "schema_version": int(schema_version),
        "published_at": transaction["published_at"],
        "station_id": transaction["station_id"],
        "operation_id": operation_id,
    }
    atomic_write_json(_head_file(), head_payload)
    try:
        atomic_write_json(_sync_file(), {
            "revision": revision,
            "snapshot_sha256": digest,
            "transaction_file_sha256": transaction_file_hash,
            "synced_at": _now(),
            "station_id": station_id(),
        })
    except OSError:
        pass
    try:
        _prune_revision_snapshots(revision)
    except OSError:
        pass
    return head_payload


def startup(migrate, *, app_version: str, schema_version: int) -> dict:
    from Core.stations import ensure_operational
    ensure_operational()
    with _PROCESS_LOCK:
        _copy_seed_if_needed()
        try:
            with _exclusive_network_lock("INICIALIZACAO"):
                _recover_file_journals_locked()
                head = _read_required_json(_head_file(), "HEAD OFICIAL") if _head_file().is_file() else {}
                if head:
                    if int(head.get("schema_version") or 0) > int(schema_version):
                        raise RuntimeError("ESTA VERSÃO DO CJL System É MAIS ANTIGA QUE O REPOSITÓRIO OFICIAL.")
                    _pull_head_locked(head)
                needs_migration = not head or int(head.get("schema_version") or 0) < int(schema_version)
                if needs_migration:
                    preimage = _database_preimage()
                    try:
                        migrate()
                        published = _publish_locked(
                            "CRIACAO_REPOSITORIO" if not head else "MIGRACAO_SCHEMA",
                            app_version=app_version,
                            schema_version=schema_version,
                        )
                        return {"online": True, "revision": published["revision"], "published": True}
                    except Exception:
                        _restore_preimage(preimage)
                        raise
                    finally:
                        preimage.unlink(missing_ok=True)
                return {"online": True, "revision": int(head.get("revision") or 0), "published": False}
        except RepositoryOfflineError:
            if _pending_local_write_file().is_file():
                raise RuntimeError(
                    "ESTA ESTAÇÃO POSSUI UMA OPERAÇÃO INTERROMPIDA E PRECISA RECONECTAR AO MESTRE PARA RECUPERAÇÃO."
                )
            # No modo offline só a migração estrutural pendente é aplicada ao
            # cache. Rotinas de manutenção não podem divergir do repositório.
            current_schema = 0
            try:
                with sqlite3.connect(local_database_path()) as connection:
                    row = connection.execute(
                        "SELECT value FROM app_meta WHERE key='schema_version'"
                    ).fetchone()
                    current_schema = int(row[0]) if row else 0
            except (sqlite3.Error, TypeError, ValueError):
                current_schema = 0
            if current_schema < int(schema_version):
                migrate()
            return {"online": False, "revision": int(_local_sync().get("revision") or 0), "published": False}


@contextmanager
def read_scope():
    from Core.stations import ensure_operational
    ensure_operational()
    with _PROCESS_LOCK:
        lock_context = None
        lock_acquired = False
        try:
            if not _network_available():
                raise RepositoryOfflineError("A PASTA OFICIAL DE REDE ESTÁ INDISPONÍVEL.")
            # A leitura mantém a barreira global até o consumidor encerrar o
            # contexto. Assim nenhuma estação observa banco antigo junto com
            # arquivos externos que já foram trocados por uma escrita ainda
            # não publicada no HEAD.
            lock_context = _exclusive_network_lock("LEITURA_CONSISTENTE")
            lock_context.__enter__()
            lock_acquired = True
            _recover_file_journals_locked()
            _pull_head_locked()
        except RepositoryOfflineError:
            if lock_acquired and lock_context is not None:
                lock_context.__exit__(None, None, None)
            if _pending_local_write_file().is_file():
                raise RuntimeError(
                    "OPERAÇÃO LOCAL INTERROMPIDA: RECONECTE AO MESTRE ANTES DE CONTINUAR."
                )
            yield {"online": False, "revision": int(_local_sync().get("revision") or 0)}
            return
        except Exception:
            if lock_acquired and lock_context is not None:
                lock_context.__exit__(None, None, None)
            raise
        try:
            yield {"online": True, "revision": int(_local_sync().get("revision") or 0)}
        finally:
            if lock_context is not None:
                lock_context.__exit__(None, None, None)


@contextmanager
def maintenance_scope(action: str):
    """Congela escritas oficiais durante uma leitura administrativa longa."""
    from Core.stations import ensure_operational
    ensure_operational()
    with _PROCESS_LOCK:
        with _exclusive_network_lock(action):
            _recover_file_journals_locked()
            _pull_head_locked()
            yield {"online": True, "revision": int(_local_sync().get("revision") or 0)}


@contextmanager
def write_scope(action: str, *, app_version: str, schema_version: int):
    from Core.stations import ensure_operational
    ensure_operational()
    with _PROCESS_LOCK:
        with _exclusive_network_lock(action):
            _recover_file_journals_locked()
            _pull_head_locked()
            before = int(_local_sync().get("revision") or 0)
            preimage = _database_preimage()
            file_transaction, token = begin_file_transaction()
            operation_id = uuid.uuid4().hex
            atomic_write_json(_pending_local_write_file(), {
                "format": 1,
                "operation_id": operation_id,
                "base_revision": before,
                "target_revision": before + 1,
                "action": action,
                "started_at": _now(),
                "station_id": station_id(),
            })
            try:
                yield {"online": True, "revision": before}
                file_transaction.prepare_journal(
                    _file_journal_dir() / f"{operation_id}.json",
                    network_root(),
                    operation_id=operation_id,
                    base_revision=before,
                    target_revision=before + 1,
                    action=action,
                )
                file_transaction.commit()
                _publish_locked(
                    action,
                    app_version=app_version,
                    schema_version=schema_version,
                    operation_id=operation_id,
                )
                try:
                    # A partir da troca atômica do HEAD a revisão é oficial. Uma
                    # falha de limpeza nunca pode acionar rollback do estado já
                    # publicado; os diários tornam essa limpeza recuperável.
                    file_transaction.mark_published()
                    cleanup_errors = file_transaction.finalize()
                    if cleanup_errors:
                        raise OSError("; ".join(cleanup_errors[:3]))
                    file_transaction.close_journal()
                    _pending_local_write_file().unlink(missing_ok=True)
                except Exception:
                    pass
            except Exception as exc:
                rollback_errors = file_transaction.rollback()
                try:
                    _restore_preimage(preimage)
                except Exception as database_error:
                    raise RuntimeError(
                        "A OPERAÇÃO FALHOU E O BANCO LOCAL NÃO PÔDE SER RESTAURADO. "
                        "INTERROMPA O USO DESTA ESTAÇÃO E ACIONE O ADMINISTRADOR."
                    ) from database_error
                if rollback_errors:
                    raise RuntimeError(
                        "A OPERAÇÃO FALHOU E UM ARQUIVO EXTERNO NÃO PÔDE SER RESTAURADO: "
                        + "; ".join(rollback_errors[:3])
                    ) from exc
                try:
                    file_transaction.close_journal()
                    _pending_local_write_file().unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            finally:
                reset_file_transaction(token)
                preimage.unlink(missing_ok=True)


def status() -> dict:
    local = _local_sync()
    online = _network_available()
    head = _read_json(_head_file()) if online else {}
    return {
        "online": bool(online),
        "station_id": station_id(),
        "local_revision": int(local.get("revision") or 0),
        "network_revision": int(head.get("revision") or 0),
        "repository_format": int(head.get("format") or 0),
        "chain_anchored": _anchor_file().is_file(),
        "network_root": str(repository_root().parent),
        "repository_root": str(repository_root()),
    }
