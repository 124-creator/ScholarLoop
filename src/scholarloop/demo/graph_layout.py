from __future__ import annotations

import html
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from scholarloop.demo.assemble import M070_GAPS_DISPLAY, load_gaps_display

WIDTH = 1180
HEIGHT = 820
MARGIN_X = 92
MARGIN_Y = 86
COLUMNS = 5


def _copy(data: Any) -> Any:
    return deepcopy(data)


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def stable_node_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(label).lower()).strip("-")
    return "n-" + (slug or "node")


def _sorted_nodes(gaps: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = _copy(gaps.get("concept_nodes") or [])
    return sorted(nodes, key=lambda n: (int(n.get("id", 10**9)), str(n.get("label") or "")))


def build_frozen_layout() -> dict[str, Any]:
    """Return a deterministic grid layout with frozen coordinates."""

    gaps = load_gaps_display()
    raw_nodes = _sorted_nodes(gaps)
    raw_edges = _copy(gaps.get("matrix_edges") or [])
    label_to_node = {str(node.get("label")): node for node in raw_nodes}
    x_step = (WIDTH - 2 * MARGIN_X) / max(1, COLUMNS - 1)
    rows = max(1, math.ceil(len(raw_nodes) / COLUMNS))
    y_step = (HEIGHT - 2 * MARGIN_Y) / max(1, rows - 1)

    nodes: list[dict[str, Any]] = []
    positions: dict[str, tuple[float, float]] = {}
    for idx, raw in enumerate(raw_nodes):
        label = str(raw.get("label") or f"node-{idx}")
        row, col = divmod(idx, COLUMNS)
        x = round(MARGIN_X + col * x_step, 3)
        y = round(MARGIN_Y + row * y_step, 3)
        node_id = stable_node_id(label)
        positions[label] = (x, y)
        nodes.append(
            {
                "id": node_id,
                "source_id": raw.get("id"),
                "label": label,
                "x": x,
                "y": y,
                "radius": 22,
                "source": str(M070_GAPS_DISPLAY),
            }
        )

    edges: list[dict[str, Any]] = []
    invalid_edges: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_edges):
        source = str(raw.get("source") or "")
        target = str(raw.get("target") or "")
        if source not in positions or target not in positions:
            invalid_edges.append({"index": idx, "source": source, "target": target})
            continue
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        future = int(raw.get("future_fill_count") or 0)
        edge = _copy(raw)
        edge.update(
            {
                "id": f"e-{idx:03d}-{stable_node_id(source)}-{stable_node_id(target)}",
                "source_id": stable_node_id(source),
                "target_id": stable_node_id(target),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "stroke": "#13b6a6" if future > 0 else "#8aa0bd",
                "stroke_width": round(1.4 + min(4, future) * 0.28, 2),
            }
        )
        edges.append(edge)

    return {
        "schema_version": "m130.frozen_graph_layout.v1",
        "mode": "verified_json_frozen_coordinates",
        "layout_algorithm": "deterministic_5_column_grid_frozen_coordinates",
        "client_force_simulation": False,
        "source_paths": {"m070_gaps_display": str(M070_GAPS_DISPLAY)},
        "viewBox": f"0 0 {WIDTH} {HEIGHT}",
        "width": WIDTH,
        "height": HEIGHT,
        "nodes": nodes,
        "edges": edges,
        "invalid_edges": invalid_edges,
        "raw_node_count": len(label_to_node),
        "raw_edge_count": len(raw_edges),
    }


def coordinate_signature(layout: dict[str, Any] | None = None) -> str:
    layout = layout or build_frozen_layout()
    coordinates = {
        "nodes": [{"id": n["id"], "label": n["label"], "x": n["x"], "y": n["y"]} for n in layout.get("nodes", [])],
        "edges": [
            {
                "id": e["id"],
                "source_id": e["source_id"],
                "target_id": e["target_id"],
                "x1": e["x1"],
                "y1": e["y1"],
                "x2": e["x2"],
                "y2": e["y2"],
            }
            for e in layout.get("edges", [])
        ],
    }
    return json.dumps(coordinates, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _nan_coordinates(layout: dict[str, Any]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    for kind in ("nodes", "edges"):
        keys = ("x", "y") if kind == "nodes" else ("x1", "y1", "x2", "y2")
        for item in layout.get(kind, []):
            for key in keys:
                value = item.get(key)
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    bad.append({"kind": kind, "id": item.get("id"), "key": key, "value": value})
    return bad


def _min_node_distance(layout: dict[str, Any]) -> float:
    nodes = layout.get("nodes", [])
    best = float("inf")
    for i, left in enumerate(nodes):
        for right in nodes[i + 1 :]:
            dist = math.hypot(float(left["x"]) - float(right["x"]), float(left["y"]) - float(right["y"]))
            best = min(best, dist)
    return round(best if math.isfinite(best) else 0.0, 3)


def render_stable_graph_svg(layout: dict[str, Any] | None = None) -> str:
    layout = layout or build_frozen_layout()
    edge_svg: list[str] = []
    for edge in layout.get("edges", []):
        title = (
            f"{edge.get('source')} -> {edge.get('target')}; "
            f"past={edge.get('past_cooccur_count')}; future={edge.get('future_fill_count')}; status={edge.get('evidence_status')}"
        )
        edge_svg.append(
            f'<line class="stable-edge" data-edge-source="{_e(edge["source_id"])}" data-edge-target="{_e(edge["target_id"])}" '
            f'x1="{edge["x1"]:.3f}" y1="{edge["y1"]:.3f}" x2="{edge["x2"]:.3f}" y2="{edge["y2"]:.3f}" '
            f'stroke="{_e(edge["stroke"])}" stroke-width="{edge["stroke_width"]:.2f}" opacity="0.66"><title>{_e(title)}</title></line>'
        )
    node_svg: list[str] = []
    for node in layout.get("nodes", []):
        label = node["label"]
        fill = "url(#nodeFuture)" if label in {str(edge.get("source")) for edge in layout.get("edges", []) if int(edge.get("future_fill_count") or 0) > 0} else "url(#nodeBase)"
        node_svg.append(
            f'<g class="stable-node" data-graph-node="1" data-node-id="{_e(node["id"])}" tabindex="0" role="listitem" aria-label="{_e(label)}">'
            f'<circle cx="{node["x"]:.3f}" cy="{node["y"]:.3f}" r="{node["radius"]}" fill="{fill}" opacity="0.96"><title>{_e(label)}</title></circle>'
            f'<text x="{node["x"]:.3f}" y="{node["y"] + 48:.3f}" text-anchor="middle" font-size="20" font-weight="760" fill="#102044" paint-order="stroke" stroke="#ffffff" stroke-width="4" stroke-linejoin="round">{_e(label)}</text>'
            f'</g>'
        )
    return (
        f'<div class="stable-graph"><svg viewBox="{_e(layout["viewBox"])}" role="img" aria-label="ScholarLoop stable verified relation graph">'
        '<defs><linearGradient id="nodeBase" x1="0" x2="1"><stop stop-color="#2563eb"/><stop offset="1" stop-color="#7c3aed"/></linearGradient><linearGradient id="nodeFuture" x1="0" x2="1"><stop stop-color="#0f766e"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs><rect width="100%" height="100%" fill="#fbfdff"/>'
        '<g role="list">'
        + "".join(edge_svg)
        + "".join(node_svg)
        + "</g></svg></div>"
    )


def stable_graph_payload(include_svg: bool = True) -> dict[str, Any]:
    layout = build_frozen_layout()
    payload = _copy(layout)
    payload["coordinate_signature"] = coordinate_signature(layout)
    if include_svg:
        payload["svg"] = render_stable_graph_svg(layout)
    return payload


def verify_graph_determinism() -> dict[str, Any]:
    first = build_frozen_layout()
    second = build_frozen_layout()
    first_sig = coordinate_signature(first)
    second_sig = coordinate_signature(second)
    first_svg = render_stable_graph_svg(first)
    second_svg = render_stable_graph_svg(second)
    nan_coordinates = _nan_coordinates(first)
    invalid_edges = first.get("invalid_edges", [])
    coordinates_byte_equal = first_sig == second_sig
    svg_byte_equal = first_svg == second_svg
    status = "PASS" if coordinates_byte_equal and svg_byte_equal and not nan_coordinates and not invalid_edges else "BLOCKED"
    return {
        "schema_version": "m130.graph_determinism.v1",
        "status": status,
        "source_path": str(M070_GAPS_DISPLAY),
        "layout_algorithm": first["layout_algorithm"],
        "client_force_simulation": False,
        "coordinates_byte_equal": coordinates_byte_equal,
        "svg_byte_equal": svg_byte_equal,
        "coordinate_signature_sha_input": first_sig,
        "invalid_edge_count": len(invalid_edges),
        "invalid_edges": invalid_edges[:20],
        "nan_coordinate_count": len(nan_coordinates),
        "nan_coordinates": nan_coordinates[:20],
        "node_count": len(first.get("nodes", [])),
        "edge_count": len(first.get("edges", [])),
        "raw_edge_count": first.get("raw_edge_count"),
        "min_node_distance_px": _min_node_distance(first),
        "viewBox": first["viewBox"],
        "hover_focus_policy": "CSS class toggles only; no coordinate mutation and no browser force simulation.",
    }


def write_graph_determinism(path: Path = Path("reports/m130/graph_determinism.json")) -> dict[str, Any]:
    report = verify_graph_determinism()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
