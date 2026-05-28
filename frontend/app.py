"""
Smart Traffic Monitoring Dashboard - Streamlit Frontend
Flipkart Gridlock Hackathon 2.0 | Bengaluru Mobility Intelligence
"""

import io
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from PIL import Image

# Page config
st.set_page_config(
    page_title="Bengaluru Traffic AI",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = st.sidebar.text_input("Backend API URL", "http://localhost:8000/api/v1")

# Dark theme CSS
st.markdown(
    """
<style>
    .stApp { background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%); }
    h1, h2, h3 { color: #58a6ff !important; }
    .metric-card {
        background: #21262d;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }
    .congestion-low { color: #3fb950; font-weight: bold; font-size: 1.4rem; }
    .congestion-medium { color: #d29922; font-weight: bold; font-size: 1.4rem; }
    .congestion-heavy { color: #f85149; font-weight: bold; font-size: 1.4rem; }
    .congestion-gridlock { color: #ff0000; font-weight: bold; font-size: 1.4rem; }
    .alert-box {
        background: #3d1f1f;
        border-left: 4px solid #f85149;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
    }
    div[data-testid="stSidebar"] { background: #161b22; }
</style>
""",
    unsafe_allow_html=True,
)


def api_get(path: str):
    try:
        r = requests.get(f"{API_URL}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(path: str, files=None, json=None):
    try:
        if files:
            r = requests.post(f"{API_URL}{path}", files=files, timeout=60)
        else:
            r = requests.post(f"{API_URL}{path}", json=json, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def congestion_class(level: str) -> str:
    m = {
        "Low Traffic": "congestion-low",
        "Medium Traffic": "congestion-medium",
        "Heavy Traffic": "congestion-heavy",
        "Gridlock": "congestion-gridlock",
    }
    return m.get(level, "congestion-low")


# Sidebar
st.sidebar.title("🚦 Traffic Controls")
page = st.sidebar.radio(
    "Navigation",
    ["Live Dashboard", "Video Processing", "Analytics", "Alerts & Reports", "About"],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Flipkart Gridlock Hackathon 2.0**")
st.sidebar.markdown("Bengaluru Smart Mobility")

# Session state
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "history" not in st.session_state:
    st.session_state.history = []


# Header
st.title("🚦 Smart Traffic Monitoring & Mobility Intelligence")
st.caption("AI-Powered CCTV Analytics for Bengaluru Traffic | YOLOv8 + ByteTrack + Real-Time Analytics")

# LIVE DASHBOARD
if page == "Live Dashboard":
    col_sid, col_refresh = st.columns([3, 1])
    with col_sid:
        session_id = st.text_input("Session ID", value=st.session_state.session_id or "")
    with col_refresh:
        st.write("")
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    if session_id:
        st.session_state.session_id = session_id
        status = api_get(f"/video/status/{session_id}")
        live = api_get(f"/analytics/live/{session_id}") if status and status.get("latest") else None

        if status:
            st.info(f"Status: **{status.get('status', 'unknown')}**")

        data = live or (status.get("latest") if status else None)
        if data:
            c1, c2, c3, c4, c5 = st.columns(5)
            counts = data.get("vehicle_counts", {})
            cong = data.get("congestion", {})
            level = cong.get("level", "Low Traffic")

            c1.metric("Total Vehicles", counts.get("total", 0))
            c2.metric("Cars", counts.get("cars", 0))
            c3.metric("Bikes", counts.get("bikes", 0))
            c4.metric("Buses", counts.get("buses", 0))
            c5.metric("Autos", counts.get("autos", 0))

            st.markdown(
                f'<p class="{congestion_class(level)}">Congestion: {level} — Score: {cong.get("score", 0):.2f}</p>',
                unsafe_allow_html=True,
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("Avg Speed", f"{cong.get('avg_speed', 0):.1f} km/h")
            m2.metric("Density", f"{cong.get('density', 0):.3f}")
            m3.metric("Occupancy", f"{cong.get('occupancy', 0):.3f}")

            # Live frame
            frame_col, chart_col = st.columns([1.2, 1])
            with frame_col:
                st.subheader("Live Processed Feed")
                try:
                    frame_url = f"{API_URL}/video/frame/{session_id}?t={int(time.time())}"
                    img_r = requests.get(frame_url, timeout=5)
                    if img_r.status_code == 200:
                        st.image(Image.open(io.BytesIO(img_r.content)), use_container_width=True)
                except Exception:
                    st.warning("Waiting for processed frames...")

            with chart_col:
                st.subheader("Vehicle Distribution")
                df = pd.DataFrame(
                    {
                        "Type": ["Cars", "Bikes", "Buses", "Trucks", "Autos"],
                        "Count": [
                            counts.get("cars", 0),
                            counts.get("bikes", 0),
                            counts.get("buses", 0),
                            counts.get("trucks", 0),
                            counts.get("autos", 0),
                        ],
                    }
                )
                fig = px.pie(df, values="Count", names="Type", color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
                st.plotly_chart(fig, use_container_width=True)

            # Congestion gauge
            st.subheader("Congestion Score")
            score = cong.get("score", 0)
            gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=score * 100,
                    title={"text": "Congestion %"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#f85149" if score > 0.75 else "#d29922" if score > 0.5 else "#3fb950"},
                        "steps": [
                            {"range": [0, 25], "color": "#1a472a"},
                            {"range": [25, 50], "color": "#3d2f00"},
                            {"range": [50, 75], "color": "#4a2020"},
                            {"range": [75, 100], "color": "#5c1010"},
                        ],
                    },
                )
            )
            gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#c9d1d9", height=250)
            st.plotly_chart(gauge, use_container_width=True)

            # Forecast
            if data.get("forecast"):
                st.subheader("🔮 Predictive Congestion Forecast")
                fc_df = pd.DataFrame(data["forecast"])
                fig_fc = px.line(fc_df, x="step", y="predicted_score", markers=True, title="Predicted Congestion Trend")
                fig_fc.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
                st.plotly_chart(fig_fc, use_container_width=True)
                if data.get("signal_recommendation"):
                    st.success(f"🚥 Signal Recommendation: {data['signal_recommendation']}")

            # Violations & Alerts
            v1, v2 = st.columns(2)
            with v1:
                st.subheader("⚠️ Violations")
                for v in data.get("violations", []):
                    st.markdown(
                        f'<div class="alert-box">{v.get("type", "").upper()}: {v.get("details", "")}</div>',
                        unsafe_allow_html=True,
                    )
            with v2:
                st.subheader("🔔 Alerts")
                for a in data.get("alerts", []):
                    st.warning(f"[{a.get('severity', '')}] {a.get('message', '')}")

            # Entry/Exit & Flow
            ee = data.get("entry_exit", {})
            flow = data.get("flow", {})
            st.subheader("Movement Analysis")
            f1, f2, f3 = st.columns(3)
            f1.metric("Entries", ee.get("entry", 0))
            f2.metric("Exits", ee.get("exit", 0))
            f3.json(flow)

            # Auto-refresh
            if status and status.get("status") == "processing":
                time.sleep(2)
                st.rerun()
        else:
            st.warning("No live data yet. Start processing a video first.")
    else:
        st.info("Enter a session ID or process a video to view live metrics.")

# VIDEO PROCESSING
elif page == "Video Processing":
    st.header("📹 Video Processing")
    tab1, tab2, tab3 = st.tabs(["Upload Video", "Sample Data", "Webcam Info"])

    with tab1:
        uploaded = st.file_uploader("Upload traffic CCTV footage", type=["mp4", "avi", "mov", "mkv", "webm"])
        frame_skip = st.slider("Frame skip (performance)", 1, 5, 2)
        max_frames = st.number_input("Max frames (0 = all)", min_value=0, value=150)

        if uploaded and st.button("🚀 Start Processing", type="primary"):
            with st.spinner("Uploading and processing..."):
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                params = {"frame_skip": frame_skip, "save_output": True}
                if max_frames > 0:
                    params["max_frames"] = int(max_frames)
                try:
                    r = requests.post(
                        f"{API_URL}/video/upload",
                        files=files,
                        params=params,
                        timeout=120,
                    )
                    r.raise_for_status()
                    result = r.json()
                    st.session_state.session_id = result["session_id"]
                    st.success(f"Processing started! Session: **{result['session_id']}**")
                    st.code(result["session_id"])
                except Exception as e:
                    st.error(str(e))

    with tab2:
        st.markdown("Generate and process synthetic Bengaluru traffic video for demo.")
        duration = st.slider("Duration (seconds)", 5, 30, 10)
        if st.button("Generate & Process Sample"):
            with st.spinner("Generating sample video..."):
                gen = api_post("/video/sample/generate", json=None)
                if gen:
                    st.info(f"Sample: {gen.get('path')}")
                proc = requests.post(
                    f"{API_URL}/video/sample/process",
                    params={"duration_sec": duration, "frame_skip": 2, "max_frames": 150},
                    timeout=60,
                )
                if proc.ok:
                    result = proc.json()
                    st.session_state.session_id = result["session_id"]
                    st.success(f"Session: {result['session_id']}")

    with tab3:
        st.markdown(
            """
            **Webcam / CCTV Integration**
            - Use RTSP URL with OpenCV: `cv2.VideoCapture('rtsp://...')`
            - Extend `VideoProcessor` for live stream ingestion
            - API endpoint: POST `/api/v1/video/process` with stream path
            """
        )

    if st.session_state.session_id:
        st.markdown(f"**Active Session:** `{st.session_state.session_id}`")

# ANALYTICS
elif page == "Analytics":
    st.header("📊 Traffic Analytics")
    sid = st.text_input("Session ID", value=st.session_state.session_id or "")

    if sid and st.button("Load Analytics"):
        summary = api_get(f"/analytics/summary/{sid}")
        history = api_get(f"/analytics/congestion/{sid}")

        if summary:
            st.subheader("Session Summary")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Frames", summary.get("total_frames", 0))
            s2.metric("Peak Congestion", summary.get("peak_congestion", "N/A"))
            s3.metric("Violations", summary.get("violations_count", 0))
            s4.metric("Alerts", summary.get("alerts_count", 0))

            vb = summary.get("vehicle_breakdown", {})
            if isinstance(vb, dict):
                chart_df = pd.DataFrame({"type": list(vb.keys()), "count": list(vb.values())})
                fig = px.bar(chart_df, x="type", y="count", color="type")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
                st.plotly_chart(fig, use_container_width=True)

        if history and history.get("history"):
            hdf = pd.DataFrame(history["history"])
            st.subheader("Congestion Timeline")
            fig2 = px.line(hdf, x="timestamp", y="score", color="level")
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
            st.plotly_chart(fig2, use_container_width=True)

            fig3 = px.area(hdf, x="timestamp", y="avg_speed", title="Average Speed Over Time")
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#21262d", font_color="#c9d1d9")
            st.plotly_chart(fig3, use_container_width=True)

# ALERTS & REPORTS
elif page == "Alerts & Reports":
    st.header("🔔 Alerts & Reports")
    sid = st.text_input("Session ID", value=st.session_state.session_id or "")

    alerts = api_get("/analytics/alerts" + (f"?session_id={sid}" if sid else ""))
    if alerts:
        st.subheader("Recent Alerts")
        for a in alerts[:20]:
            icon = "🔴" if a.get("severity") == "high" else "🟡"
            st.markdown(f"{icon} **{a.get('alert_type')}** — {a.get('message')} _{a.get('timestamp')}_")

    if sid:
        st.subheader("Download Reports")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown(f"[📥 Traffic CSV]({API_URL}/reports/traffic/{sid})")
        with r2:
            st.markdown(f"[📥 Violations CSV]({API_URL}/reports/violations/{sid})")
        with r3:
            st.markdown(f"[📥 Summary Report]({API_URL}/reports/summary/{sid})")

# ABOUT
else:
    st.header("About Smart Traffic AI")
    st.markdown(
        """
        ### Bengaluru Mobility Intelligence System

        **Flipkart Gridlock Hackathon 2.0** — Production-ready AI traffic monitoring platform.

        #### Architecture
        ```
        Video Input → Frame Extraction → YOLOv8 Detection → ByteTrack Tracking
        → Congestion Analysis → Helmet Detection → Analytics → Dashboard → Alerts
        ```

        #### Features
        - Real-time vehicle detection (cars, bikes, buses, trucks, autos)
        - Congestion classification (Low / Medium / Heavy / Gridlock)
        - Helmet violation & triple riding detection
        - Vehicle tracking with speed estimation
        - Heatmap visualization
        - Accident/anomaly detection
        - Predictive congestion forecasting
        - Dynamic signal timing recommendations
        - CSV & summary report generation

        #### Tech Stack
        Python | FastAPI | OpenCV | YOLOv8 | ByteTrack | Streamlit | SQLite | Docker
        """
    )
    health = api_get("/health")
    if health:
        st.success(f"Backend: {health.get('status')} | Models: {health.get('models_loaded')}")
