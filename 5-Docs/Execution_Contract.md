# CJL Execution Contract

Status: HOMOLOGATED
Revision: EXEC-CONTRACT-008
Prior Revision: EXEC-CONTRACT-007
Date: 2026-08-23
Timezone: America/Sao_Paulo
Operator Approval: APPROVED
Digital Signature: PENDING
Language: English
Operational Text Policy: ASCII-only

# THIS DOCUMENT IS HOSTED AT

Repository:
TokDev-Carlos/CJL-System

Canonical path:
1-Dev/System/Flow/Execution_Contract.md

This document is the mutual execution contract between the Operator, AI agents,
developers, HOME, WORK, GitHub, the Linux development environment, the Compiler,
the Windows pre-production environment and the real CJL MAIN.

Every accepted revision must preserve prior Git history, identify the prior
revision, state the reason for change and identify Operator approval.

The real CJL MAIN production root is permanently:

C:\CJL\System

Any active operational reference to C:\System is invalid.

===============================================================================
1. FINAL AUTHORITY AND ACCEPTANCE
===============================================================================

The Operator is the final authority for CJL development acceptance.

Approval is based on:

requested behavior
-> delivered behavior
-> practical result
-> expected result
-> approval or rejection

AI agents and developers may analyze, propose, implement, test, document and
recommend. They do not replace final Operator approval.

A release is not approved only because it compiled or because an automated test
returned PASS.

===============================================================================
2. TWO SELF-SUFFICIENT AI WORKING CONTEXTS
===============================================================================

Context A - GitHub persistent memory

GitHub contains the durable repository tree, contracts, README guidance, stage
requirements, accepted decisions, evidence references, procedures and evolutive
technical memory.

Context B - OpenAI or other AI temporary workspace

The AI workspace is temporary. Before work starts, it must reconstruct current
context from GitHub.

Required pattern:

GitHub
-> read root
-> read branch identity
-> read complete Execution Contract
-> read Knowledge
-> read active stage
-> read applicable Steps
-> read component/tool/language guidance and Skills
-> execute
-> test
-> document
-> persist accepted work to GitHub

The temporary AI workspace is never an independent permanent authority.

===============================================================================
3. GITHUB IS THE FIXED MEETING POINT
===============================================================================

GitHub is the fixed communication and synchronization point between AI temporary
workspaces, HOME, WORK, future approved DEV hosts, developers and the Operator.

All DEV environments must understand the same relative tree, branch model and
stage meaning. An official engineering state must be traceable to an exact Git
commit and branch identity.

Detailed project recording does not require one Git commit per recorded action.
Evidence, Logs, Receipts, Black Book, White Book and cumulative documentation may
contain multiple chronological events inside one logical Git transaction.

Git commits represent coherent engineering state transitions. They are not
individual receipts for every file write, API call, command or documentation
append.

Canonical branch governance is defined by root `BRANCHES.md`. Every permanent
branch must also carry root `BRANCH.md` describing its role and owner line.

===============================================================================
4. ROOT READ ORDER
===============================================================================

Before any CJL engineering action, read in this order:

1. CJL-System/README.md
2. root BRANCH.md
3. 1-Dev/System/Flow/Execution_Contract.md completely to END OF CONTRACT
4. Knowledge/INDEX.md
5. README.md for the active stage
6. required Step README files for that stage in numeric order
7. README.md for the affected component, tool or language area
8. applicable technical reference documents
9. applicable Skill from the Skills repository when needed
10. current evidence and known issue records relevant to the task
11. relevant Black Book and White Book references

This order applies at the beginning of every execution cycle, not only at the
beginning of a conversation, session or development day.

No agent may begin from remembered repository structure or branch identity when
current GitHub state is available.

===============================================================================
5. LOCAL README MEMORY CONTRACT
===============================================================================

Every CJL-authored README must be classified as one of:

GOVERNANCE
DESCRIPTIVE
MIRRORED
THIRD_PARTY

GOVERNANCE applies to README files that authorize, sequence, permit, block or
control engineering work, including root, stage, Step and Flow guidance.

A GOVERNANCE README must contain or clearly inherit:

- Status
- Revision
- Date
- Timezone
- Execution Contract stable identity and current internal compatibility rule
- purpose and scope
- allowed actions
- forbidden actions
- required inputs
- required reading
- procedure or flow
- Evidence requirements
- PASS criteria
- FAIL or STOP criteria
- next allowed state

DESCRIPTIVE applies to a CJL directory README whose main purpose is to define the
role of a folder rather than control an execution gate.

A DESCRIPTIVE README must contain or clearly inherit:

- purpose
- owner stage
- allowed content
- forbidden content
- canonical effect
- governing README or Execution Contract

MIRRORED applies to README material carried inside a byte-exact mirror such as:

3-Git_Main/System/**

MIRRORED README content must not be rewritten merely to satisfy repository
governance formatting. Its bytes are governed by the mirror contract.

THIRD_PARTY applies to upstream/vendor documentation. Preserve upstream content;
do not rewrite it to CJL formatting merely for conformance.

The documentation tree exists so an authorized AI or developer can reconstruct
intended behavior without fragile conversational memory.

===============================================================================
6. EVOLUTIVE MEMORY RULE
===============================================================================

Important technical memory must not be silently destroyed.

A document may be ADDED, UPDATED, CORRECTED, SUPERSEDED, MERGED, DEPRECATED or
ARCHIVED.

A relevant update records, as applicable:

- what changed
- why it changed
- prior rule
- new rule
- supporting evidence
- date
- approving authority

Historical mistakes remain useful engineering knowledge when context is
preserved. No AI may erase project memory merely because a newer approach exists.

===============================================================================
7. OPENAI WORKSPACE RULE
===============================================================================

The OpenAI workspace is a temporary engineering table.

Normal flow:

read GitHub
-> reconstruct context
-> confirm Dev-A.I branch identity when AI-owned work is persisted
-> analyze real components
-> edit
-> run available tests
-> prepare documentation/evidence/manifests/hashes
-> persist accepted candidate work to Dev-A.I
-> identify whether the human developer is working on HOME or WORK
-> route the candidate to Dev-Home or Dev-Work
-> reproduce and test there when required
-> obtain human review on that selected line
-> only then use the human-line integration route

Files that exist only in the temporary workspace are not official CJL state.

Dev-A.I never integrates directly into main. AI agents may not self-approve
their work, select an unknown human route or bypass required HOME/WORK evidence.

===============================================================================
8. REPRODUCIBILITY BETWEEN AI, HOME AND WORK
===============================================================================

Anything developed in a temporary AI environment and accepted into GitHub must
be reproducible from GitHub on HOME or WORK when the applicable gate requires it.

Required invariant:

same selected Git source identity
+ compatible locked toolchain
+ compatible dependencies
= equivalent development result

Machine-specific state is not blindly copied between HOME and WORK.

Permanent development branches are:

Dev-Home
Dev-Work
Dev-A.I

main is the complete portable repository body. Every development branch inherits
that body and acts as an extension. Extension means the branch-specific Git diff,
not a partial copy of the repository.

Dev-Home and Dev-Work are independent human working lines. Dev-A.I is a controlled
candidate line. Portable approved changes move through selective integration;
machine-specific operational state does not.

===============================================================================
9. MACHINE IDENTITY
===============================================================================

Each DEV machine has independent identity including, as applicable:

- machine_id
- line
- role
- OS
- architecture
- hardware profile
- toolchain profile
- permissions profile
- inventory revision
- last validation state

Current physical development lines:

HOME
WORK

AI/cloud development uses `Dev-A.I` as a repository owner line, but a branch name
is not a substitute for physical machine identity.

At DEV operation start:

find machine config
-> validate
-> if missing, require setup
-> if invalid, STOP

No patch may assume machine identity only from a folder or branch name.

===============================================================================
10. MACHINE INVENTORY
===============================================================================

Inventory should include what is required to reproduce and diagnose the
environment, including OS, CPU, RAM, storage, GPU when relevant, WSL, Linux
distro, Docker, Git, .NET, Python, Node, build tools, services, permissions and
DEV role.

Do not publish secrets, passwords, tokens, private keys or live credentials into
Git.

===============================================================================
11. PRIVILEGE AND EXECUTION CONTROL
===============================================================================

Before an elevated action:

check required privilege
-> if sufficient, continue
-> if elevation is required, request approved elevation
-> if elevation fails, STOP

No CJL tool may bypass OS authorization controls. Partial mutation caused by
insufficient privilege is unacceptable.

===============================================================================
12. MACHINE IDENTITY IN GIT EVIDENCE
===============================================================================

Git alone does not attach complete machine inventory to every event.

CJL must use wrappers, hooks, receipts or machine-readable metadata when needed
to associate engineering evidence with:

- commit SHA
- branch name
- machine_id
- HOME, WORK or AI owner line
- developer/operator identity
- stage
- run_id
- test result
- timestamp
- evidence location

This must support statements such as "Passed on HOME and failed on WORK" without
guessing.

===============================================================================
13. PATCH FRESHNESS CHECK
===============================================================================

Before applying a DEV patch, compare it with current authorized GitHub state when
connectivity is available.

local patch
-> query GitHub
-> compare identity/version
-> current: continue
-> newer patch exists: NEW_PATCH_FOUND

NEW_PATCH_FOUND requires Operator choice to use the newer patch or explicitly
continue with the older patch.

If the older patch continues:

- local execution may continue under warning
- status OUTDATED_PATCH
- status REVIEW_REQUIRED
- canonical cloud promotion blocked
- DEV UI may display NEW_VERSION_AVAILABLE

An outdated result must not silently become canonical GitHub state.

===============================================================================
14. GITHUB UNAVAILABLE DURING FRESHNESS CHECK
===============================================================================

If GitHub cannot be reached:

SOURCE_FRESHNESS_UNKNOWN

Operator choices:

RETRY
CANCEL
CONTINUE_LOCAL_WITH_WARNING

Local continuation does not authorize canonical promotion until freshness is
revalidated.

===============================================================================
15. CANONICAL DEVELOPMENT TREE
===============================================================================

Logical CJL engineering root:

/Dev_CJL/

Execution stages:

1-Dev
2-Compiler
3-Git_Main

Transversal knowledge root:

Knowledge

Root branch-governance files:

BRANCH.md
BRANCHES.md

Knowledge is not an execution stage. It is shared cumulative engineering memory.

Required Knowledge structure:

Knowledge/
  README.md
  INDEX.md
  Black_Book/
    INDEX.md
    VOLUME-001.md
  White_Book/
    INDEX.md
    VOLUME-001.md

Black and White Book volumes summarize and connect knowledge across stages. They
do not replace original Evidence, Logs, Receipts, test reports or stage-local
records.

Human development flow:

Dev-Home / Dev-Work
-> applicable 1-Dev work
-> LINUX_TESTED when required
-> DEV Handoff
-> human developer review
-> selective approved integration into main
-> MAIN_INTEGRATED

AI candidate flow:

Dev-A.I
-> candidate and isolated evidence
-> selected Dev-Home or Dev-Work
-> required local reproduction and human review
-> human development flow
-> main

Direct Dev-A.I -> main integration is forbidden.

Downstream engineering flow from the approved integrated identity:

main
-> 2-Compiler
-> WINDOWS_BUILD
-> 3-Git_Main
-> WINDOWS_TESTED
-> ENCODING_TEST
-> ROLLBACK_TEST
-> OPERATOR_APPROVED
-> production precheck
-> C:\CJL\System
-> MAIN_VERIFY
-> MAIN_STABLE
-> station release gate

A task may require additional branch-local validation before integration. Missing
applicable evidence is never treated as PASS.

===============================================================================
16. 1-Dev - LINUX DEVELOPMENT
===============================================================================

Each DEV machine uses the approved Linux development line based on Ubuntu 24.04
LTS under the CJL WSL development model.

1-Dev is where active source work happens. It may contain source changes,
modules, hooks, tools, candidates, experiments, patch definitions, tests and
engineering documentation.

1-Dev is flexible compared with pre-production, but it is not uncontrolled.

Normal active development must occur on the branch that owns the working line:
Dev-Home, Dev-Work or Dev-A.I.

===============================================================================
17. AI LINUX TO LOCAL LINUX EQUIVALENCE
===============================================================================

If a change is declared functional in the AI Linux engineering workspace, it
must also pass required local Linux tests on HOME or WORK before Windows
compilation when that gate applies.

The AI environment need not be physically identical, but must use compatible
engineering assumptions, toolchain contracts and dependencies.

If local Linux validation fails, promotion stops.

===============================================================================
18. LOCAL LINUX FAILURE
===============================================================================

On required Linux validation failure:

FAIL
-> stop promotion
-> preserve evidence
-> restore or return to last known-good DEV state where required
-> record failure
-> update rejection knowledge
-> correct in 1-Dev
-> retest

It does not enter main integration or 2-Compiler while the blocking gate remains
failed.

===============================================================================
19. BLACK BOOK - CONTEXTUAL REJECTION MEMORY
===============================================================================

The Black Book is a cumulative transversal knowledge volume for failed or
rejected procedures with context.

It does not replace original Evidence, Logs, Receipts, test reports or
stage-local records. The original record remains primary technical proof.

A Black Book entry records as applicable action, context, target, expected and
actual result, failure, evidence, reason, environment, conditions, possible
future reuse context, correction state and related White Book entry.

Required model:

failure
-> preserve original stage evidence
-> classify
-> summarize contextual lesson in Black Book
-> reference original evidence
-> keep future correction linked

A Black Book entry must not erase, relocate or rewrite original failure evidence.
A rejected technique is rejected for its recorded context, not necessarily for
all future use.

===============================================================================
20. WHITE BOOK - VALIDATED KNOWLEDGE
===============================================================================

The White Book is a cumulative transversal volume for validated procedures and
useful knowledge such as proven tools, reliable commands, correct patterns,
known-good configurations, successful builds and successful recovery methods.

It does not replace original Evidence, Receipts, Logs or test results.

A correction or technique may enter the White Book as PROVEN only after required
validation succeeds.

Reference as applicable:

- related Black Book entry
- original failure evidence
- corrective implementation
- validation evidence
- exact commit/artifact identity
- environment and proven conditions

Required model:

Black Book failure
-> correction
-> retest
-> PASS evidence
-> White Book validated knowledge

A proposed correction is not White Book knowledge until proven.

===============================================================================
21. NO GHOST DECISIONS
===============================================================================

Do not use:

FAIL -> forget

Use:

FAIL
-> preserve original evidence
-> record/classify
-> Black Book
-> correct
-> retest

If correction passes:

PASS
-> preserve validation evidence
-> link Black Book record
-> White Book proven knowledge
-> preserve exact conditions and identity

A decision without a traceable reason is not acceptable project memory.

===============================================================================
22. PERMANENT ENCODING DOMAIN CONTRACT
===============================================================================

CJL separates SYSTEM, CODE and USER_DATA.

SYSTEM:
- English operational names
- ASCII-only operational paths, identifiers, config keys and commands
- no hidden Unicode execution dependency

CODE:
- English identifiers
- ASCII-only machine-influencing names and control text
- predictable encoding
- no hidden Unicode execution dependency

USER_DATA:
- may preserve native language and Unicode when required
- must display correctly
- must not become the only technical identity of an entity

===============================================================================
23. USER DATA TECHNICAL IDENTITY
===============================================================================

Human-readable text is data, not the primary technical key.

Recommended model:

entity_id
display_name
search_key
content_hash

Preserve original human Unicode text where required. Use stable entity_id for
internal references and a separate normalized search key when needed.

===============================================================================
24. 1-Dev TEST PROFILE
===============================================================================

1-Dev tests are fast, structural, semantic and source-oriented compared with
3-Git_Main.

As applicable test syntax, source structure, static analysis, unit/integration,
config/schema, dependencies, path/naming/ASCII policy, encoding/BOM, source
integrity and organization.

Required state before applicable integration/handoff:

LINUX_TESTED = PASS

===============================================================================
25. DEV HANDOFF
===============================================================================

DEV Handoff freezes the exact source proposed for integration and downstream
Compiler use.

Record source commit/tree identity, source branch, machine_id, HOME/WORK/AI owner
line, changed files/scope, required Windows tests, dependencies, warnings and DEV
receipt.

Any source change after Handoff invalidates affected tests and requires a new
Handoff.

If the source is Dev-A.I, Handoff ends at the selected Dev-Home or Dev-Work line.
It must be reproduced and reviewed there. It does not integrate directly into
main.

After the applicable human-line DEV gates pass, the Handoff is reviewed by the
human developer before the approved logical changeset is integrated into main.

===============================================================================
26. 2-Compiler PURPOSE
===============================================================================

2-Compiler compiles everything required for CJL to execute correctly on Windows.
Development remains Linux-controlled.

Normal Compiler input is an exact approved source identity from `main` after the
required DEV branch validation, Handoff and human developer integration gate.

Locked active toolchain:

.NET SDK 10.0.400
.NET 10 LTS
C# 14
Windows x64
Windows API floor 10.0.19041.0

Windows 11 x64 is the primary supported build and homologation lane.

Windows 10 Pro 22H2 build 19045 is a compatibility lane only. A supported
acceptance claim requires recorded active Extended Security Updates entitlement
and current security state. The API floor does not grant OS support.

Architecture and OS support must be proven by build/runtime evidence.

===============================================================================
27. FUTURE WEB READINESS
===============================================================================

WEB is not the primary runtime today. New architecture should avoid unnecessary
choices that block future cloud/Web integration.

Future-compatible concerns may include cloud transport, remote APIs, online
services, hybrid processing, hosted components and remote integrations.

This does not require converting CJL into a Web application now.

===============================================================================
28. COMPILER DOES NOT FIX SOURCE
===============================================================================

If Compiler discovers a source defect:

STOP
-> return to owning development branch
-> correct source in 1-Dev
-> rerun Linux validation
-> new DEV Handoff
-> human developer review
-> new approved main integration
-> rebuild

Forbidden:

Compiler finds source error
-> silently edits source
-> build passes

This breaks traceability.

===============================================================================
29. WINDOWS RELEASE CANDIDATE
===============================================================================

2-Compiler produces an exact candidate with declared runtime files and
dependencies, source SHA, build_id, package manifest, artifact/manifest SHA256,
toolchain/dependency identity and build receipt.

Only a frozen verified candidate may enter 3-Git_Main.

===============================================================================
30. 3-GIT_MAIN PURPOSE
===============================================================================

3-Git_Main is the practical Windows pre-production test field. Its controlled
System must reproduce the behavior/layout expected from C:\CJL\System.

3-Git_Main != real CJL MAIN.

Normal pre-production use must not use real users, live production DB/UserData,
live credentials or live operational workload.

A separately authorized one-time bootstrap may preserve current test/synthetic
state when required to create the initial controlled twin, provided production
secrets are excluded and the bootstrap remains isolated until validated.

===============================================================================
31. REAL PATCH APPLICATION IN 3-GIT_MAIN
===============================================================================

3-Git_Main must use a controlled application method for the exact audited
patch/release candidate. The patch process itself must be tested; manual file
copying until it appears to work is not homologation.

The normal candidate entering this stage is already compiled for the intended
Windows runtime profile.

===============================================================================
32. PRACTICAL WINDOWS TESTS
===============================================================================

As applicable test patch apply, startup, functional use, shutdown, restart,
update, backup, snapshot, rollback, recovery, integrity, encoding, database,
permissions, dependencies, error handling and logs.

A practical PASS makes the exact candidate eligible for Operator approval. It
does not mean MAIN_DEPLOYED.

===============================================================================
33. PATCH FAMILY - BA
===============================================================================

BA represents Business Architecture or Business Rule change. BA may be
non-structural or structural. Structural BA is critical and requires isolation,
controlled update, service restoration, station behavior testing and rollback
proof as applicable.

Risk is based on real impact, not only the BA label.

===============================================================================
34. PATCH FAMILY - ES
===============================================================================

ES represents structural patching and is always treated as critical.

Examples include folder movement, code relocation, architecture redefinition,
storage/core contract changes and structural migrations.

Tests consider as applicable server offline, station disconnect, interrupted
update, safe power-loss simulation, blocked access, partial copy, rollback,
recovery and data isolation.

===============================================================================
35. PATCH FAMILY - IN
===============================================================================

IN represents increments/implementations such as modules, features, appearance,
interaction, functions, filters and lightweight DB extensions.

Typical risk is LOW or MODERATE, but actual impact overrides the label.

===============================================================================
36. PATCH FAMILY - SE
===============================================================================

SE represents Security changes and security validation.

Conceptual layers:

SE-1 authentication/direct credential resistance
SE-2 unauthorized access/data manipulation/hostile-access simulation
SE-3 structural security, dependency, code/config hardening and standards review

Testing must be controlled and isolated. Do not use destructive malware on live
CJL systems. Preserve restoration capability.

===============================================================================
37. SECURITY TEST RESTORATION
===============================================================================

After security testing, test-induced state must be restored to expected baseline
or explicitly preserved as evidence under the test contract.

No hidden corruption may remain.

===============================================================================
38. FINDING OUTSIDE CURRENT PATCH SCOPE
===============================================================================

If a test finds an issue:

inside current approved scope?
YES -> correct -> retest -> evidence
NO  -> register -> classify -> pending work -> do not silently expand scope

A finding may be important without belonging to the current patch.

===============================================================================
39. PATCH TIMELINE AND VERSION FAMILIES
===============================================================================

Primary families:

BA
ES
IN
SE

System version derives from approved family states. Current format model:

BA.ES.IN.SE

Example:
1.05.01.006

Counters may grow beyond initial visual width. Do not truncate valid counters to
preserve an old width.

===============================================================================
40. ISSUE SEVERITY FOR DEVELOPMENT FLOW
===============================================================================

Minimum classes:

BLOCK - cannot advance
WARN - may advance only under defined gate when impact is understood
INFO - does not block approval
DEFERRED - intentionally moved to future work with traceability and approval as
required

Examples of BLOCK include data corruption, build failure, critical encoding or
security defect, structural inconsistency and rollback failure.

===============================================================================
41. DEV WARNING INDICATORS
===============================================================================

DEV or 3-Git_Main may show developer-only indicators such as Known issue,
Deferred issue, New version available, Pending correction or Unresolved warning.

These must not automatically leak into production-facing UI.

===============================================================================
42. ACCEPTED NON-BLOCKING ISSUE
===============================================================================

issue
-> analyze impact
-> classify
-> evidence
-> Operator decision when required
-> DEFERRED if accepted

Preserve backlog/evidence and remove DEV-only warnings from production-facing
release without erasing engineering memory.

===============================================================================
43. NO UNCLASSIFIED SMALL ERROR EXCEPTION
===============================================================================

Do not use:

"It looks harmless" -> continue

Use:

issue -> impact analysis -> classification -> evidence -> gate decision

WARN may cross a stage only when the contract allows. BLOCK may not.

===============================================================================
44. LOCAL HISTORY RETENTION
===============================================================================

A DEV machine need not keep every historical working copy locally.

Initial local recovery target:

Current
Previous-1
Previous-2
Previous-3

Longer engineering history remains in GitHub.

===============================================================================
45. FORMAL HISTORICAL RETRIEVAL
===============================================================================

If old material is actually required:

request
-> justify
-> authorize
-> retrieve exact identity
-> use read-only where possible
-> record access/result

Do not restore large obsolete trees only "just in case".

===============================================================================
46. SKILLS REPOSITORY
===============================================================================

Repository:
TokDev-Carlos/Skills

Purpose:
evolutive AI capability memory for languages, tools, architecture, security,
database, debugging, patching, build, testing and documentation.

Skill history must not be automatically deleted. Merge/deprecation/archive
requires traceable governance and approval where defined.

Skills is not a production runtime dependency.

===============================================================================
47. DOCS REPOSITORY
===============================================================================

Repository:
TokDev-Carlos/Docs

Purpose:
restricted formal documentation, legal records, ownership evidence, signatures,
certificates, scans and formal provenance.

Docs is not a runtime dependency and normal engineering should not require
unrestricted access.

===============================================================================
48. DOCS ACCESS CONTROL GATE
===============================================================================

Docs has an additional Operator-intent control gate even when the API technically
has permission.

The counter-password is a control confirmation, not the cryptographic boundary.
Real security remains repository/API permissions and credential handling.

The counter-password value must not be stored in this contract.

===============================================================================
49. DOCS ACCESS FLOW
===============================================================================

request Docs operation
-> verify necessity
-> explicit Operator authorization
-> request Docs control counter-password
-> failure: STOP
-> success: execute only approved scope
-> record access/action when required

Do not reveal or infer the control answer from project documentation.

===============================================================================
50. RESPONSIBILITY BETWEEN STAGES
===============================================================================

Stages and branches may provide evidence/requirements to each other but must not
silently take another stage or owner line's responsibility.

Examples:

Dev-A.I finds source change -> AI evidence -> selected HOME/WORK line -> local validation -> human review
1-Dev finds build requirement -> records -> Compiler builds
3-Git_Main finds source defect -> runtime evidence -> return to owning DEV branch
Compiler finds missing official tool knowledge -> block -> obtain/record reference
-> resume only when understood

Each stage owns its gate. Each permanent development branch owns its working line.

===============================================================================
51. COMPLETE MASTER FLOW
===============================================================================

OPERATOR
-> GITHUB main portable body, contract and branch governance
-> select originating line
-> if AI: Dev-A.I -> selected Dev-Home or Dev-Work
-> if human: Dev-Home or Dev-Work
-> branch freshness against main
-> 1-Dev Ubuntu 24.04 LTS
-> sync/freshness
-> edit
-> Linux tests
-> LINUX_TESTED when required
-> DEV Handoff
-> human developer review on HOME or WORK
-> selective approved integration from Dev-Home or Dev-Work into main
-> MAIN_INTEGRATED
-> 2-Compiler
-> Windows build/package/verify
-> WINDOWS_BUILD
-> 3-Git_Main
-> exact Windows candidate
-> practical/stress/security/encoding/rollback tests as required
-> Operator review
-> HOMOLOGATED
-> freeze exact release
-> real MAIN precheck
-> C:\CJL\System
-> MAIN_VERIFY
-> MAIN_STABLE
-> production acceptance
-> station release gate
-> stations

Failure paths return to the responsible branch/stage with evidence.

===============================================================================
52. GLOBAL INVARIANTS
===============================================================================

1. GitHub is the persistent meeting point and engineering contract.
2. AI workspaces are temporary.
3. HOME and WORK are independent but structurally equivalent DEV lines.
4. 1-Dev is the normal source editing stage inside an owning development branch.
5. 2-Compiler compiles Windows output and does not silently rewrite source.
6. Windows compilation occurs before final practical Windows homologation.
7. 3-Git_Main is an isolated practical Windows pre-production environment.
8. 3-Git_Main must behave like intended real MAIN where relevant.
9. Real MAIN root is always C:\CJL\System.
10. C:\CJL\System is never the development/homologation laboratory.
11. BUILD PASS does not mean WINDOWS TEST PASS.
12. WINDOWS TEST PASS does not mean MAIN DEPLOYED.
13. Missing evidence is not PASS.
14. Change after a frozen gate invalidates affected downstream evidence.
15. Update-induced MAIN failure requires rollback to known-good state.
16. Station release remains CLOSED until exact MAIN release is stable and
    explicitly accepted.
17. Failed procedures are remembered with context.
18. Successful procedures are remembered with context.
19. A failed technique is rejected for its execution context, not every future
    use.
20. System/code operational control text remains ASCII-safe.
21. User data may preserve native-language Unicode without becoming sole
    technical identity.
22. No unclassified issue silently crosses a gate.
23. Docs access requires the Operator-intent gate.
24. Skills and Docs support the project but do not control runtime behavior.
25. Operator remains final approval authority.
26. Every new execution cycle re-reads root README, branch identity and complete
    current contract.
27. Black/White Books are cumulative transversal knowledge and never replace
    original evidence.
28. Detailed recording does not imply one Git commit per recorded event.
29. Related changes from one logical engineering cycle should be consolidated
    into one coherent commit unless an independent technical checkpoint requires
    separation.
30. Connector/API implementation details must not dictate CJL commit history.
31. CJL-authored README files must remain classified and compatible with the
    active Execution Contract.
32. MIRRORED and THIRD_PARTY README files must not be rewritten merely to satisfy
    CJL documentation formatting.
33. main is the complete portable repository body and canonical integration state.
34. main is not a direct experimental branch or the real production system.
35. Permanent extension branches are Dev-Home, Dev-Work and Dev-A.I.
36. Every permanent branch carries root BRANCH.md identity.
37. Development branches persist after integration; approved changesets move, not
    necessarily entire branches.
38. Dev-A.I never integrates directly into main.
39. AI work first routes to the human-selected Dev-Home or Dev-Work line.
40. Integration into main originates only from Dev-Home or Dev-Work and requires
    valid non-redundant scope, applicable evidence and human developer approval.
41. Machine-specific operational state is never blindly synchronized between
    Dev-Home, Dev-Work and Dev-A.I.
42. Operational UserData, databases, secrets, caches and mutable runtime state are
    forbidden in the active portable repository body.
43. Legacy temporary branches must not receive new work after their permanent
    replacement is established.
44. The active .NET SDK is locked to 10.0.400 with latest-patch roll-forward only.
45. Windows 11 is the primary supported lane; Windows 10 Pro 22H2 requires
    documented active ESU state for a supported acceptance claim.

===============================================================================
53. DOCUMENT EVOLUTION, REVISION HISTORY AND SIGNATURE
===============================================================================

This contract is homologated as internal revision EXEC-CONTRACT-008.

Revision identity and change history remain inside this stable document. Exact
historical bytes remain proven by Git commit SHA and content hash.

Revision 001 - initial homologated mutual CJL execution contract.

Revision 002 - added central Knowledge, cumulative Black/White Books and complete
contract reload between execution cycles.

Revision 003 - classified README documents, separated cumulative records from Git
commit granularity and established coherent logical transactions.

Revision 004 - established permanent main, HOME, WORK and AI lines, branch-local
identity and reviewed selective integration. Its valid rules remain, except where
revision 007 explicitly corrects branch responsibility.

Revision 005 - established stable document filenames, internal version metadata,
the neutral Souvenir protocol and scope-specific evolutive memory.

Revision 006 - corrected the placement of the Souvenir section at the true end of
the contract without changing its approved meaning.

Revision 007 - current approved correction:

- defines main as the complete portable repository body;
- defines Dev-Home and Dev-Work as human extensions over that body;
- defines Dev-A.I as a controlled candidate extension;
- forbids direct Dev-A.I -> main integration;
- requires AI work to pass through the human-selected HOME or WORK branch;
- removes operational UserData and mutable runtime state from the active tree;
- keeps historical contaminated states recoverable without history rewriting;
- unifies the former external contract changelog into this section;
- locks .NET SDK 10.0.400 and C# 14 for the active Windows host;
- makes Windows 11 the primary supported lane;
- limits Windows 10 Pro 22H2 supported acceptance to recorded active ESU state;
- adds executable governance, route and data-boundary validation.

Reason for revision 007:

The prior model incorrectly allowed Dev-A.I to appear as a direct main source and
treated main as a narrow integration subset rather than the complete portable
body. The development tree also contained operational database rows and files in
areas that its own data policy classified as excluded. The corrected model keeps
one complete body, isolates branch extensions and prevents operational data from
crossing repository gates.

Approval:

Human Developer explicitly authorized these GitHub, branch, documentation,
toolchain and Skills corrections on 2026-08-20 America/Sao_Paulo.

Revision 008 - current approved clarification:

- preserves the prohibition on direct Dev-A.I branch/candidate/code integration;
- defines BOOK_RECORD_DIRECT as main-based path-limited Book persistence;
- permits only Knowledge/Black_Book/** and Knowledge/White_Book/** on that route;
- forbids source, config, AI branch state, Machine state, credentials, UserData and
  runtime content on the record-only path;
- preserves HOME/WORK review for every broader AI change.

Reason: the permanent Dev-A.I branch contains branch-local AI state, so the
Operator's narrow PASS/FAIL recording exception must be represented as record
persistence rather than whole-branch integration.

Approval: Operator authorized this reconciliation on 2026-08-23
America/Sao_Paulo.

Every future revision records the prior revision, new revision, changed rules,
reason, evidence, approval and effective date in this section.

Digital signing, when used, must preserve exact signed bytes, file SHA256,
signature metadata, signer identity, verification evidence and timestamp. A later
revision never alters prior signed bytes or validity evidence.
===============================================================================
54. MANDATORY CONTRACT RELOAD BETWEEN EXECUTION CYCLES
===============================================================================

CJL work is executed in controlled execution cycles.

A cycle normally contains:

context reconstruction
-> analysis
-> permitted action
-> execution
-> validation/inspection
-> evidence/documentation
-> result classification
-> cycle close

A cycle is considered closed on an applicable PASS, FAIL, STOP, BLOCK, PENDING,
DEFERRED, HANDOFF, OPERATOR DECISION, STAGE TRANSITION, PATCH TRANSITION, BRANCH
TRANSITION or completion of the currently authorized action.

If more work remains, the next cycle must not begin only from conversation,
previous AI reasoning or cached context.

Mandatory reentry:

1. read current CJL-System/README.md
2. read root BRANCH.md
3. read this Execution Contract completely to END OF CONTRACT
4. read Knowledge/INDEX.md
5. read active stage README
6. read required Step README files in numeric order
7. read applicable component/tool/language/Skill guidance
8. read relevant current Evidence, Black Book and White Book references
9. confirm exact Git commit, branch, stage and current task state
10. only then begin the next cycle

A prior reading does not authorize skipping this requirement. Newest authorized
GitHub state governs when documentation changed.

Required loop:

CYCLE
-> CLOSE
-> RETURN TO ROOT
-> READ ROOT README
-> READ BRANCH IDENTITY
-> READ COMPLETE EXECUTION CONTRACT
-> READ CURRENT KNOWLEDGE
-> READ ACTIVE STAGE
-> CONFIRM CURRENT STATE
-> NEXT CYCLE

This remains mandatory until the requested engineering task is fully closed or
the Operator explicitly stops the work.

===============================================================================
55. LOGICAL GIT TRANSACTION AND COMMIT CONSOLIDATION
===============================================================================

A Git commit represents one coherent engineering state transition.

Do not create a separate Git commit merely because:

- one file was created;
- one file was updated;
- one Evidence entry was appended;
- one API write occurred;
- one command completed;
- one README was adjusted.

During one authorized execution cycle, related accepted changes should be
accumulated and committed together when they represent the same logical result.

Preferred model:

EXECUTION CYCLE
-> analyze
-> modify related files
-> test
-> update Evidence
-> update cumulative documentation
-> update Black/White Book when applicable
-> validate final repository state
-> ONE LOGICAL COMMIT
-> record resulting commit SHA
-> close cycle

A separate commit is justified when an independent technical identity is needed,
including:

- a test requires an exact intermediate commit SHA;
- an independent rollback boundary is required;
- a frozen candidate must be tested separately;
- security or structural isolation requires it;
- an unrelated logical change must remain independently reversible;
- the Operator explicitly requires a separate commit.

Tool implementation must not dictate project history. If a cloud file API creates
one commit per file, prefer an available multi-file Git tree/commit operation for
a multi-file logical change.

Do not intentionally generate micro-commit chains solely because a connector
writes files individually.

Historical published micro-commits remain part of the audit trail. Do not rewrite
published history merely to make it visually cleaner without explicit Operator
authorization.

===============================================================================
56. README CONFORMANCE AND CONTRACT ALIGNMENT
===============================================================================

Every CJL-authored README and root branch-governance document must remain
compatible with the current homologated Execution Contract.

A contract change requires README and branch-governance impact analysis.

If the change affects global behavior such as root read order, execution cycles,
stage responsibility, branch responsibility, evidence, commit governance,
approval gates, Knowledge, Black Book or White Book, all applicable GOVERNANCE
README files and BRANCH documents must be audited before the governance cycle
closes.

A README or BRANCH contradiction with the current contract is not silently
ignored.

Use:

document mismatch
-> classify
-> correct or explicitly defer
-> verify
-> record conformance

Do not modify MIRRORED or THIRD_PARTY README content merely to satisfy CJL
governance formatting.

Maintain cumulative conformance matrix at:

1-Dev/System/Flow/README_CONFORMANCE.md

Minimum fields:

Path
README/document class
Owner
Current revision
Execution Contract compatibility
Status
Last audit date
Notes

Allowed statuses:

ALIGNED
PARTIAL
STALE
EXEMPT_MIRRORED
EXEMPT_THIRD_PARTY
BLOCK

A BLOCK governance mismatch that can direct an agent into an invalid action must
be corrected before that action is executed.

===============================================================================
57. PERMANENT BRANCH OWNERSHIP AND MAIN PROMOTION
===============================================================================

Canonical branch:

main

Permanent development branches:

Dev-Home
Dev-Work
Dev-A.I

Root `BRANCHES.md` is the canonical branch map. Root `BRANCH.md` identifies the
currently checked-out permanent branch.

Responsibilities:

main:
- complete portable repository body;
- canonical integrated engineering state;
- approved source, contracts, governance, tests and controlled artifacts;
- no operational UserData or branch-local physical inventory;
- no normal experimental feature development.

Dev-Home:
- HOME-owned development and validation;
- HOME machine evidence, receipts and reproducible working state;
- no blind WORK or AI machine-state synchronization.

Dev-Work:
- WORK-owned development and validation;
- WORK machine evidence, receipts and reproducible working state;
- no blind HOME or AI machine-state synchronization.

Dev-A.I:
- AI/cloud analysis, development, isolated testing and candidate preparation;
- AI-generated PASS is evidence, not approval;
- no fabricated physical machine inventory;
- no direct integration into main.

AI route:

Dev-A.I
-> select Dev-Home or Dev-Work from the human work location
-> selectively integrate the candidate into that human line
-> reproduce and test as required
-> human developer review
-> human-line integration rule

Human-line integration rule:

Dev-Home or Dev-Work
-> compare with current main
-> classify scope
-> remove redundant, obsolete and branch-local changes
-> run applicable tests
-> prove operational UserData is absent
-> preserve evidence
-> human developer review
-> APPROVED
-> selectively integrate approved logical changeset into main
-> verify resulting main state

Operator approval remains required where this contract separately requires it.

Development branches normally persist after promotion. Changesets move; branch
identity is not consumed by promotion.

Legacy transition:

`bootstrap/git-main-initial-clone` is superseded for new work by `Dev-Home`.
Its history remains valid provenance until the legacy ref is safely removed.

`governance/exec-contract-002` is superseded. Its valid governance content is
already contained in later approved contract revisions and must not be developed
further.

Do not blindly synchronize UserData, caches, credentials, machine identity or
operational state between development branches. These items are also forbidden
from the active portable main body.

===============================================================================
58. PORTABLE BODY, DATA BOUNDARY AND WINDOWS TOOLCHAIN
===============================================================================

main is the complete portable repository body. It contains the current approved
system source, contracts, reproducible declarations, tests, controlled candidate
material and navigation required to reconstruct engineering work.

Development branches inherit that body. Their branch-specific diffs contain only
the extension work, evidence and identity allowed for HOME, WORK or AI.

Active repository content must not include operational database rows, UserData,
clients, works, operations, photos, generated business documents, credentials,
caches or mutable runtime state. Schema and synthetic fixtures are allowed only
when explicitly classified and unable to disclose real operational identity.

The exact controlled Data/sistema.db seed is System data, not UserData. It is
allowed only when SQLite integrity passes, all application tables contain zero
rows, DEV and Git_Main bytes match and no sidecar is present.

Historical commits containing prior state remain immutable provenance. Correcting
the active tree does not authorize rewriting or deleting Git history.

The active Windows host toolchain is .NET SDK 10.0.400, .NET 10 LTS, C# 14 and
win-x64. global.json locks the SDK with latest-patch roll-forward and no
prerelease.

Windows 11 x64 is the primary supported build and homologation target. Windows 10
Pro 22H2 build 19045 is a compatibility lane only and requires a receipt proving
active ESU entitlement and current security state for supported acceptance.

Governance automation must block forbidden AI routing, stale document identity,
operational data, missing portable-body structure and toolchain drift.

===============================================================================
59. STABLE DOCUMENT IDENTITY AND SOUVENIR CYCLE MEMORY
===============================================================================

Every active governance document keeps one stable descriptive filename.

Revision, status, compatibility, approval, supersession and change history remain
inside the document. A consumer must not pin another document by a
revision-bearing identifier. Relative paths are navigation aids and are not
normative authority.

Exact historical states remain provable by Git commit SHA, snapshot and content
hash. Historical logs may retain prior revision identifiers as facts.

At the beginning of every execution cycle, after this contract is read completely:

1. read the neutral Souvenir.md in the current authorized AI entity root;
2. identify the active project and scope from this contract and repository state;
3. read the scope-specific Souvenir file completely;
4. compare recovered memory with the current branch, commit and evidence;
5. classify context as ALIGNED, CONFLICT or INCOMPLETE;
6. resolve or stop on blocking conflict;
7. identify the next permitted workflow step;
8. continue only through the applicable contract gates.

The current CJL scope memory identity is CJL DEV CORE SOUVENIR. Its filename is
stable and its internal revision is not copied into this contract as a
compatibility pin.

At the end of context reconstruction, memory alignment may be homologated as
context. It does not approve a build, patch, release, production promotion or an
AI agent's own work.

===============================================================================
60. BOOK_RECORD_DIRECT - RECORD-ONLY MAIN PERSISTENCE
===============================================================================

All earlier statements forbidding `Dev-A.I -> main` remain authoritative for
branch, candidate, source, code, configuration and release integration.

BOOK_RECORD_DIRECT is not an integration edge. Its write base and destination are
current main. Allowed changed paths are only:

Knowledge/Black_Book/**
Knowledge/White_Book/**

The record must identify originating AI evidence when available. Any other changed
path invalidates this route and returns the change to the normal selected
HOME/WORK route. The record never constitutes AI self-approval, build approval,
release approval or production approval.

END OF CONTRACT
