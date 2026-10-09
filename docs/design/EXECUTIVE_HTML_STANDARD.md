# Executive HTML output standard — proposed, not implemented

Purpose: present a source-linked book synthesis in two printable pages without losing scope, uncertainty or citations. The current Python package has no executive HTML renderer. This document defines a future acceptance target.

## Page hierarchy

1. Lead with one clear key message, then show selection/book coverage and the decision or learning question.
2. Use short supporting evidence and distinguish source claims from interpretations and applications.
3. Include a 2×2 matrix, three-circle diagram and journey map as editorial organizing tools, not as quantitative findings invented from prose.
4. Keep uncertainties, disagreements and a compact source key visible. Provide the full evidence ledger as a companion, not by shrinking body type until it is unreadable.

## Required visual semantics

- **2×2:** named axes, direction meanings, four labeled cells, supporting citations and explicit unsupported cells. No fabricated measurements or rankings.
- **Three circles:** named sets, meaningful overlaps and an explanation of whether overlap is conceptual. Equal sizes carry no quantitative claim.
- **Journey:** ordered stages, questions, observations, decision branches and uncertainty. Proposed actions are not completed actions; no invented timing or guaranteed outcomes.

Each diagram must visibly say “Editorial framework derived from selected passages” or an equally clear label, with citations. Store exact node/source references in the eventual shared synthesis model. Do not imply an author drew or endorsed a new diagram.

## Future acceptance checks

- Exactly two print pages on both A4 and Letter, verified after content or CSS changes
- Key message first; legible text and accessible contrast; no clipped diagrams or orphaned source labels
- Self-contained offline HTML with no tracking, remote fonts, scripts evaluating source content, or external asset requests
- Every displayed statement resolves to the same frozen synthesis revision and original source IDs
- Source HTML escaped, citation aliases pinned per artifact, text alternative supplied
- Full source evidence and receipts retained without making them part of the two-page print flow

No current README, example or screenshot should claim this renderer exists until implementation and these checks pass.
