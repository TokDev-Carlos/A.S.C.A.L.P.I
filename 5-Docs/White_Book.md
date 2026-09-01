# CJL White Book - Volume 001

Status: ACTIVE
Revision: WHITE-VOL-006
Date: 2026-08-21
Timezone: America/Sao_Paulo

This volume accumulates proven engineering knowledge.

White Book entries do not replace original Evidence, Logs, Receipts or test
results. A correction enters this volume only after the applicable proof passes.

===============================================================================
WB-0001 - BYTE-EXACT GIT_MAIN PRESERVATION UNDER WINDOWS CHECKOUT
===============================================================================

Date proven: 2026-08-20
Status: PROVEN
Area: 3-Git_Main / Git / Windows
Related failure: FAIL-0001

Problem solved:
Git text end-of-line normalization changed thousands of files when the first
byte-exact Git_Main bootstrap was retrieved on Windows.

Proven repository rule:
`3-Git_Main/System/** -text`

Related corrected reindex commit:
`497374cd9ef876c45761f9daa66b7d8b9336dbb6`

Proof commit:
`b42f61c1dd67b9ec06fc5889ad5c42768e639ebb`

Proof conditions:
- Windows 2022 clean checkout;
- Git LFS payload restored;
- `core.autocrlf=true` forced before re-checkout;
- frozen MAIN source inventory used as authority;
- every restored relative path checked;
- size and SHA256 reconciliation performed.

Proven result:
- source files: 16749
- restored files: 16749
- source bytes: 1621127928
- restored bytes: 1621127928
- SHA256 mismatches: 0
- Git_Main byte-exact status: PASS

PASS evidence:
`3-Git_Main/Evidence/Initial-Clone/COLD_RESTORE_PASS_001.md`

Failure evidence:
`3-Git_Main/Evidence/Initial-Clone/COLD_RESTORE_FAIL_001.md`

Validated use:
For a repository-controlled System tree that must preserve exact bytes across
Windows Git checkout, explicitly disable text normalization for the complete
mirror. LFS-only `-text` rules are insufficient for the remaining text-like files.

Limitation:
WB-0001 proves byte-exact Git storage/retrieval only.

===============================================================================
WB-0002 - MULTI-FILE LOGICAL GIT TRANSACTION
===============================================================================

Date proven: 2026-08-20
Status: PROVEN
Area: GitHub / documentation and governance writes
Related failure: FAIL-0003

Problem solved:
A multi-file documentation cycle initially created avoidable per-file commits,
contradicting the logical-transaction rule.

Proven procedure:
For one coherent multi-file change, prepare all required file objects first and
then perform one logical Git transaction using:

`create_blob -> create_tree -> create_commit -> update_ref`

or an equivalent native Git operation that produces one coherent commit.

Proof commit:
`f6b7736a35016fe9f06b0c49ca869df7e495dae2`

Observed result:
- a repository-wide documentation synchronization was represented by one logical
  multi-file commit;
- no source or Git_Main System bytes were rewritten by the documentation commit;
- previously published microcommits remained in history rather than being
  destructively rewritten.

Validated use:
Use this model whenever multiple file writes belong to the same engineering state
transition and no independent rollback/test checkpoint requires separate commits.

Limitation:
Independent technical checkpoints may still justify separate commits as defined
by the Execution Contract.

===============================================================================
WB-0003 - CJL WINDOWS RUNTIME DISCOVERY THROUGH INSTANCE REGISTRY
===============================================================================

Date proven: 2026-08-20
Status: PROVEN
Area: 3-Git_Main / Windows runtime smoke harness
Related failure: FAIL-0002

Problem solved:
The first runtime harness depended on parsing stdout for a localhost URL and
failed before the CJL runtime could be classified.

Proven correction:
Use the CJL application's machine-readable instance registry as the authoritative
runtime discovery contract, validate the published process identity and port, and
correct PID handling before issuing the HTTP request.

Application contract used:
`App/Core/instance.py` publishes process/runtime metadata including PID and port.

Proof commit:
`42a7fd3290cfba899df1f256fefac6e268193e66`

Confirmed statuses:
- `cjl/linux-dev = success`
- `cjl/git-main-byte-exact = success`
- `cjl/git-main-system-validation = success`
- `cjl/git-main-runtime-smoke = success`

Validated use:
When the application exposes a machine-readable runtime registry, prefer that
contract over parsing human-oriented stdout for endpoint discovery.

Evidence:
`3-Git_Main/Evidence/Initial-Clone/GIT_MAIN_RUNTIME_STATUS_001.md`

Limitation:
WB-0003 proves the tested Windows initializer/local HTTP runtime path in the
isolated validation environment. It does not by itself prove production rollout,
rollback behavior or Operator production acceptance.

===============================================================================
WB-0004 - INTEGRITY-CONTROLLED SOURCE PRESERVATION
===============================================================================

Date proven: 2026-08-20
Status: PROVEN
Area: release integrity / governance-only corrections
Related failure: FAIL-0005

Problem solved:
A governance correction rewrote an integrity-manifested runtime policy even
though the approved bytes already expressed the required data boundary.

Proven procedure:
- inspect the current runtime policy before editing it;
- preserve approved integrity-controlled bytes when behavior need not change;
- express repository enforcement in the external governance validator;
- do not regenerate a release manifest for a governance-only correction.

Proof commit:
`bc395584b165f1b76f07ee66010c51066c68cc8c`

Proof run:
GitHub Actions run `32433240298` passed governance, Python compile/Linux smoke
and .NET 10.0.400 cross-target build.

Validated use:
Use this rule whenever documentation or repository governance is corrected around
an application file protected by release-integrity metadata.

Limitation:
If runtime behavior truly changes, the source and its release-integrity metadata
must evolve together under the applicable release procedure.

===============================================================================
WB-0005 - PORTABLE ROW-FREE SQLITE SCHEMA SEED
===============================================================================

Date proven: 2026-08-20
Status: PROVEN
Area: portable body / SQLite / UserData separation
Related failure: FAIL-0006

Problem solved:
Removing an operational database also removed the bootstrap prerequisite required
to create isolated local state.

Proven repository rule:
The exact `Data/sistema.db` seed may be System data only when both controlled
copies are byte-identical, SQLite integrity passes, every application table has
zero rows, no sidecar exists and every other active Data file is absent.

Proof commit:
`bc395584b165f1b76f07ee66010c51066c68cc8c`

Proof run:
GitHub Actions run `32433240298` passed all three independent jobs, including
governance inspection and Linux startup from the seed.

Proven seed identity:
- bytes: 344064;
- SQLite application tables: 27;
- application tables with rows: 0;
- indexes: 20;
- integrity: PASS;
- SHA256: d5ab9e4e389d6b026ba90d22e21bb1d93d20b1ace2f1b2451ea7ddfda6b98213.

Validated use:
Separate System data from UserData by role and verified content, not only by the
folder name. Preserve only the minimum deterministic bootstrap prerequisite.

Limitation:
This proof does not replace HOME/WORK practical reproduction, Windows acceptance
or production rollout approval.

===============================================================================
WB-0006 - EXPLICIT WORK WSL IDENTITY AND SHELL-BOUNDARY VALIDATION
===============================================================================

Date proven: 2026-08-21
Status: PROVEN
Area: Dev-Work / Windows host / WSL2 / Linux development shell
Related failure: FAIL-0007

Problem solved:
Localized WSL output, redundant state mutation and ambiguous prompt boundaries
made the first WORK bootstrap commands non-deterministic.

Proven procedure:
- use PowerShell only for actual Windows host control;
- launch the exact WSL distribution with an explicit non-root Linux user and home;
- use Bash only after the Linux prompt, user and directory are proven;
- verify distribution, systemd, sudo, toolchain and controlled root independently;
- never concatenate a new command with an unfinished interactive construction.

Proof result:
Ubuntu-24.04, user carlos_alberto, systemd, sudo, .NET 10.0.400 and /cjl passed
on <LOCAL_MACHINE>. The exact Dev-Work source was subsequently cloned without
production mutation.

Validated use:
Apply this boundary whenever Windows launches or controls a Linux development
environment.

Limitation:
Host-only actions still require PowerShell. Development, tests and compilation
remain Linux actions unless the Execution Contract explicitly assigns otherwise.

===============================================================================
WB-0007 - AUTHENTICATED PRIVATE REMOTE PREFLIGHT BEFORE CLONE
===============================================================================

Date proven: 2026-08-21
Status: PROVEN
Area: Dev-Work / GitHub / Git LFS / private source retrieval
Related failure: FAIL-0008

Problem solved:
A private HTTPS remote was queried before supported authentication and Git LFS
were prepared, causing an invalid password flow and an avoidable stop.

Proven procedure:
- install and validate the official GitHub CLI;
- authenticate by supported browser/device flow and prove the expected account;
- configure the Git credential helper before invoking Git remote operations;
- keep credential files outside repositories, owner-only and excluded from
  evidence;
- install the current approved Git LFS release from a verified archive;
- pin and compare the approved remote commit before clone;
- validate active branch, origin, clean worktree and every LFS object after clone.

Proof result:
TokDev-Carlos authenticated; credential file owner carlos_alberto and mode 600;
Git LFS 3.7.1 installed; Dev-Work commit
e383abc37bbbdf7e81ede6a4f29c269a723bc699 cloned; seven LFS objects filtered;
874.14 MiB LFS payload retrieved; git lfs fsck passed; worktree clean.

Validated use:
Apply before every new private repository clone or after credential/toolchain
replacement on HOME or WORK.

Limitation:
The GitHub CLI reported local plaintext credential storage because no encrypted
Linux credential store was available. This proof permits only the observed
owner-only file outside every repository and evidence root. Migration to an
encrypted credential store or SSH may be performed as a separate hardening cycle.

===============================================================================
WB-0008 - DOCKER DESKTOP WSL PROXY, SOCKET AND GROUP RECOVERY GATE
===============================================================================

Date proven: 2026-08-21
Status: PROVEN
Area: Dev-Work / Docker Desktop / WSL2
Related failure: FAIL-0009

Problem solved:
Docker Desktop appeared running but the exact Ubuntu user session could not
initially reach the Docker API because its user-distro integration proxy/socket
was unavailable or not loaded into the session.

Proven procedure:
- preserve Docker Desktop and WSL error evidence;
- stop WSL from Windows and restart Docker Desktop through the Windows host;
- prove Docker Desktop reports running before opening the Linux distribution;
- reopen the exact Ubuntu distribution and non-root user;
- wait for /var/run/docker.sock;
- require owner root, group docker and mode 660;
- require current user membership in docker;
- require Docker server version, Linux engine identity and Compose response.

Proof result:
Ubuntu-24.04 user carlos_alberto reached Docker Desktop server 29.5.3 through a
root:docker mode-660 socket; Linux/x86_64 engine and Compose v5.1.4 passed.

Limitation:
Docker Desktop upgrades or a failed WSL proxy may invalidate the current socket
state. Repeat the gate after integration failure rather than assuming the visible
Desktop process proves API readiness.

===============================================================================
WB-0009 - EVIDENCE-ROOT-ONLY PACKAGING
===============================================================================

Date proven: 2026-08-21
Status: PROVEN
Area: Dev-Work / evidence / Windows filesystem
Related failure: FAIL-0010

Problem solved:
A complete evidence archive attempted to use the protected Windows drive root
after the technical environment gate had already passed.

Proven procedure:
- use C:\CJL_Work_Evidence as the explicit evidence root;
- prove that exact root is writable before the audit;
- create receipt directory, ZIP and SHA256 sidecar inside that root;
- classify technical readiness separately from packaging;
- retain the original technical receipt even if an optional archive fails.

Proof result:
The final audit reported EVIDENCE_PACKAGING=PASS and produced archive SHA256
e6de9b7b984964b171ec18ef6abf74d4e99015e51df6a0d5f597fdc32aa9476a.

Limitation:
This proves the configured WORK evidence root. A different destination requires
its own path resolution and write preflight.

===============================================================================
WB-0010 - WINDOWS POWERSHELL 5.1 GUARDED ENVIRONMENT AUDIT
===============================================================================

Date proven: 2026-08-21
Status: PROVEN
Area: Dev-Work / Windows PowerShell 5.1 / WSL audit
Related failure: FAIL-0011

Problem solved:
Early audit revisions used overload and generic-list behavior that differed on
Windows PowerShell 5.1, and a separately pasted command could continue after a
hash guard failed.

Proven procedure:
- keep the stable script filename and internal revision identity;
- verify delivery ZIP and extracted script SHA256 before replacement;
- perform replacement, second hash verification and execution in one script
  block with ErrorActionPreference Stop;
- use `-split` instead of ambiguous String.Split overload selection;
- use PowerShell-native arrays for audit collections;
- normalize native null output and prove WSL by direct execution in the named
  distribution;
- preserve exception line, position and stack;
- return exit code 2 only for blocking findings or audit failure.

Proven identity:
- internal revision: CJL-ENVIRONMENT-003;
- script SHA256:
  37dd5615ca2a5a778ccc4295ee54fdd8e85debfc9b167c8023aabf2b96637e62;
- audit exit code: 0;
- evidence packaging: PASS.

Limitation:
Revision 003 is currently a proven WORK-local candidate. Repository placement on
Dev-Work and any future Prepare or Repair mode require a separate reviewed
evolution. Audit PASS does not authorize automatic machine mutation.

===============================================================================
WB-0011 - WORK CORRECTED-BODY ENVIRONMENT READINESS
===============================================================================

Date proven: 2026-08-21
Status: PROVEN
Area: Dev-Work / corrected portable body / local development
Related failure: FAIL-0004

Problem solved:
The corrected portable body required practical reproduction on HOME or WORK
before the repository data-boundary failure could close its machine gate.

Proven conditions:
- machine ID: A5C486A67B75E1A4;
- computer: <LOCAL_MACHINE>;
- branch: Dev-Work;
- source commit: a7aca1c4b7e4f9934dcf43fbc584fae00923e51a;
- worktree: clean and remote-fresh;
- Ubuntu-24.04, user carlos_alberto and systemd: PASS;
- Python 3.12.3 virtual environment and dependency check: PASS;
- .NET SDK 10.0.400 evidence: PASS;
- Docker Desktop Linux engine and Compose: PASS;
- governance, repository tree, LFS and authorized path access: PASS;
- blocking findings: 0;
- local development ready: YES.

Proof receipt:
- identity: 20260821T220042_WORK_ENVIRONMENT_AUDIT;
- archive SHA256:
  e6de9b7b984964b171ec18ef6abf74d4e99015e51df6a0d5f597fdc32aa9476a.

Validated use:
The exact WORK environment is eligible for continued Linux development on its
authorized Dev-Work line.

Limitations:
- HOME remains PENDING;
- Windows 10 supported acceptance remains PENDING active ESU evidence;
- Compiler, Windows candidate, 3-Git_Main and production gates remain PENDING;
- production C:\CJL\System was not present and was not modified.
