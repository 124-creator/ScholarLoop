from __future__ import annotations

import numpy as np

from scholarloop.rank.fusion_v2 import (
    FusionV2Config,
    build_feature_matrix,
    candidate_weight_grid,
    deterministic_query_split,
    metric_with_ndcg,
    rank_with_features,
)
from scholarloop.retrieval.dense_v2 import text_for_model


def test_m040_split_is_deterministic_and_disjoint() -> None:
    query_ids = [f"litsearch_{i:03d}" for i in range(100)]
    first = deterministic_query_split(query_ids)
    second = deterministic_query_split(reversed(query_ids))
    assert first == second
    assert set(first) == set(query_ids)
    assert set(first.values()) == {"train", "holdout", "test"}


def test_m040_dense_v2_prefixes_model_conventions() -> None:
    assert text_for_model("abc", "intfloat/e5-base-v2", True) == "query: abc"
    assert text_for_model("abc", "intfloat/e5-base-v2", False) == "passage: abc"
    assert text_for_model("abc", "BAAI/bge-base-en-v1.5", True).startswith("Represent this sentence")
    assert text_for_model("abc", "BAAI/bge-base-en-v1.5", False) == "abc"


def test_m040_fusion_v2_uses_cross_encoder_and_subquery_features() -> None:
    corpus_ids = np.array([10, 20, 30], dtype=np.int64)
    pool_indices = [0, 1, 2]
    bm25 = np.array([0.1, 0.9, 0.2], dtype=np.float32)
    dense = np.array([0.9, 0.1, 0.2], dtype=np.float32)
    sub_bm25 = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    sub_dense = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    cross = {2: 2.0}
    features = build_feature_matrix(pool_indices, bm25, dense, sub_bm25, sub_dense, cross)
    cfg = FusionV2Config(weights={"bm25": 0.0, "dense_v2": 0.0, "sub_bm25": 0.2, "sub_dense_v2": 0.2, "cross_encoder": 0.6})
    ranked = rank_with_features(pool_indices, corpus_ids, features, cfg)
    assert ranked[0].corpusid == 30
    assert "cross_encoder" in ranked[0].reason


def test_m040_metric_with_ndcg_binary_relevance() -> None:
    metrics = metric_with_ndcg([9, 2, 3, 4], {2, 4}, k=4)
    assert metrics["P@10"] == 0.2
    assert metrics["R@20"] == 1.0
    assert 0.0 < metrics["F1"] < 1.0
    assert 0.0 < metrics["NDCG@20"] <= 1.0


def test_m040_weight_grid_contains_cross_and_no_cross_configs() -> None:
    grid = candidate_weight_grid(include_cross=True)
    assert any(cfg.normalized_weights()["cross_encoder"] > 0 for cfg in grid)
    assert any(cfg.normalized_weights()["cross_encoder"] == 0 for cfg in grid)
