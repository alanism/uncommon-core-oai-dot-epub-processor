# Source port and prompt contracts

## Pinned upstream

The prompt layer is adapted from `alanism/UCC-Reader-Engine-Apple`, commit
[`c5e57408b69444fc09fbd0dfd7e683d7b8517d13`](https://github.com/alanism/UCC-Reader-Engine-Apple/commit/c5e57408b69444fc09fbd0dfd7e683d7b8517d13).
The reference modules were supplied as local snapshots. No live provider endpoint,
credential, desktop runtime, or network was used to develop or test this port.

Snapshot SHA-256 values:

| Module | SHA-256 |
| --- | --- |
| `learningService.ts` | `f3d7fe1cdc3933bf2d0cccb22a73a0c2504a3e4b6d9c9a4e9e9733761de26c5b` |
| `learningConstants.ts` | `8c70b5622cdcac80289718644c6f1c42e53685aa4bece2d5b18eb67737d4c37c` |
| `sketchnoteService.ts` | `550102bc8c0cebeb2532c29480eae5858ba4d8faf6fff816b1a7615f6476577f` |
| `sketchnoteTypes.ts` | `a9648d85b0cc07a2a3211e4312c8fae164300dbebee425c53fda2fb609fd8b65` |
| `types.ts` | `a01ac2dd830f84e540c21cacea4c6be461095b02f3a57b520971657ec642c09a` |
| `ledgerService.ts` | `287c771b4ba77d2c0e4ff13c94e49b372ed5f1fbd25bf4ca1f5efec9cd0c6672` |

## What was reused or adapted

### Analysis

- `learningService.ts: buildAnalysisInstruction` supplies the construction pattern:
  selected persona, explanation depth, analysis focus, and a separate untrusted source
  payload. `analysis_prompt()` returns `{system, instructions, input}` instead of a
  native `NormalizedLearningAIRequest` or provider request body.
- `learningConstants.ts: PERSONAS` is ported with every value and nested field unchanged
  for all eight lenses: `fun_science_guy`, `contrarian`, `philosopher`, `journalist`,
  `study_buddy`, `therapist`, `ela_editor`, and `mathematician`. Python mapping syntax
  replaces TypeScript object syntax. Persona definitions are never loaded from source
  passage metadata.
- `BASE_LEARNING_SYSTEM_PROMPT` provides the ebook-assistant role, untrusted-source
  boundary, source-as-evidence rule, implicit persona behavior, and final-output-only
  principle. Its free-text output requirements are deliberately replaced by the
  cited JSON contract. Evidence rules take precedence over rhetorical persona traits.
- `EXPLANATION_DEPTH_INSTRUCTIONS` retains the original text for `5th Grader`,
  `8th Grader`, and `MBA`.
- `ANALYSIS_FOCUS_INSTRUCTIONS` retains the native focus names and conceptual frameworks,
  but adapts free-form output requests to structured cited claims. In particular,
  `Reels` can no longer suppress citations, and narrative/rubric preferences cannot
  require fabricated supporting material. Unknown lens/focus/depth values fail explicitly.
- Defaults are `lens="philosopher"`, `focus="Expert"`, and `depth="MBA"`.

### Source boundaries and provenance

- `learningService.ts: escapePromptBoundaryText` and `wrapUntrustedPromptBlock` provide
  the boundary concept. The port serializes whole input objects as JSON, escaping every
  literal `<`, `>`, and `&` in JSON strings before placing them inside fixed tags. This
  prevents a hostile field from closing a block or introducing a literal markup tag.
  JSON decoding recovers exact source content, including Unicode, whitespace, IDs,
  metadata, and embedded delimiter-like strings. No source text enters the system role.
- `formatProjectSynthesisLedgerEntry` and `sketchnoteService.ts:
  formatSketchnoteLedgerEntries` provide the separation between primary source text,
  identifying metadata, and analysis notes. The headless version keeps passage records
  and prior analyses in separate structured blocks rather than combining them into
  interpolated prose.
- `ledgerService.ts: formatLedgerExport` and `formatGroupedEntryMarkdown` inform the
  preservation of source text, analysis, IDs, chapter, and location metadata. Their
  Markdown serialization, date formatting, native save/share hooks, compression, and
  import heuristics are not copied into the prompt layer.
- The source contract is a passage record with `id`, `book_id`, `chapter`, `section`,
  `href`, `element_id`, `cfi`, `text`, and `ordinal`. Present fields and any additional
  JSON metadata are retained. The prompt builder requires unique nonempty string IDs
  and nonempty text; it does not manufacture missing location metadata or CFIs. EPUB
  ingestion is responsible for validating the full provenance contract.

### Sketchnote outline and image

- `sketchnoteService.ts: buildSketchnoteStructuringPrompt`,
  `SKETCHNOTE_STRUCTURING_SYSTEM_PROMPT`, and `SKETCHNOTE_OUTLINE_SCHEMA` inform
  `outline_prompt()` and `OUTLINE_SCHEMA`.
- The one-page portrait layout, blank paper, concise title, concrete visual anchors,
  under-120-character bullet preference, preservation of tension, and six visual-thinking
  mappings are retained: Portrait, Chart, Map, Timeline, Flowchart, and Multiple-variable
  plot. Interpretive visuals must not invent quantities or imply unsupported causality.
- `sketchnoteTypes.ts: SketchnoteOutline` supplies the `meta`/`sections` shape. Bullet
  strings become `{text, source_ids}` objects to preserve traceable citations.
- Four to eight sections remain the normal writing target. The minimum is deliberately
  relaxed to one for sparse evidence, rather than forcing padding; eight is the maximum.
  Empty or duplicate sections are rejected. Bullet text is strictly under 120 characters
  (119 Unicode code points maximum), excluding source IDs.
- `sketchnoteService.ts: buildSketchnoteRenderingPrompt` supplies the image prompt's
  Moleskine canvas, exact palette (`#FFF8DC`, `#134686`, `#ED3F27`, `#FEB21A`, `#FDF4E3`),
  title/heading lettering, visual grammar, modular/path/vertical/radial composition,
  legibility, exact meaning, and no-grid/no-spread constraints. `image_prompt()` adds
  visible exact source-ID labels and safely enclosed untrusted outline JSON.
- `normalizeSketchnoteOutline` is not ported as lossy normalization. The image builder
  rejects invalid layout, missing citations, duplicate IDs, too many sections, and
  oversized bullets; it does not slice sections, clip text, discard invalid bullets,
  normalize source wording, or invent section IDs.

### Cross-source synthesis

- `learningService.ts: buildProjectSynthesisRequest` supplies the research-synthesizer
  role, context-based relevance, one concise key message, source-grounded supporting
  ideas, traceability, and JSON-only response.
- `PROJECT_SYNTHESIS_SCHEMA` and `types.ts: ProjectSynthesisResult` supply the concepts
  of a key message and source-linked supporting ideas. Their original
  `relevantQuotes`/`keyMessage`/`supportingIdeas` shape is deliberately replaced by the
  headless analysis shape plus `key_message: {text, source_ids}`. This is an adapter
  contract, not wire-format compatibility with native project synthesis.
- `synthesis_prompt()` accepts the research question as a safely enclosed relevance
  query, not an instruction that can override source rules. It requires explicit
  disagreements and uncertainties, and citations to all sides of material conflicts.
  Prior analysis is fallible interpretation and must be checked against original text;
  repeating an analysis does not create independent corroboration.

## Deliberate strengthening and limits

1. Every substantive claim, disagreement, outline bullet, and synthesis key message
   requires nonempty exact source IDs. Distinct `source`, `interpretation`, and
   `application` claim kinds prevent silent promotion of the assistant's ideas into
   statements made by a book. Citations prove record membership, not semantic support;
   both the host and the user still need to assess support.
2. All source fields, prior analyses, query text, and outline content are untrusted.
   JSON escaping prevents structural delimiter breakouts, but a text prompt is not a
   security sandbox and cannot guarantee resistance to model-level prompt injection.
   Host execution must independently enforce its no-tools/no-network/source-only policy.
3. There is no silent input truncation. Upstream `applyTokenBudget`,
   `budgetLedgerEntries`, `compressSourceText`, and `applySourceTextMode` are excluded.
   If a host context window cannot fit a job, the host must reject or explicitly split
   it with coverage accounting; it must not claim to have processed unseen material.
4. Claims and disagreements can be empty where the evidence cannot support them;
   uncertainty and missing context must be explicit instead of creating filler claims.
5. JSON schemas set `additionalProperties=false`; source-ID membership and response
   structure must be checked by the workflow importer. Prompt generation alone does
   not validate a model's eventual response.
6. Functions are deterministic and standard-library-only. They do not mutate caller
   inputs, perform provider discovery, read environment credentials, use network calls,
   choose a runtime model, generate an image, or claim a model execution occurred.

## Native gate and host model preference

The existing native availability gate in `learningService.ts: runRequest`, the desktop
check in `sketchnoteService.ts: getOpenAISketchnoteKey`, `learningSecretsAvailable`,
`aiSecretStore`, provider HTTP implementations, image endpoints, and native save/share
paths remain unchanged and are not imported. This package adds a separate text-contract
adapter; it does not bypass or weaken the native gate and does not repurpose desktop keys.

The requested processing preference is the fast, low-cost Luna model. That preference
is metadata for the host; it is not a verified API model ID or proof of actual execution.
The prompt functions intentionally do not choose a model. Requested preference and the
actual host-reported executor/model belong in separate job/receipt fields. An unavailable
Luna route requires an explicit resolution rather than an undisclosed heavier fallback.
Image generation similarly remains a separate host action, with its own actual result
and receipt; returning `image_prompt()` text is not image generation.

## Offline validation

Run from this package directory:

```sh
PYTHONPATH=. python -m unittest discover -s tests -p test_prompts.py -v
```

Tests cover defaults and all eight lenses, output schemas, metadata and Unicode
round-tripping, over-budget source retention, hostile closing tags in source IDs/text,
previous-analysis and query isolation, disagreement/citation requirements, no mutation,
invalid input rejection, rendering palette, cited image content, and explicit rejection
rather than clipping. These are prompt-contract tests, not live-model quality claims.

## Deterministic image citation aliases

Rendering maps sorted canonical source IDs to compact S1, S2, etc. labels. The
semantic outline keeps source_ids unchanged; the image job stores source_aliases
and its prompt includes a separate untrusted alias map for accompanying evidence.
Only bracket labels render on the page, preventing long hashes from overwhelming
legibility. The alias map belongs beside the exported ledger, and the exact image
prompt (including aliases) is covered by the image job hash.
