# T5 C-lite ablation gate

- Date: 2026-06-18
- Conclusion: **no-go**
- Small sample: per arm N=3; query_id=litsearch_096, litsearch_018, litsearch_023.
- Arms: single / multi(A-min) / multi+deterministic quality gate.
- Quality gate: Top-20 DOI resolvable in Crossref and OpenAlex, with Semantic Scholar author/year present; no LLM self-judgement.

## mean+/-std (per arm N=3)
| arm | P@10 mean+/-std | R@20 mean+/-std | F1 mean+/-std | tokens mean | latency_s mean | hallucinated/out_of_pool |
|---|---:|---:|---:|---:|---:|---:|
| single | 0.0333+/-0.0471 | 0.0667+/-0.0943 | 0.0444+/-0.0629 | 4459.3 | 16.91 | 0 |
| multi | 0.0667+/-0.0943 | 0.1333+/-0.1886 | 0.0889+/-0.1257 | 285.0 | 2.30 | 0 |
| multi_quality | 0.0333+/-0.0471 | 0.1333+/-0.1886 | 0.0533+/-0.0754 | 285.0 | 2.30 | 0 |

## go/no-go judgement
- multi+quality vs single: F1 delta `0.0089`; Recall@20 delta `0.0667`; variance_ok=False.
- Judgement: no-go.

## Evidence files
- `spike/eval/results_t5.json`
- `spike/raw/llm/t5_single_run1/` / `spike/raw/llm/t5_multi_run1/`
- `spike/raw/quality/`
