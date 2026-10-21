# Aiqon Shipment Route Recommender

A small, explainable route decision system for the Aiqon take-home assignment. It ranks candidate routes by cost, transit time, and delay risk; supports shipment-specific weights and limits; and explains the recommendation against the next-best option.

**Live demo:** [Shipment Route Planner](https://developer0880.pythonanywhere.com/)

## Quick start

Requires Python 3.10+ and uses only the standard library.

```bash
python3 main.py list
python3 main.py recommend SHP-001
python3 main.py recommend SHP-001 --profile time_sensitive
python3 main.py recommend SHP-001 --max-cost 5000 --max-days 30
python3 main.py evaluate
```

Use `python3 main.py --help` for the available commands. The `data/routes.csv` file contains 30 synthetic shipments with four candidate routes apiece. `data/profiles.json` contains three example preference profiles. All amounts are illustrative USD values; the dataset is not operational or market data.

## Optional browser UI

The assignment does not require a UI, so the CLI remains the simplest path and has no additional dependencies. You can try the [hosted demo](https://developer0880.pythonanywhere.com/) or run the interface locally:

```bash
python3 ui.py
```

Open `http://127.0.0.1:8000` in a browser. Select a shipment and profile, adjust the cost/time/risk weights, and optionally set hard cost, time, or delay-risk limits. The page shows the selected route, its score breakdown, a plain-language trade-off explanation, and a ranked comparison of alternatives. Stop the local server with Ctrl+C.

## Deploy the UI on PythonAnywhere

The local UI uses Python's development HTTP server. For PythonAnywhere, use the WSGI entry point in `pythonanywhere_wsgi.py`; it serves the same page and recommendation logic without starting a separate server. It uses only the Python standard library, so there are no packages to install.

1. Push this project to your GitHub repository, then clone it in a PythonAnywhere Bash console:

   ```bash
   git clone https://github.com/Manixhor/shipment-route-recommender.git
   ```

2. In PythonAnywhere, create a web app using **Manual configuration** and select a Python version compatible with the project.
3. Open the WSGI configuration file linked from the **Web** tab. Replace its application setup with the following, changing `YOURUSERNAME` if needed:

   ```python
   import sys
   project_path = '/home/YOURUSERNAME/shipment-route-recommender'
   if project_path not in sys.path:
       sys.path.insert(0, project_path)
   from pythonanywhere_wsgi import application
   ```

4. Save the WSGI file, then click **Reload** on the PythonAnywhere **Web** tab and open the web app URL shown there.

The app reads the checked-in CSV and profile JSON from the project folder. When you push code or data changes later, pull them in the PythonAnywhere Bash console and reload the web app. PythonAnywhere's current free account has limits and its free web app expires after one month; see [current free account features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/).

## Decision model

Feasibility is checked first. Optional maximum cost, transit days, and risk constraints remove routes that violate the shipment's requirements. Remaining routes receive a weighted score from 0 to 100, with lower scores preferred. Each metric is normalized against the candidate routes for that shipment: the minimum is 0 and maximum is 100. The default weights are cost 0.40, time 0.35, and delay probability 0.25. Risk uses the supplied estimated probability of a material delay, expressed between 0 and 1. Weights are normalized to sum to one.

The recommendation includes its component scores and concise comparisons to the runner-up. If constraints eliminate every route, the system returns a clear infeasible result rather than quietly relaxing a requirement. Ties are resolved by lower risk, then lower cost, then route ID.

Profiles: `balanced` (default), `cost_sensitive`, and `time_sensitive`. These are illustrative preferences; operators should set weights and limits based on service commitments and business context. A route's score is relative to its shipment's candidate set and should not be compared across shipments.

## Why this approach is useful

- **It makes competing priorities explicit.** Profiles and editable weights show how a cost-first decision differs from a time-first decision.
- **It respects operational requirements.** Hard limits filter out unacceptable routes before ranking; the tool says when no route qualifies.
- **It is explainable.** Operators see the score components, the runner-up comparison, and the exact route attributes behind the choice.
- **It is easy to reproduce and inspect.** The checked-in synthetic CSV, fixed-seed generator, and standard-library implementation make the example straightforward to run and change.
- **It supports a human decision.** The tool compares the given options; it does not claim to generate routes or replace planner approval.

It is most effective when shipment-level cost, transit estimates, and calibrated delay probabilities are trustworthy and operators have agreed on meaningful weights and limits. It is less dependable when estimates are stale or uncertain, the candidate route set changes materially, or omitted factors such as capacity and emissions drive the decision.

## Evaluation

`python3 main.py evaluate` reports recommendation coverage, mean normalized score of selected routes, and how often the selection is cheapest, fastest, or lowest risk. The synthetic routes are intentionally constructed with trade-offs: typically no single option is best on every dimension. This is a descriptive consistency check, not evidence of real-world performance or calibration.

## Files

- `main.py`: CLI and orchestration.
- `ui.py`: optional local browser interface; starts only on the local computer.
- `pythonanywhere_wsgi.py`: WSGI entry point for the PythonAnywhere-hosted interface.
- `route_recommender.py`: data loading, validation, scoring, explanation, and evaluation logic.
- `generate_data.py`: deterministic generator for the sample routes (seed `20261019`).
- `data/routes.csv`: synthetic shipment-route candidates.
- `data/profiles.json`: editable objective profiles.
- `report.pdf`: technical summary and limitations.

Regenerate the checked-in sample data with `python3 generate_data.py`.

## Limitations and next steps

Min-max scaling is sensitive to outliers and changes when candidate routes are added or removed. Delay probability is treated as known and accurate, although real estimates are uncertain and may be correlated with congestion or geopolitical exposure. The model omits capacity, emissions, transshipment handling, service-level penalties, and interactions between legs. For production use, replace synthetic inputs with governed data, calibrate delay estimates, set policy-approved constraints, show sensitivity to uncertain inputs, and retain planner review for exceptions.

## Assumptions

- Each CSV row is a complete route alternative for one shipment; leg-level operational planning is out of scope.
- Route cost, days, and delay probability are comparable within a shipment.
- `risk_index` is an illustrative 0–100 indicator included for context; the baseline ranking uses delay probability as the reliability/risk measure to avoid counting correlated signals twice.
- This tool recommends among supplied alternatives; it does not generate routes.
# shipment-route-recommender
