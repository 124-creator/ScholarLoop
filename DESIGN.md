# ScholarLoop Public Demo Design

This public snapshot has two surfaces:

1. **GitHub Pages static Studio** - `index.html` is generated from the M180 Studio renderer and patched for static GitHub Pages. It demonstrates the product experience without credentials or private corpora.
2. **Local stdlib demo server** - `src/scholarloop/demo/app.py` exposes `/`, `/pro`, `/studio`, `/api/search`, `/api/verify_span`, and `/api/trail` for offline/local validation.

Design constraints:

- no external CDN assets;
- explicit unavailable states for realtime search;
- no fabricated recommendation rows;
- every load-bearing metric points back to `reports/` artifacts;
- fields that cannot be matched to source text remain in manual-review state.

Latest public polish: M180 changed realtime-card wording so author/year/DOI for live queries remain "to be verified" rather than guessed, while benchmark queries keep OpenAlex-verified metadata.
