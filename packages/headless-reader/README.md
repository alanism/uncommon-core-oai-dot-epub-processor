# UnCommon Core OAI Dot ePub Processor — headless package

A separate, offline Python 3.11+ package for OAI dot and other trusted hosts. It reads DRM-free EPUBs into source-linked passages, exports deterministic enrichment jobs, validates imported results, and builds citation-preserving sketchnote and cross-book synthesis jobs. It does not start a server, execute book content, call a model, read credentials, or change the native reader's AI gate.

## First run (no install needed)

From this directory:

```sh
python -m unittest discover -s tests -v
python -m ucc_headless ingest /private/input/book.epub /private/output/ledger.json
python -m ucc_headless jobs /private/output/ledger.json /private/output/jobs.json
```

Outputs refuse overwrites. Keep outputs outside the checkout. `jobs.json` is a list: give one job at a time to a trusted host. Adjacent passages are batched within their chapter up to `--job-chars` (default 6000 source characters), avoiding a model call per paragraph. This is a source-character budget, not a token-window guarantee. The host must obey the job's source-as-data security boundary, perform the actual model invocation, return the structured result, and provide its execution receipt. This package cannot force another host's behavior or attest that a supplied receipt is truthful.

The default enrichment preference is **Luna / fast-low-cost** (configurable with `--model-preference` on jobs, outline and synthesis). It is a human-facing preference, not an invented API model ID. The host must record the actual model used and must not silently substitute a heavier model. EPUB parsing itself is deterministic and uses no model.

## Host-mediated workflow

1. Read each analysis job; its ID hashes its exact source, configuration and prompt. Default lens/focus/depth: Philosopher / Expert / MBA.
2. Execute with the host's existing model capability. Follow the structured contract embedded in the prompt; every claim cites existing passage IDs and distinguishes source evidence, interpretation, and application. Preserve uncertainties and disagreements.
3. Write `{job_id, result, receipt}`. Required receipt: `executor`, actual `model`, `execution_id`, ISO-8601 `completed_at`, `status: completed`, `mode: host-model`, `job_hash` (job ID without `job:`), `result_hash` (`workflow.digest(result)`). Never invent a provider response ID. A host session/task ID is appropriate when that is the available execution identifier.
4. Import one job/result pair:

```sh
python -m ucc_headless import job.json response.json record.json
```

5. Combine imported records into a JSON list, then:

```sh
python -m ucc_headless coverage ledger.json records.json coverage.json
python -m ucc_headless markdown ledger.json records.json ledger.md
python -m ucc_headless outline records.json outline-job.json --ledgers ledger.json --source-ids SOURCE_ID
python -m ucc_headless import outline-job.json outline-response.json outline-record.json
python -m ucc_headless image outline-record.json image-job.json
```

`--source-ids` is an explicit partial selection. A selection intersecting a batched analysis expands to the whole batch to preserve its supporting citations; `scope.requested_source_ids`, `scope.selected_source_ids`, and `scope.expanded_to_preserve_analysis_batches` expose this exactly. Omitting it requires analysis for every source passage. Every selected source and its imported enriched analysis are included; no head/middle/tail sampling or silent budget truncation. For very large books, select chapter-sized batches and retain the coverage ledger. An oversized job is an explicit host batching decision, never permission to omit sources.

6. A trusted image host reads `image-job.json` and invokes its available image-generation tool. The job is a tool contract, not a pretend rendered image. Import the actual `{artifact_ref,mime_type,sha256}` with `mode: host-image`. Artifact references are opaque; the package does not fetch them. Verify image bytes and deliver the file through the host. The image uses compact [S1] citation labels; preserve `image-job.json.source_aliases` beside the ledger so each label resolves to its full canonical source ID. For a correction, use `image-revision image-record.json exact-edit-prompt.txt revision-job.json`; it preserves the original job ID, input artifact checksum, source mapping and new exact prompt. Keep both imported generation and revision receipts. Image availability and limits belong to that host; no paid API fallback occurs.
7. For multiple books:

```sh
python -m ucc_headless synthesis records.json synthesis-job.json --ledgers book-a.json book-b.json --question 'Where do these sources agree or disagree about the decision?'
```

The result has a cited `key_message`, typed cited claims, explicit disagreements and uncertainties. Source IDs retain their book hashes and locations. Conflicting sources must remain distinct. The package validates citation membership, not whether the model's argument is correct; human/source review is still needed.

## Honest state and provenance

- `coverage.complete` from ingestion means the declared readable spine was parsed, subject to recorded intentional exclusions. It does not mean an AI has read the book.
- Workflow coverage separately counts passages with imported completed host-analysis attestations. Test fixtures never count as real analysis and cannot feed production derived jobs.
- Receipts bind job and result hashes, but are **host attestations**, not signed execution proofs. Anyone who can author input JSON can forge one. Do not import untrusted result files as evidence of execution.
- A source passage records book SHA-256, reading-order chapter, section, resource href, genuine element ID when available, and full text. CFIs are null because this parser does not calculate a genuine EPUB CFI. It does not claim page numbers or native highlighted-selection equivalence.
- The JSON ledger is this adapter's versioned format. It is not promised to import into the native app's existing grouped Markdown importer.

## Sign in with ChatGPT and subscription usage

This cloud package uses the surrounding assistant's existing model/image tools. It needs no extra login or API key, and it makes no independent subscription-quota entitlement claim.

Official **Sign in with ChatGPT token sharing** documentation now describes subscription-backed Responses API inference for eligible local/open-source apps, with explicit user consent, app-owned OAuth credentials, user/workspace binding and a persistent host identifier. Hosted/paid apps have a separate eligibility/partner path. This cloud adapter does not assume it qualifies and implements no OAuth flow.

The documented text route uses eligible signed-in models, `stream: true`, `store: false`, and must wait for `response.completed`; failures can occur after streaming begins. The preview excludes image generation. A future eligible standalone adapter must validate this contract, bind its own credentials correctly, fail closed on auth/quota failures, and never silently fall back to billed API use. Never read or copy another app's auth store, `auth.json`, browser cookies or private tokens.

Official references, checked 2026-10-09:
- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
- https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery
- https://learn.chatgpt.com/docs/image-generation

## Security and limits

No extraction to disk, network requests, shell execution, dynamic code, user EPUB fixtures, keys, tokens, or public server. ZIP/XML and resource limits reject malformed/hostile input. DRM/encrypted containers are not bypassed. External resource URLs are not fetched. Book text remains untrusted data even when the user trusts the author or supplier. A book cannot authorize a tool, change a system instruction, or request a secret.

See `SOURCE_PORT.md` for the pinned upstream mapping, `LEARNING_LOG.md` for decisions, and `PR_PROPOSAL.md` for review scope. Run the package tests independently; the native app's Rust, frontend and full aggregate CI are not exercised by this package's test suite.

## Release license

This independently developed package uses the [custom Fair Source license](LICENSE) for owned or authorized material, with per-file Apache-2.0 conversion after four years. Earlier AGPL grants and third-party rights remain intact. See the repository THIRD_PARTY_NOTICES.md. This is not an official OpenAI product. A Fair Source release must not assume eligibility under an open-source authentication program.
