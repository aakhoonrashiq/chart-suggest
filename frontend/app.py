"""
Chart Suggest — Streamlit Frontend
Intelligent CSV-to-Chart Recommendation Engine powered by FastAPI & Apache ECharts.
"""
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# Ensure backend modules can be imported for config generation & catalog
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from services.chart_matcher import _load_catalog
    from services.config_generator import generate_echarts_config
    from services.profiler import profile_dataset
    SERVICES_AVAILABLE = True
except Exception as e:
    SERVICES_AVAILABLE = False

# Page Configuration
st.set_page_config(
    page_title="ChartSuggest | Intelligent Chart Recommendation Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for High-Aesthetic Dark Theme ───────────────────────────────────
st.markdown(
    """
    <style>
    /* Global Typography & Palette */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* Header Styling */
    .app-header {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(139, 92, 246, 0.08) 50%, rgba(217, 70, 239, 0.05) 100%);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.8rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
        backdrop-filter: blur(12px);
    }

    .app-header h1 {
        margin: 0;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .app-header p {
        margin: 0.35rem 0 0 0;
        color: #94a3b8;
        font-size: 0.95rem;
    }

    /* Status Badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .status-badge.online {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
    }

    .status-badge.offline {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        color: #f87171;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }

    .status-dot.online {
        background: #10b981;
        box-shadow: 0 0 8px #10b981;
    }

    .status-dot.offline {
        background: #ef4444;
        box-shadow: 0 0 8px #ef4444;
    }

    /* Metric Cards */
    .metric-card {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        backdrop-filter: blur(8px);
        transition: transform 0.2s, border-color 0.2s;
    }

    .metric-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
        transform: translateY(-2px);
    }

    .metric-val {
        font-size: 1.7rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
    }

    .metric-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0;
    }

    /* Signal Badges */
    .signal-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 500;
        margin: 2px;
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #e2e8f0;
    }

    /* Semantic Type Pills */
    .badge-type {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .badge-type-integer, .badge-type-float { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
    .badge-type-datetime { background: rgba(139, 92, 246, 0.2); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.4); }
    .badge-type-categorical { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-type-geo_named, .badge-type-latitude, .badge-type-longitude { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-type-flow_source, .badge-type-flow_target { background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }
    .badge-type-currency, .badge-type-percentage { background: rgba(6, 182, 212, 0.2); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.4); }
    .badge-type-unknown, .badge-type-text { background: rgba(100, 116, 139, 0.2); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.4); }

    /* Recommendation Card Styling */
    .rec-card {
        background: rgba(17, 24, 39, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(10px);
        transition: all 0.2s ease-in-out;
    }

    .rec-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 8px 30px 0 rgba(99, 102, 241, 0.15);
        transform: translateY(-2px);
    }

    .rec-card-top1 {
        border: 1px solid rgba(245, 158, 11, 0.4) !important;
        background: linear-gradient(180deg, rgba(245, 158, 11, 0.06) 0%, rgba(17, 24, 39, 0.9) 100%) !important;
    }

    .rank-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 0.85rem;
        padding: 3px 10px;
        border-radius: 8px;
    }

    .rank-gold { background: linear-gradient(135deg, #f59e0b, #d97706); color: #000000; box-shadow: 0 0 12px rgba(245, 158, 11, 0.4); }
    .rank-silver { background: linear-gradient(135deg, #94a3b8, #64748b); color: #ffffff; }
    .rank-bronze { background: linear-gradient(135deg, #b45309, #78350f); color: #ffffff; }
    .rank-default { background: rgba(30, 41, 59, 0.8); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.1); }

    .score-badge {
        font-size: 0.85rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 8px;
    }

    .score-high { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .score-med { background: rgba(245, 158, 11, 0.18); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }

    .mapping-chip {
        display: inline-block;
        background: rgba(30, 41, 59, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.78rem;
        color: #cbd5e1;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .mapping-chip strong {
        color: #818cf8;
    }

    /* Button Polish */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helper: ECharts HTML Component ─────────────────────────────────────────────
def render_echarts(option: Dict[str, Any], height: int = 480, chart_id: str = "chart"):
    """Render an Apache ECharts instance inside Streamlit with dark mode and full interactivity."""
    # Ensure options look great in dark theme
    option_clean = json.loads(json.dumps(option))
    option_clean["backgroundColor"] = "transparent"

    # Ensure toolbox has useful default actions (download PNG, restore, data zoom)
    if "toolbox" not in option_clean:
        option_clean["toolbox"] = {
            "show": True,
            "feature": {
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
                "saveAsImage": {"pixelRatio": 2, "backgroundColor": "#0b0f19"},
            },
            "iconStyle": {"borderColor": "#94a3b8"},
            "emphasis": {"iconStyle": {"borderColor": "#6366f1"}},
        }

    opt_json = json.dumps(option_clean)
    chart_dom_id = f"echarts_{chart_id.replace('-', '_')}"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            body, html {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                background: transparent;
                overflow: hidden;
            }}
            #{chart_dom_id} {{
                width: 100%;
                height: {height}px;
            }}
        </style>
    </head>
    <body>
        <div id="{chart_dom_id}"></div>
        <script>
            (function() {{
                var chartDom = document.getElementById('{chart_dom_id}');
                var myChart = echarts.init(chartDom, 'dark', {{ renderer: 'canvas' }});
                var option = {opt_json};
                myChart.setOption(option);
                window.addEventListener('resize', function() {{
                    myChart.resize();
                }});
            }})();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15)


# ── Helper: Backend Health Check & API Calls ───────────────────────────────────
def check_backend_health(base_url: str) -> bool:
    """Ping the FastAPI backend to verify it is reachable."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/health", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        try:
            # Fallback check on openapi docs
            resp2 = requests.get(f"{base_url.rstrip('/')}/openapi.json", timeout=1.5)
            return resp2.status_code == 200
        except Exception:
            return False


def call_recommend_charts(file_bytes: bytes, filename: str, base_url: str, top_n: int = 5) -> Dict[str, Any]:
    """Call FastAPI POST /recommend-charts endpoint."""
    url = f"{base_url.rstrip('/')}/recommend-charts"
    files = {"file": (filename, file_bytes, "text/csv")}
    data = {"top_n": str(top_n)}
    response = requests.post(url, files=files, data=data, timeout=60)
    if response.status_code != 200:
        error_detail = response.text
        try:
            error_detail = response.json().get("detail", error_detail)
        except Exception:
            pass
        raise RuntimeError(f"Backend returned HTTP {response.status_code}: {error_detail}")
    return response.json()


# ── Sample Datasets ────────────────────────────────────────────────────────────
SAMPLE_DATASETS = {
    "Categorical Sales (Bar / Pie)": {
        "file": "dataset1_categorical.csv",
        "desc": "Product names with sales numbers — ideal for Bar, Column, and Pie charts.",
    },
    "Monthly Revenue (Timeseries)": {
        "file": "dataset2_timeseries.csv",
        "desc": "Dates and recurring revenue — ideal for Line, Area, and Stepped charts.",
    },
    "Ad Spend vs Sales (Correlation)": {
        "file": "dataset3_numeric.csv",
        "desc": "Two continuous numerical dimensions — ideal for Scatter plots and Regression.",
    },
    "Supply Chain Network (Flow)": {
        "file": "dataset7_flow.csv",
        "desc": "Source, Target, and Value nodes — ideal for Sankey and Chord diagrams.",
    },
    "House Prices (Multi-feature)": {
        "file": "house_price_dataset.csv",
        "desc": "1,200 property records with 6 features — ideal for Scatter, Histograms, and Tables.",
    },
}


# ── Header Banner ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="app-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div>
                <h1>⚡ ChartSuggest</h1>
                <p>Intelligent CSV-to-Chart Recommendation Engine powered by Apache ECharts & FastAPI</p>
            </div>
            <div>
                <span class="signal-chip" style="background: rgba(99, 102, 241, 0.2); border-color: rgba(99, 102, 241, 0.4); color: #c7d2fe;">
                    📊 81 Catalog Charts
                </span>
                <span class="signal-chip" style="background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.4); color: #a7f3d0;">
                    🚀 Apache ECharts 5.5
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar Configuration ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Backend Connection")
    backend_url = st.text_input("FastAPI Server URL", value="http://localhost:8000")

    is_online = check_backend_health(backend_url)
    if is_online:
        st.markdown(
            f"""
            <div class="status-badge online">
                <span class="status-dot online"></span>
                <span>FastAPI Connected</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Connected to `{backend_url}`")
    else:
        st.markdown(
            f"""
            <div class="status-badge offline">
                <span class="status-dot offline"></span>
                <span>FastAPI Offline</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.warning(
            "FastAPI backend is not running at this URL. Start it using:\n```bash\ncd backend\nuvicorn main:app --reload --port 8000\n```"
        )

    st.markdown("---")
    st.markdown("### ⚙️ Recommendation Settings")
    top_n_val = st.slider(
        "Top-N Recommendations",
        min_value=1,
        max_value=20,
        value=5,
        help="Number of best-matching charts to return from the 81-chart catalog.",
    )

    chart_filter = st.selectbox(
        "Filter by Chart Category",
        options=["All Categories", "Bar Charts", "Line Charts", "Scatter Charts", "Pie Charts", "Flow", "Heatmap", "Tree/Hierarchy", "Table/KPI", "3D/WebGL"],
        index=0,
    )

    search_query = st.text_input("🔍 Search charts or reasons", value="")

    st.markdown("---")
    st.markdown("### 📖 About")
    st.caption(
        "ChartSuggest analyzes your CSV schema, profiles column distributions and semantic types, "
        "detects relationship patterns, and scores 81 Apache ECharts chart types using a 100-point suitability algorithm."
    )
    if st.button("Reset Session / Clear Data"):
        for key in ["result", "df", "filename", "raw_bytes"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


# ── Data Ingestion: Upload or 1-Click Sample ────────────────────────────────────
tab_upload, tab_samples = st.tabs(["📁 Upload Custom CSV", "⚡ Try Sample Datasets"])

uploaded_file = None
sample_selected = None

with tab_upload:
    uploaded_file = st.file_uploader(
        "Drag and drop or select a CSV file to analyze",
        type=["csv"],
        help="Supports any valid CSV up to 50 MB.",
    )

with tab_samples:
    st.markdown("Select one of the bundled benchmark datasets for an instant test run:")
    sample_cols = st.columns(len(SAMPLE_DATASETS))
    for idx, (s_name, s_info) in enumerate(SAMPLE_DATASETS.items()):
        with sample_cols[idx]:
            if st.button(f"{s_name.split(' (')[0]}", key=f"btn_sample_{idx}", use_container_width=True):
                sample_selected = s_info["file"]
            st.caption(s_info["desc"])

# Resolve file input
file_bytes: Optional[bytes] = None
active_filename = ""

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    active_filename = uploaded_file.name
elif sample_selected:
    sample_path = ROOT_DIR / "tests" / "test_datasets" / sample_selected
    if sample_path.exists():
        with open(sample_path, "rb") as f:
            file_bytes = f.read()
        active_filename = sample_selected
    else:
        st.error(f"Sample dataset `{sample_selected}` not found on disk.")

# If we have new bytes, update session state and trigger backend
if file_bytes is not None and (
    "raw_bytes" not in st.session_state or st.session_state.get("filename") != active_filename
):
    try:
        # Parse into pandas for live rendering & table inspection
        df = pd.read_csv(io.BytesIO(file_bytes), on_bad_lines="skip", low_memory=False)
        st.session_state["df"] = df
        st.session_state["filename"] = active_filename
        st.session_state["raw_bytes"] = file_bytes

        # Call FastAPI backend
        with st.spinner(f"⚡ FastAPI backend is profiling `{active_filename}` and scoring 81 catalog charts..."):
            res = call_recommend_charts(
                file_bytes=file_bytes,
                filename=active_filename,
                base_url=backend_url,
                top_n=top_n_val,
            )
            st.session_state["result"] = res
            st.toast(f"✅ Successfully profiled `{active_filename}`! Found {len(res.get('recommendations', []))} top charts.", icon="✨")

    except Exception as e:
        st.error(f"⚠️ Error processing dataset: {str(e)}")


# ── Render Results if Available ────────────────────────────────────────────────
if "result" in st.session_state and "df" in st.session_state:
    result = st.session_state["result"]
    df: pd.DataFrame = st.session_state["df"]
    fname = st.session_state.get("filename", "dataset.csv")

    dataset_info = result.get("dataset", {})
    profile_info = result.get("profile", {})
    signals = profile_info.get("signals", {})
    col_profiles = profile_info.get("columns", {})
    relationships = result.get("relationships_detected", [])
    recommendations: List[Dict[str, Any]] = result.get("recommendations", [])
    total_eval = result.get("total_charts_evaluated", 81)
    total_eligible = result.get("total_charts_eligible", 0)

    # 1. Dataset Overview Metric Cards
    st.markdown(f"### 📋 Dataset Overview: `{fname}`")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(
            f"""<div class="metric-card"><p class="metric-label">Total Rows</p><p class="metric-val">{dataset_info.get('rows', len(df)):,}</p></div>""",
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""<div class="metric-card"><p class="metric-label">Columns</p><p class="metric-val">{dataset_info.get('columns', len(df.columns))}</p></div>""",
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""<div class="metric-card"><p class="metric-label">Evaluated Charts</p><p class="metric-val">{total_eval}</p></div>""",
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f"""<div class="metric-card"><p class="metric-label">Eligible Charts</p><p class="metric-val">{total_eligible}</p></div>""",
            unsafe_allow_html=True,
        )
    with m5:
        st.markdown(
            f"""<div class="metric-card"><p class="metric-label">Top Matches</p><p class="metric-val">{len(recommendations)}</p></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 2. Detected Signals & Relationships
    sig_col, rel_col = st.columns([1, 1])

    with sig_col:
        st.markdown("**Detected Structural Signals:**")
        signal_labels = [
            ("has_datetime", "⏱️ Time Series"),
            ("has_numeric", "🔢 Numeric"),
            ("has_categorical", "🏷️ Categorical"),
            ("has_geo_latlon", "🌍 Geo Lat/Lon"),
            ("has_geo_named", "🗺️ Geo Named"),
            ("has_flow", "🔀 Flow Network"),
            ("has_hierarchy", "🌲 Hierarchy"),
            ("has_ohlc", "📈 OHLC Financial"),
        ]
        chips_html = ""
        for sig_key, sig_label in signal_labels:
            if signals.get(sig_key):
                chips_html += f'<span class="signal-chip" style="background: rgba(99, 102, 241, 0.2); border-color: rgba(99, 102, 241, 0.4); color: #c7d2fe;">{sig_label}</span>'
        if not chips_html:
            chips_html = '<span style="color: #94a3b8; font-size: 0.85rem;">No special structural signals detected.</span>'
        st.markdown(chips_html, unsafe_allow_html=True)

    with rel_col:
        st.markdown("**Detected Relationship Patterns:**")
        rel_html = ""
        for rel in relationships:
            clean_rel = rel.replace("_", " ").title()
            rel_html += f'<span class="signal-chip" style="background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.4); color: #a7f3d0;">✨ {clean_rel}</span>'
        if not rel_html:
            rel_html = '<span style="color: #94a3b8; font-size: 0.85rem;">Standard tabular relationship.</span>'
        st.markdown(rel_html, unsafe_allow_html=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # 3. Column Profiling & Raw Data Accordions
    with st.expander("🔍 Inspect Detected Columns & Semantic Types", expanded=False):
        col_data_list = []
        for cname, cinfo in col_profiles.items():
            col_data_list.append({
                "Column Name": cname,
                "Detected Semantic Type": cinfo.get("semantic_type", "unknown"),
                "Unique Values": cinfo.get("unique_count", 0),
                "Missing Values": cinfo.get("missing_count", 0),
                "Missing Pct": f"{cinfo.get('missing_pct', 0.0):.1f}%",
            })
        if col_data_list:
            cdf = pd.DataFrame(col_data_list)
            st.dataframe(cdf, use_container_width=True, hide_index=True)
        else:
            st.info("No column profile information available.")

    with st.expander("📄 Raw Dataset Preview (First 20 Rows)", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)

    st.markdown("---")

    # 4. Filter Recommendations
    filtered_recs = recommendations
    if chart_filter != "All Categories":
        filtered_recs = [
            r for r in filtered_recs
            if chart_filter.lower() in r.get("category", "").lower()
            or chart_filter.lower() in r.get("chart_name", "").lower()
        ]

    if search_query.strip():
        q = search_query.lower()
        filtered_recs = [
            r for r in filtered_recs
            if q in r.get("chart_name", "").lower()
            or q in r.get("chart_type_label", "").lower()
            or q in r.get("reason", "").lower()
            or q in r.get("category", "").lower()
        ]

    st.markdown(f"### 🏆 Ranked Recommendations ({len(filtered_recs)} charts)")

    if not filtered_recs:
        st.info("No charts match your current category or search filter.")

    # Load chart catalog lookup for rendering configs
    catalog_lookup = {}
    if SERVICES_AVAILABLE:
        try:
            catalog_lookup = {c["id"]: c for c in _load_catalog()}
        except Exception:
            pass

    # Profile dataset for local config generator if available
    local_profile = None
    if SERVICES_AVAILABLE:
        try:
            local_profile = profile_dataset(df, "streamlit_session", fname)
        except Exception:
            pass

    # 5. Render Recommendation Cards
    for idx, rec in enumerate(filtered_recs):
        rank = rec.get("rank", idx + 1)
        cid = rec.get("chart_id", "")
        cname = rec.get("chart_name", "")
        clabel = rec.get("chart_type_label", cname.upper())
        category = rec.get("category", "General")
        score = rec.get("score", 0)
        confidence = rec.get("confidence", "medium").upper()
        reason = rec.get("reason", "")
        mapping = rec.get("mapping", {})
        warnings = rec.get("warnings", [])

        # Rank badge style
        rank_class = "rank-gold" if rank == 1 else ("rank-silver" if rank == 2 else ("rank-bronze" if rank == 3 else "rank-default"))
        card_class = "rec-card rec-card-top1" if rank == 1 else "rec-card"
        score_class = "score-high" if score >= 80 else "score-med"

        # Build column mapping chips
        mapping_chips = ""
        for role, col_mapped in mapping.items():
            mapping_chips += f'<span class="mapping-chip"><strong>{role}:</strong> {col_mapped}</span>'

        st.markdown(
            f"""
            <div class="{card_class}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span class="rank-badge {rank_class}">#{rank}</span>
                        <span style="font-size: 1.25rem; font-weight: 700; color: #f8fafc;">{cname}</span>
                        <span style="font-size: 0.78rem; text-transform: uppercase; color: #818cf8; background: rgba(99, 102, 241, 0.15); padding: 2px 8px; border-radius: 6px; font-weight: 600;">{category}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="score-badge {score_class}">{score}% MATCH • {confidence}</span>
                    </div>
                </div>
                <div style="color: #cbd5e1; font-size: 0.92rem; margin: 0.5rem 0 0.8rem 0; line-height: 1.5;">
                    {reason}
                </div>
                <div>
                    <span style="font-size: 0.78rem; color: #94a3b8; margin-right: 8px;">Recommended Mappings:</span>
                    {mapping_chips}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if warnings:
            for w in warnings:
                st.warning(f"⚠️ {w}")

        # Interactive Chart Studio: ECharts Live View, Mapping Customizer, and JSON Option
        c_view_tab, c_edit_tab, c_json_tab = st.tabs([
            f"📊 View {cname} Chart",
            "⚙️ Customize Column Mapping",
            "💻 ECharts JSON Config",
        ])

        # State key for custom mapping of this chart
        mapping_state_key = f"mapping_{cid}_{idx}"
        if mapping_state_key not in st.session_state:
            st.session_state[mapping_state_key] = dict(mapping)

        active_mapping = st.session_state[mapping_state_key]

        # Generate config for live rendering
        echarts_option = None
        if SERVICES_AVAILABLE and cid in catalog_lookup and local_profile is not None:
            try:
                chart_def = catalog_lookup[cid]
                echarts_option = generate_echarts_config(
                    chart=chart_def,
                    mapping=active_mapping,
                    profile=local_profile,
                    df=df,
                )
            except Exception as e:
                echarts_option = None

        with c_view_tab:
            if echarts_option:
                render_echarts(echarts_option, height=480, chart_id=f"{cid}_{idx}")
            elif cid == "table":
                st.dataframe(df.head(100), use_container_width=True)
            else:
                st.info(
                    f"Live rendering for **{cname}** ({cid}) requires special geographical geoJSON or WebGL dependencies. "
                    f"Recommended mapping: `{active_mapping}`."
                )

        with c_edit_tab:
            st.markdown("##### 🔀 Remap Columns to Chart Axes / Roles")
            available_columns = [""] + list(df.columns)
            edit_cols = st.columns(max(1, len(mapping.keys())))

            updated_mapping = {}
            for col_idx, (role, current_col) in enumerate(active_mapping.items()):
                with edit_cols[col_idx % len(edit_cols)]:
                    curr_val = current_col if current_col in available_columns else available_columns[0]
                    selected_col = st.selectbox(
                        f"Axis / Role: `{role}`",
                        options=available_columns,
                        index=available_columns.index(curr_val) if curr_val in available_columns else 0,
                        key=f"select_{cid}_{idx}_{role}",
                    )
                    updated_mapping[role] = selected_col

            remap_btn = st.button(
                f"🔄 Update & Re-render {cname}",
                key=f"apply_{cid}_{idx}",
            )
            if remap_btn:
                st.session_state[mapping_state_key] = updated_mapping
                st.rerun()

        with c_json_tab:
            if echarts_option:
                st.code(json.dumps(echarts_option, indent=2), language="json")
            else:
                st.code(
                    json.dumps({
                        "chart_id": cid,
                        "chart_name": cname,
                        "mapping": active_mapping,
                        "note": "ECharts option requires WebGL or external GeoJSON resources.",
                    }, indent=2),
                    language="json",
                )

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

else:
    # Empty State — Instructions
    st.markdown(
        """
        <div style="text-align: center; padding: 3rem 1rem; background: rgba(17, 24, 39, 0.4); border: 1px dashed rgba(255, 255, 255, 0.12); border-radius: 16px; margin-top: 1rem;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">📊</div>
            <h3 style="color: #f1f5f9; margin-bottom: 0.5rem;">Upload a CSV or select a sample dataset above</h3>
            <p style="color: #94a3b8; max-width: 600px; margin: 0 auto 1.5rem auto; font-size: 0.95rem;">
                ChartSuggest will analyze your data structure, detect column semantics and relationships,
                and instantly recommend the best Apache ECharts visualizations with live rendering.
            </p>
            <div style="display: flex; justify-content: center; gap: 8px; flex-wrap: wrap;">
                <span class="signal-chip">Categorical Sales</span>
                <span class="signal-chip">Time Series Revenue</span>
                <span class="signal-chip">Ad Spend Correlation</span>
                <span class="signal-chip">Supply Chain Flow</span>
                <span class="signal-chip">House Prices</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
