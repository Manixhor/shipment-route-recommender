#!/usr/bin/env python3
"""Optional local browser interface for the route recommender."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from route_recommender import Constraints, explain, load_profiles, load_routes, rank_routes

ROOT = Path(__file__).resolve().parent

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shipment Route Planner</title><style>
:root{--ink:#172c3d;--muted:#617384;--line:#dce5eb;--blue:#154b6b;--teal:#07818b;--bg:#f3f7f9;--card:#fff;--good:#e7f5f1;--warn:#fff4df}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{background:linear-gradient(115deg,#12334d,#087f8c);color:white;padding:30px max(22px,calc((100vw - 1120px)/2)) 28px}
header h1{font-size:27px;margin:0 0 4px}header p{margin:0;color:#e1eff3}.wrap{max-width:1120px;margin:22px auto;padding:0 18px}
.grid{display:grid;grid-template-columns:310px 1fr;gap:18px;align-items:start}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:19px;box-shadow:0 3px 14px #16354b0b}
h2{font-size:17px;margin:0 0 12px}.field{margin:12px 0}.field label{display:block;font-weight:650;font-size:13px;margin-bottom:5px}.field select,.field input{width:100%;padding:9px 10px;border:1px solid #cbd7df;border-radius:7px;background:white;font:inherit;color:var(--ink)}
.weights{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.weights label{font-size:12px;color:var(--muted)}.weights input{margin-top:4px}.hint{font-size:12px;color:var(--muted);margin:5px 0}.limits{display:grid;grid-template-columns:1fr 1fr;gap:8px}.button{border:0;border-radius:8px;padding:11px 14px;background:var(--blue);color:white;font-size:14px;font-weight:700;width:100%;cursor:pointer}.button:hover{background:#0c3955}
.empty,.error{padding:22px;color:var(--muted);text-align:center}.error{color:#8a330e;background:var(--warn);border-radius:8px}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.pill{font-size:12px;padding:4px 9px;border-radius:99px;background:var(--good);color:#176552;font-weight:700;white-space:nowrap}.recommended{background:linear-gradient(120deg,#edf8f6,#f8fbfc);border:1px solid #cce8df;border-radius:10px;padding:16px;margin:12px 0}.recommended h3{margin:0;font-size:19px}.route-meta{color:var(--muted);margin:3px 0 10px}.why{margin:0;font-size:14px}.stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.stat{background:white;border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:13px}.stat b{display:block;font-size:15px}
.section-title{margin:18px 0 8px;font-size:14px;font-weight:750}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:var(--muted);font-weight:650;background:#f6f9fa}th,td{padding:9px 8px;border-bottom:1px solid var(--line)}tr.best{background:#f0f8f6}td.route{font-weight:700}.bars{display:grid;gap:8px}.barrow{display:grid;grid-template-columns:105px 1fr 42px;gap:10px;align-items:center;font-size:12px}.track{height:9px;background:#e9eff2;border-radius:99px;overflow:hidden}.fill{height:100%;background:var(--teal);border-radius:99px}.foot{font-size:12px;color:var(--muted);margin:16px 2px}.loading{opacity:.6;pointer-events:none}
@media(max-width:760px){.grid{grid-template-columns:1fr}.wrap{margin:13px auto}header{padding:23px 18px}.limits{grid-template-columns:1fr 1fr}table{font-size:12px}th,td{padding:8px 5px}.top{display:block}}
</style></head><body>
<header><h1>Shipment Route Planner</h1><p>Compare routes against your shipment priorities and operating limits.</p></header>
<main class="wrap"><div class="grid"><section class="card"><h2>Shipment preferences</h2>
<div class="field"><label for="shipment">Shipment</label><select id="shipment"></select></div>
<div class="field"><label for="profile">Starting profile</label><select id="profile"></select><p class="hint">Choose a profile, then adjust weights below. Weights are normalized automatically.</p></div>
<div class="weights"><div><label for="wc">Cost</label><input id="wc" type="number" min="0" max="100" value="40"></div><div><label for="wt">Transit time</label><input id="wt" type="number" min="0" max="100" value="35"></div><div><label for="wr">Delay risk</label><input id="wr" type="number" min="0" max="100" value="25"></div></div>
<div class="section-title">Optional hard limits</div><div class="limits"><div class="field"><label for="maxCost">Max cost (USD)</label><input id="maxCost" type="number" min="0" placeholder="No limit"></div><div class="field"><label for="maxDays">Max days</label><input id="maxDays" type="number" min="0" placeholder="No limit"></div></div>
<div class="field"><label for="maxRisk">Max delay probability (%)</label><input id="maxRisk" type="number" min="0" max="100" placeholder="No limit"></div>
<button class="button" id="go">Compare routes</button><p class="hint">A limit removes routes that exceed it. If none qualify, the tool reports that clearly.</p></section>
<section class="card" id="results"><div class="empty">Select a shipment and compare its available routes.</div></section></div>
<p class="foot">Decision support using synthetic data. Scores are relative to the shipment’s feasible route options; they are not calibrated service forecasts.</p></main>
<script>
const $=id=>document.getElementById(id);let profiles={};
function setWeights(){const w=profiles[$('profile').value];if(w){$('wc').value=Math.round(w.cost*100);$('wt').value=Math.round(w.time*100);$('wr').value=Math.round(w.risk*100)}}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function metric(v){return esc(v)}
function paint(data){const el=$('results');if(data.status!=='ok'){el.innerHTML='<div class="error">'+esc(data.message)+'</div>'+(data.excluded?.length?'<div class="section-title">Excluded routes</div><ul>'+data.excluded.map(x=>'<li><b>'+esc(x.route_id)+'</b>: '+esc(x.violations.join(', '))+'</li>').join('')+'</ul>':'');return}
const best=data.recommendation,r=best.route;let bars=Object.entries(best.components).map(([k,v])=>'<div class="barrow"><span>'+({cost:'Cost',time:'Transit time',risk:'Delay risk'}[k])+'</span><div class="track"><div class="fill" style="width:'+Math.max(0,Math.min(100,v))+'%"></div></div><span>'+v.toFixed(0)+'/100</span></div>').join('');
el.innerHTML='<div class="top"><div><h2>Recommended route</h2><span class="route-meta">'+esc(r.origin)+' → '+esc(r.destination)+' · '+esc(r.hubs)+'</span></div><span class="pill">Score '+best.score.toFixed(1)+' / 100</span></div><div class="recommended"><h3>'+esc(r.route_id)+'</h3><div class="stats"><div class="stat"><b>$'+Number(r.cost_usd).toLocaleString()+'</b>estimated cost</div><div class="stat"><b>'+r.transit_days+' days</b>transit time</div><div class="stat"><b>'+Math.round(r.delay_probability*100)+'%</b>estimated delay probability</div><div class="stat"><b>'+r.risk_index+'/100</b>context risk index</div></div><p class="why">'+esc(data.explanation)+'</p></div><div class="section-title">Score by criterion <span class="hint">(lower is better)</span></div><div class="bars">'+bars+'</div><div class="section-title">Route comparison</div><div style="overflow-x:auto"><table><thead><tr><th>Rank</th><th>Route</th><th>Score</th><th>Cost</th><th>Days</th><th>Delay</th><th>Hubs</th></tr></thead><tbody>'+data.ranked.map((x,i)=>'<tr class="'+(i===0?'best':'')+'"><td>'+(i+1)+'</td><td class="route">'+esc(x.route.route_id)+'</td><td>'+x.score.toFixed(1)+'</td><td>$'+Number(x.route.cost_usd).toLocaleString()+'</td><td>'+x.route.transit_days+'</td><td>'+Math.round(x.route.delay_probability*100)+'%</td><td>'+esc(x.route.hubs)+'</td></tr>').join('')+'</tbody></table></div>'}
async function compare(){const el=$('results');el.classList.add('loading');try{const p=new URLSearchParams({shipment_id:$('shipment').value,cost_weight:$('wc').value,time_weight:$('wt').value,risk_weight:$('wr').value});if($('maxCost').value)p.set('max_cost',$('maxCost').value);if($('maxDays').value)p.set('max_days',$('maxDays').value);if($('maxRisk').value)p.set('max_delay_probability',Number($('maxRisk').value)/100);const res=await fetch('/api/recommend?'+p);const data=await res.json();if(!res.ok)throw Error(data.error||'Request failed');paint(data)}catch(e){el.innerHTML='<div class="error">'+esc(e.message)+'</div>'}finally{el.classList.remove('loading')}}
async function init(){const res=await fetch('/api/options');const data=await res.json();profiles=data.profiles;for(const id of data.shipments){const o=document.createElement('option');o.value=id;o.textContent=id;$('shipment').append(o)}for(const [name,w] of Object.entries(profiles)){const o=document.createElement('option');o.value=name;o.textContent=name.replaceAll('_',' ');$('profile').append(o)}$('profile').addEventListener('change',setWeights);$('go').addEventListener('click',compare);setWeights();compare()}
init().catch(e=>{$('results').innerHTML='<div class="error">Could not load route data: '+esc(e.message)+'</div>'});
</script></body></html>"""


def create_handler(routes, profiles):
    grouped = {}
    for route in routes:
        grouped.setdefault(route.shipment_id, []).append(route)

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                raw = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if parsed.path == "/api/options":
                self._json(200, {"shipments": sorted(grouped), "profiles": profiles})
                return
            if parsed.path != "/api/recommend":
                self._json(404, {"error": "Not found"})
                return
            query = parse_qs(parsed.query)
            try:
                shipment_id = query.get("shipment_id", [""])[0]
                candidates = grouped.get(shipment_id)
                if not candidates:
                    raise ValueError("Choose a valid shipment ID.")
                if all(k in query for k in ("cost_weight", "time_weight", "risk_weight")):
                    weights = {"cost": float(query["cost_weight"][0]), "time": float(query["time_weight"][0]), "risk": float(query["risk_weight"][0])}
                else:
                    weights = profiles["balanced"]
                limits = {}
                for param, key in (("max_cost", "max_cost"), ("max_days", "max_days"), ("max_delay_probability", "max_delay_probability")):
                    if param in query:
                        limits[key] = float(query[param][0])
                        if limits[key] < 0 or (key == "max_delay_probability" and limits[key] > 1):
                            raise ValueError(f"{param} is outside its valid range.")
                result = rank_routes(candidates, weights, Constraints(**limits))
                result["explanation"] = explain(result)
                def serial(item):
                    return {"route": item["route"].__dict__, "score": item["score"], "components": item["components"]}
                result["ranked"] = [serial(item) for item in result["ranked"]]
                result["recommendation"] = serial(result["recommendation"]) if result["recommendation"] else None
                result["runner_up"] = serial(result["runner_up"]) if result["runner_up"] else None
                self._json(200, result)
            except (ValueError, KeyError) as exc:
                self._json(400, {"error": str(exc)})

        def log_message(self, fmt, *args):
            print(f"[ui] {self.address_string()} - {fmt % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional local browser UI for shipment route recommendations")
    parser.add_argument("--host", default="127.0.0.1", help="local bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", default=str(ROOT / "data/routes.csv"))
    parser.add_argument("--profiles", default=str(ROOT / "data/profiles.json"))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("For safety, the demo server only binds to the local computer.")
    routes, profiles = load_routes(args.data), load_profiles(args.profiles)
    server = ThreadingHTTPServer((args.host, args.port), create_handler(routes, profiles))
    print(f"Route Planner UI is ready at http://{args.host}:{args.port} (press Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Route Planner UI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
