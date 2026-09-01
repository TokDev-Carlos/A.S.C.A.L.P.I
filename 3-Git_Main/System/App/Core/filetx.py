from __future__ import annotations

import os
import hashlib
import shutil
import tempfile
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path

from Core.atomic import atomic_write_bytes, atomic_write_json
from Core.storage import ensure_disk_space


_CURRENT: ContextVar["FileTransaction | None"] = ContextVar("cjl_file_transaction", default=None)


@dataclass
class _Operation:
    kind: str
    source: Path | None
    destination: Path
    staged: Path | None = None
    backup: Path | None = None
    applied: bool = False
    original_exists: bool = False
    staged_sha256: str = ""
    created_directories: list[Path] = field(default_factory=list)


class FileTransaction:
    """Coordena arquivos externos com a publicação do snapshot oficial.

    Os serviços apenas preparam operações. A troca física ocorre depois que as
    transações SQLite terminam e ainda pode ser desfeita caso a publicação da
    revisão oficial falhe.
    """

    def __init__(self) -> None:
        self.operations: list[_Operation] = []
        self.committed = False
        self.journal_path: Path | None = None
        self.journal_root: Path | None = None
        self.journal_metadata: dict = {}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _relative(self, path: Path | None) -> str:
        if path is None:
            return ""
        if self.journal_root is None:
            raise RuntimeError("RAIZ DO DIÁRIO DE ARQUIVOS NÃO FOI DEFINIDA.")
        try:
            return path.resolve().relative_to(self.journal_root).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"ARQUIVO FORA DO MESTRE NÃO PODE SER TRANSACIONADO: {path}") from exc

    def _write_journal(self, phase: str, current_index: int = -1) -> None:
        if self.journal_path is None:
            return
        payload = dict(self.journal_metadata)
        payload.update({
            "phase": phase,
            "current_index": current_index,
            "operations": [
                {
                    "kind": operation.kind,
                    "source": self._relative(operation.source),
                    "destination": self._relative(operation.destination),
                    "staged": self._relative(operation.staged),
                    "backup": self._relative(operation.backup),
                    "applied": operation.applied,
                    "original_exists": operation.original_exists,
                    "staged_sha256": operation.staged_sha256,
                }
                for operation in self.operations
            ],
        })
        atomic_write_json(self.journal_path, payload)

    def prepare_journal(
        self,
        journal_path: Path,
        master_root: Path,
        *,
        operation_id: str,
        base_revision: int,
        target_revision: int,
        action: str,
    ) -> None:
        if not self.operations:
            return
        self.journal_path = Path(journal_path)
        self.journal_root = Path(master_root).resolve()
        self.journal_metadata = {
            "format": 1,
            "operation_id": operation_id,
            "base_revision": int(base_revision),
            "target_revision": int(target_revision),
            "action": action,
        }
        for operation in self.operations:
            # Valida todos os caminhos antes de registrar qualquer intenção.
            self._relative(operation.destination)
            self._relative(operation.source)
            self._relative(operation.staged)
            operation.original_exists = operation.destination.exists()
            if operation.kind == "replace" and operation.original_exists:
                operation.backup = operation.destination.with_name(
                    f".{operation.destination.name}.{operation_id}.rollback"
                )
                self._relative(operation.backup)
                if operation.backup.exists():
                    raise RuntimeError(
                        f"RESÍDUO DE ROLLBACK JÁ EXISTE PARA {operation.destination}."
                    )
            if operation.staged and operation.staged.is_file():
                operation.staged_sha256 = self._sha256(operation.staged)
        self._write_journal("PREPARED")

    def mark_published(self) -> None:
        self._write_journal("PUBLISHED")

    def close_journal(self) -> None:
        if self.journal_path:
            self.journal_path.unlink(missing_ok=True)

    @staticmethod
    def _parents_to_create(path: Path) -> list[Path]:
        missing: list[Path] = []
        current = path
        while not current.exists() and current != current.parent:
            missing.append(current)
            current = current.parent
        for item in reversed(missing):
            item.mkdir()
        return missing

    def stage_bytes(self, destination: Path, value: bytes) -> None:
        destination = Path(destination)
        ensure_disk_space(destination, len(value), label="GRAVAÇÃO PROTEGIDA")
        staging_parent = destination.parent
        while not staging_parent.exists() and staging_parent != staging_parent.parent:
            staging_parent = staging_parent.parent
        if not staging_parent.is_dir():
            raise OSError(f"NÃO HÁ PASTA DE ESTÁGIO ACESSÍVEL PARA {destination}.")
        fd, name = tempfile.mkstemp(
            prefix=f".{destination.name}.cjl-",
            suffix=".stage",
            dir=staging_parent,
        )
        staged = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        self.operations.append(_Operation("replace", None, destination, staged=staged))

    def stage_move(self, source: Path, destination: Path) -> None:
        source, destination = Path(source), Path(destination)
        if not source.exists():
            return
        self.operations.append(_Operation("move", source, destination))

    def stage_directory(self, source: Path, destination: Path) -> None:
        source, destination = Path(source), Path(destination)
        if not source.is_dir():
            raise FileNotFoundError(source)
        self.operations.append(_Operation("directory", source, destination))

    def stage_mkdir(self, destination: Path) -> None:
        self.operations.append(_Operation("mkdir", None, Path(destination)))

    def commit(self) -> None:
        if self.committed:
            return
        try:
            self._write_journal("COMMITTING")
            for index, operation in enumerate(self.operations):
                self._write_journal("APPLYING", index)
                destination = operation.destination
                operation.created_directories = self._parents_to_create(destination.parent)
                if operation.kind == "replace":
                    if destination.exists():
                        backup = operation.backup or destination.with_name(
                            f".{destination.name}.{uuid.uuid4().hex}.rollback"
                        )
                        os.replace(destination, backup)
                        operation.backup = backup
                    os.replace(operation.staged, destination)  # type: ignore[arg-type]
                elif operation.kind in {"move", "directory"}:
                    if destination.exists():
                        raise FileExistsError(f"O DESTINO JÁ EXISTE: {destination}")
                    os.replace(operation.source, destination)  # type: ignore[arg-type]
                elif operation.kind == "mkdir":
                    if not destination.exists():
                        destination.mkdir()
                    else:
                        operation.created_directories = []
                        operation.applied = False
                        continue
                else:
                    raise RuntimeError(f"OPERAÇÃO DE ARQUIVO DESCONHECIDA: {operation.kind}")
                operation.applied = True
                self._write_journal("COMMITTING", index)
            self.committed = True
            self._write_journal("FILES_COMMITTED")
        except Exception as exc:
            rollback_errors = self.rollback()
            if rollback_errors:
                detail = "; ".join(rollback_errors[:3])
                raise RuntimeError(
                    f"A GRAVAÇÃO FALHOU E A RESTAURAÇÃO DE ARQUIVOS NÃO FOI COMPLETA: {detail}"
                ) from exc
            raise

    def rollback(self) -> list[str]:
        errors: list[str] = []
        try:
            self._write_journal("ROLLING_BACK")
        except OSError as exc:
            errors.append(f"DIÁRIO DE ROLLBACK: {exc}")
        for operation in reversed(self.operations):
            try:
                if operation.kind == "replace":
                    # O backup pode já ter sido criado mesmo quando a troca do
                    # arquivo de estágio falha antes de ``applied`` ser marcado.
                    # Nesse intervalo, restaurar o backup é obrigatório.
                    if operation.backup and operation.backup.exists():
                        operation.destination.unlink(missing_ok=True)
                        operation.destination.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(operation.backup, operation.destination)
                    elif operation.applied:
                        operation.destination.unlink(missing_ok=True)
                elif operation.kind in {"move", "directory"}:
                    # Também cobre uma interrupção logo após os.replace e antes
                    # da atualização do marcador em memória.
                    if (
                        operation.destination.exists()
                        and operation.source is not None
                        and not operation.source.exists()
                    ):
                        operation.source.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(operation.destination, operation.source)
                elif operation.kind == "mkdir" and operation.applied:
                    try:
                        operation.destination.rmdir()
                    except OSError:
                        pass
                if operation.staged and operation.staged.exists():
                    operation.staged.unlink(missing_ok=True)
                if operation.backup and operation.backup.exists():
                    # Só é removido quando a restauração acima já ocorreu ou
                    # quando nunca houve arquivo original a preservar.
                    if operation.destination.exists() or not operation.applied:
                        try:
                            operation.backup.unlink()
                        except OSError:
                            pass
                for directory in operation.created_directories:
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
            except OSError as exc:
                errors.append(f"{operation.destination}: {exc}")
        self.committed = False
        if not errors:
            try:
                self._write_journal("ROLLED_BACK")
            except OSError as exc:
                errors.append(f"DIÁRIO DE ROLLBACK: {exc}")
        return errors

    def finalize(self) -> list[str]:
        errors: list[str] = []
        for operation in self.operations:
            try:
                if operation.staged:
                    operation.staged.unlink(missing_ok=True)
                if operation.backup:
                    operation.backup.unlink(missing_ok=True)
            except OSError as exc:
                errors.append(f"{operation.destination}: {exc}")
        self.operations.clear()
        return errors


def begin() -> tuple[FileTransaction, Token]:
    transaction = FileTransaction()
    return transaction, _CURRENT.set(transaction)


def reset(token: Token) -> None:
    _CURRENT.reset(token)


def current() -> FileTransaction | None:
    return _CURRENT.get()


def stage_bytes(path: Path, value: bytes) -> None:
    transaction = current()
    if transaction:
        transaction.stage_bytes(path, value)
    else:
        atomic_write_bytes(Path(path), value)


def stage_move(source: Path, destination: Path) -> None:
    transaction = current()
    if transaction:
        transaction.stage_move(source, destination)
    else:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)


def stage_directory(source: Path, destination: Path) -> None:
    transaction = current()
    if transaction:
        transaction.stage_directory(source, destination)
    else:
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)


def stage_mkdir(path: Path) -> None:
    transaction = current()
    if transaction:
        transaction.stage_mkdir(path)
    else:
        Path(path).mkdir(parents=True, exist_ok=True)
