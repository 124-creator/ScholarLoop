from __future__ import annotations

from typing import Any


def build_internal_citation_graph(papers: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {int(p['corpusid']) for p in papers}
    edges: list[dict[str, int]] = []
    for paper in papers:
        src = int(paper['corpusid'])
        citations = paper.get('citations')
        if citations is None:
            citations = []
        try:
            iterable = list(citations)
        except TypeError:
            iterable = []
        for dst_raw in iterable:
            try:
                dst = int(dst_raw)
            except Exception:
                continue
            if dst in ids:
                edges.append({'source': src, 'target': dst})
    return {'nodes': sorted(ids), 'edges': edges, 'scope': 'top_n_internal_only'}
