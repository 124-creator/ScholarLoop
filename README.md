# ScholarLoop · Trusted Paper Search and Evidence-Chain Agent

ScholarLoop 是一个面向复杂学术查询的 AI Agent 原型：它把研究问题拆成可检索子问题，融合 BM25、Embedding 与 Cross-Encoder 排序，并把推荐论文组织成可核验的 evidence card / evidence matrix。

> Status: **work in progress**. This repository is a public-safe snapshot for portfolio review. Runtime caches, private credentials, raw corpora, and large benchmark files are intentionally excluded.

## Why this project

普通论文搜索通常只给标题列表。ScholarLoop 关注科研流程里的三个问题：

1. 用户问题是否被拆成了可检索的研究对象、方法、数据、指标与争议点？
2. 推荐结果是否比 BM25 / 单轮检索更好，并且可复现？
3. 每个推荐理由是否能追溯到论文标题、摘要、正文片段或外部元数据，而不是模型自行编造？

## Current verified results

The following metrics come from saved evaluation artifacts under `reports/`.

| Module | Evidence |
|---|---|
| Retrieval benchmark | LitSearch 597 queries |
| A-v2 ranking | F1 = 0.1312, Recall@20 = 0.7564, NDCG@20 = 0.5657 |
| BM25 baseline | F1 = 0.0964, Recall@20 = 0.5683, NDCG@20 = 0.3931 |
| Significance | A-v2 vs BM25 ΔF1 = 0.0348, 95% CI = [0.0287, 0.0409] |
| Evidence matrix | 30 rendered query docs, 0 fabricated citation fields in the public report |
| External metadata | OpenAlex / Crossref resolver layer; 82 / 90 sample cards resolved in M050 |
| Public smoke tests | 10 lightweight tests pass in this public snapshot |

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
  web/            lightweight stdlib Web demo renderer
```

## Reports included

```text
reports/m010/A-main-evaluation-report.md       A-v1 retrieval/ranking evaluation
reports/m020/evidence-matrix-report.md         evidence card / matrix report
reports/m030/web-verification.json             Web rendering verification
reports/m040/A-v2评测报告.md                    A-v2 ranking and significance report
reports/m050/final_summary.json                metadata resolver summary
reports/m050/data-sources.md                   public data-source notes
```

Large files are excluded on purpose: raw corpora, model caches, `.npy`, `.parquet`, `.zip`, `.omx`, and secrets are not part of this public snapshot.

## Quick validation

Install lightweight test dependencies:

```bash
python -m pip install -r requirements.txt
```

Run public smoke tests:

```bash
python -m pytest -q
```

These tests cover:

- deterministic train / holdout / test split logic;
- metric and fusion behavior;
- OpenAlex fixture parsing;
- metadata resolver behavior;
- cache redaction behavior.

Full LitSearch evaluation is not included because it depends on excluded benchmark/corpus artifacts and runtime caches.

## Relationship to ResearchLoop

ScholarLoop is one applied case of [ResearchLoop](https://github.com/124-creator/ResearchLoop): the project was planned and reviewed with a dual-loop workflow covering problem freezing, route selection, Test Oracle, implementation review, and retrospective artifacts.

## Author

田中斐 · AI Agent / LLM application engineering portfolio
