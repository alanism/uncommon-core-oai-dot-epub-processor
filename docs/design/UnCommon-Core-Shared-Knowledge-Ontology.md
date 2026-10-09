# Shared book knowledge ontology — proposed design

## Recommendation

Use one versioned, source-linked JSON knowledge ledger per book as the shared foundation for three outputs: the enriched ledger, an executive-summary HTML, and a sketchnote image. Add a collection-level synthesis layer for comparing books. Keep the HTML and image as views of an explicit synthesis revision, so a correction can propagate without rewriting the original evidence.

The intended home is **UnCommon Core OAI Dot ePub Processor**, repository slug `uncommon-core-oai-dot-epub-processor`. This document is a proposed design, not an implementation or publication receipt.

The first implementation should be a small adapter around the working parser and job contracts, rather than a new parser, a graph database, or an authentication project.

## What exists today

The inspected Python package has offline EPUB ingestion, passage IDs and source locations, deterministic analysis jobs, result validation, host execution receipts, selected-scope coverage, Markdown export, cited sketchnote outlines, image jobs and revisions, and cross-book synthesis job contracts. Its current ledger and workflow records use `schema_version: 1`.

Public examples use synthetic text and identifiers only. The package's current automated suite validates parser, job, receipt, citation and coverage contracts with synthetic fixtures. A successful contract test does not establish live-model quality, whole-book analysis or a shipped HTML renderer.

The planned executive HTML will use key message first, a 2×2 matrix, three circles and a journey map within two print pages. Conceptual diagrams must be labeled editorial synthesis. This renderer and a normalized shared ontology are not yet implemented. Existing Markdown and image-job workflows are separate from these proposals.

**Proposed additions:** explicit Concept, Question and Action nodes; versioned Lens references; a shared Synthesis record; graph relations; artifact manifests; review and correction records; and renderers consuming the same frozen synthesis. Cross-book job generation exists, but synthetic contract tests do not establish live cross-book output quality.

## The canonical model

The conceptual chain is:

`Book → SourcePassage → Claim / Concept / Question / Action / Lens → Synthesis → Artifact`

This is a graph of typed references, not a requirement to duplicate text at every step. Lens is configuration applied during analysis, not evidence derived from a passage. Use ordinary JSON files and indexes initially; a graph database can wait until query volume justifies it.

### Core record types

- **Book:** one exact EPUB edition/file, identified by the existing `sha256:<file hash>`. Keep title, author, source hash, parser version and rights/access metadata. An optional `work_id` can later group editions without collapsing their passage identities.
- **SourcePassage:** preserve the existing `id`, `book_id`, chapter and section metadata, `href`, real `element_id` if available, `cfi`, normalized text, ordinal, block ordinal and chunk ordinal. Keep raw EPUB bytes private and unchanged. Whitespace-normalized extraction is not an exact byte quotation.
- **Claim:** one proposition with `text`, existing `kind` (`source`, `interpretation`, `application`), exact `source_ids`, uncertainty, context and provenance. Add `epistemic_mode` to distinguish source quotation, source paraphrase, interpretation and application. Do not turn a cited paraphrase into a quotation.
- **Concept:** a reusable term plus a book-specific definition, cited occurrences and optional reviewed links to other definitions. Same label does not mean same concept. Keep interpretive labels distinct from terms used verbatim in the source.
- **Question:** wording, purpose, source/claim references and `question_role` such as author question, unresolved question or proposed interview question. Open questions remain open; an image must not imply they have been answered.
- **Action:** a proposed application with preconditions, cited rationale, expected observation and status. An action in a book or summary is not permission for the assistant to execute it. User-specific assignments and results belong in a separate private overlay.
- **Lens:** versioned persona/focus/depth configuration and prompt-definition hash. Keep the requested model preference separate from the actual model in the execution receipt. A lens changes framing, not the underlying source.
- **Synthesis:** scope, research question, cited key message, supporting node references, tensions, uncertainties, context and visual specifications. Each synthesis is a frozen revision. It must retain source references through every intermediate node.
- **Artifact:** ledger Markdown, HTML or image with MIME type, byte hash, producing run, exact synthesis revision, rendering configuration, source-label map and QA result. Artifact IDs should identify bytes; an alias such as “latest” is a separate mutable pointer.

### Shared metadata and evidence status

Give derived nodes `id`, `revision_id`, `created_by_run_id`, `source_ids`, `context`, `supersedes_revision_id` and `review`. Keep three independent status dimensions:

1. **Origin:** extracted source, model interpretation, user annotation or editorial transformation.
2. **Support review:** unreviewed, supported, partially supported, unsupported or disputed, with reviewer and reason. A successful schema import proves neither semantic support nor truth.
3. **Execution:** planned, completed or failed, with the actual imported receipt when present. A completed model run does not mean a human approved its conclusions.

Do not generate numerical confidence values unless a defined method supports them. Preserve “not reported” separately from “no” and “false.” Author assertions, illustrative anecdotes and measured findings should remain distinguishable through an evidence-basis field.

### Relations and referential integrity

Use relation records with `subject_id`, `predicate`, `object_id`, `source_ids`, context, origin and review. Initial predicates: `contained_in`, `supported_by`, `interpreted_through`, `defines`, `asks_about`, `applies`, `qualifies`, `contradicts`, `related_to`, `synthesizes`, `renders` and `supersedes`.

Evidence-bearing relations need source support. Administrative relations such as `renders` use run and artifact provenance instead. Reject dangling references and cross-book citations pointing to an absent edition. Flattening the transitive source references for each displayed statement makes export checks practical.

## Identity and source anchors

Preserve existing passage IDs exactly. The parser derives chapter IDs from book ID, reading-order position and href, and passage IDs from chapter ID, block ordinal, chunk ordinal and normalized text. They are stable for unchanged inputs and parsing rules, not universal IDs across editions or arbitrary parser changes.

For migrated claims, a reproducible seed is the immutable analysis job ID plus the result JSON pointer, as illustrated below. Pair it with the imported result hash: a new result from the same job must receive a distinct revision. New authoring can use generated entity IDs plus content-hashed revisions. Do not hash a display label alone or regenerate identities when a heading changes.

An anchor consists of the EPUB hash, resource href, real element ID where present, ordinals and a text hash. The current parser deliberately emits `cfi: null`; it does not supply page numbers. Keep that honest. If later adapters provide verified CFI or page mapping, record their adapter and edition.

Navigation labels can improve between parser revisions while old model jobs retain resource-name labels. Keep both as versioned metadata views. Do not edit old jobs or receipts merely to improve labels. A migration must verify unchanged passage IDs/text and record the metadata mapping.

Compact labels such as `[S1]` are presentation aliases. Preserve the existing image’s exact label map; never assume S1 is the first passage in reading order. Adding a source can change a newly generated sorted alias map, so pin aliases per artifact revision.

## Practical JSON example

The following is a **synthetic proposed wrapper projection**, not a complete book export or implemented schema. Repeated-character hashes are deliberately fictional design placeholders and must never pass as computed runtime provenance. The example makes no claim of a model or image execution.

```json
{
  "ontology_version": "0.1.0-proposed",
  "example_scope": "Synthetic design fixture only; not an executed model run or implemented schema",
  "book": {
    "id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "title": "Synthetic Field Notes",
    "author": "Example Author",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "passage": {
    "id": "passage:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "book_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "href": "OPS/chapter-01.xhtml",
    "element_id": "observation-1",
    "cfi": null,
    "ordinal": 0,
    "block_ordinal": 0,
    "chunk_ordinal": 0,
    "text": "Record a recent observation before forming a conclusion."
  },
  "source_snapshot": {
    "job_id": "job:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "json_pointer": "/sources/0",
    "text_storage": "Synthetic fixture source shown above"
  },
  "claim": {
    "id": "fixture:claim:1",
    "type": "Claim",
    "text": "The source recommends collecting an observation before drawing a conclusion.",
    "source_ids": [
      "passage:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ],
    "kind": "source",
    "uncertainty": "This short fixture supplies no evidence about how broadly the rule applies.",
    "epistemic_mode": "source_paraphrase",
    "support_review": "unreviewed",
    "origin": {
      "record": "synthetic-analysis.json",
      "pointer": "/result/claims/0"
    }
  },
  "lens": {
    "id": "lens:philosopher:example-v1",
    "type": "Lens",
    "lens": "philosopher",
    "focus": "Expert",
    "depth": "MBA",
    "status": "Proposed identifier; illustrative configuration"
  },
  "coverage": {
    "selected_passages": 4,
    "selected_analyzed_passages": 4,
    "book_passages": 8,
    "book_analyzed_passages": 4,
    "whole_book_analysis_complete": false
  },
  "run": {
    "job_id": "job:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "mode": "test-fixture",
    "status": "illustrative_not_executed",
    "receipt": null,
    "attestation_level": "no_execution_claim"
  },
  "artifact": {
    "id": "fixture:artifact:1",
    "type": "sketchnote_image",
    "artifact_ref": null,
    "mime_type": "image/png",
    "sha256": null,
    "status": "Proposed only; no image bytes exist",
    "synthesis_revision_id": null
  }
}
```

In production, use arrays or ID-keyed maps for `books`, `passages`, `nodes`, `relations`, `syntheses`, `runs`, `artifacts` and `corrections`. The single-object projection above keeps the mapping readable. A first JSON Schema should validate these normalized records separately from the existing version-1 importer. Avoid adding fields directly to existing model results: their schemas reject unknown properties.

## One synthesis feeding three outputs

The **enriched ledger** remains the detailed evidence view: original passages, analysis, questions, actions, uncertainties, source anchors, coverage and provenance. Retain both machine-readable JSON and human-readable Markdown.

The **executive HTML** presents the key message first and prints within two pages. Page one can hold the key message, scope badge, short supporting points and 2×2 matrix; page two can hold the three-circle diagram, journey map, cautions and source key. The full ledger can be a companion file or embedded downloadable payload outside print flow. Keep it local-first, self-contained and free of external trackers or asset requests. Revalidate A4 and Letter whenever content or CSS changes.

The **sketchnote** uses the same approved message, node references, source labels and scope wording. Its layout can be more visual, but it cannot silently add claims, omit a material caveat, or substitute a more dramatic conclusion. Keep a text alternative and evidence manifest alongside the raster image.

### Visual contracts

Every visual specification stores its type, cited node references, exact source IDs, labels, semantics and whether it is source-derived or an editorial interpretation. Each of the three interpretive visuals must also display a human-readable label such as ‘Editorial framework derived from selected passages’ and a compact citation key. This visible label is required in the HTML and sketchnote, not just in JSON metadata.

- **2×2 matrix:** name both axes, the meaning of each direction, all four cells and each cell’s citations. For a synthetic observation exercise, “direct versus inferred evidence” and “low versus high verification effort” could be an editorial organizing device. Do not manufacture measured scores, populate an unsupported cell, or present the axes as a framework quoted from the book.
- **Three-circle diagram:** name each set and explain any overlaps. “Observation,” “context” and “verification” are a possible cited interpretation of synthetic study notes. Equal circle sizes have no quantitative meaning. If overlap is only conceptual, say so; do not imply tested necessary-and-sufficient conditions for a conclusion.
- **Journey map:** stages, questions, observations, uncertainty and branching conditions. A synthetic application moves from an observation to a tentative explanation, a check, and a revised conclusion. Do not depict a proposed check as already completed, make a conclusion inevitable, or invent elapsed times.

These are proposed semantic contracts for a shared renderer. The currently implemented package does not provide the normalized ontology, executive HTML renderer or these diagram renderers. The image workflow uses a cited section outline.

## Corrections and reproducibility

A correction record should include target artifact/revision, optional region coordinates, relevant node/source IDs, the user’s request, classification, resolution and review result.

- **Presentation correction:** spelling, clipped labels or unreadable text. Regenerate or edit the image while preserving the semantic synthesis and source mapping. Record the exact edit prompt, input image checksum, prior image job ID, output checksum and receipt. This extends the image-revision chain already implemented.
- **Meaning correction:** wrong claim, source, scope or diagram implication. Create a new reviewed node/synthesis revision first; mark dependent outputs stale; regenerate all affected outputs. Never treat image pixels as the authoritative knowledge record.
- **Unclear correction:** keep it pending and ask for the intended meaning. Preserve earlier revisions and the reason for replacing them.

Pin the exact EPUB hash, parser/code revision, prompt/configuration hashes, job input, imported result, host receipt, selection, alias map and rendering assets. HTML can be byte-reproducible with pinned renderer inputs. Model text and image generation are not guaranteed to reproduce identical bytes; reproducibility here means reconstructable provenance and replayable inputs. Retain the actual output bytes. Receipts are host attestations, not signed proof of execution.

## Multiple books without false consensus

A collection manifest lists exact book editions and the analysis coverage for each. Cross-book synthesis uses a specific question and includes original passages as evidence; prior summaries remain fallible interpretations. Repeated analysis of one passage is not independent corroboration.

Keep each book’s definitions and claims separate, then propose reviewed concept alignments. Record contradictions as relations with both sides’ citations and the context in which they conflict. A claim about a classroom exercise and one about a laboratory study may differ in scope rather than contradict each other. Preserve conditions, audience, time and evidence basis before deciding.

A collection synthesis must surface unsupported alignment, unresolved disagreement and unequal coverage. It must not convert a majority of books into a truth score, infer consensus from missing passages, or summarize an unprocessed book as though it had been read. The synthetic integration tests do not establish production multi-book output quality.

## Proposed repository and manifest

```text
uncommon-core-oai-dot-epub-processor/
  README.md
  LICENSE                         owned-code Fair Source; four-year Apache conversion
  THIRD_PARTY_NOTICES.md           upstream source and attribution
  packages/headless-reader/       existing parser and workflow contracts
  packages/knowledge-model/       proposed types, validation and migrations
  packages/renderers/             proposed ledger, HTML and image adapters
  schemas/                       versioned normalized JSON schemas
  prompts/                       versioned additions and prompt manifests
  examples/synthetic/            redistributable fixtures only
  tests/                         integrity, coverage, rendering and security
  docs/                          architecture, host contract, auth status
```

Keep actual EPUBs, full extracted text, user annotations and private outputs outside the repository. A private runtime bundle can use `manifest.json`, `source/`, `knowledge/`, `runs/`, `artifacts/` and `corrections/`. The manifest should list schema and package versions, bundle ID, exact book hash, selection IDs, coverage, artifact relative paths/MIME/hash, synthesis revision IDs, run IDs and current revision pointers. Validate relative paths against traversal and verify bytes before opening artifacts.

Use semantic versions for the new ontology independently of the existing integer `schema_version: 1`. Start with a proposed `0.1.0`; incompatible changes require explicit migrations and a new major schema version once stable. Preserve original input/record files, write migrations to new paths, and include migration checksums and reports. Pin dependencies and release the parser adapter and renderers together only after compatibility tests pass.

The release's custom Fair Source license applies only to material Alan Nguyen owns or is authorized to license. Earlier AGPL grants remain intact, and upstream native-reader or third-party components are not relicensed. See the root LICENSE and THIRD_PARTY_NOTICES.md. Nothing here authorizes publishing books, private annotations or user artifacts.

## Host and authentication boundary

The working path is **host-assisted**: the package creates and validates jobs; the surrounding dot host performs text analysis and image generation. The offline package itself requires no API key. Host-assisted execution uses the surrounding host’s own authorized capabilities; that statement applies to the host workflow, not to a general standalone executable, an unlimited subscription entitlement or a new authentication implementation.

Standalone **Sign in with ChatGPT** is a possible future adapter only after current eligibility review; no OAuth flow is implemented. This custom Fair Source license must not be assumed to qualify under an open-source program. The package’s documented references are [token sharing](https://developers.openai.com/siwc/token-sharing-open-source), [models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), and [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations). Recheck eligibility and current requirements before implementation. Keep image generation a separate host capability; do not infer that a future text authentication route includes it. Never copy another application’s credentials or silently fall back to billed API usage.

Book content is untrusted data. Preserve the existing offline/no-tool execution boundary and DRM rejection. The proposed manifest and renderers must escape source HTML and avoid evaluating code, loading remote resources or allowing source text to trigger actions. Public export requires an explicit content/rights review; a private Git repository is not a substitute for permission to upload sensitive or copyrighted source material.

## MVP acceptance criteria and implementation order

1. **Normalize without replacing ingestion.** Convert existing version-1 ledgers and records into the proposed wrapper. Test all passage IDs, text hashes, source anchors, record hashes and coverage counts against the originals. Preserve differing metadata snapshots.
2. **Freeze a shared synthesis.** Add typed nodes, relation validation, reviewed key message and the three visual contracts. Reject invented citations, incomplete source closure, duplicate identities and unsupported scope upgrades.
3. **Render all three views.** Verify every visible claim resolves to the same synthesis and source IDs. Test two-page printing on A4 and Letter, readable labels, offline asset loading, and an accessible text alternative.
4. **Close the correction loop.** Test presentation-only edits versus meaning changes, dependency invalidation, preservation of old outputs, image byte verification and alias-map consistency.
5. **Exercise a second book safely.** Use synthetic or permission-cleared fixtures to test conflicting definitions, genuine disagreement, contextual differences, uneven coverage and repeated evidence. Do not invent a production multi-book result.

Keep the existing EPUB, prompt, workflow, integration and regression tests. Add golden serialization/migration tests, broken-reference tests, malformed manifests, unknown-version rejection, stale-artifact detection, explicit partial-coverage checks, failed/fixture receipt rejection, source prompt-injection cases, and tests showing that artifact corrections cannot mutate source evidence. Before sharing a repository, scan tracked content and history for private books, annotations and credentials.

## Design basis and status

This public proposal is derived from the version-1 headless parser, workflow and prompt contracts. It contains only synthetic examples. It does not implement a normalized ontology, create an HTML renderer, establish model execution or authorize publication of private content. The shipped package and ROADMAP.md are the implementation-status authority.
