"""WSGI entry point for deploying the route planner on PythonAnywhere.

PythonAnywhere imports the ``application`` callable from its WSGI config. This
module reuses the same HTML page and recommendation engine as the local UI,
without starting a separate HTTP server or requiring Flask.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from urllib.parse import parse_qs

from route_recommender import Constraints, explain, load_profiles, load_routes, rank_routes
from ui import PAGE

ROOT = Path(__file__).resolve().parent
ROUTES = load_routes(ROOT / "data" / "routes.csv")
PROFILES = load_profiles(ROOT / "data" / "profiles.json")
SHIPMENTS = {}
for _route in ROUTES:
    SHIPMENTS.setdefault(_route.shipment_id, []).append(_route)


def _response(start_response, status: str, content_type: str, body: bytes):
    start_response(status, [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
    ])
    return [body]


def _json_response(start_response, status: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    return _response(start_response, status, "application/json; charset=utf-8", body)


def _serialize_ranked(item):
    if item is None:
        return None
    return {
        "route": asdict(item["route"]),
        "score": item["score"],
        "components": item["components"],
    }


def application(environ, start_response):
    """Serve the browser UI and its two small JSON endpoints."""
    if environ.get("REQUEST_METHOD", "GET") != "GET":
        return _response(start_response, "405 Method Not Allowed", "text/plain; charset=utf-8", b"Method not allowed")

    path = environ.get("PATH_INFO", "/")
    if path == "/":
        return _response(start_response, "200 OK", "text/html; charset=utf-8", PAGE.encode("utf-8"))

    if path == "/api/options":
        return _json_response(start_response, "200 OK", {
            "shipments": sorted(SHIPMENTS),
            "profiles": PROFILES,
        })

    if path != "/api/recommend":
        return _json_response(start_response, "404 Not Found", {"error": "Not found"})

    query = parse_qs(environ.get("QUERY_STRING", ""))
    try:
        shipment_id = query.get("shipment_id", [""])[0]
        candidates = SHIPMENTS.get(shipment_id)
        if not candidates:
            raise ValueError("Choose a valid shipment ID.")

        weight_names = ("cost_weight", "time_weight", "risk_weight")
        if all(name in query for name in weight_names):
            weights = {
                "cost": float(query["cost_weight"][0]),
                "time": float(query["time_weight"][0]),
                "risk": float(query["risk_weight"][0]),
            }
        else:
            weights = PROFILES["balanced"]

        limits = {}
        for parameter in ("max_cost", "max_days", "max_delay_probability"):
            if parameter in query:
                value = float(query[parameter][0])
                if value < 0 or (parameter == "max_delay_probability" and value > 1):
                    raise ValueError(f"{parameter} is outside its valid range.")
                limits[parameter] = value

        result = rank_routes(candidates, weights, Constraints(**limits))
        result["explanation"] = explain(result)
        result["ranked"] = [_serialize_ranked(item) for item in result["ranked"]]
        result["recommendation"] = _serialize_ranked(result["recommendation"])
        result["runner_up"] = _serialize_ranked(result.get("runner_up"))
        return _json_response(start_response, "200 OK", result)
    except (ValueError, KeyError) as exc:
        return _json_response(start_response, "400 Bad Request", {"error": str(exc)})
