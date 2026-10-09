# Engineering learning log

## 2026-10-09

- This standalone release adapts owned UnCommon Core AI/knowledge-ledger contracts from pinned upstream revision c5e57408b69444fc09fbd0dfd7e683d7b8517d13. Source mapping is documented in SOURCE_PORT.md. It does not contain the upstream native reader implementation.
- Package validation is independent of native/frontend/Rust aggregate CI; those checks are not claimed here.
- Original learning/sketchnote services import Tauri HTTP and secret stores at module scope. Importing them directly would cross the cloud/native boundary. Port only pure prompt/schema concepts, retaining source references and leaving native providers and app UI untouched.
- Original budget helpers use excerpts/slices; cloud workflow instead emits all passage jobs and reports coverage. Derived jobs require every explicitly selected passage's completed analysis. Context-window limitations remain visible to the host.
- A trustworthy file supplier does not make EPUB instructions executable. Preserve parser limits and prompt data boundaries with the same safety checks for every book.
- Default processing preference is fast/cheap Luna. Preserve requested preference separately from actual execution model in receipts; do not invent a public model identifier or silently escalate.
- New official Sign in with ChatGPT documentation invalidates older blanket claims that subscription-backed inference is impossible. Eligibility matters: local/open-source text inference does not establish hosted cloud eligibility or image access. No auth implementation is claimed here.
- Tests use synthetic DRM-free EPUBs and explicitly marked model fixtures. User books, private ledger exports, images and private identifiers never belong in the Git patch.

- Independent adversarial review found and resolved repeated-spine/XML allocation/metadata amplification, literal-doctype source loss, MathML omission reporting, batch-selection dependencies, schema parity and rendered-Markdown escaping. Compact image citation aliases preserve canonical provenance without printing long hashes.
