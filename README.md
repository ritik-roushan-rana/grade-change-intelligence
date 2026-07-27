# Grade Change Intelligence System

**Live demo:** deploy your own in a few minutes — see [Deployment](#deployment).

> Startup no longer trains anything. The two estimators are fitted during the
> image build and stored in `artifacts/model_cache.joblib`, so the service is
> ready **~0.3 s** after the container starts, against the ~25 s it used to spend
> retraining — 7 minutes of it on a free 0.1-CPU instance, which is what made the
> old demo link look broken. Ready-made configs for Fly.io, Render and Hugging
> Face Spaces are in the repo.

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
Models ready (23.5s). 119 events, 344 recovery patterns.
```

That pause is the one-time warm-up: reading ~50K samples, running the correlation suite, training the classifier and regressor, and building the KNN recovery library. It happens **once at startup**, not per request, so every API call afterwards is served from warm objects.

Skip it after the first run by fitting the models once and caching them:

```bash
python3 scripts/build_model_cache.py     # ~25s, writes artifacts/model_cache.joblib
```

Startup then drops to **~0.3 s** — the API reloads the fitted objects instead of
retraining. The cache is keyed to the CSVs, the files in `modules/` and the
installed library versions, so editing a model or regenerating the data makes the
API ignore it and train as before. Rerun the script to refresh it.

Check either path with:

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ready","events":119,"startup_seconds":0.31,"models":"cache"}
# models: "cache" = restored from artifacts/, "trained" = fitted in this process
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

## The displays

| View | What it shows |
|------|---------------|
| **Live Monitor** | Event selector, Moderate/Extreme demo presets, simulation time slider, risk level, current & projected (60s) deviation, status label, plain-language prediction explanation, basis-weight and deviation charts, process-variable detail, future-state projection with dashed forward extrapolation and a "Now" marker, per-60s rate-of-change metrics, recipe-limit table with live values, and recommendation cards with Accept/Reject |
| **Correlations** | Finding counts by impact, six discovered correlations with r-value, p-value, recommendation, source and variables, grade-pair difficulty chart, and the twelve highest-impact parameters on stabilization with plain-language explanations |
| **Historical Events** | Deviation vs stabilization scatter across all 119 events, sortable event register, per-event detail metrics, full-transition charts, operator action log, and optimal setpoints for the grade |
| **Feedback Log** | Accept/reject totals and accept rate, full decision history, per-variable breakdown, CSV download |
| **Settings** | Resets for each kind of state the station holds: browser display cache, session decision marks, event/clock selection, the API's memoised scoring (with hit/miss counters), and the persistent feedback log. Every control states what it drops and what survives; clearing the feedback log requires typing a confirmation token, and there is deliberately no control to drop the trained models |

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
| `DELETE` | `/feedback?confirm=CLEAR` | Clear the feedback log. The token is required, not optional |
| `GET` | `/cache` | Hit/miss counters for the per-(event, time) scoring caches |
| `POST` | `/cache/clear` | Drop memoised scoring results. Trained models are retained |
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
│       ├── model_cache.py              # Load/save the build-time trained models
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
├── Dockerfile                          # Multi-stage build: UI bundle + trained models + API
├── fly.toml                            # Fly.io config (suspend/resume, health check)
├── render.yaml                         # Render blueprint (health check + feedback disk)
├── deploy/huggingface/                 # Space card front matter + one-command deploy script
├── scripts/build_model_cache.py        # Fit the models once, for fast startup
├── scripts/smoke_test.sh               # Verify any running deployment
├── modules/                            # Unchanged, validated model code
│   ├── correlation_analysis.py
│   ├── prediction_model.py
│   ├── recommendation_engine.py
│   └── recipe_limits.py
├── data/                               # Process timeseries (~50K rows) + 119-event summary
├── artifacts/                          # Trained models (build output, not committed)
├── docs/                               # ARCHITECTURE.md, DOCUMENTATION.md
└── feedback_logs/                      # Operator decision log (written at runtime)
```

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

Build the image yourself — the `Dockerfile` compiles the UI and packages it with
the API in one artifact:

```bash
docker build -t grade-change-intelligence .
docker run -p 8000:8000 grade-change-intelligence
```

An image published earlier still exists in GHCR and runs as-is, but nothing
rebuilds it now, so treat it as a snapshot rather than the current code:

```bash
docker run -p 8000:8000 ghcr.io/ritik-roushan-rana/grade-change-intelligence:latest
```

Then open <http://localhost:8000>. The multi-stage build compiles the UI in a Node stage and copies the bundle into the Python stage alongside `modules/` and `data/`.

The build also runs `scripts/build_model_cache.py`, so the image ships with the
models already fitted and the container is ready ~0.3 s after it starts. That is
the difference between a demo link that opens and one that looks broken while a
throttled CPU retrains a Random Forest.

Any host that runs a container will take this image as-is: Hugging Face Spaces,
Render, Fly.io, Railway, Cloud Run, an EC2 box with Docker. Point it at port 8000
(or set `PORT`) and give it a 512 MB instance.

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
inside the deployed artifact, all five client-side routes return the app shell,
an unknown `/api` path still returns JSON 404, and the hashed bundle referenced
by `index.html` is actually served. Non-zero exit on the first failure.

Run it against the container before you hand a URL to anyone — there is no CI
pipeline doing that check for you.

### Choosing a host

The prebuilt model artifact removes the warm-up on every host, so what separates
them now is only how fast an idle instance answers again:

| Host | Config in repo | Idle behaviour | Cost |
|---|---|---|---|
| **Fly.io** | `fly.toml` | Machine suspends and resumes in ~1 s with the models still in memory | Pay-as-you-go; a 512 MB shared-CPU machine is a couple of dollars a month, and less if it idles |
| **Render** | `render.yaml` | Free spins down after ~15 min, then a container start on 0.1 CPU; Starter stays awake | Free, or $7/mo Starter |
| **Hugging Face Spaces** | `deploy/huggingface/` | Free CPU basic (2 vCPU, 16 GB) sleeps after ~48 h and restarts on a visit | The hardware has no hourly cost, but creating a Docker Space needs a paid HF plan |
| **Cloud Run / any container host** | — | Scales to zero; cold visit is an image pull plus ~0.3 s | Free tier covers demo traffic |

### Fly.io — the recommended target

Suspend-and-resume is the reason: a woken machine still has the loaded models in
memory, so an idle demo answers in about a second rather than booting a container.

```bash
fly launch --copy-config --no-deploy   # rename `app` in fly.toml first — names are global
fly deploy
./scripts/smoke_test.sh https://your-app.fly.dev
```

`fly.toml` sets `internal_port = 8000`, a `/api/health` check, a 512 MB
shared-CPU machine, and `min_machines_running = 0` so an idle demo costs nothing.
Set it to `1` to keep the service permanently warm. The feedback log is
ephemeral unless you attach a volume — the commented block at the bottom of
`fly.toml` has the two commands.

### Hugging Face Spaces

A Space runs this same `Dockerfile` on **CPU basic** (2 vCPU, 16 GB — 20× the CPU
of Render's free plan) and only sleeps after about two days of inactivity. Worth
knowing before you plan on it: the hardware itself is free, but Hugging Face now
requires a paid plan to *create* a Space that runs on compute, Docker included.

1. Create the Space: <https://huggingface.co/new-space> → **Docker → Blank**,
   hardware **CPU basic**.
2. Push this repository to it:

```bash
export HF_TOKEN=hf_...                                  # write-scoped token
./deploy/huggingface/deploy.sh your-name/grade-change-intelligence
```

The script exports the tracked files of `HEAD`, prepends the Space card front
matter from `deploy/huggingface/space_card.md` to the README (Spaces reads
`sdk: docker` and `app_port: 8000` from there), and pushes one commit. Your
working tree is untouched, and it refuses to run on a dirty tree, so what you
publish is a commit you can point at.

3. Watch the build, then verify the running Space:

```bash
./scripts/smoke_test.sh https://your-name-grade-change-intelligence.hf.space
```

Notes specific to Spaces: the container runs as UID 1000, so the feedback log
directory is world-writable in the image; disk is ephemeral, so the log resets on
restart unless you attach persistent storage and set
`FEEDBACK_LOG_DIR=/data/feedback_logs`. A public Space is a public URL with no
auth in front of it — keep it private if that matters.

### Render — the original target, still supported

Two ways in, both landing on the same single service.

**From `render.yaml`** (Blueprint, and the one to prefer): point Render at the
repository and choose **New → Blueprint**. It builds from the current code, sets
`healthCheckPath: /api/health` and attaches a 1 GB disk at `/var/data`, with
`FEEDBACK_LOG_DIR` pointing into it so the operator feedback log survives
redeploys.

**From the published image** (nothing to build, but it is a snapshot — no
pipeline refreshes it):

1. **New → Web Service → Existing image from a registry**
2. Image URL: `ghcr.io/ritik-roushan-rana/grade-change-intelligence:latest`
3. **Advanced → Health Check Path:** `/api/health`
4. No environment variables and no start command — Render injects `PORT` and the image honours it.

Instance sizing: with the models baked into the image, startup is no longer the
bottleneck on any plan. What remains on **Free** (0.1 CPU) is that the instance
spins down after ~15 minutes of inactivity, so the next visitor waits for the
container to start, and every request is served by a tenth of a core. **Starter**
(0.5 CPU) stays awake. 512 MB of RAM is enough either way. Note that the
image published to GHCR predates the model cache, so a deployment from that
snapshot still trains at startup — build from `render.yaml` to get the fast boot.

Confirm the result:

```bash
./scripts/smoke_test.sh https://your-service.onrender.com
```

> Serverless function platforms are not an option for this service. The ML stack
> alone is ~253 MB installed (scipy 99, pandas 72, scikit-learn 48, numpy 34),
> which exceeds the ~250 MB bundle ceiling such platforms typically impose before
> any project code is added; and per-invocation functions have no long-lived
> process to hold the trained models, so the warm-up would run on every cold call
> or time out. This service needs a container or a persistent process.

### What to expect when hosting

| | |
|---|---|
| Cold start | **~0.3 s** from the image built by this `Dockerfile`: the models are fitted during the build and reloaded from `artifacts/model_cache.joblib`. Without that artifact (or if it no longer matches the data) the service trains at startup instead — ~25 s on a fast CPU, minutes on a throttled shared core. `/api/health` reports which path ran via `"models": "cache" \| "trained"`. |
| Memory | **~190 MB** in the container once warm (~80 MB for the API process alone). A 512 MB instance is enough; 256 MB is not. |
| Workers | **One.** Each worker would load its own copy of the models — triple the memory for no gain at demo concurrency. |
| Feedback log | The only runtime write. On a host with an ephemeral filesystem it resets on redeploy; mount a volume and set `FEEDBACK_LOG_DIR` to keep it. |
| Sleeping instances | An idled-out instance pays a container start on the next request — seconds, not minutes, now that nothing retrains. Fly's suspend/resume skips even that. Render free idles out after ~15 minutes, Spaces free CPU after ~48 hours. |
| Auth | **There is none.** Every endpoint, including `POST /api/feedback`, is open. That is fine for a private demo URL; put it behind access control before exposing it anywhere real. |

### Environment variables

| Variable | Purpose |
|---|---|
| `PORT` | Port to bind. Defaults to 8000; hosts that inject it are honoured. |
| `ARTIFACT_DIR` | Where the trained-model cache is read and written. Defaults to `artifacts/`. Point it at an empty directory to force training. |
| `FEEDBACK_LOG_DIR` | Where `feedback_log.csv` lives. Point at a mounted volume to persist it. |
| `FRONTEND_DIST` | Override the location of the built UI. Unset it to run API-only. |
| `CORS_ORIGINS` | Comma-separated allowed origins. Only needed if the UI is hosted separately. |
| `VITE_API_BASE_URL` | Build-time only. Leave empty for the single-service setup so the bundle calls a relative `/api`. |

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
