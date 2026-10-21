"""Explainable route scoring and evaluation for the Aiqon assignment."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Route:
    shipment_id: str
    route_id: str
    origin: str
    destination: str
    hubs: str
    cost_usd: float
    transit_days: float
    delay_probability: float
    risk_index: float


@dataclass(frozen=True)
class Constraints:
    max_cost: float | None = None
    max_days: float | None = None
    max_delay_probability: float | None = None


DEFAULT_WEIGHTS = {"cost": 0.40, "time": 0.35, "risk": 0.25}


def load_routes(path: str | Path) -> list[Route]:
    routes: list[Route] = []
    with open(path, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            route = Route(
                shipment_id=row["shipment_id"], route_id=row["route_id"],
                origin=row["origin"], destination=row["destination"], hubs=row["hubs"],
                cost_usd=float(row["cost_usd"]), transit_days=float(row["transit_days"]),
                delay_probability=float(row["delay_probability"]), risk_index=float(row["risk_index"]),
            )
            if route.cost_usd < 0 or route.transit_days <= 0:
                raise ValueError(f"Invalid cost or transit time in {route.route_id}")
            if not 0 <= route.delay_probability <= 1 or not 0 <= route.risk_index <= 100:
                raise ValueError(f"Invalid risk value in {route.route_id}")
            routes.append(route)
    if not routes:
        raise ValueError("The route dataset is empty")
    return routes


def load_profiles(path: str | Path) -> dict[str, dict[str, float]]:
    profiles = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, weights in profiles.items():
        if set(weights) != {"cost", "time", "risk"} or any(float(v) < 0 for v in weights.values()):
            raise ValueError(f"Profile {name!r} must have non-negative cost, time, and risk weights")
        if sum(float(v) for v in weights.values()) <= 0:
            raise ValueError(f"Profile {name!r} must have a positive total weight")
    return profiles


def _normalized(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if high == low:
        return [0.0] * len(values)
    return [(value - low) * 100.0 / (high - low) for value in values]


def rank_routes(routes: Iterable[Route], weights: dict[str, float], constraints: Constraints = Constraints()) -> dict:
    candidates = list(routes)
    if not candidates:
        return {"status": "no_routes", "recommendation": None, "ranked": [], "message": "No candidate routes were supplied."}
    total = sum(float(weights[k]) for k in ("cost", "time", "risk"))
    if not math.isfinite(total) or total <= 0 or any(not math.isfinite(float(weights[k])) or float(weights[k]) < 0 for k in ("cost", "time", "risk")):
        raise ValueError("Weights must be non-negative with a positive total")
    for key, value in (("max_cost", constraints.max_cost), ("max_days", constraints.max_days), ("max_delay_probability", constraints.max_delay_probability)):
        if value is not None and (not math.isfinite(value) or value < 0 or (key == "max_delay_probability" and value > 1)):
            raise ValueError(f"Invalid {key} constraint")
    w = {k: float(weights[k]) / total for k in ("cost", "time", "risk")}
    def violations(r: Route) -> list[str]:
        out = []
        if constraints.max_cost is not None and r.cost_usd > constraints.max_cost: out.append("cost limit")
        if constraints.max_days is not None and r.transit_days > constraints.max_days: out.append("transit-time limit")
        if constraints.max_delay_probability is not None and r.delay_probability > constraints.max_delay_probability: out.append("delay-risk limit")
        return out
    feasible = [r for r in candidates if not violations(r)]
    if not feasible:
        return {"status": "infeasible", "recommendation": None, "ranked": [], "message": "No route satisfies all supplied constraints.", "excluded": [{"route_id": r.route_id, "violations": violations(r)} for r in candidates]}
    components = {
        "cost": _normalized([r.cost_usd for r in feasible]),
        "time": _normalized([r.transit_days for r in feasible]),
        "risk": _normalized([r.delay_probability for r in feasible]),
    }
    ranked = []
    for i, route in enumerate(feasible):
        parts = {key: components[key][i] for key in components}
        score = sum(w[key] * parts[key] for key in w)
        ranked.append({"route": route, "score": score, "components": parts})
    ranked.sort(key=lambda x: (round(x["score"], 10), x["route"].delay_probability, x["route"].cost_usd, x["route"].route_id))
    return {"status": "ok", "recommendation": ranked[0], "runner_up": ranked[1] if len(ranked) > 1 else None,
            "ranked": ranked, "weights": w, "message": "Recommendation selected from feasible routes."}


def explain(result: dict) -> str:
    if result["status"] != "ok":
        return result["message"]
    best, runner = result["recommendation"], result["runner_up"]
    r = best["route"]
    text = (f"Recommend {r.route_id} via {r.hubs}: ${r.cost_usd:,.0f}, {r.transit_days:.0f} days, "
            f"{r.delay_probability:.0%} estimated delay probability. Its weighted score is {best['score']:.1f}/100 (lower is better).")
    if runner:
        q = runner["route"]
        text += (f" Compared with {q.route_id}, it is ${abs(q.cost_usd-r.cost_usd):,.0f} "
                 f"{'cheaper' if r.cost_usd < q.cost_usd else 'more expensive' if r.cost_usd > q.cost_usd else 'the same cost'}, "
                 f"{abs(q.transit_days-r.transit_days):.0f} days {'faster' if r.transit_days < q.transit_days else 'slower' if r.transit_days > q.transit_days else 'the same speed'}, "
                 f"and its estimated delay probability is {abs(q.delay_probability-r.delay_probability)*100:.1f} percentage points "
                 f"{'lower' if r.delay_probability < q.delay_probability else 'higher' if r.delay_probability > q.delay_probability else 'the same'}.")
    return text


def evaluate(routes: list[Route], profiles: dict[str, dict[str, float]]) -> list[dict]:
    grouped: dict[str, list[Route]] = {}
    for r in routes: grouped.setdefault(r.shipment_id, []).append(r)
    reports = []
    for name, weights in profiles.items():
        scores, wins = [], {"cost": 0, "time": 0, "risk": 0}
        for group in grouped.values():
            result = rank_routes(group, weights)
            chosen = result["recommendation"]
            scores.append(chosen["score"])
            rr = chosen["route"]
            wins["cost"] += rr.cost_usd == min(x.cost_usd for x in group)
            wins["time"] += rr.transit_days == min(x.transit_days for x in group)
            wins["risk"] += rr.delay_probability == min(x.delay_probability for x in group)
        reports.append({"profile": name, "shipments": len(grouped), "coverage": len(scores) / len(grouped) if grouped else 0,
                        "average_score": sum(scores) / len(scores) if scores else 0, "criterion_wins": wins})
    return reports
