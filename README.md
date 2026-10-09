# UnCommon Core OAI Dot ePub Processor

Turn a DRM-free EPUB into a source-linked knowledge ledger and verifiable jobs for a trusted AI host. Keep the evidence, interpretation, coverage, and output history separate.

This independently developed project is not affiliated with or endorsed by OpenAI. “OAI Dot” describes the intended host workflow; it does not provide OpenAI credentials, an official integration, or guaranteed subscription quota.

## Start here

Python 3.11+; no runtime dependencies, API key, native app, or Rust install is required for offline processing.

```sh
cd packages/headless-reader
python -m unittest discover -s tests -v
python -m ucc_headless ingest /path/to/your-book.epub /path/outside/repo/ledger.json
python -m ucc_headless jobs /path/outside/repo/ledger.json /path/outside/repo/jobs.json
```

Output paths must not already exist. Keep books and generated results outside this repository.

- [OAI dot onboarding](docs/platforms/oai-dot/OAI-Dot.md): host-assisted text and image workflow
- [Package commands and contracts](packages/headless-reader/README.md)
- [Roadmap and implementation status](ROADMAP.md)
- [Shared knowledge ontology proposal](docs/design/UnCommon-Core-Shared-Knowledge-Ontology.md)
- [Executive HTML design standard](docs/design/EXECUTIVE_HTML_STANDARD.md)
- [Source mapping](packages/headless-reader/SOURCE_PORT.md) and [provenance notices](THIRD_PARTY_NOTICES.md)

## What works

- Bounded, offline EPUB ZIP/XML parsing in reading order; genuine navigation labels and element IDs; explicit omissions; no fabricated CFIs
- Stable source IDs and book hashes, deterministic chapter-batched jobs, and no silent text truncation
- Philosopher / Expert / MBA defaults plus configurable persona/focus/depth
- Fast/cheap Luna processing preference, separately recorded from the actual host model; no undisclosed heavier fallback
- Strict result imports, citation membership, unsigned host execution receipts and selected/whole-book coverage
- Source-plus-analysis sketchnote outlines, compact citation maps, image-tool jobs and linked image corrections
- Cross-book synthesis job contracts preserving citations, disagreement and uncertainty

The Python package does not call a model or generate an image itself. The surrounding trusted host must execute each job and return an honest receipt. Tests use synthetic fixtures and do not prove live-model output quality.

## Planned, not built

The normalized ontology, shared synthesis revisions, synchronized three-output renderers, two-page executive HTML renderer and diagram contracts are design proposals. Existing ledger Markdown and image-job contracts are implemented; they do not establish those proposed renderers. See ROADMAP.md.

There is no automatic Sign in with ChatGPT or standalone OAuth flow. Future authentication requires its own current eligibility and security review; a custom Fair Source repository must not assume eligibility under an open-source program. Host text/image availability and limits remain the host’s responsibility. There is no silent billed-API fallback.

## Safety and privacy

Books are data, not commands. No content execution, network client, credential access, public server, DRM bypass, or automatic external action is implemented. Reject unsupported/malformed inputs explicitly. Receipts validate consistency, not cryptographic execution identity or semantic truth. Never publish user books, annotations, results or credentials as fixtures.

## License

[UnCommon Core OAI Dot ePub Processor Fair Source License v1.0](LICENSE), adapted from the Licensor’s existing Fair Source terms. Personal, educational, research, evaluation and small-team internal uses are permitted under its terms. Commercial redistribution, hosted services, competing commercial products, commercial embedding and enterprise-wide deployment require a separate written license as specified there.

Each source file converts to Apache-2.0 four years after its first public release by the Licensor, using its first public repository commit when no date is stated. This is custom source-available licensing, not a claim of OSI approval. The license applies only to owned or authorized material; earlier AGPL grants and third-party rights remain intact. See [license scope](licenses/README.md).
