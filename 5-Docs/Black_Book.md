# CJL Black Book - Volume 001

Status: ACTIVE
Revision: BLACK-VOL-010
Date: 2026-08-21
Timezone: America/Sao_Paulo

This volume accumulates contextual failures and rejected procedures.

Original Evidence, Logs, Receipts and stage-local records remain authoritative
and stay in their original locations.

===============================================================================
FAIL-0001 - GIT EOL NORMALIZATION IN GIT_MAIN COLD RESTORE
===============================================================================

Date: 2026-08-20 00:02 America/Sao_Paulo
Area: 3-Git_Main / Git / Windows
Status: CORRECTED / RETEST PASS / CLOSED

Context:
The initial Git_Main bootstrap was pushed and then retrieved through a clean cold
clone to prove that GitHub could reconstruct the selected MAIN.

Expected result:
The restored `3-Git_Main/System` must match `C:\CJL\System` byte-for-byte.

Failed result:
- source files: 16749
- restored files: 16749
- source bytes: 1621127928
- restored bytes: 1625479523
- Git LFS entries restored: 7
- mismatches: 6443
- mismatch class: SIZE
- missing files: 0
- extra files: 0

Representative changed files:
- COPYRIGHT.txt: 1612 -> 1653
- LICENSE.txt: 8760 -> 8960
- App/estrutura_sistema.py: 1852 -> 1899
- App/painel.py: 62432 -> 63657
- App/Config/runtime.integrity.json: 2592708 -> 2609190
- App/Core/db.py: 37793 -> 38318

Confirmed cause:
Git text end-of-line normalization changed stored/restored byte representation
for thousands of files under `3-Git_Main/System`.

Failure evidence:
`3-Git_Main/Evidence/Initial-Clone/COLD_RESTORE_FAIL_001.md`

Failed bootstrap commit:
`df4b31666b38f5f8aa18db3558b255b8b581106e`

Correction:
`3-Git_Main/System/** -text`

Corrected byte-exact reindex candidate:
`497374cd9ef876c45761f9daa66b7d8b9336dbb6`

Retest proof:
A Windows checkout forced `core.autocrlf=true`, reset the worktree, restored Git
LFS and compared the frozen MAIN inventory against every restored file by path,
size and SHA256.

Confirmed retest result:
- source files: 16749
- restored files: 16749
- source bytes: 1621127928
- restored bytes: 1621127928
- SHA256 mismatches: 0
- byte-exact status: PASS

Proof commit:
`b42f61c1dd67b9ec06fc5889ad5c42768e639ebb`

PASS evidence:
`3-Git_Main/Evidence/Initial-Clone/COLD_RESTORE_PASS_001.md`

White Book relationship:
`WB-0001 - Byte-exact Git_Main preservation under Windows checkout`.

Lesson:
A byte-exact Git_Main mirror must explicitly disable Git text normalization for
the complete mirrored System tree. File-count equality alone is not sufficient;
retrieval must also be proven by byte count and SHA256 comparison.

===============================================================================
FAIL-0002 - WINDOWS RUNTIME SMOKE HARNESS DID NOT CLASSIFY CJL RUNTIME
===============================================================================

Date: 2026-08-20
Area: 3-Git_Main / GitHub Actions / Windows smoke harness
Status: CORRECTED / RETEST PASS / CLOSED

Context:
After byte-exact retrieval and the canonical System validator passed, the test
line attempted to execute the real Windows initializer and verify the local HTTP
panel.

Expected result:
The real initializer publishes a running local CJL instance, the harness discovers
the endpoint, requests it, and the panel returns the expected HTTP response.

First failed harness result:
The PowerShell harness attempted to derive the runtime URL from stdout and failed
while applying regex Match to a null stdout value.

First observable diagnostic:
`Exception calling Match with 2 argument(s): Value cannot be null...`

First runtime-smoke commit:
`eb82bea04916864d7efd03590cd03d8bc3cec0f0`

Classification at failure time:
TEST HARNESS FAILURE. The CJL application runtime itself was UNCLASSIFIED.

Original evidence:
`3-Git_Main/Evidence/Initial-Clone/GIT_MAIN_RUNTIME_STATUS_001.md`

Correction sequence:
- stop treating stdout regex as the authoritative runtime endpoint source;
- use the CJL application instance registry published under its state root;
- validate the published process identity and port;
- correct PID handling in the Windows smoke harness;
- request the real local HTTP endpoint and require success.

Correction proof commit:
`42a7fd3290cfba899df1f256fefac6e268193e66`

Confirmed commit statuses after correction:
- `cjl/linux-dev = success`
- `cjl/git-main-byte-exact = success`
- `cjl/git-main-system-validation = success`
- `cjl/git-main-runtime-smoke = success`

Final classification:
CJL Windows runtime smoke: PASS.
Test harness correction: PROVEN.

Related White Book:
`WB-0003 - CJL Windows runtime discovery through the application instance registry`.

Lesson:
A failing test harness must never be reported as a product failure. Prefer the
application's explicit machine-readable runtime contract over fragile parsing of
human-oriented stdout when such a contract exists.

===============================================================================
FAIL-0003 - DOCUMENTATION CYCLE CREATED AVOIDABLE MICROCOMMITS
===============================================================================

Date: 2026-08-20 06:09 America/Sao_Paulo
Area: GitHub / documentation governance
Status: PROCEDURE CORRECTED / RETEST PASS / CLOSED

Context:
The repository-wide documentation synchronization was authorized after
EXEC-CONTRACT-003 had already formalized logical Git transactions and commit
consolidation.

Expected procedure:
Collect all related documentation changes, build one Git tree, create one logical
commit and advance the working branch once.

Actual procedure at cycle start:
The changelog was first written through the per-file contents API and then a
duplicate no-op write was issued before switching to the required tree-based
consolidated workflow.

Git evidence of avoidable microcommits:
- `2f81ef83e5bc8f01b0fcdc0a25a6976c9b2721c8`
- `17a3452246c1d52393c82c613afd5b03828452da`

Impact:
- no source corruption;
- no Git_Main System mutation;
- no production mutation;
- extra history noise only.

Cause:
Tool-selection/procedure error: per-file Contents API was used before completing
the multi-file logical transaction.

Correction:
Use a consolidated Git object flow for one logical multi-file change:
`create_blob -> create_tree -> create_commit -> update_ref` or equivalent.

Proof:
The later repository-wide synchronization closed as one logical multi-file commit:
`f6b7736a35016fe9f06b0c49ca869df7e495dae2`

The historical microcommits were preserved rather than rewritten.

Final classification:
Consolidated multi-file Git transaction: PASS.
Procedure correction: PROVEN.

Related White Book:
`WB-0002 - Multi-file logical Git transaction using blob/tree/commit/ref flow`.

Lesson:
Detailed cumulative recording does not require one Git commit per file operation.
Connector behavior must not dictate the project history model.

===============================================================================
FAIL-0004 - OPERATIONAL DATA ENTERED ACTIVE REPOSITORY TREES
===============================================================================

Date: 2026-08-20 America/Sao_Paulo
Area: repository boundary / SQLite / UserData / Git_Main
Status: CLOSED / WORK PRACTICAL RETEST PASS / RELATED WHITE BOOK WB-0011

Context:
The development and Git_Main trees contained a SQLite database with operational
rows plus Shared and Repo material representing real system use. Git_Main also
contained mutable Logs and Export content.

Expected result:
The active repository body contains system source and schema contracts only.
Operational Data, Shared, Repo, Logs, Export and Temp content is excluded.

Observed result:
- the source database passed SQLite integrity inspection and contained rows;
- operational files were present under active UserData roots;
- the same classes were duplicated in the Git_Main System tree;
- the existing data policy already declared these roots EXCLUDE and required
  schema-contract-only database content.

Impact:
- active-tree policy violation;
- risk of carrying real business/user information across development lines;
- false claim that Dev-Home or Git_Main was a clean portable system body;
- historical Windows proof remains valid only for its exact historical identity.

Correction implemented in the integration candidate:
- remove operational roots and replace the operational database with an exact
  schema-only seed whose application tables all contain zero rows;
- remove the historical production path inventory from the active tree because it
  contains operational filename metadata while preserving it in Git history;
- preserve prior Git history rather than rewriting it during this correction;
- add path-specific ignore rules;
- add an executable governance/data-boundary validator;
- keep schema initialization in source code and create mutable databases only in
  local state at runtime;
- require current candidate tests instead of inheriting historical PASS.

Proof completed:
- candidate tree contains no forbidden operational path or operational database;
- both permitted schema seeds are byte-identical, pass SQLite integrity and have
  zero rows in every application table;
- governance, Python compile/Linux smoke and .NET 10.0.400 cross-target build pass
  for commit bc395584b165f1b76f07ee66010c51066c68cc8c in GitHub Actions run
  32433240298;
- no production mutation occurred.

Practical closure proof:
- WORK reproduced the corrected portable body on Dev-Work commit
  a7aca1c4b7e4f9934dcf43fbc584fae00923e51a;
- governance, Python runtime, .NET cross-target evidence, Docker WSL integration,
  repository identity and required path access passed;
- final audit reported zero blocking findings and local development ready YES;
- receipt identity: 20260821T220042_WORK_ENVIRONMENT_AUDIT;
- receipt archive SHA256:
  e6de9b7b984964b171ec18ef6abf74d4e99015e51df6a0d5f597fdc32aa9476a.

White Book relationship:
WB-0011 - WORK corrected-body environment readiness and practical reproduction.

Lesson:
A repository can be byte-exact and still violate its data boundary. Storage
integrity does not authorize operational UserData. Validate content class and
policy, not only file counts, bytes or hashes.

===============================================================================
FAIL-0005 - SOURCE POLICY CHANGED WITHOUT INTEGRITY MANIFEST UPDATE
===============================================================================

Date: 2026-08-20 America/Sao_Paulo
Area: Linux smoke / release integrity / source policy
Status: CLOSED / RELATED WHITE BOOK WB-0004

Observed failure:
Governance and .NET checks passed, but the Linux smoke stopped before runtime
startup because App/Config/data.policy.json no longer matched the application
release integrity manifest.

Cause:
The governance correction rewrote a runtime-integrity-controlled source policy
even though its existing approved contents already excluded operational UserData
and required a row-free schema contract. The change was unnecessary.

Correction:
- restore the approved policy blob exactly;
- enforce its existing declarations from the external governance validator;
- keep operational data removal outside the application source manifest;
- do not regenerate a release manifest for a governance-only correction.

Closure proof:
Commit bc395584b165f1b76f07ee66010c51066c68cc8c passed governance,
Python compile/Linux smoke and .NET 10.0.400 cross-target build in GitHub Actions
run 32433240298. HOME/WORK practical reproduction remains a separate system gate.

Lesson:
Do not rewrite an integrity-controlled runtime file merely to restate an existing
rule. First determine whether the current bytes already express the required
contract; enforce externally when no runtime behavior change is needed.

===============================================================================
FAIL-0006 - PORTABLE STARTUP LOST ITS CONTROLLED DATABASE SEED
===============================================================================

Date: 2026-08-20 America/Sao_Paulo
Area: Linux smoke / SQLite seed / portable body
Status: CLOSED / RELATED WHITE BOOK WB-0005

Observed failure:
After the approved policy bytes were restored, integrity validation passed but
Linux startup stopped because repository initialization requires the declared
Data/sistema.db seed before it creates isolated local state.

Cause:
The first sanitization correctly removed the operational database but treated the
entire Data root as forbidden. That removed a System prerequisite together with
UserData.

Correction:
- derive a new SQLite database containing the current schema objects only;
- require PRAGMA integrity_check=ok;
- require zero rows in every application table;
- store identical seed bytes in DEV Source and Git_Main System;
- allow no other Data file and no SQLite sidecar;
- keep all operational rows and attachments absent.

Prepared seed proof:
- SQLite tables: 27;
- application tables with rows: 0;
- indexes: 20;
- integrity: PASS;
- bytes: 344064;
- SHA256: d5ab9e4e389d6b026ba90d22e21bb1d93d20b1ace2f1b2451ea7ddfda6b98213.

Closure proof:
Commit bc395584b165f1b76f07ee66010c51066c68cc8c independently validated both
seeds, completed Linux startup from the row-free seed and retained the .NET
10.0.400 build PASS in GitHub Actions run 32433240298.

Lesson:
System data and UserData are separated by content and role, not only by folder
name. Sanitization must preserve a controlled row-free bootstrap prerequisite
while excluding every operational row and mutable file.

===============================================================================
FAIL-0007 - WORK WSL BOOTSTRAP COMMANDS WERE NOT TERMINAL-SAFE
===============================================================================

Date: 2026-08-21 America/Sao_Paulo
Area: Dev-Work / Windows PowerShell / WSL bootstrap
Status: CLOSED / PRACTICAL RETEST PASS / RELATED WHITE BOOK WB-0006

Context:
The WORK machine <LOCAL_MACHINE>, machine identity A5C486A67B75E1A4, was being
prepared with a dedicated Ubuntu-24.04 WSL2 distribution. Initial commands used
localized display text, repeated a satisfied WSL2 conversion and allowed adjacent
interactive commands to concatenate.

Correction:
- use the exact registered distribution identity;
- verify WSL2 state without repeating conversion;
- launch through the absolute Windows WSL executable with an explicit Linux user
  and explicit home directory;
- keep PowerShell host actions and Linux development actions visibly separated;
- validate identity, home, distribution, systemd and toolchain before continuing;
- treat the operator-selected Linux user as machine identity rather than imposing
  an unrelated fixed username.

Practical proof:
- distribution: Ubuntu-24.04;
- Linux user: carlos_alberto, UID 1000, sudo validated;
- OS: Ubuntu 24.04.4 LTS;
- kernel: Microsoft WSL2 x86_64;
- PID 1: systemd;
- home: /home/carlos_alberto;
- .NET SDK: 10.0.400;
- controlled Linux root: /cjl;
- exact Dev-Work clone completed and validated;
- production modified: NO.

Final classification:
WORK WSL bootstrap and deterministic shell handoff: PASS.

White Book relationship:
WB-0006 - Explicit WORK WSL identity and shell-boundary validation.

Lesson:
Interactive shell instructions are execution artifacts. State, shell, user,
directory, localization and prompt boundaries must be explicit before any
machine-changing command.

===============================================================================
FAIL-0008 - PRIVATE GITHUB ACCESS STARTED WITHOUT AUTHENTICATION PREFLIGHT
===============================================================================

Date: 2026-08-21 America/Sao_Paulo
Area: Dev-Work / WSL / GitHub authentication / Git LFS
Status: CLOSED / PRACTICAL RETEST PASS / RELATED WHITE BOOK WB-0007

Context:
The first private remote read used HTTPS before a supported authentication method
had been prepared. Git prompted for a username and password, and GitHub rejected
the password because password-based Git authentication is not supported.

Additional observed failure:
The first GitHub CLI web flow assumed a graphical Linux URL opener existed inside
the headless WSL environment. Automatic browser launch failed. The authorized
device flow still completed manually through the Windows browser.

Causes:
- private remote authentication was not a precondition of git ls-remote;
- a human password prompt was allowed even though it could not satisfy GitHub;
- WSL browser integration was assumed instead of detected;
- Git LFS was not yet included in the pre-clone toolchain gate.

Correction:
- install the current official GitHub CLI from its signed repository;
- authenticate TokDev-Carlos through the browser/device flow;
- configure Git to use the authenticated GitHub CLI credential helper;
- restrict the local credential file to owner carlos_alberto and mode 600;
- never copy credential contents into repository evidence;
- install Git LFS 3.7.1 from its official release after SHA256 verification;
- require authenticated ls-remote and exact Dev-Work SHA before clone;
- clone only Dev-Work and validate branch, origin, clean worktree and LFS objects.

Practical proof:
- authenticated account: TokDev-Carlos;
- credential owner: carlos_alberto;
- credential mode: 600;
- GitHub remote read: PASS;
- expected and cloned commit:
  e383abc37bbbdf7e81ede6a4f29c269a723bc699;
- Git LFS filtered objects: 7;
- Git LFS checkout payload: 874.14 MiB;
- git lfs fsck: PASS;
- active local branch: Dev-Work;
- worktree: CLEAN;
- remote branch created: NO;
- GitHub write during clone: NO;
- production modified: NO.

Final classification:
Private GitHub preflight, exact Dev-Work clone and Git LFS retrieval: PASS.

White Book relationship:
WB-0007 - Authenticated private remote preflight before clone.

Lesson:
A private clone begins with authentication, account, credential boundary and LFS
validation. A username/password prompt or implicit browser opener is not an
acceptable machine contract.

===============================================================================
FAIL-0009 - DOCKER DESKTOP WSL PROXY AND SOCKET UNAVAILABLE
===============================================================================

Date: 2026-08-21 America/Sao_Paulo
Area: Dev-Work / Docker Desktop / WSL2 integration
Status: CLOSED / PRACTICAL RETEST PASS / RELATED WHITE BOOK WB-0008

Context:
Docker Desktop was running and its Windows CLI files were present. The first WSL
gate found either no Docker API socket or a socket that the current WSL session
could not use. Docker Desktop also reported that the Ubuntu-24.04 user-distro
proxy stopped while its backend shared socket was unavailable.

Expected result:
The exact Ubuntu-24.04 user session can access a Docker Desktop Linux engine
through /var/run/docker.sock without sudo.

Observed failures:
- Docker CLI path existed but the WSL integration was not initially active;
- /var/run/docker.sock was absent after one restart attempt;
- an earlier session received permission denied on the Docker API;
- Docker Desktop reported a user-distro proxy/backend socket startup failure.

Correction:
- preserve the logs before changing state;
- stop WSL through the Windows host;
- start Docker Desktop and prove its desktop status is running;
- reopen the exact Ubuntu-24.04 session as carlos_alberto;
- wait for the integration socket;
- prove socket owner root, group docker and mode 660;
- prove the user session contains group docker;
- prove Docker client/server, Linux engine and Compose independently.

Closure proof:
- socket: /var/run/docker.sock;
- owner/group/mode: root/docker/660;
- user docker group: present;
- Docker client/server: 29.5.3/29.5.3;
- operating system: Docker Desktop;
- engine type: linux;
- architecture: x86_64;
- Compose: v5.1.4;
- final WORK audit Docker checks: PASS.

Lesson:
A visible Docker Desktop process and CLI file do not prove WSL API access. The
gate must test the user-distro proxy, socket, current group membership and engine
response in the exact Linux session.

===============================================================================
FAIL-0010 - COMPLETE EVIDENCE ARCHIVE TARGETED WINDOWS DRIVE ROOT
===============================================================================

Date: 2026-08-21 America/Sao_Paulo
Area: Dev-Work / evidence packaging / Windows filesystem
Status: CLOSED / PACKAGING RETEST PASS / RELATED WHITE BOOK WB-0009

Context:
The technical environment gate passed and its individual receipt archive was
created under C:\CJL_Work_Evidence. A later consolidation step attempted to
create a complete archive directly under C:\.

Observed failure:
Python zipfile returned PermissionError for the target
C:\CJL_WORK_EVIDENCE_COMPLETE_<run_id>.zip.

Cause:
The script selected the protected drive root without a write preflight. It also
wrote the technical PASS result and disabled the Bash ERR trap before every
packaging operation had completed.

Correction:
- confine every receipt and archive to C:\CJL_Work_Evidence;
- perform a write probe before evidence generation;
- classify technical audit and evidence packaging independently;
- never use C:\ as an inferred evidence destination;
- preserve the successful technical receipt when optional consolidation fails.

Closure proof:
The environment audit created its receipt directory and ZIP under the evidence
root and reported EVIDENCE_PACKAGING=PASS. Receipt archive SHA256:
e6de9b7b984964b171ec18ef6abf74d4e99015e51df6a0d5f597fdc32aa9476a.

Lesson:
A technical PASS and a packaging PASS are different gates. Validate the exact
destination before writing and never place generated evidence in a protected
filesystem root by assumption.

===============================================================================
FAIL-0011 - WINDOWS POWERSHELL 5.1 AUDIT COMPATIBILITY DEFECTS
===============================================================================

Date: 2026-08-21 America/Sao_Paulo
Area: Dev-Work / Windows PowerShell 5.1 / environment manager
Status: CLOSED / AUDIT REVISION 003 PASS / RELATED WHITE BOOK WB-0010

Context:
The first environment-audit revisions were statically checked outside Windows,
then executed by Windows PowerShell 5.1 on <LOCAL_MACHINE>.

Observed failures:
- revision 001 called String.Split with an overload interpreted as an invalid
  StringSplitOptions value;
- parsing WSL list output produced a false distro BLOCK because of native output
  encoding;
- revision 002 completed every technical check but generic .NET list aggregation
  failed while building the final PowerShell summary;
- the first interactive hash guard was followed by separately pasted commands,
  allowing the old file to run after its hash mismatch had already thrown.

Correction:
- use the PowerShell `-split` operator with a maximum result count;
- normalize native null characters and use a direct command inside the named WSL
  distribution instead of parsing localized list text as the primary proof;
- use native PowerShell arrays rather than generic .NET lists;
- run replacement, hash guard and execution inside one controlled script block;
- record exception line, position and stack in failure evidence;
- keep the stable filename and evolve revision metadata only inside the script.

Closure proof:
- manager internal revision: CJL-ENVIRONMENT-003;
- proven script SHA256:
  37dd5615ca2a5a778ccc4295ee54fdd8e85debfc9b167c8023aabf2b96637e62;
- final audit exit code: 0;
- blocking findings: 0;
- local development ready: YES;
- evidence packaging: PASS.

Lesson:
Static Bash validation does not prove Windows PowerShell 5.1 behavior. A guarded
target-host execution with exact hashes is required before the audit manager is
declared proven.
