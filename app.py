"""
Grade Change Intelligence Dashboard
=====================================
Streamlit web application for the paper mill QCS Grade Change Intelligence System.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.correlation_analysis import CorrelationAnalyzer
from modules.prediction_model import PredictionModel
from modules.recommendation_engine import RecommendationEngine, FeedbackLogger
from modules.recipe_limits import get_limits_for_grade, get_limits_dataframe, check_within_limits

# ─── Page Config ───
st.set_page_config(
    page_title="Grade Change Intelligence",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS for clean dark look ───
st.markdown("""
<style>
    /* Global */
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    h1 { font-size: 1.8rem !important; font-weight: 700 !important; margin-bottom: 0.3rem !important; }
    h2 { font-size: 1.3rem !important; font-weight: 600 !important; }
    h3 { font-size: 1.1rem !important; font-weight: 600 !important; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0e1117; }
    [data-testid="stSidebar"] .stMarkdown p { font-size: 0.85rem; }

    /* Metrics */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #161b22 100%);
        border: 1px solid #2d333b;
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.5px; }

    /* Cards / Containers */
    .risk-card {
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.35);
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 74px;
    }
    .risk-card h2 { margin: 0; font-size: 1.5rem; color: white; line-height: 1.1; }
    .risk-card p { margin: 2px 0 0 0; font-size: 0.7rem; color: rgba(255,255,255,0.85); text-transform: uppercase; letter-spacing: 0.6px; }

    /* Recommendation cards */
    .rec-card {
        background: #161b22;
        border: 1px solid #2d333b;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .rec-card:hover { border-color: #58a6ff; }
    .rec-variable { font-weight: 700; font-size: 0.95rem; color: #58a6ff; }
    .rec-change { font-family: monospace; font-size: 0.9rem; }
    .rec-rationale { font-size: 0.8rem; color: #8b949e; margin-top: 6px; }
    .rec-source { font-size: 0.72rem; color: #6e7681; margin-top: 4px; }

    /* Expander */
    .streamlit-expanderHeader { font-size: 0.9rem !important; font-weight: 600 !important; }

    /* Tables */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Info/Success/Warning boxes */
    .stAlert { border-radius: 8px !important; }

    /* Dividers */
    hr { border-color: #21262d !important; }
</style>
""", unsafe_allow_html=True)

# ─── Paths ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TIMESERIES_PATH = os.path.join(DATA_DIR, "grade_change_timeseries.csv")
SUMMARY_PATH = os.path.join(DATA_DIR, "grade_change_event_summary.csv")
FEEDBACK_LOG_DIR = os.path.join(BASE_DIR, "feedback_logs")
FEEDBACK_LOG_PATH = os.path.join(FEEDBACK_LOG_DIR, "feedback_log.csv")
os.makedirs(FEEDBACK_LOG_DIR, exist_ok=True)


# ─── Cached Loading ───
@st.cache_data
def load_data():
    ts_df = pd.read_csv(TIMESERIES_PATH, parse_dates=["timestamp"])
    summary_df = pd.read_csv(SUMMARY_PATH)
    return ts_df, summary_df


@st.cache_resource
def load_correlation_analyzer():
    analyzer = CorrelationAnalyzer(TIMESERIES_PATH, SUMMARY_PATH)
    analyzer.run_full_analysis()
    return analyzer


@st.cache_resource
def load_prediction_model():
    model = PredictionModel(TIMESERIES_PATH, SUMMARY_PATH)
    model.train()
    return model


@st.cache_resource
def load_recommendation_engine():
    engine = RecommendationEngine(TIMESERIES_PATH, SUMMARY_PATH)
    engine.build_recovery_library()
    return engine


def get_feedback_logger():
    return FeedbackLogger(FEEDBACK_LOG_PATH)


# ═══════════════════════════════════════════════════════
# BOOT SEQUENCE
# ═══════════════════════════════════════════════════════
# Cold start costs ~26 seconds: reading ~50K samples, running the correlation
# suite, training two models, and building the KNN recovery library. Without
# feedback that is a blank page, so the work is staged behind a progress
# screen that names the step currently running.

_BOOT_STAGES = [
    ("Loading process data",
     "~50K samples across 119 grade-change events"),
    ("Discovering correlations",
     "Cross-correlation, variability and grade-pair analysis"),
    ("Training prediction models",
     "Random Forest classifier + Gradient Boosting regressor"),
    ("Building recovery library",
     "KNN index over successful historical recoveries"),
]

# Percent complete shown as each stage begins. Model training dominates the
# wall clock, so the bar is weighted to match rather than split evenly.
_BOOT_CHECKPOINTS = [4, 16, 28, 94]

_BOOT_CSS = """
<style>
@keyframes gci-spin   { to { transform: rotate(360deg); } }
@keyframes gci-pulse  { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
@keyframes gci-sheen  { 0% { transform: translateX(-100%); } 100% { transform: translateX(280%); } }
@keyframes gci-rise   { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

.gci-boot {
    display: flex; justify-content: center; align-items: center;
    min-height: 62vh; padding: 24px 12px;
    animation: gci-rise 0.45s ease both;
}
.gci-card {
    width: 100%; max-width: 470px;
    background: linear-gradient(160deg, #161b22 0%, #11151c 100%);
    border: 1px solid #2d333b; border-radius: 16px;
    padding: 34px 34px 26px;
    box-shadow: 0 18px 48px rgba(0,0,0,0.45);
}
.gci-logo { font-size: 2.4rem; line-height: 1; animation: gci-pulse 2.1s ease-in-out infinite; }
.gci-title { margin-top: 12px; font-size: 1.16rem; font-weight: 700; color: #e6edf3; letter-spacing: -0.2px; }
.gci-sub { margin-top: 3px; font-size: 0.76rem; color: #6e7681; text-transform: uppercase; letter-spacing: 1.1px; }

.gci-track {
    position: relative; height: 6px; margin: 22px 0 8px;
    background: #21262d; border-radius: 99px; overflow: hidden;
}
.gci-fill {
    height: 100%; border-radius: 99px;
    background: linear-gradient(90deg, #1f6feb, #58a6ff);
}
.gci-sheen {
    position: absolute; inset: 0 auto 0 0; width: 34%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.22), transparent);
    animation: gci-sheen 1.5s ease-in-out infinite;
}
.gci-meta { display: flex; justify-content: space-between; font-size: 0.72rem; color: #8b949e; }
.gci-pct { font-variant-numeric: tabular-nums; color: #58a6ff; font-weight: 600; }

.gci-steps { list-style: none; margin: 20px 0 0; padding: 0; }
.gci-step { display: flex; gap: 11px; align-items: flex-start; padding: 7px 0; }
.gci-mark {
    flex: 0 0 auto; width: 14px; height: 14px; margin-top: 2px;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 0.62rem; font-weight: 700;
}
.gci-mark-done { background: #238636; color: #ffffff; }
.gci-mark-idle { border: 2px solid #30363d; }
.gci-spin {
    flex: 0 0 auto; width: 14px; height: 14px; margin-top: 2px; border-radius: 50%;
    border: 2px solid rgba(88,166,255,0.25); border-top-color: #58a6ff;
    animation: gci-spin 0.75s linear infinite;
}
.gci-text { display: flex; flex-direction: column; line-height: 1.35; }
.gci-name { font-size: 0.85rem; color: #484f58; }
.gci-desc { font-size: 0.72rem; color: #30363d; }
.gci-step-active .gci-name { color: #e6edf3; font-weight: 600; }
.gci-step-active .gci-desc { color: #8b949e; }
.gci-step-done  .gci-name { color: #8b949e; }
.gci-step-done  .gci-desc { color: #484f58; }

.gci-note {
    margin-top: 22px; padding-top: 16px; border-top: 1px solid #21262d;
    font-size: 0.72rem; color: #6e7681; line-height: 1.5;
}
</style>
"""


def _render_boot(slot, stage_index, pct):
    """Paint the boot screen with `stage_index` in flight at `pct` complete."""
    steps = []
    for i, (name, desc) in enumerate(_BOOT_STAGES):
        if i < stage_index:
            marker, row_cls = '<div class="gci-mark gci-mark-done">&#10003;</div>', "gci-step gci-step-done"
        elif i == stage_index:
            marker, row_cls = '<div class="gci-spin"></div>', "gci-step gci-step-active"
        else:
            marker, row_cls = '<div class="gci-mark gci-mark-idle"></div>', "gci-step"
        steps.append(
            f'<li class="{row_cls}">{marker}'
            f'<div class="gci-text"><span class="gci-name">{name}</span>'
            f'<span class="gci-desc">{desc}</span></div></li>'
        )

    active = _BOOT_STAGES[stage_index][0] if stage_index < len(_BOOT_STAGES) else "Ready"

    slot.markdown(
        _BOOT_CSS
        + f"""
<div class="gci-boot">
  <div class="gci-card" role="status" aria-live="polite"
       aria-label="Starting Grade Change Intelligence: {active}, {pct} percent complete">
    <div class="gci-logo" aria-hidden="true">&#127981;</div>
    <div class="gci-title">Grade Change Intelligence</div>
    <div class="gci-sub">Honeywell QCS &middot; Paper Mill</div>

    <div class="gci-track" role="progressbar" aria-valuenow="{pct}"
         aria-valuemin="0" aria-valuemax="100">
      <div class="gci-fill" style="width:{pct}%;"></div>
      <div class="gci-sheen" aria-hidden="true"></div>
    </div>
    <div class="gci-meta"><span>{active}&hellip;</span><span class="gci-pct">{pct}%</span></div>

    <ul class="gci-steps">{''.join(steps)}</ul>

    <div class="gci-note">
      Models are trained once on first launch, then held in cache &mdash;
      later visits open instantly.
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


@st.cache_resource
def _boot_state():
    """Shared warm-start marker.

    Lives in the same cache as the models, so it is discarded whenever they
    are. That keeps the boot screen tied to real work: it appears on a genuine
    cold start and is skipped once the caches are populated.
    """
    return {"warm": False}


def _bootstrap():
    state = _boot_state()
    slot = None if state["warm"] else st.empty()

    def begin(i):
        if slot is not None:
            _render_boot(slot, i, _BOOT_CHECKPOINTS[i])

    begin(0)
    data = load_data()
    begin(1)
    correlation = load_correlation_analyzer()
    begin(2)
    predictor = load_prediction_model()
    begin(3)
    recommender = load_recommendation_engine()

    if slot is not None:
        _render_boot(slot, len(_BOOT_STAGES), 100)
        # Hold the completed state briefly, otherwise the 100% frame is
        # replaced before the browser paints it and the bar appears to stop
        # short of full.
        time.sleep(0.35)
        state["warm"] = True
        slot.empty()

    return data, correlation, predictor, recommender


if not os.path.exists(TIMESERIES_PATH) or not os.path.exists(SUMMARY_PATH):
    st.error("Process data not found — the dashboard has nothing to load.")
    st.markdown(
        f"Expected both CSVs in `{os.path.relpath(DATA_DIR, BASE_DIR)}/`. "
        "Regenerate them with:"
    )
    st.code("python3 scripts/generate_grade_change_data.py", language="bash")
    st.stop()

(ts_df, summary_df), analyzer, model, engine = _bootstrap()
feedback_logger = get_feedback_logger()

# ─── Chart template (dark) ───
CHART_TEMPLATE = "plotly_dark"
CHART_BG = "#0e1117"
CHART_PAPER_BG = "#0e1117"
CHART_GRID_COLOR = "#21262d"
CHART_FONT_COLOR = "#c9d1d9"


def style_chart(fig, height=400):
    """Apply consistent dark styling to charts."""
    fig.update_layout(
        template=CHART_TEMPLATE,
        height=height,
        paper_bgcolor=CHART_PAPER_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color=CHART_FONT_COLOR, size=11),
        legend=dict(
            orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5,
            font=dict(size=10), bgcolor="rgba(0,0,0,0)",
        ),
        title=dict(font=dict(size=13), x=0, xanchor="left"),
        margin=dict(l=55, r=25, t=45, b=60),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=CHART_GRID_COLOR, zeroline=False)
    fig.update_yaxes(gridcolor=CHART_GRID_COLOR, zeroline=False)
    return fig


# ═══════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════
st.sidebar.markdown(
    '<h2 style="margin:0;padding:0;">🏭 Grade Change<br>Intelligence</h2>',
    unsafe_allow_html=True,
)
st.sidebar.caption("Honeywell QCS | Paper Mill")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Live Monitor", "Correlations", "Historical Events", "Feedback Log"],
    index=0,
)

st.sidebar.divider()

# Quick demo presets
st.sidebar.markdown("**Demo Presets**")
demo_col1, demo_col2 = st.sidebar.columns(2)
with demo_col1:
    if st.button("⚡ Moderate", key="demo_mod", width="stretch",
                 help="Event 46 — typical transition"):
        st.session_state["selected_event"] = 46
with demo_col2:
    if st.button("🔥 Extreme", key="demo_ext", width="stretch",
                 help="Event 5 — worst-case"):
        st.session_state["selected_event"] = 5

st.sidebar.divider()

# Event selector — keyed so the choice persists across reruns
event_ids = sorted(summary_df["grade_change_event_id"].unique())
if "selected_event" not in st.session_state:
    st.session_state["selected_event"] = 46 if 46 in event_ids else event_ids[0]

# Records which suggestions have already been decided this session, so a
# suggestion can only be accepted or rejected once (prevents double-counting
# in the feedback log if a button is clicked repeatedly during a demo).
if "decisions" not in st.session_state:
    st.session_state["decisions"] = {}

selected_event = st.sidebar.selectbox(
    "Grade Change Event",
    event_ids,
    key="selected_event",
    format_func=lambda x: f"#{x} — {summary_df[summary_df['grade_change_event_id']==x]['grade'].values[0]}",
)

# Event info card
event_info = summary_df[summary_df["grade_change_event_id"] == selected_event].iloc[0]
st.sidebar.markdown(f"""
<div style="background:#161b22;border:1px solid #2d333b;border-radius:8px;padding:12px;margin-top:8px;">
<strong>Event #{selected_event}</strong><br>
<span style="color:#8b949e;font-size:0.8rem;">
Grade: <code>{event_info['grade']}</code><br>
Max Deviation: <strong>{event_info['max_deviation_pct']:.1f}%</strong><br>
Stabilization: <strong>{event_info['time_to_stabilize_sec']:.0f}s</strong><br>
Operator Actions: {event_info['n_operator_actions']}
</span>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.caption("Hackathon 2026 | Python + Streamlit + scikit-learn")


# ═══════════════════════════════════════════════════════
# PAGE: LIVE MONITOR
# ═══════════════════════════════════════════════════════
if page == "Live Monitor":
    st.markdown("## Live Grade Change Monitor")
    st.caption("Simulating an in-progress grade change with real-time risk prediction and corrective recommendations.")

    event_data = ts_df[ts_df["grade_change_event_id"] == selected_event].copy()
    transition_data = event_data[event_data["phase"] == "transition"].sort_values(
        "time_since_transition_start_sec"
    ).reset_index(drop=True)

    if transition_data.empty:
        st.warning("No transition data for this event.")
        st.stop()

    max_time = int(transition_data["time_since_transition_start_sec"].max())

    # ── Time Slider (keyed per event so it persists but resets on event change) ──
    slider_col, prog_col = st.columns([4, 1])
    with slider_col:
        current_time = st.slider(
            "Simulation Time (seconds since transition start)",
            min_value=0, max_value=max_time, value=min(180, max_time), step=15,
            key=f"sim_time_{selected_event}",
        )
    with prog_col:
        st.metric("Progress", f"{current_time}s", delta=f"of {max_time}s",
                  delta_color="off")

    current_data = transition_data[
        transition_data["time_since_transition_start_sec"] <= current_time
    ]
    if current_data.empty:
        st.info("Move the slider forward to see predictions.")
        st.stop()

    current_state = current_data.iloc[-1].to_dict()
    history_window = current_data.tail(9)

    # ── Prediction ──
    prediction = model.predict_risk(current_state, history_window)

    # ── Risk Display Row ──
    risk_colors = {"low": "#238636", "medium": "#d29922", "high": "#da3633", "critical": "#8b1a1a"}
    risk_level = prediction["risk_level"]
    current_dev = prediction["current_deviation_pct"]

    col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1.2])
    with col1:
        bg = risk_colors.get(risk_level, "#333")
        st.markdown(
            f'<div class="risk-card" style="background:{bg};">'
            f'<h2>{risk_level.upper()}</h2>'
            f'<p>Risk Level</p></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.metric("Current Deviation", f"{current_dev:.2f}%",
                  delta=f"{current_dev - 2.5:+.2f}% vs spec", delta_color="inverse")
    with col3:
        st.metric("Projected (60s)", f"{prediction['projected_deviation_pct']:.2f}%")
    with col4:
        # Status label — no contradiction
        if current_dev > 2.5:
            dev_rate = 0
            if len(history_window) >= 2:
                dev_rate = (
                    history_window["basis_weight_deviation_pct"].iloc[-1]
                    - history_window["basis_weight_deviation_pct"].iloc[0]
                )
            if dev_rate < -0.05:
                st.metric("Status", "Recovering ↓", delta="Trending on-spec", delta_color="normal")
            else:
                st.metric("Status", "Off-Spec ⚠", delta="Above 2.5%", delta_color="inverse")
        elif prediction.get("time_to_breach_sec") and prediction["time_to_breach_sec"] > 0:
            st.metric("Time to Breach", f"{prediction['time_to_breach_sec']}s")
        else:
            st.metric("Status", "Within Spec ✓")

    # ── Explanation ──
    with st.container():
        st.markdown(
            f'<div style="background:#161b22;border-left:3px solid {bg};'
            f'border-radius:6px;padding:12px 16px;margin:8px 0;">'
            f'<strong style="font-size:0.85rem;">Prediction:</strong> '
            f'<span style="font-size:0.85rem;">{prediction["explanation"]}</span>'
            f'<br><span style="font-size:0.7rem;color:#6e7681;">Source: {prediction["source"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")  # spacer

    # ── Charts ──
    chart_col1, chart_col2 = st.columns(2)

    target_bw = current_data["basis_weight_target_gsm"].iloc[-1]
    t = current_data["time_since_transition_start_sec"]

    with chart_col1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=current_data["basis_weight_gsm"],
                                 name="Basis Weight", line=dict(color="#58a6ff", width=2.5)))
        fig.add_trace(go.Scatter(x=t, y=current_data["basis_weight_target_gsm"],
                                 name="Target", line=dict(color="#3fb950", width=1.5, dash="dash")))
        fig.add_trace(go.Scatter(x=t, y=[target_bw * 1.025] * len(t),
                                 name="+2.5% Spec", line=dict(color="#f85149", width=1, dash="dot")))
        fig.add_trace(go.Scatter(x=t, y=[target_bw * 0.975] * len(t),
                                 name="-2.5% Spec", line=dict(color="#f85149", width=1, dash="dot")))
        fig.update_layout(title="Basis Weight vs Target (gsm)")
        style_chart(fig, height=320)
        st.plotly_chart(fig, width="stretch")

    with chart_col2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=t, y=current_data["basis_weight_deviation_pct"],
            name="Deviation %", line=dict(color="#a371f7", width=2.5),
            fill="tozeroy", fillcolor="rgba(163,113,247,0.08)",
        ))
        fig.add_hline(y=2.5, line_dash="dash", line_color="#f85149", line_width=1.5,
                      annotation_text="2.5% Off-Spec",
                      annotation_font_color="#f85149", annotation_font_size=10)
        fig.update_layout(title="Deviation from Spec (%)")
        style_chart(fig, height=320)
        st.plotly_chart(fig, width="stretch")

    # ── Process variables ──
    with st.expander("Process Variables Detail", expanded=False):
        pv_col1, pv_col2 = st.columns(2)
        with pv_col1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=t, y=current_data["steam_pressure"],
                                     name="Steam Pressure", line=dict(color="#f0883e", width=2)))
            fig.add_trace(go.Scatter(x=t, y=current_data["moisture_pct"],
                                     name="Moisture %", line=dict(color="#79c0ff", width=2),
                                     yaxis="y2"))
            fig.update_layout(
                title="Steam Pressure & Moisture",
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            title=dict(text="Moisture %", font=dict(color="#79c0ff")),
                            tickfont=dict(color="#79c0ff")),
            )
            style_chart(fig, height=280)
            st.plotly_chart(fig, width="stretch")
        with pv_col2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=t, y=current_data["stock_flow"],
                                     name="Stock Flow", line=dict(color="#d2a8ff", width=2)))
            fig.add_trace(go.Scatter(x=t, y=current_data["machine_speed"],
                                     name="Machine Speed", line=dict(color="#8b949e", width=2),
                                     yaxis="y2"))
            fig.update_layout(
                title="Stock Flow & Machine Speed",
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            title=dict(text="Speed (m/min)", font=dict(color="#8b949e")),
                            tickfont=dict(color="#8b949e")),
            )
            style_chart(fig, height=280)
            st.plotly_chart(fig, width="stretch")

    # ── Future-State Trend Projection (multi-variable) ──
    st.markdown("### Future-State Projection")
    if len(current_data) >= 5:
        recent = current_data.tail(8)
        recent_t = recent["time_since_transition_start_sec"].values

        if len(recent_t) >= 2 and recent_t.std() > 0:
            # Project forward 5 minutes (20 samples at 15s)
            future_t = np.arange(current_time + 15, min(current_time + 300, max_time + 300), 15)

            # Basis weight deviation projection
            dev_vals = recent["basis_weight_deviation_pct"].values
            dev_coeffs = np.polyfit(recent_t, dev_vals, 1)
            projected_dev = np.clip(np.polyval(dev_coeffs, future_t), 0, None)

            # Moisture projection (correlated with steam pressure lag)
            moist_vals = recent["moisture_pct"].values
            moist_coeffs = np.polyfit(recent_t, moist_vals, 1)
            projected_moist = np.polyval(moist_coeffs, future_t)

            # Steam pressure projection
            steam_vals = recent["steam_pressure"].values
            steam_coeffs = np.polyfit(recent_t, steam_vals, 1)
            projected_steam = np.polyval(steam_coeffs, future_t)

            proj_col1, proj_col2 = st.columns(2)

            with proj_col1:
                fig = go.Figure()
                # Historical actual
                fig.add_trace(go.Scatter(
                    x=t, y=current_data["basis_weight_deviation_pct"],
                    name="Actual Deviation", line=dict(color="#58a6ff", width=2.5),
                ))
                # Projected (dashed)
                fig.add_trace(go.Scatter(
                    x=future_t, y=projected_dev,
                    name="Projected Deviation", line=dict(color="#f85149", width=2.5, dash="dash"),
                    fill="tozeroy", fillcolor="rgba(248,81,73,0.06)",
                ))
                # Threshold
                all_t = np.concatenate([t.values, future_t])
                fig.add_trace(go.Scatter(
                    x=all_t, y=[2.5] * len(all_t),
                    name="Off-Spec Threshold (2.5%)", line=dict(color="#f85149", width=1, dash="dot"),
                    showlegend=True,
                ))
                # Vertical "now" line
                fig.add_vline(x=current_time, line_dash="dash", line_color="#6e7681", line_width=1,
                              annotation_text="Now", annotation_font_color="#6e7681",
                              annotation_font_size=10)
                fig.update_layout(
                    title="Basis Weight Deviation — Trend Projection",
                    xaxis_title="Time (sec)",
                    yaxis_title="Deviation (%)",
                )
                style_chart(fig, height=300)
                st.plotly_chart(fig, width="stretch")

            with proj_col2:
                fig = go.Figure()
                # Moisture actual
                fig.add_trace(go.Scatter(
                    x=t, y=current_data["moisture_pct"],
                    name="Actual Moisture", line=dict(color="#79c0ff", width=2.5),
                ))
                # Moisture projected
                fig.add_trace(go.Scatter(
                    x=future_t, y=projected_moist,
                    name="Projected Moisture", line=dict(color="#79c0ff", width=2, dash="dash"),
                ))
                # Steam actual
                fig.add_trace(go.Scatter(
                    x=t, y=current_data["steam_pressure"],
                    name="Actual Steam Pressure", line=dict(color="#f0883e", width=2.5),
                    yaxis="y2",
                ))
                # Steam projected
                fig.add_trace(go.Scatter(
                    x=future_t, y=projected_steam,
                    name="Projected Steam", line=dict(color="#f0883e", width=2, dash="dash"),
                    yaxis="y2",
                ))
                fig.add_vline(x=current_time, line_dash="dash", line_color="#6e7681", line_width=1,
                              annotation_text="Now", annotation_font_color="#6e7681",
                              annotation_font_size=10)
                fig.update_layout(
                    title="Correlated Parameters — Trend Projection",
                    xaxis_title="Time (sec)",
                    yaxis_title="Moisture (%)",
                    yaxis2=dict(overlaying="y", side="right", showgrid=False,
                                title=dict(text="Steam Pressure (kPa)", font=dict(color="#f0883e")),
                                tickfont=dict(color="#f0883e")),
                )
                style_chart(fig, height=300)
                st.plotly_chart(fig, width="stretch")

            # Rate-of-change summary
            dev_rate = dev_coeffs[0] * 4  # per 60 seconds (4 steps)
            moist_rate = moist_coeffs[0] * 4
            steam_rate = steam_coeffs[0] * 4
            rate_col1, rate_col2, rate_col3 = st.columns(3)
            with rate_col1:
                st.metric("Deviation Rate (per 60s)", f"{dev_rate:+.2f}%",
                          delta="worsening" if dev_rate > 0 else "improving",
                          delta_color="inverse" if dev_rate > 0 else "normal")
            with rate_col2:
                st.metric("Moisture Rate (per 60s)", f"{moist_rate:+.3f}%")
            with rate_col3:
                st.metric("Steam Rate (per 60s)", f"{steam_rate:+.2f} kPa")

            st.caption(
                "**Projection assumes** current 60-second rate of change continues unchanged. "
                "Does not account for recommended corrective actions, operator interventions, "
                "or non-linear process dynamics. Correlated parameters (moisture, steam) are "
                "shown because steam pressure affects moisture with a ~60s lag, which in turn "
                "drives basis weight deviation."
            )
    else:
        st.info("Insufficient data points for trend projection. Move the slider forward.")

    st.divider()

    # ── Recommendations ──
    st.markdown("### Recommended Actions")

    # Show recipe limits for context
    current_grade = current_state.get("grade", "")
    with st.expander(f"Recipe Limits for {current_grade}", expanded=False):
        limits_df = get_limits_dataframe(current_grade)
        if not limits_df.empty:
            # Add current value and status columns
            process_var_map = {
                "Stock Flow": "stock_flow",
                "Filler Flow": "filler_flow",
                "Steam Pressure": "steam_pressure",
                "Machine Speed": "machine_speed",
                "Moisture Pct": "moisture_pct",
                "Ash Pct": "ash_pct",
                "Caliper Um": "caliper_um",
            }
            current_vals = []
            statuses = []
            for _, row in limits_df.iterrows():
                var_key = process_var_map.get(row["Variable"], "")
                val = current_state.get(var_key, 0)
                current_vals.append(round(val, 2))
                check = check_within_limits(current_grade, var_key, val)
                statuses.append("✓ OK" if check["within_limits"] else f"⚠ Violation ({check['violation']:+.2f})")
            limits_df["Current"] = current_vals
            limits_df["Status"] = statuses
            st.dataframe(limits_df[["Variable", "Min", "Current", "Max", "Status"]],
                         width="stretch", hide_index=True)
            st.caption("Limits derived from steady-state operating ranges (mean ± 2.5σ). Source: Recipe limits")
        else:
            st.info("No recipe limits available for this grade.")

    recommendation = engine.recommend(current_state, prediction)

    if recommendation["action"] == "maintain":
        st.markdown(
            '<div style="background:#0d1f0d;border:1px solid #238636;border-radius:8px;'
            'padding:14px;display:flex;align-items:center;gap:10px;">'
            '<span style="font-size:1.3rem;">✓</span>'
            f'<span style="font-size:0.9rem;">{recommendation["message"]}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(recommendation["message"])
        if recommendation.get("estimated_recovery_time_sec"):
            st.markdown(
                f'<span style="color:#3fb950;font-size:0.8rem;">'
                f'Estimated recovery: {recommendation["estimated_recovery_time_sec"]}s '
                f'(based on similar historical events)</span>',
                unsafe_allow_html=True,
            )

        for i, rec in enumerate(recommendation.get("recommendations", [])):
            arrow = "↑" if rec["change"] > 0 else "↓"
            change_color = "#3fb950" if rec["change"] > 0 else "#f85149"
            limit_check = rec.get("recipe_limit_check", {})
            clamped = limit_check.get("flagged", False)
            # Carry the risk level onto the individual recommendation so the
            # feedback log records the risk context of each decision.
            rec["risk_level"] = recommendation.get("risk_level", prediction["risk_level"])

            with st.container(border=True):
                head_col, match_col = st.columns([3, 1])
                with head_col:
                    st.markdown(
                        f'<span style="font-weight:700;font-size:0.95rem;color:#58a6ff;">'
                        f'{rec["variable"].replace("_", " ").title()}</span>'
                        f'<span style="font-family:monospace;font-size:0.9rem;margin-left:10px;">'
                        f'<span style="color:#8b949e;">{rec["current_value"]}</span>'
                        f' → <span style="color:{change_color};font-weight:700;">{rec["recommended_value"]}</span>'
                        f' <span style="color:{change_color};">({rec["change"]:+.2f} {rec["unit"]} {arrow})</span>'
                        f'</span>',
                        unsafe_allow_html=True,
                    )
                with match_col:
                    st.markdown(
                        f'<div style="text-align:right;font-size:0.75rem;color:#8b949e;">'
                        f'Similarity Match<br><strong style="font-size:1rem;color:#c9d1d9;">'
                        f'{rec["confidence"]:.0%}</strong></div>',
                        unsafe_allow_html=True,
                    )

                # Recipe limit badge
                if clamped:
                    st.markdown(
                        f'<span style="background:#3d2b04;border:1px solid #d29922;color:#d29922;'
                        f'border-radius:4px;padding:2px 8px;font-size:0.7rem;font-weight:600;">'
                        f'⚠ CLAMPED TO RECIPE LIMITS '
                        f'[{limit_check.get("min")} – {limit_check.get("max")}]</span>',
                        unsafe_allow_html=True,
                    )
                elif limit_check.get("min") is not None:
                    st.markdown(
                        f'<span style="background:#0d2818;border:1px solid #238636;color:#3fb950;'
                        f'border-radius:4px;padding:2px 8px;font-size:0.7rem;font-weight:600;">'
                        f'✓ WITHIN RECIPE LIMITS '
                        f'[{limit_check.get("min")} – {limit_check.get("max")}]</span>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div style="font-size:0.8rem;color:#8b949e;margin-top:8px;">'
                    f'{rec["rationale"]}</div>'
                    f'<div style="font-size:0.72rem;color:#6e7681;margin-top:4px;">'
                    f'Source: {rec["source"]}</div>',
                    unsafe_allow_html=True,
                )

                # ── One decision per suggestion ──
                # Identity is the suggestion itself (event + variable + the exact
                # values shown), so moving the slider to a new process state
                # correctly presents a NEW suggestion that can be decided again.
                sug_id = (
                    f"{selected_event}|{rec['variable']}"
                    f"|{rec['current_value']:.2f}|{rec['recommended_value']:.2f}"
                )
                decided = st.session_state["decisions"].get(sug_id)

                btn_col1, btn_col2, status_col = st.columns([1, 1, 5])
                if decided is None:
                    with btn_col1:
                        if st.button("✓ Accept", key=f"acc_{selected_event}_{i}",
                                     width="stretch"):
                            feedback_logger.log_decision(selected_event, rec, "accept")
                            st.session_state["decisions"][sug_id] = "accept"
                            st.rerun()
                    with btn_col2:
                        if st.button("✗ Reject", key=f"rej_{selected_event}_{i}",
                                     width="stretch"):
                            feedback_logger.log_decision(selected_event, rec, "reject")
                            st.session_state["decisions"][sug_id] = "reject"
                            st.rerun()
                else:
                    with btn_col1:
                        st.button("✓ Accept", key=f"acc_{selected_event}_{i}",
                                  width="stretch", disabled=True)
                    with btn_col2:
                        st.button("✗ Reject", key=f"rej_{selected_event}_{i}",
                                  width="stretch", disabled=True)
                    with status_col:
                        col = "#3fb950" if decided == "accept" else "#f85149"
                        icon = "✓" if decided == "accept" else "✗"
                        st.markdown(
                            f'<div style="padding-top:8px;font-size:0.78rem;color:{col};'
                            f'font-weight:600;">{icon} Recorded: {decided}ed '
                            f'<span style="color:#6e7681;font-weight:400;">'
                            f'— logged to feedback log</span></div>',
                            unsafe_allow_html=True,
                        )

    # ── Contributing Factors ──
    if prediction.get("contributing_factors"):
        with st.expander("Contributing Factors (Feature Importance)"):
            factors_df = pd.DataFrame(prediction["contributing_factors"])
            factors_df.columns = ["Variable", "Importance", "Current Value"]
            st.dataframe(factors_df, width="stretch", hide_index=True)


# ═══════════════════════════════════════════════════════
# PAGE: CORRELATIONS
# ═══════════════════════════════════════════════════════
elif page == "Correlations":
    st.markdown("## Correlation Analysis")
    st.caption("Patterns mined from 119 historical grade-change events — relationships that impact transition quality.")

    findings = analyzer.findings

    # Impact summary badges at top
    high_count = sum(1 for f in findings if f["impact"] == "high")
    med_count = sum(1 for f in findings if f["impact"] == "medium")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Findings", len(findings))
    with col2:
        st.metric("High Impact", high_count)
    with col3:
        st.metric("Medium Impact", med_count)

    st.divider()

    for finding in findings:
        impact_badge = {
            "high": "🔴 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"
        }.get(finding["impact"], "⚪ UNKNOWN")

        with st.expander(f"{impact_badge}  |  {finding['title']}", expanded=False):
            # Description
            st.markdown(f"**{finding['description']}**")

            # Metrics row
            if finding.get("correlation_strength") is not None:
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Correlation (r)", f"{finding['correlation_strength']:.3f}")
                with m2:
                    st.metric("p-value", f"{finding['p_value']:.4f}")
                with m3:
                    st.metric("Impact", finding["impact"].upper())

            # Recommendation box
            st.markdown(
                f'<div style="background:#0d2818;border:1px solid #238636;'
                f'border-radius:8px;padding:12px;margin:10px 0;">'
                f'<strong style="color:#3fb950;font-size:0.8rem;">RECOMMENDATION</strong><br>'
                f'<span style="font-size:0.85rem;">{finding["recommendation"]}</span></div>',
                unsafe_allow_html=True,
            )

            # Source + variables
            st.caption(f"Source: {finding['source']}")
            st.markdown(
                "Variables: " + " · ".join(
                    [f"`{v}`" for v in finding["variables_involved"]]
                )
            )

            # Grade pair chart
            if finding["id"] == "grade_pair_difficulty" and finding.get("detail_data"):
                pair_df = pd.DataFrame(finding["detail_data"])
                fig = px.bar(
                    pair_df.sort_values("avg_stabilize", ascending=False),
                    x="grade_pair", y="avg_stabilize",
                    color="avg_deviation",
                    labels={"avg_stabilize": "Avg Stabilization (sec)",
                            "grade_pair": "Grade Transition",
                            "avg_deviation": "Avg Max Deviation (%)"},
                    color_continuous_scale="YlOrRd",
                )
                style_chart(fig, height=300)
                st.plotly_chart(fig, width="stretch")

    st.divider()

    # Feature importance — High Impact Parameters on Stabilization
    st.divider()
    st.markdown("### Parameters With Highest Impact on Stabilization")
    st.markdown(
        "These are the process variables and derived signals that most strongly "
        "determine whether a grade change will stabilize quickly or go off-spec. "
        "Ranked by their importance in the trained prediction model (Random Forest)."
    )

    importance_df = model.get_feature_importances().head(12)

    # Plain-language explanation for each top feature
    feature_explanations = {
        "current_deviation_pct": (
            "The single strongest driver. If deviation is already elevated, "
            "the system is more likely to remain off-spec in the near future."
        ),
        "bw_distance_from_target": (
            "How far the actual basis weight is from its target in absolute terms. "
            "Larger gaps take longer to close and signal active instability."
        ),
        "bw_volatility": (
            "Variability (std dev) of deviation over the last ~2 minutes. "
            "High volatility means the control system is oscillating rather than settling."
        ),
        "moisture_volatility": (
            "Unstable moisture indicates steam pressure hasn't settled, "
            "which will continue to perturb basis weight via the ~60s steam-moisture lag."
        ),
        "bw_deviation_rate": (
            "Rate of change in deviation: is the situation getting better or worse? "
            "A positive rate means the breach is deepening."
        ),
        "deviation_trend": (
            "Linear trend slope over recent samples. Captures whether "
            "the system is converging toward target or diverging away."
        ),
        "time_since_start_sec": (
            "How far into the transition we are. Early instability often self-corrects; "
            "late instability suggests the control system is struggling."
        ),
        "basis_weight_gsm": (
            "The raw sheet weight. Heavier grades have more thermal inertia "
            "and tend to take longer to respond to control adjustments."
        ),
        "moisture_pct": (
            "Current moisture level. Elevated moisture directly increases basis weight "
            "deviation since moisture is a major component of sheet weight."
        ),
        "steam_pressure": (
            "Steam drives the drying process. If steam hasn't settled to its target, "
            "moisture will remain unstable and BW deviation persists."
        ),
        "steam_rate": (
            "Rate of change in steam pressure. Rapid changes propagate through "
            "to moisture (with ~60s lag) and then to basis weight."
        ),
        "steam_volatility": (
            "Fluctuating steam pressure means the dryer section isn't in steady state, "
            "which guarantees continued moisture — and thus BW — instability."
        ),
    }

    # Render top features with explanations
    for _, row in importance_df.iterrows():
        feat = row["Feature"]
        imp = row["Importance"]
        pct = imp * 100
        explanation = feature_explanations.get(feat, "Contributes to predicting transition outcome.")

        # Color intensity based on importance
        bar_width = int(min(imp / importance_df["Importance"].max() * 100, 100))
        color = "#58a6ff" if pct > 8 else "#79c0ff" if pct > 4 else "#8b949e"

        st.markdown(
            f'<div style="margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<strong style="font-size:0.9rem;">{feat.replace("_", " ").title()}</strong>'
            f'<span style="font-size:0.8rem;color:{color};font-weight:700;">{pct:.1f}%</span>'
            f'</div>'
            f'<div style="background:#21262d;border-radius:4px;height:6px;margin:4px 0;">'
            f'<div style="background:{color};border-radius:4px;height:6px;width:{bar_width}%;"></div>'
            f'</div>'
            f'<span style="font-size:0.78rem;color:#8b949e;">{explanation}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.caption(
        "Source: Feature importance scores from the Random Forest classifier, "
        "trained on 15,664 transition-window samples with event-based holdout validation. "
        "Importance reflects how much each variable reduces prediction uncertainty (Gini impurity)."
    )


# ═══════════════════════════════════════════════════════
# PAGE: HISTORICAL EVENTS
# ═══════════════════════════════════════════════════════
elif page == "Historical Events":
    st.markdown("## Historical Grade Change Events")
    st.caption("Overview of all 119 simulated grade changes. Click any event in the sidebar to inspect it.")

    # Scatter overview
    fig = px.scatter(
        summary_df,
        x="time_to_stabilize_sec",
        y="max_deviation_pct",
        color="grade",
        size="n_operator_actions",
        size_max=18,
        hover_data=["grade_change_event_id"],
        labels={
            "time_to_stabilize_sec": "Time to Stabilize (sec)",
            "max_deviation_pct": "Max Deviation (%)",
            "n_operator_actions": "Operator Actions",
        },
        color_discrete_sequence=["#58a6ff", "#3fb950", "#f0883e", "#d2a8ff"],
    )
    fig.add_hline(y=2.5, line_dash="dash", line_color="#f85149", line_width=1,
                  annotation_text="Off-Spec Threshold (2.5%)",
                  annotation_font_color="#f85149", annotation_font_size=10)
    style_chart(fig, height=420)
    fig.update_layout(title="All Events: Deviation vs Stabilization Time")
    st.plotly_chart(fig, width="stretch")

    st.divider()

    # Selected event detail
    st.markdown(f"### Event #{selected_event} — Detail")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Max Deviation", f"{event_info['max_deviation_pct']:.1f}%")
    with col2:
        st.metric("Stabilization", f"{event_info['time_to_stabilize_sec']:.0f}s")
    with col3:
        st.metric("Operator Actions", f"{event_info['n_operator_actions']}")
    with col4:
        st.metric("Grade", event_info["grade"])

    # Event timeline chart
    event_data = ts_df[ts_df["grade_change_event_id"] == selected_event]
    transition_data = event_data[event_data["phase"] == "transition"]

    if not transition_data.empty:
        t = transition_data["time_since_transition_start_sec"]
        target_bw = transition_data["basis_weight_target_gsm"].iloc[0]

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=("Basis Weight", "Process Variables"),
                            vertical_spacing=0.1)

        fig.add_trace(go.Scatter(x=t, y=transition_data["basis_weight_gsm"],
                                 name="Basis Weight", line=dict(color="#58a6ff", width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t, y=transition_data["basis_weight_target_gsm"],
                                 name="Target", line=dict(color="#3fb950", dash="dash")), row=1, col=1)
        fig.add_trace(go.Scatter(x=t, y=[target_bw * 1.025] * len(t),
                                 name="+2.5%", line=dict(color="#f85149", dash="dot", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=t, y=[target_bw * 0.975] * len(t),
                                 name="-2.5%", line=dict(color="#f85149", dash="dot", width=1)), row=1, col=1)

        for var, color in [("stock_flow", "#d2a8ff"), ("steam_pressure", "#f0883e"),
                           ("moisture_pct", "#79c0ff"), ("filler_flow", "#56d4dd")]:
            fig.add_trace(go.Scatter(x=t, y=transition_data[var],
                                     name=var.replace("_", " ").title(),
                                     line=dict(color=color, width=1.5)), row=2, col=1)

        style_chart(fig, height=500)
        st.plotly_chart(fig, width="stretch")

    # Operator actions
    if not transition_data.empty:
        actions = transition_data[transition_data["operator_action"] != ""]
        if not actions.empty:
            st.markdown("**Operator Actions**")
            actions_display = actions[["time_since_transition_start_sec", "operator_action",
                                       "basis_weight_deviation_pct"]].copy()
            actions_display.columns = ["Time (sec)", "Action", "Deviation (%)"]
            st.dataframe(actions_display, width="stretch", hide_index=True)

    # Optimal setpoints
    with st.expander(f"Optimal Setpoints for {event_info['grade']}"):
        optimal = engine.get_optimal_setpoints_for_grade(event_info["grade"])
        opt_col1, opt_col2 = st.columns(2)
        with opt_col1:
            for k, v in optimal["optimal_setpoints"].items():
                st.markdown(f"**{k.replace('_',' ').title()}:** `{v}`")
        with opt_col2:
            st.caption(f"Source: {optimal['source']}")
            st.caption(f"Avg stabilize (fastest events): {optimal['avg_stabilize_time_sec']}s")
            st.caption(f"BW Target: {optimal['basis_weight_target_gsm']} gsm")


# ═══════════════════════════════════════════════════════
# PAGE: FEEDBACK LOG
# ═══════════════════════════════════════════════════════
elif page == "Feedback Log":
    st.markdown("## Feedback Log")
    st.caption("Accept/reject decisions on recommendations — tracks suggestion quality over time.")

    log_df = feedback_logger.get_log()

    if log_df.empty:
        st.markdown(
            '<div style="text-align:center;padding:60px 0;color:#8b949e;">'
            '<p style="font-size:2rem;">📋</p>'
            '<p>No feedback recorded yet.</p>'
            '<p style="font-size:0.8rem;">Accept or reject recommendations on the '
            'Live Monitor page to start logging.</p></div>',
            unsafe_allow_html=True,
        )
    else:
        stats = feedback_logger.get_accuracy_stats()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Decisions", stats["total_decisions"])
        with col2:
            st.metric("Accepted", stats["accepted"])
        with col3:
            st.metric("Rejected", stats["rejected"])
        with col4:
            st.metric("Accept Rate", f"{stats['accept_rate']:.0%}")

        st.divider()
        st.dataframe(log_df, width="stretch", hide_index=True)

        csv = log_df.to_csv(index=False)
        st.download_button("⬇ Download CSV", csv, "feedback_log.csv", "text/csv")
