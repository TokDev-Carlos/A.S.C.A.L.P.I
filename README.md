# ASCALPI - Dev-Work

This branch is the portable engineering representation of the current ASCALPI development environment.

Versioned development components:

- `1-Dev`
- `2-Compiler`
- `3-Git_Main`
- `4-Control`
- `5-Docs`
- portable content under `WSL`

Local-only machine state is intentionally excluded:

- `Git`
- WSL virtual disks
- credentials and secrets
- machine identity
- operational databases and user data
- local logs and receipts
- rollback state
- `1-Dev` Runtime and compiled Host/Bin payload
- `2-Compiler` local Runtime
- transient compiler runs and handoff outputs
- caches and temporary files

Runtime policy:

- `1-Dev`: engineering source/scripts/config only; no complete Runtime payload;
- `2-Compiler`: compiler logic/config only; no local Runtime payload;
- `3-Git_Main`: the only complete Windows Runtime/executable payload in Dev-Work.

Large executable/runtime/archive assets that remain intentionally versioned
under `3-Git_Main` are transported through Git LFS.

The Dev-Work bootstrap does not write to `main`.
