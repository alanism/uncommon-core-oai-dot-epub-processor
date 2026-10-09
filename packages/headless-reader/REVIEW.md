# Independent review

Reviewed 2026-10-09. Scope: this additive Python package, its CLI, EPUB parser,
prompt contracts, result/receipt validation, coverage, Markdown export, image
citation mapping, and synthetic tests. This was a manual code review with
adversarial regression testing, not a repository-wide or certified security audit.

## Final result

No unresolved high- or medium-severity findings were identified in this bounded
review after the fixes below. All **95 package tests passed** on Python 3.12,
including 10 independent review regressions. `python -m compileall -q
ucc_headless` and CLI help also passed. The six reference-file SHA-256 values in
`SOURCE_PORT.md` matched the supplied upstream snapshots.

Commands, run from this directory:

```sh
python -m unittest discover -s tests -v
python -m compileall -q ucc_headless
python -m ucc_headless --help
```

## Findings resolved and retested

- Result contracts: empty claim uncertainty is accepted consistently with the
  prompts; nested unexpected fields, invalid citations, oversized outline
  bullets, and too many sections are rejected before downstream use.
- Receipts: impossible dates, invalid timezone offsets, unfinished executions,
  changed job/result hashes, and unexpected credential fields are rejected.
  Synthetic fixtures do not count as production analysis.
- Selection: partial selections of a batched analysis expand explicitly to retain
  dependencies. Requested and effective sources, expansion, and scope are hashed.
- Parser resource safety: repeated spine references fail before chapter parsing;
  XML depth/node limits apply before allocation. Archive, passage, navigation,
  metadata/locator, and serialized-output limits fail explicitly without a
  success-shaped partial ledger.
- Source fidelity: one-character chunk sizes fail explicitly instead of producing
  unusable whitespace passages. MathML structural loss is reported as a content
  omission. Doctype-like prose in CDATA is never silently deleted; unsupported
  forms fail closed.
- Rendering: image citation aliases have a reversible canonical source mapping
  included in the hashed job. Original outline citations remain intact. Markdown
  escapes existing backslashes before brackets/backticks and exports each batched
  analysis once.

Adversarial probes included ZIP traversal, canonical-name collisions, symlinks,
encryption flags, excessive compression, invalid CRC, XML entities/DTDs, deep
structure, source-boundary closing tags, invented citation fields, malformed
receipts, and external media/script content. A targeted ingestion/job test blocked
socket creation and subprocess launching and still passed. Production code
contains no credential-store access, network client, model invocation, subprocess
execution, extraction to disk, or native-provider import.

## Remaining boundaries

- Hashes establish consistency, not identity. Imported receipts are unsigned host
  attestations and can be forged by their author. Accept only trusted host output.
- Citation membership is validated; semantic support and model accuracy require
  source review. Prompt escaping is not a model-level injection-proof sandbox.
- Image references/checksums are supplied by the host. This package does not fetch
  or authenticate image bytes or prove an image was generated.
- Parsing completeness describes supported spine processing. Media, formulas,
  excluded executable/style content, and unsupported EPUB features have separate
  omissions or explicit failures. Resource limits intentionally reject some books.
- Only synthetic data was used in these tests. No private EPUB, real credential,
  or private execution result is included in the package.
- No full native repository checkout, native/frontend/Rust aggregate CI,
  standalone OAuth eligibility, live-provider behavior, Python 3.11 execution, or
  real-model/image quality was verified by this review.
