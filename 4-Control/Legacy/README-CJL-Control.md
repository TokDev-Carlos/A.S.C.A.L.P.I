# CJL Control

Version: 1.1.2
Date: 2026-08-28
Timezone: America/Sao_Paulo

## Review result

This revision keeps the proven v1.0.1 main window and corrects the secondary 21-stage window.

Corrections over v1.1.1:

- stage definitions now use explicit PSCustomObject records instead of nested arrays;
- stage action/state travels through ListViewItem.Tag;
- option 16 is LOCKED until option 15 actually applies a candidate;
- option 09 uses .NET SHA256 instead of Get-FileHash for Windows PowerShell compatibility;
- option 09 persists selected-patch.json as UTF-8 without BOM;
- events.jsonl appends UTF-8 without BOM;
- MessageBox overloads use explicit enum values;
- multiline status messages use String.Join instead of fragile line continuation;
- startup error capture remains enabled.

## Main window

- 1-Dev Linux: status, open/reopen, open folder.
- 2-Compiler: PAUSED, no execution.
- 3-Git_Main: status, open system, ADMIN/DEV, open folder.
- Fluxo 21 Etapas: opens the historical stage map.

## Active/selective stages

- 01: partial local environment check, read-only;
- 03: machine identity, read-only;
- 05: development tree, read-only;
- 06: graphical flow itself;
- 08: open current Linux launcher;
- 09: select local Patch ZIP, calculate SHA256, persist selection only;
- 14: open current Git_Main.

Stage 16 is intentionally LOCKED until stage 15 exists and has actually applied a candidate.

Compiler remains PAUSED.
GitHub write is not enabled.
Production write is not enabled.
Patch apply is not enabled.
