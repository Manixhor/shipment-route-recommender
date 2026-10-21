"""Regenerate the illustrative route dataset with a fixed random seed."""
import csv
import random
from pathlib import Path

SEED = 20261019
PORTS = ["Singapore", "Colombo", "Dubai", "Rotterdam", "Hamburg", "Busan", "Shanghai", "Jebel Ali", "Valencia", "Piraeus"]
FIELDS = ["shipment_id", "route_id", "origin", "destination", "hubs", "cost_usd", "transit_days", "delay_probability", "risk_index"]
ARCHETYPES = [(-0.14, 0.27, 0.16), (0.20, -0.22, 0.11), (0.12, 0.10, -0.48), (0.02, -0.02, -0.08)]


def generate(path: str | Path = Path(__file__).parent / "data/routes.csv") -> None:
    rng = random.Random(SEED)
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for i in range(1, 31):
            base_cost = rng.randint(2400, 6200)
            base_days = rng.randint(18, 38)
            for j, (cost_shift, time_shift, risk_shift) in enumerate(ARCHETYPES, 1):
                cost = max(900, round(base_cost * (1 + cost_shift + rng.uniform(-.035, .035)) / 10) * 10)
                days = max(8, round(base_days * (1 + time_shift + rng.uniform(-.04, .04))))
                delay = min(.55, max(.025, round(rng.uniform(.06, .24) * (1 + risk_shift), 3)))
                risk = min(95, max(5, round(delay * 100 + rng.uniform(-9, 15))))
                hubs = " → ".join(rng.sample(PORTS, 2 if j < 4 else 1))
                writer.writerow({
                    "shipment_id": f"SHP-{i:03d}", "route_id": f"SHP-{i:03d}-R{j}",
                    "origin": f"Origin-{(i-1)%6+1:02d}", "destination": f"Destination-{(i-1)%5+1:02d}",
                    "hubs": hubs, "cost_usd": cost, "transit_days": days,
                    "delay_probability": delay, "risk_index": risk,
                })


if __name__ == "__main__":
    generate()
    print(f"Wrote {Path(__file__).parent / 'data/routes.csv'}")
