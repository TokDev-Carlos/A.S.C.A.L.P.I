# Souvenir Memory Protocol

Status: IMMUTABLE ENTRY PROTOCOL
Document Identity: SOUVENIR MEMORY PROTOCOL
Internal Revision: 001
Date: 2026-08-20
Timezone: America/Sao_Paulo
Text Policy: English ASCII-only

## Purpose

Reconstruct valid project memory before an execution cycle without depending on cached conversation context, an agent brand, a temporary workspace or a filename that embeds a revision. This protocol is entity-neutral.

## Mandatory read sequence

At the start of every new execution cycle:

1. read the repository execution contract completely;
2. read this Souvenir protocol completely;
3. identify the current repository, branch, project, scope and stage;
4. locate the scope-specific Souvenir file under the current AI entity root;
5. read the scope-specific Souvenir completely;
6. compare remembered decisions with current repository evidence;
7. report any conflict and use the applicable source-of-truth order;
8. continue only from the latest valid and authorized state.

Repeat this sequence whenever a new cycle starts, even inside the same conversation or session.

## Scope-specific discovery

A scope-specific memory uses a stable descriptive filename:

Souvenir_<Scope>.md

The scope name is stable. A revision is recorded inside the file and never added to its filename.

Do not guess a scope-specific path. Determine the active scope from the repository contract, skill registry or project instructions. If the required file is missing, mark memory as unavailable and stop any decision that depends on it.

## Evolution rules

- newer approved decision supersedes the older active rule;
- new compatible information accumulates;
- redundant information is unified;
- incorrect or discarded information is removed from active memory;
- historical proof remains recoverable through Git or evidence records;
- conceptual information includes its justification and boundary;
- immutable information is explicitly marked IMMUTABLE;
- unverified information is marked UNVERIFIED;
- future planning is not represented as implemented behavior.

## Document identity rule

Document filenames remain stable. Internal revision, status, compatibility, approval and change history belong inside the document.

Do not use a revision-bearing external identifier as the operational identity of another document. Do not use a relative path as normative authority. Paths may be used for navigation only.

Exact historical states are proven by commit SHA, snapshot and content hash.

## End-of-read gate

After reading the scope-specific Souvenir:

1. classify the recovered context as ALIGNED, CONFLICT or INCOMPLETE;
2. resolve conflicts against current repository evidence and authorized human decisions;
3. record the exact branch, commit, scope and stage being used;
4. state the next permitted workflow step;
5. continue only when the applicable entry gate is satisfied.

Memory alignment is not release approval. Human or Operator approval remains required wherever the project contract requires it.

END OF SOUVENIR PROTOCOL
