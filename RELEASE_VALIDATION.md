# Public release preparation validation

Status: local sanitized release candidate; this file does not assert remote publication.

## Executed checks

- Python 3.12: `cd packages/headless-reader && python -m unittest discover -s tests -v` — 95 tests passed.
- `python -m compileall -q ucc_headless` — passed.
- `python -m ucc_headless --help` — passed.
- Synthetic suite: 47 EPUB, 25 prompt, 8 workflow, 5 integration and 10 independent regression tests.
- Public-tree audit: no user EPUBs/images/exports, private Library references, known private example identifiers, workspace paths, credential-shaped values, symlinks or non-text files found. Production Python imports are standard library or local modules.
- Root and package Fair Source license texts are identical. Historical AGPL text and scope notices are preserved separately. No Readest/Foliate implementation or native bundled dependency is included.

The audit combines known-pattern checks and manual inspection, not a guarantee that every possible secret shape can be detected. Synthetic fixtures do not establish live-model quality, actual model execution authenticity or copyright rights to arbitrary input books.

## Not executed or not implemented

Python 3.11 execution, wheel build/install, native app/frontend/Rust CI, normalized ontology migrations, executive HTML rendering/print checks, standalone OAuth or automatic subscription-quota integration. No remote repository, push, deployment or release publication is established by these local checks.

Design documents explicitly label ontology, common synthesis and key-message-first two-page HTML with 2×2, three circles and journey map as proposed work.
