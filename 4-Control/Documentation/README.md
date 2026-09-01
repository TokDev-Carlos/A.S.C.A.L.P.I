# CJL Documentation Trigger Engine

This local Windows PowerShell 5.1 engine records explicit CJL workflow events and
projects only approved failure knowledge into `Black_Book.md` and approved,
reusable proof into `White_Book.md`.

## Layout

- `Policy`: hard-locked event, document and rendering policy.
- `Engine`: stable event emission, processing, verification and recovery entrypoints.
- `State`: append-only event ledger, processed ledger, pending remote-sync queue and baselines.
- `Tests`: isolated sandbox acceptance suite.

## Emit an event

Use `Emit-CJLEvent.cmd` with named PowerShell parameters, or invoke
`Engine\Emit-CJLEvent.ps1` directly. Emission appends the event durably and then
immediately processes pending events.

Failures allowed by `EVENT_RULES.json` create managed Black Book blocks. Ordinary
success is ledger-only. Proof-class events create White Book entries only when
`-ReusableKnowledge` is supplied.

## Protection boundary

`Execution_Contract.md`, `Souvenir.md`, and any future non-book Markdown accepted
through the operator rebaseline route are static. Black and White books are the
only automatically evolutive documents. Policy files are ReadOnly and verified
against `POLICY_BASELINE.json` on every processor start.

Remote synchronization is `QUEUE_ONLY`. Local book changes append records to
`State\pending-sync.jsonl`; this engine never calls Git or GitHub.

## Recovery and rebaseline

Run `Process-Pending.cmd` to retry events that were appended but not projected.
Static rebaseline is available only through the separate interactive
`Engine\Rebaseline-StaticDocuments.ps1 -InteractiveOperator` route and requires
two exact human confirmations. The automatic processor cannot invoke it.
