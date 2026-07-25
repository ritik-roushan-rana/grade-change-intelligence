# Grade Change Intelligence System

An intelligent assistant for a paper mill's Quality Control System (QCS) that predicts and helps prevent off-spec paper during grade changes, learning from historical transition data.

The system watches an in-progress grade change, flags rising risk of exceeding the 2.5% Basis Weight deviation limit *before* it happens, recommends corrective setpoint adjustments based on similar historical recoveries, and explains the reasoning behind every suggestion.

---

## Features

| Module | What it does |
|--------|--------------|
| **Correlation Analysis** | Discovers real process relationships — steam→moisture lag, filler→ash variability, grade-pair difficulty ranking, early volatility signals |
| **Prediction Model** | Random Forest classifier (will deviation breach 2.5% in the next 60s?) + Gradient Boosting regressor (projected deviation magnitude) |
| **Recommendation Engine** | KNN similarity search over a library of historical recoveries, returning weighted setpoint adjustments with rationale |
| **Recipe Limits** | Per-grade constraint tables so recommendations stay inside valid operating ranges |
| **Feedback Logging** | Records every operator accept/reject decision with full context for later review |

Model performance is evaluated with an **event-based holdout** (all samples from a held-out grade change go exclusively to the test set) to avoid the data leakage that random row splitting introduces. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for honest metrics.

---

## Quickstart

Requires Python 3.10+.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the dashboard
streamlit run app.py
```

Then open http://localhost:8501.

Alternatively use the launch script:

```bash
./run_dashboard.sh
```

---

## Project Structure

```
grade-change-intelligence/
├── app.py                              # Streamlit dashboard (main entry point)
├── requirements.txt                    # Pinned Python dependencies
├── run_dashboard.sh                    # Convenience launch script
├── .streamlit/config.toml              # Dark theme + server config
├── modules/
│   ├── correlation_analysis.py         # Correlation discovery
│   ├── prediction_model.py             # ML risk prediction
│   ├── recommendation_engine.py        # KNN recovery matching + feedback logging
│   └── recipe_limits.py                # Grade recipe constraint tables
├── data/
│   ├── grade_change_timeseries.csv     # Process timeseries (~50K rows, 15-sec resolution)
│   └── grade_change_event_summary.csv  # Per-event outcome summary (119 events)
├── scripts/
│   ├── generate_grade_change_data.py   # Synthetic dataset generator (seeded, reproducible)
│   └── evaluation_report.py            # Prints model evaluation report
├── docs/
│   ├── ARCHITECTURE.md                 # System architecture & validation
│   └── DOCUMENTATION.md                # Extended documentation
└── feedback_logs/                      # Operator decision log (written at runtime)
```

---

## Data

The dataset is **synthetic**, produced by `scripts/generate_grade_change_data.py`. It simulates a Honeywell QCS / MD-control style paper machine across 119 grade-change events, with deliberately embedded, discoverable relationships (for example a steam-pressure lag driving moisture, which in turn drives basis weight).

The committed CSVs are the exact inputs the dashboard reads. To regenerate them:

```bash
python3 scripts/generate_grade_change_data.py
```

The generator is seeded (`SEED = 42`), so output is reproducible. Adjust the `CONFIG` block at the top of the script to change event count, noise, or resolution.

---

## Deployment

The app is ready to deploy to [Streamlit Community Cloud](https://share.streamlit.io) straight from this repository.

| Setting | Value |
|---------|-------|
| Repository | `ritik-roushan-rana/grade-change-intelligence` |
| Branch | `main` |
| Main file path | `app.py` |
| Python version | **3.13** (set under *Advanced settings*) |

Python 3.13 is not optional: the pinned `numpy` and `scipy` releases require Python 3.12 or newer, so selecting 3.11 or older in the deploy dialog will fail during dependency installation.

No secrets or environment variables are needed — the dashboard reads only the bundled CSVs in `data/`.

**Resource profile** (measured locally): peak memory ~320 MB, cold start ~26 seconds while the correlation analysis, model training, and recovery library are built. Results are held in `st.cache_resource`, so only the first visit after a restart pays that cost. Both figures sit within Community Cloud's free-tier limits.

The dark theme is pinned in `.streamlit/config.toml`. The dashboard's custom CSS is built for a dark surface, so leaving the theme to the viewer's local preference would render it with unreadable contrast.

---

## Running Components Individually

```bash
python3 scripts/evaluation_report.py       # Model evaluation report
python3 -m modules.correlation_analysis    # Correlation findings
python3 -m modules.prediction_model        # Train + report metrics
python3 -m modules.recommendation_engine   # Build recovery library
```

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design, data flow, validation summary, honest model metrics
- [Full documentation](docs/DOCUMENTATION.md) — module internals, feature engineering, requirement coverage
