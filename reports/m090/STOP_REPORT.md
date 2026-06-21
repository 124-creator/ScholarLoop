# M090 rev2 T0 stop report

- Status: BLOCKED
- Gate: true iterative LLM retrieval + LLM listwise rerank was executed, but A-v3 did not pass the frozen A-v2 F1 wall.
- Sample queries: 10
- LLM calls: 20 total, 0 cached, tokens=61388, latency_s=273.23
- New candidates from whole-corpus re-retrieval: 600
- H5 final out-of-pool recommendations: 0

## F1 delta vs frozen A-v2

- train: 0.000000
- holdout: 0.000000
- test: 0.000000
- all: 0.000000
- bootstrap mean_delta=0.000000, CI95=[0.000000, 0.000000], passed=False

## Stop reasons

- A-v3 rev2 T0 F1 delta was not positive on train split.
- A-v3 rev2 T0 F1 delta was not positive on holdout split.
- A-v3 rev2 T0 F1 delta was not positive on test split.
- Paired bootstrap CI lower bound was not > 0.

No gold labels were supplied to query refinement or listwise reranking. Gold ids were used only after ranking to compute metrics.
