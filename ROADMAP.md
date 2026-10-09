# Status and roadmap

## Implemented: headless adapter v0.1.0

Offline ingestion, provenance, deterministic jobs, strict imports, coverage, Markdown evidence export, source-plus-analysis outlines, compact image citation labels, image/revision contracts and cross-book synthesis contracts. The baseline has 95 passing synthetic tests.

## Proposed: shared knowledge ontology

Book → SourcePassage → Claim / Concept / Question / Action / Lens → Synthesis → Artifact, with typed relations, versioned revisions, integrity checks and correction records. No normalized ontology schema, migration engine, graph database or renderer integration is implemented yet.

## Proposed: one synthesis, three views

1. Migrate version-1 records without changing original evidence or receipts.
2. Freeze a reviewed synthesis and its transitive source closure.
3. Render enriched ledger, two-page executive HTML and sketchnote from that same revision.
4. Distinguish presentation corrections from meaning changes and mark stale outputs.
5. Verify multi-book disagreement and unequal coverage on synthetic/permission-cleared fixtures.

The planned HTML standard is key message first, a 2×2 matrix, three-circle diagram and journey map, within two print pages on both A4 and Letter. This is a requirement to implement and test, not a shipped renderer or a guarantee of current output.

## Separate future eligibility decision

A standalone ChatGPT sign-in adapter is not implemented. Text authentication eligibility does not imply image-generation eligibility or unlimited quota. No credentials are copied from another application.
