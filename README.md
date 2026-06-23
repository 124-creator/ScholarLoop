# ScholarLoop - Trusted Paper Search and Evidence-Chain Agent

**Portfolio link:** ScholarLoop 可信论文搜索与证据链推荐智能体｜GitHub: https://github.com/124-creator/ScholarLoop ｜ Demo: https://124-creator.github.io/ScholarLoop/

**Live Demo:** https://124-creator.github.io/ScholarLoop/ | **GitHub:** https://github.com/124-creator/ScholarLoop

ScholarLoop is a competition-grade AI Agent prototype for complex academic paper search. It decomposes research questions, combines BM25, dense retrieval and cross-encoder reranking, then presents recommendations as verifiable evidence cards and evidence matrices.

> Status: **public-safe competition snapshot, updated with five-page topic-research demo**. The GitHub Pages demo now supports browser-side OpenAlex realtime search for arbitrary topics, with embedded safe snapshots as fallback. A serverless `/api/search` backend is included for OpenAlex + DeepSeek realtime mode; private DeepSeek keys are never exposed in the browser.

## Why this project

A normal paper search page usually returns a title list. ScholarLoop focuses on three stricter questions:

1. Is the user question decomposed into searchable objects, methods, datasets, metrics and controversy points?
2. Are the recommendations better than BM25 / single-pass retrieval under a reproducible benchmark protocol?
3. Can each recommendation reason be traced back to a title, abstract, source span or external metadata record instead of being invented by a model?

## Current verified results

The following metrics come from saved evaluation artifacts under `reports/`.

| Module | Evidence |
|---|---|
| Retrieval benchmark | LitSearch 597 queries |
| A-v2 ranking | F1 = 0.1312, Recall@20 = 0.7564, NDCG@20 = 0.5657 |
| BM25 baseline | F1 = 0.0964, Recall@20 = 0.5683, NDCG@20 = 0.3931 |
| Significance (LitSearch) | A-v2 vs BM25 delta-F1 = 0.0348, 95% CI = [0.0287, 0.0409] |
| Cross-benchmark zero-shot | RealScholarQuery/PaSa: A-v2 F1 = 0.1972 vs BM25 F1 = 0.1058, delta-F1 = 0.0914, 95% CI = [0.0657, 0.1176], permutation p < 1e-4 under the frozen M040 config |
| Evidence matrix | 30 rendered query docs, 0 fabricated citation fields in the public report |
| External metadata | OpenAlex / Crossref resolver layer; 82 / 90 sample cards resolved in M050 |
| Click-to-verify demo | 1170 span checks; 989 highlightable fields; mismatch = 0; 120 trace steps; fabrication = 0 |
| Public smoke tests | 6 lightweight public-snapshot tests pass; the original full local suite recorded 77 passed in `reports/m180/pytest.txt` |
| Latest presentation polish | M180 keeps live-query author/year/DOI as "to be verified" instead of guessing |

## Public demo

Open: **https://124-creator.github.io/ScholarLoop/**

The public page is designed for recruiter and judge review:

- **Five-page topic research:** recommended papers -> prior issues -> reading route -> execution plan -> web research notes.
- **Search Loop:** query decomposition -> hybrid retrieval -> reranking -> evidence cards.
- **Trust Loop:** source-span verification -> artifact trace -> human-review boundary.
- **Click-to-verify:** fields are highlighted only when `source_text[char_span] == field value`; otherwise they remain marked for manual review.
- **Realtime honesty:** GitHub Pages performs public OpenAlex realtime search in the browser and falls back to safe snapshots if unavailable. For DeepSeek summarization, deploy the included serverless API and keep the key in environment variables. Unavailable states stay explicit and never fabricate recommendation rows.

Verified offline demo endpoints in local runtime: `/`, `/pro`, `/studio`, `/api/search`, `/api/verify_span`, `/api/trail`.

Realtime deployment guide: [`docs/deploy-realtime.md`](docs/deploy-realtime.md).

## Architecture

```text
Complex research question
  -> query decomposition
  -> candidate retrieval: keyword / BM25 / dense embedding
  -> reranking and feature fusion
  -> evidence card generation
  -> source / DOI / author-year verification
  -> Web evidence matrix and review artifacts
```

Main source tree:

```text
src/scholarloop/
  connectors/     OpenAlex, Crossref, Semantic Scholar, arXiv metadata connectors
  corpus/         benchmark and corpus loading helpers
  evidence/       evidence cards, matrix rendering, field status verification
  query/          query decomposition
  rank/           fusion and reranking logic
  retrieval/      BM25 and dense retrieval helpers
  demo/           offline Studio, realtime wrapper, graph and click-to-verify views
  web/            lightweight stdlib Web demo renderer
```

## Reports included

```text
reports/m040/results.json                  A-v2 ranking and significance artifacts
reports/m060/results.json                  second-benchmark zero-shot generalization artifacts
reports/m100/                              expert-score demo and graph/realtime additions
reports/m120/validation_summary.json       interactive demo verification summary
reports/m130..m180/validation_summary.json flagship Studio, bilingual, a11y and realtime-polish checks
docs/submission/                           competition submission materials
docs/dev/plans/                            original module plans through M180
```

Large files are excluded on purpose: raw corpora, model caches, `.npy`, `.parquet`, `.zip`, `.omx`, and secrets are not part of this public snapshot. See `PUBLIC_SNAPSHOT.json` for the snapshot manifest.

## Quick validation

Install lightweight test dependencies:

```bash
python -m pip install -r requirements.txt
```

Run public smoke tests:

```bash
python -m pytest -q
```

These tests cover the static Studio page, verified metric artifacts, M180 validation summaries, OpenAlex fixture parsing, public-snapshot exclusions, and high-risk secret scanning.

The original full local suite recorded `77 passed` in `reports/m180/pytest.txt`, but reproducing it requires excluded raw/parquet corpora and optional model dependencies. Full LitSearch / RealScholarQuery evaluation is not included because it depends on excluded benchmark/corpus artifacts and runtime caches.

## Relationship to ResearchLoop

ScholarLoop is one applied case of [ResearchLoop](https://github.com/124-creator/ResearchLoop): the project was planned and reviewed with a dual-loop workflow covering problem freezing, route selection, Test Oracle, implementation review and retrospective artifacts.

## Author

Tian Zhongfei - AI Agent / LLM application engineering portfolio
