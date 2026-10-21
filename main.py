#!/usr/bin/env python3
"""Command-line interface for the Aiqon route recommendation demo."""
import argparse
from pathlib import Path

from route_recommender import Constraints, evaluate, explain, load_profiles, load_routes, rank_routes

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend explainable shipment routes")
    parser.add_argument("--data", default=str(ROOT / "data/routes.csv"), help="route CSV path")
    parser.add_argument("--profiles", default=str(ROOT / "data/profiles.json"), help="preference profile JSON path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list available shipment IDs")
    rec = sub.add_parser("recommend", help="rank routes for one shipment")
    rec.add_argument("shipment_id")
    rec.add_argument("--profile", default="balanced")
    rec.add_argument("--max-cost", type=float)
    rec.add_argument("--max-days", type=float)
    rec.add_argument("--max-delay-probability", type=float)
    ev = sub.add_parser("evaluate", help="summarize synthetic-data objective consistency")
    args = parser.parse_args()
    routes = load_routes(args.data)
    profiles = load_profiles(args.profiles)
    if args.command == "list":
        ids = sorted({r.shipment_id for r in routes})
        print(f"{len(ids)} shipments: " + ", ".join(ids))
    elif args.command == "recommend":
        if args.profile not in profiles:
            parser.error(f"Unknown profile {args.profile!r}; choose from {', '.join(sorted(profiles))}")
        group = [r for r in routes if r.shipment_id == args.shipment_id]
        if not group:
            parser.error(f"Unknown shipment {args.shipment_id!r}")
        result = rank_routes(group, profiles[args.profile], Constraints(args.max_cost, args.max_days, args.max_delay_probability))
        print(explain(result))
        if result["status"] == "ok":
            print("\nRanking:")
            for index, item in enumerate(result["ranked"], 1):
                r = item["route"]
                print(f" {index}. {r.route_id} | score {item['score']:.1f} | ${r.cost_usd:,.0f} | {r.transit_days:.0f} days | delay {r.delay_probability:.0%} | {r.hubs}")
        elif result.get("excluded"):
            for item in result["excluded"]:
                print(f" {item['route_id']}: violates {', '.join(item['violations'])}")
    else:
        print("Selected-route score and single-criterion wins on synthetic data:")
        for row in evaluate(routes, profiles):
            n = row["shipments"]
            w = row["criterion_wins"]
            print(f" {row['profile']}: {n} shipments; coverage {row['coverage']:.0%}; mean selected score {row['average_score']:.1f}/100 (lower is better); cheapest/fastest/lowest-risk wins {w['cost']}/{w['time']}/{w['risk']}")


if __name__ == "__main__":
    main()
