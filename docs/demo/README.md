# ScholarLoop Public Demo

Live demo: https://124-creator.github.io/ScholarLoop/

This is a public-safe GitHub Pages demo for portfolio and internship review. It converts the verified M120 local demo into a static interactive walkthrough:

- Search Loop: query decomposition -> hybrid retrieval -> reranking -> evidence card generation.
- Trust Loop: source span verification -> trail audit -> human-review boundary.
- Honest boundary: the public page does not access private corpora, secrets, raw benchmark caches, or live LLM/API keys.

## Verification carried from local M120 artifacts

- `span_fidelity`: 1170 checks, 989 highlightable fields, mismatch = 0.
- `trail_fidelity`: 120 traced steps, fabrication = 0.
- local offline endpoints: `/pro`, `/api/verify_span`, `/api/trail`.

The static page is designed for recruiters to understand the value quickly while preserving the project truthfulness constraints.
