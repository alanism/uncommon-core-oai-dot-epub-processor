# Validation record

Validated in a Linux cloud workspace with Python 3.12.14 on 2026-10-09.

## Passed

- `python -m unittest discover -s tests -v`: 95 tests, including 47 EPUB tests, prompt-contract tests, workflow/CLI integration, and 10 independent review regressions.
- `python -m compileall -q ucc_headless`: passed.
- `python -m ucc_headless --help`: passed.
- All six pinned upstream source-reference hashes match the supplied TypeScript snapshots.
- Independent review: no unresolved high/medium findings in this additive package's scope. See REVIEW.md.


## Explicitly not established

- Full native app/frontend/Rust test suites or native packaging. No full repository checkout or native dependency installation was performed.
- A standalone OAuth login, cloud-app subscription eligibility, or direct model API integration. The default adapter only exports host jobs and imports results.
- Cryptographic model execution identity, semantic truth, or image quality from a checksum/receipt. Host receipts are unsigned attestations.
- A real multi-book model synthesis run: cross-book citations/disagreements are covered by synthetic integration tests.
- Remote push, PR publication, deployment, or merge. Delivery is an additive Git-ready patch/package.

No private books, ledger exports, images, private Library identifiers, keys, or authentication material are included in this package. Private acceptance artifacts are excluded from this public release.
