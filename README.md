# Grade Change Intelligence System

An intelligent assistant for a paper mill's Quality Control System (QCS) that predicts and helps prevent off-spec paper during grade changes, learning from historical transition data.

The system watches an in-progress grade change, flags rising risk of exceeding the 2.5% Basis Weight deviation limit *before* it happens, recommends corrective setpoint adjustments based on similar historical recoveries, and explains the reasoning behind every suggestion.

The user interface is a **React + TypeScript** app. All model logic stays in **Python**, reached over a REST API:

```
React (UI)  ──HTTP──▶  FastAPI  ──▶  modules/  (Random Forest · Gradient Boosting · KNN · correlations)
    ◀────────JSON──────────────────────┘
```

No prediction, scoring, projection or recommendation logic is reimplemented in JavaScript. The browser formats and draws what Python returns.

---

## Quickstart

Requires **Python 3.12+** and **Node.js 20+**. Two terminals: the API has to be up before the UI is useful.

### 1. Backend (port 8000) — start this first

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd backend
uvicorn main:app --port 8000
```

Wait for the readiness line before opening the UI:

```
Models ready (23.9s). 119 events, 344 recovery patterns.
```

That pause is the one-time warm-up: reading ~50K samples, running the correlation suite, training the classifier and regressor, and building the KNN recovery library. It happens **once at startup**, not per request, so every API call afterwards is served from warm objects.

Check it with:

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ready","events":119,"startup_seconds":23.91}
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### 2. Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so the browser talks to a same-origin path and CORS never comes up during a demo. The API also sends CORS headers for ports 5173/4173, so a production build can call it directly — point it somewhere else with `VITE_API_BASE_URL`.

If the API is not running, the UI says so plainly ("Prediction service offline") with the command to start it, rather than showing a raw fetch error.

---

## The four views

| View | What it shows |
|------|---------------|
| **Live Monitor** | Event selector, Moderate/Extreme demo presets, simulation time slider, risk level, current & projected (60s) deviation, status label, plain-language prediction explanation, basis-weight and deviation charts, process-variable detail, future-state projection with dashed forward extrapolation and a "Now" marker, per-60s rate-of-change metrics, recipe-limit table with live values, and recommendation cards with Accept/Reject |
| **Correlations** | Finding counts by impact, six discovered correlations with r-value, p-value, recommendation, source and variables, grade-pair difficulty chart, and the twelve highest-impact parameters on stabilization with plain-language explanations |
| **Historical Events** | Deviation vs stabilization scatter across all 119 events, sortable event register, per-event detail metrics, full-transition charts, operator action log, and optimal setpoints for the grade |
| **Feedback Log** | Accept/reject totals and accept rate, full decision history, per-variable breakdown, CSV download |

Interaction details: the time slider debounces ~150ms so a drag fires one request instead of one per pixel; responses are cached per `(event, time)` so scrubbing back is instant; requests slower than 300ms show a skeleton or spinner instead of a blank flash; Accept/Reject switches to a recorded badge immediately without waiting on a re-render.

---

## API

All endpoints are under `/api`.

| Method | Endpoint | Returns |
|--------|----------|---------|
| `GET` | `/events` | All events: id, grade, max deviation, stabilization time, operator action count |
| `GET` | `/events/{id}` | One event summary plus its transition duration |
| `GET` | `/events/{id}/timeline` | Full timeseries for one event, plus operator actions |
| `GET` | `/events/{id}/predict?t=` | Risk level, current & projected deviation, status label, explanation, contributing factors |
| `GET` | `/events/{id}/projection?t=` | Forward trend extrapolation: deviation plus correlated moisture/steam, and per-60s rates |
| `GET` | `/events/{id}/recommendations?t=` | Setpoint changes with rationale, source tag, similarity match %, and recipe-limit clamp status |
| `GET` | `/correlations` | Correlation findings and model feature importances |
| `GET` | `/recipe-limits/{grade}` | Min/max operating ranges; pass `event_id` and `t` to annotate with live values |
| `GET` | `/optimal-setpoints/{grade}` | Setpoints from the fastest historical transitions into a grade |
| `POST` | `/feedback` | Record a decision: `{event_id, timestamp, recommendation_id, decision}` |
| `GET` | `/feedback` | Decision history with accept/reject totals |
| `GET` | `/health`, `/model-info` | Readiness, model configuration, held-out evaluation metrics |

`timestamp` on `POST /feedback` is the simulation time in seconds that the recommendation was generated for. The API resolves the recommendation server-side from its id, so the logged values always match what the model actually said.

---

## Model performance

Evaluated with an **event-based holdout**: every sample from a held-out grade change goes exclusively to the test set, avoiding the leakage that random row splitting introduces on timeseries data.

| Metric | Held-out test |
|--------|---------------|
| Classifier accuracy | 94.5% (majority-class baseline 78.1%) |
| Precision / Recall | 83.9% / 92.8% |
| F1 | 88.1% |
| Regressor R² | 0.985 |
| Regressor MAE | 0.283% |

89 train events / 30 test events · 15,664 train samples / 5,280 test samples. Reproduce with `python3 scripts/evaluation_report.py`.

---

## Project structure

```
grade-change-intelligence/
├── backend/                            # FastAPI app — wraps the models, defines no model logic
│   ├── main.py                         # Entry point (uvicorn main:app)
│   ├── requirements.txt                # Web layer + the pinned ML stack
│   └── gci_api/
│       ├── app.py                      # App factory, CORS, startup warm-up
│       ├── api.py                      # Route definitions
│       ├── services.py                 # Read paths into the models + trend extrapolation
│       ├── registry.py                 # Process-wide singletons (data, models, feedback log)
│       ├── paths.py                    # Locates the repo root, data CSVs, feedback log
│       ├── schemas.py                  # Request validation
│       ├── serialization.py            # pandas/numpy → JSON-safe values
│       └── explanations.py             # Plain-language copy for model features
├── frontend/                           # React + TypeScript + Vite
│   ├── tailwind.config.js              # Design tokens: colours, type scale, radii, motion
│   └── src/
│       ├── lib/                        # Typed API client, React Query hooks, risk/format helpers
│       ├── store/                      # Zustand: selected event, sim time, decisions
│       ├── components/{ui,charts,layout,monitor}/
│       └── pages/                      # One file per view
├── app.py                              # Original Streamlit dashboard (still runnable)
├── modules/                            # Unchanged, validated model code
│   ├── correlation_analysis.py
│   ├── prediction_model.py
│   ├── recommendation_engine.py
│   └── recipe_limits.py
├── data/                               # Process timeseries (~50K rows) + 119-event summary
├── scripts/                            # Dataset generator, evaluation report
├── docs/                               # ARCHITECTURE.md, DOCUMENTATION.md
└── feedback_logs/                      # Operator decision log (written at runtime)
```

Both UIs read and write the same `feedback_logs/feedback_log.csv`, in the same format.

---

## Design notes

The interface is modelled on a DCS operator console (Honeywell Experion / TDC style), not a web dashboard. Every colour, size and radius the UI may use is declared in `frontend/tailwind.config.js`; the alarm/pen/tag semantics live in `frontend/src/lib/hmi.ts`.

- **Console surfaces** — page `#0A0E14`, panel face `#12181F`, header strip `#171E27`, recessed wells `#0D1218`. Panels are separated by 1px hairlines (`#1F2937`) with a 2px radius and no drop shadows, so they read as bezelled instruments rather than soft cards. A faint schematic grid sits behind the whole display area.
- **Alarm scale (ISA-18.2)** — CRITICAL `#E5484D`, HIGH `#F5A524`, MEDIUM `#F5D90A` (used sparingly), NORMAL `#2DD4BF`. Defined once and resolved through `alarmStyle()` wherever a state appears: banner, badge, table cell, chart stroke. Red is desaturated enough not to vibrate on a projector.
- **One interactive signal** — the same teal as NORMAL marks everything actionable: active display in the rail, transport slider, ACKNOWLEDGE control, focus ring.
- **Trend pens** — saturated recorder colours, one fixed pen per instrument tag (`BW.PV` blue, `BW.SP` green, `BW.DEV` violet, `MOI.PV` cyan, `ST.PV` amber, `SF.PV` magenta, `MS.PV` steel), each printed with its tag in a pen bar above the chart.
- **Typography** — IBM Plex Mono for every process value, tag code, setpoint and timestamp, with tabular figures so digits do not shift as the clock advances. IBM Plex Sans is reserved for prose (prediction explanation, rationale) and for uppercase letter-spaced panel labels. Fonts are bundled, so the app renders correctly with no outbound network.
- **Instrument conventions** — variables carry tag codes alongside human names (`Steam Pressure · ST.PV`), events are tagged `GC-0046`, screens are numbered `DISP-01`…`DISP-04`, and process values are shown as faceplates: large digits plus a bar locating the reading inside its recipe range, with a tick at the operating limit.
- **One signature moment** — the trends are strip-chart recorders: traces sit on graph paper, a square pen nib rests on the newest sample and blinks on a slow two-step cycle, and a dashed NOW scan line divides measured paper from extrapolation. Nothing else in the app animates, and it respects `prefers-reduced-motion`.

---

## Deployment

For a hosted demo the app runs as **one service**: FastAPI serves the API *and* the compiled React bundle, so there is a single URL, no CORS configuration, and no separate static host. The API detects `frontend/dist` at startup and mounts it; unknown paths return `index.html` so client-side routes like `/correlations` survive a cold link.

### Container

Every push to `main` builds the image, starts it, probes every endpoint plus the
four client-side routes, asserts the held-out metrics still read 94.5% / 88.1% /
0.985 from inside the container, and only then publishes to GHCR. So a
ready-to-run image already exists:

```bash
docker run -p 8000:8000 ghcr.io/ritik-roushan-rana/grade-change-intelligence:latest
```

Or build it yourself:

```bash
docker build -t grade-change-intelligence .
docker run -p 8000:8000 grade-change-intelligence
```

Then open <http://localhost:8000>. The multi-stage build compiles the UI in a Node stage and copies the bundle into the Python stage alongside `modules/` and `data/`.

Any host that runs a container will take this image as-is: Render, Fly.io,
Railway, Cloud Run, an EC2 box with Docker. Point it at port 8000 (or set `PORT`)
and give it a 512 MB instance.

### Verifying a deployment

`scripts/smoke_test.sh` checks the things a "deploy succeeded" message can still
get wrong. Point it at any running instance:

```bash
./scripts/smoke_test.sh                        # local, defaults to :8000
./scripts/smoke_test.sh https://your-host.app  # a live deployment
```

It waits out the model warm-up, then asserts the service reports ready with all
119 events loaded, every endpoint the UI calls answers 200 (including a scored
prediction and its recommendations, so the classifier, regressor and KNN engine
are all exercised), the held-out metrics still read 94.5% / 88.1% / 0.985 from
inside the deployed artifact, the four client-side routes return the app shell,
an unknown `/api` path still returns JSON 404, and the hashed bundle referenced
by `index.html` is actually served. Non-zero exit on the first failure.

CI runs this same script twice: once against the freshly built image, and again
after publishing, against the image pulled back down from the registry.

### Vercel — frontend only, API elsewhere

**Vercel cannot host the API.** Two independent blockers:

- **Size.** scipy, pandas, scikit-learn and numpy total ~253 MB installed, against
  Vercel's 250 MB unzipped serverless function limit — exceeded before any
  project code is added.
- **Lifecycle.** Functions are per-invocation. There is no long-lived process to
  hold the trained models, so the 25-60 s warm-up would run on every cold
  invocation or time out.

A Vercel deployment therefore serves the UI while every `/api/*` call returns
404. `frontend/vercel.json` adds the SPA fallback so client-side routes like
`/correlations` resolve on a cold link, but the UI still needs an API to talk to.

That file lives in `frontend/`, not the repository root, because the Vercel
project's **Root Directory** is `frontend` — paths in `vercel.json` resolve
relative to the Root Directory, so a root-level config with `cd frontend` and
`frontend/dist` in it points one level too deep and fails the build. It
deliberately contains no build overrides: Vercel auto-detects Vite from
`frontend/package.json` and that already works.

To run split hosting, deploy the API as a container (see above) and then wire the
two together:

| Where | Setting | Value |
|---|---|---|
| Vercel project → Environment Variables | `VITE_API_BASE_URL` | `https://your-api-host.example.com` |
| API host | `CORS_ORIGINS` | `https://your-project.vercel.app` |

Both are already supported in code; no changes are needed. Redeploy Vercel after
setting the variable — it is read at build time, not at runtime.

Also check **Settings → Deployment Protection** on the Vercel project. Vercel
Authentication is on by default for some accounts, which makes preview and
production URLs redirect to a Vercel SSO login instead of serving the app.

The single-service container remains the simpler option: one URL, no CORS, no
split env wiring, and it is what the health check, blueprint and CI verify.

### Render

`render.yaml` is a ready blueprint — point Render at the repository and choose **New → Blueprint**. It sets `healthCheckPath: /api/health` and attaches a 1 GB disk mounted at `/var/data`, with `FEEDBACK_LOG_DIR` pointed into it so the operator feedback log survives redeploys.

### What to expect when hosting

| | |
|---|---|
| Cold start | **~25 s on a fast CPU, up to ~60 s on a shared runner** (measured 59 s on a GitHub Actions runner). Models train at startup, not per request. The socket opens only when the service is genuinely ready, so a passing health check means it can serve traffic — but give the host a generous initial health-check grace period. |
| Memory | **~190 MB** in the container once warm (~80 MB for the API process alone). A 512 MB instance is enough; 256 MB is not. |
| Workers | **One.** Each worker would train its own copy of the models — triple the memory and startup for no gain at demo concurrency. |
| Feedback log | The only runtime write. On a host with an ephemeral filesystem it resets on redeploy; mount a volume and set `FEEDBACK_LOG_DIR` to keep it. |
| Sleeping instances | Free tiers that idle out pay the ~25 s warm-up again on the next request. For a live demo, use a plan that stays awake. |
| Auth | **There is none.** Every endpoint, including `POST /api/feedback`, is open. That is fine for a private demo URL; put it behind access control before exposing it anywhere real. |

### Environment variables

| Variable | Purpose |
|---|---|
| `PORT` | Port to bind. Defaults to 8000; hosts that inject it are honoured. |
| `FEEDBACK_LOG_DIR` | Where `feedback_log.csv` lives. Point at a mounted volume to persist it. |
| `FRONTEND_DIST` | Override the location of the built UI. Unset it to run API-only. |
| `CORS_ORIGINS` | Comma-separated allowed origins. Only needed if the UI is hosted separately. |
| `VITE_API_BASE_URL` | Build-time only. Leave empty for the single-service setup so the bundle calls a relative `/api`. |

---

## Original Streamlit dashboard

`app.py` is untouched and still runs, which makes it easy to compare the two front ends side by side:

```bash
pip install -r requirements.txt
streamlit run app.py                     # http://localhost:8501
```

---

## Running components individually

```bash
python3 scripts/evaluation_report.py       # Model evaluation report
python3 scripts/generate_grade_change_data.py  # Regenerate the dataset (seeded, SEED = 42)
python3 -m modules.correlation_analysis    # Correlation findings
python3 -m modules.prediction_model        # Train + report metrics
python3 -m modules.recommendation_engine   # Build recovery library
```

Frontend checks:

```bash
cd frontend
npm run typecheck                          # tsc --noEmit
npm run build                              # typecheck + production bundle
```

---

## Data

The dataset is **synthetic**, produced by `scripts/generate_grade_change_data.py`. It simulates a Honeywell QCS / MD-control style paper machine across 119 grade-change events, with deliberately embedded, discoverable relationships — for example a steam-pressure lag driving moisture, which in turn drives basis weight. The generator is seeded, so output is reproducible.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design, data flow, validation summary, honest model metrics
- [Full documentation](docs/DOCUMENTATION.md) — module internals, feature engineering, requirement coverage
