# ScholarLoop Public Demo

Live demo: https://124-creator.github.io/ScholarLoop/

This is a public-safe GitHub Pages demo for portfolio and internship review. It converts the verified offline demo into a static interactive walkthrough:

- Search Loop: query decomposition -> hybrid retrieval -> reranking -> evidence card generation.
- Trust Loop: source span verification -> trail audit -> human-review boundary.
- Competition framing: F1, efficiency, structured display, and expert-review value are surfaced in the first screen.
- Visual language: retrieval uses cyan/blue gradients, evidence uses green, efficiency uses amber, and risk/final-claim states use rose.
- Honest boundary: the public page does not access private corpora, secrets, raw benchmark caches, or live LLM/API keys.

## Verification carried from offline artifacts

- `span_fidelity`: 1170 checks, 989 highlightable fields, mismatch = 0.
- `trail_fidelity`: 120 traced steps, fabrication = 0.
- local offline endpoints: `/pro`, `/api/verify_span`, `/api/trail`.

The static page is designed for recruiters to understand the value quickly while preserving the project truthfulness constraints.
