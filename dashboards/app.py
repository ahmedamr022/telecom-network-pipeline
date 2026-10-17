import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json

# Setup sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.storage.db_engine import db_engine
from src.storage.repository import TelecomRepository

# Page Configuration
st.set_page_config(
    page_title="TelcoPulse | Network Operations Center",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for high-density NOC aesthetic
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border: 1px solid #2E3440;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }
    .metric-val {
        font-size: 26px;
        font-weight: bold;
        color: #ECEFF4;
    }
    .metric-label {
        font-size: 13px;
        color: #88C0D0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .incident-badge-crit {
        background-color: #BF616A;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 11px;
    }
    .incident-badge-maj {
        background-color: #D08770;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 11px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=10)
def load_data():
    repo = TelecomRepository(db_engine)
    try:
        silver_df = db_engine.query("SELECT * FROM silver_cell_telemetry ORDER BY timestamp DESC LIMIT 3000;")
    except Exception:
        silver_df = pd.DataFrame()

    try:
        incidents_df = repo.get_recent_incidents(50)
    except Exception:
        incidents_df = pd.DataFrame()

    try:
        worst_cells_df = repo.get_worst_performing_cells(15)
    except Exception:
        worst_cells_df = pd.DataFrame()

    try:
        regional_df = repo.get_regional_summary()
    except Exception:
        regional_df = pd.DataFrame()

    # Load DLQ records
    dlq_records = []
    dlq_file = settings.DLQ_DIR / "quarantined_records.jsonl"
    if dlq_file.exists():
        with open(dlq_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        dlq_records.append(json.loads(line))
                    except Exception:
                        pass

    return silver_df, incidents_df, worst_cells_df, regional_df, dlq_records


# Sidebar Navigation
st.sidebar.title("📡 TelcoPulse NOC")
st.sidebar.caption("Radio Access & IP Transport Observability")
nav_choice = st.sidebar.radio(
    "Navigation",
    ["Executive Overview", "Cell Topology & Map", "Telemetry Deep-Dive", "Incident RCA Feed", "DLQ Quarantine", "SQL Console"]
)

# Pipeline trigger in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Pipeline Ingestion Controls")
if st.sidebar.button("⚡ Ingest New 5-Min Telemetry ROP"):
    with st.spinner("Executing pipeline batch..."):
        from src.generator.telemetry_producer import TelecomTelemetryProducer
        from src.ingestion.validator import TelemetryContractValidator
        from src.ingestion.bronze_writer import BronzeStorageWriter
        from src.transformation.silver_enricher import SilverEnricher
        from src.analytics.anomaly_detector import NetworkAnomalyDetector
        from src.analytics.rca_engine import TelecomRCAEngine
        from src.transformation.gold_aggregator import GoldAggregator
        from datetime import datetime

        producer = TelecomTelemetryProducer()
        frames = producer.generate_snapshot(datetime.now(), anomaly_ratio=0.10, corruption_ratio=0.03)
        report = TelemetryContractValidator.validate_batch(frames)
        
        writer = BronzeStorageWriter()
        writer.write_bronze_batch(report.valid_records)
        writer.write_dlq_quarantine(report.quarantined_records)
        
        enricher = SilverEnricher()
        silver = enricher.enrich(pd.DataFrame(report.valid_records))
        
        detector = NetworkAnomalyDetector()
        scored = detector.detect_anomalies(silver)
        
        rca = TelecomRCAEngine()
        inc = rca.diagnose_dataframe(scored)
        
        repo = TelecomRepository(db_engine)
        repo.save_silver_telemetry(scored)
        if not inc.empty:
            repo.save_incidents(inc)
            
        hourly = GoldAggregator.aggregate_cell_hourly(scored)
        reg = GoldAggregator.aggregate_regional_sla(hourly)
        repo.save_gold_hourly(hourly)
        repo.save_gold_regional(reg)

        st.sidebar.success(f"Ingested {len(scored)} frames, {len(inc)} incidents!")
        st.cache_data.clear()
        st.rerun()

silver_df, incidents_df, worst_cells_df, regional_df, dlq_records = load_data()

# ------------------------------------------------------------------------------
# PAGE 1: EXECUTIVE OVERVIEW
# ------------------------------------------------------------------------------
if nav_choice == "Executive Overview":
    st.title("🌐 Network Operations Center — Executive Overview")
    st.markdown("Real-time monitoring across 4G LTE & 5G NR Radio Access Network and Backhaul Links.")

    if silver_df.empty:
        st.warning("No telemetry records found. Click '⚡ Ingest New 5-Min Telemetry ROP' in the sidebar to populate the Lakehouse.")
    else:
        # Top KPI Metrics Row
        latest_ts = silver_df["timestamp"].max()
        snapshot = silver_df[silver_df["timestamp"] == latest_ts]

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("Monitored Sectors", f"{snapshot['cell_id'].nunique()}")
        with col2:
            sla_rate = snapshot['is_sla_compliant'].mean() * 100.0
            st.metric("SLA Compliance", f"{sla_rate:.1f}%", delta=f"{sla_rate - 99.0:.1f}% vs Target")
        with col3:
            avg_lat = snapshot['latency_ms'].mean()
            st.metric("Mean Latency", f"{avg_lat:.1f} ms", delta=f"{-1 if avg_lat < 50 else 1}", delta_color="inverse")
        with col4:
            avg_loss = snapshot['packet_loss_pct'].mean()
            st.metric("Packet Loss", f"{avg_loss:.2f}%")
        with col5:
            total_tp = snapshot['throughput_dl_mbps'].sum() / 1000.0
            st.metric("Aggregate DL Traffic", f"{total_tp:.2f} Gbps")
        with col6:
            active_anom = snapshot['is_anomaly'].sum()
            st.metric("Active Anomalies", f"{active_anom}", delta=f"{active_anom} alarms", delta_color="inverse")

        st.markdown("---")

        # Two Column Layout: Regional Table and Latency Distribution
        r_col1, r_col2 = st.columns([1, 1])

        with r_col1:
            st.subheader("Regional SLA Performance")
            if not regional_df.empty:
                st.dataframe(
                    regional_df.style.format({
                        "avg_latency_ms": "{:.1f} ms",
                        "avg_packet_loss_pct": "{:.2f}%",
                        "avg_throughput_mbps": "{:.1f} Mbps",
                        "avg_prb_dl_pct": "{:.1f}%",
                        "avg_nqi": "{:.1f}",
                        "sla_compliance_pct": "{:.1f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No regional data aggregated yet.")

        with r_col2:
            st.subheader("Transport Latency vs Packet Loss Distribution")
            fig = px.scatter(
                snapshot,
                x="latency_ms",
                y="packet_loss_pct",
                color="backhaul_type",
                size="connected_users",
                hover_data=["cell_id", "technology", "throughput_dl_mbps"],
                labels={"latency_ms": "Round-Trip Latency (ms)", "packet_loss_pct": "Packet Loss (%)"},
                template="plotly_dark",
                color_discrete_map={"FIBER_10G": "#A3BE8C", "MICROWAVE_1G": "#EBCB8B"}
            )
            # Add SLA threshold boundaries
            fig.add_vline(x=settings.SLA_MAX_LATENCY_MS, line_dash="dash", line_color="#BF616A", annotation_text="Max SLA Latency (50ms)")
            fig.add_hline(y=settings.SLA_MAX_PACKET_LOSS_PCT, line_dash="dash", line_color="#BF616A", annotation_text="Max SLA Loss (1%)")
            st.plotly_chart(fig, use_container_width=True)

        # Bottom Row: Worst Performing Cells
        st.subheader("⚠️ Top 10 Degraded Cells Requiring Engineering Attention")
        if not worst_cells_df.empty:
            st.dataframe(
                worst_cells_df.style.background_gradient(subset=["sla_compliance_pct"], cmap="RdYlGn"),
                use_container_width=True,
                hide_index=True
            )

# ------------------------------------------------------------------------------
# PAGE 2: CELL TOPOLOGY & MAP
# ------------------------------------------------------------------------------
elif nav_choice == "Cell Topology & Map":
    st.title("🗺️ Network Topology & Geospatial Coverage")
    st.markdown("Geographic distribution of base station towers, antenna sectors, and backhaul transmission types.")

    if not silver_df.empty:
        latest_ts = silver_df["timestamp"].max()
        map_df = silver_df[silver_df["timestamp"] == latest_ts].copy()

        map_df["health_status"] = np.where(
            map_df["is_anomaly"], "Anomaly Detected",
            np.where(map_df["is_sla_compliant"], "SLA Compliant (Healthy)", "Degraded SLA")
        )

        color_map = {
            "SLA Compliant (Healthy)": "#2ECC71",
            "Degraded SLA": "#F39C12",
            "Anomaly Detected": "#E74C3C"
        }

        fig_map = px.scatter_mapbox(
            map_df,
            lat="latitude",
            lon="longitude",
            color="health_status",
            size="throughput_dl_mbps",
            hover_name="cell_id",
            hover_data={
                "technology": True,
                "backhaul_type": True,
                "latency_ms": ":.1f",
                "packet_loss_pct": ":.2f",
                "prb_utilization_dl_pct": ":.1f",
                "latitude": False,
                "longitude": False
            },
            color_discrete_map=color_map,
            zoom=10,
            mapbox_style="carto-darkmatter",
            title="Cell Tower Real-Time Health Map"
        )
        fig_map.update_layout(height=650, margin={"r": 0, "t": 35, "l": 0, "b": 0})
        st.plotly_chart(fig_map, use_container_width=True)

        st.subheader("Sector Azimuth & Transmission Profiles")
        c1, c2 = st.columns(2)
        with c1:
            fig_tech = px.pie(map_df, names="technology", title="Technology Distribution", hole=0.4, color_discrete_sequence=["#88C0D0", "#81A1C1"])
            st.plotly_chart(fig_tech, use_container_width=True)
        with c2:
            fig_bh = px.pie(map_df, names="backhaul_type", title="Backhaul Transmission Media", hole=0.4, color_discrete_sequence=["#A3BE8C", "#D08770"])
            st.plotly_chart(fig_bh, use_container_width=True)

# ------------------------------------------------------------------------------
# PAGE 3: TELEMETRY DEEP-DIVE
# ------------------------------------------------------------------------------
elif nav_choice == "Telemetry Deep-Dive":
    st.title("📈 Cell Sector Telemetry Deep-Dive")
    st.markdown("Granular 5-minute ROP time-series telemetry analysis.")

    if not silver_df.empty:
        cells_list = sorted(silver_df["cell_id"].unique().tolist())
        selected_cell = st.selectbox("Select Cell Sector ID:", cells_list)

        cell_ts = silver_df[silver_df["cell_id"] == selected_cell].sort_values("timestamp")

        if not cell_ts.empty:
            meta = cell_ts.iloc[0]
            st.info(f"📍 **Site:** `{meta['site_id']}` | **Region:** `{meta['region']}-{meta['subregion']}` | **Tech:** `{meta['technology']}` ({meta['frequency_band_mhz']} MHz, {meta['bandwidth_mhz']} MHz BW) | **Backhaul:** `{meta['backhaul_type']}`")

            # 4 Key Charts
            col1, col2 = st.columns(2)
            with col1:
                fig1 = px.line(cell_ts, x="timestamp", y=["throughput_dl_mbps", "throughput_ul_mbps"],
                               title="Downlink & Uplink Throughput (Mbps)", template="plotly_dark")
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                fig2 = px.line(cell_ts, x="timestamp", y="prb_utilization_dl_pct",
                               title="Physical Resource Block (PRB) DL Utilization %", template="plotly_dark")
                fig2.add_hline(y=settings.CONGESTION_PRB_THRESHOLD, line_dash="dash", line_color="red", annotation_text="Congestion Threshold (85%)")
                st.plotly_chart(fig2, use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                fig3 = px.line(cell_ts, x="timestamp", y=["latency_ms", "jitter_ms"],
                               title="Round-Trip Latency & Jitter (ms)", template="plotly_dark")
                fig3.add_hline(y=settings.SLA_MAX_LATENCY_MS, line_dash="dash", line_color="orange", annotation_text="SLA 50ms")
                st.plotly_chart(fig3, use_container_width=True)

            with col4:
                fig4 = px.line(cell_ts, x="timestamp", y=["sinr_db", "rsrp_dbm"],
                               title="Radio Frequency Quality (SINR dB vs RSRP dBm)", template="plotly_dark")
                fig4.add_hline(y=0.0, line_dash="dash", line_color="red", annotation_text="Interference 0 dB")
                st.plotly_chart(fig4, use_container_width=True)

# ------------------------------------------------------------------------------
# PAGE 4: INCIDENT RCA FEED
# ------------------------------------------------------------------------------
elif nav_choice == "Incident RCA Feed":
    st.title("🔍 Automated Root Cause Analysis (RCA) Incident Feed")
    st.markdown("Diagnosed network anomalies with root cause explanations and NOC operational recommendations.")

    if incidents_df.empty:
        st.success("🎉 No active network incidents recorded. All cell sectors operating within nominal thresholds.")
    else:
        st.metric("Total Diagnosed Incidents", len(incidents_df))

        for _, inc in incidents_df.iterrows():
            severity = inc["severity"]
            badge_color = "red" if severity == "CRITICAL" else ("orange" if severity == "MAJOR" else "blue")
            
            with st.expander(f"🚨 [{severity}] {inc['cell_id']} — {inc['root_cause_category']} ({inc.get('confidence_pct', 90)}% Confidence)"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**Root Cause Diagnosis:**\n{inc['root_cause_summary']}")
                    st.markdown(f"**🔧 Recommended NOC Remediation:**\n`{inc['recommended_action']}`")
                with c2:
                    st.metric("Affected Subscribers", f"{inc['affected_users']}")
                    st.caption(f"Incident ID: `{inc['incident_id']}`")
                    st.caption(f"Timestamp: `{inc['timestamp']}`")

# ------------------------------------------------------------------------------
# PAGE 5: DLQ QUARANTINE
# ------------------------------------------------------------------------------
elif nav_choice == "DLQ Quarantine":
    st.title("🛑 Dead-Letter Queue (DLQ) Diagnostic Viewer")
    st.markdown("Quarantined payloads that violated perimeter data contracts (RFC 2544, 3GPP range validations).")

    if not dlq_records:
        st.success("No records in DLQ quarantine log.")
    else:
        st.metric("Quarantined Records", len(dlq_records))
        dlq_df = pd.DataFrame(dlq_records)
        
        display_cols = [c for c in ["quarantine_timestamp", "error_code", "error_message", "rejection_stage"] if c in dlq_df.columns]
        st.dataframe(dlq_df[display_cols], use_container_width=True)

        st.subheader("Raw Payload Inspection")
        selected_idx = st.selectbox("Select record index to inspect:", list(range(len(dlq_records))))
        st.json(dlq_records[selected_idx])

# ------------------------------------------------------------------------------
# PAGE 6: SQL CONSOLE
# ------------------------------------------------------------------------------
elif nav_choice == "SQL Console":
    st.title("💻 Lakehouse SQL Query Playground")
    st.markdown("Run interactive SQL queries directly against the DuckDB / PostgreSQL storage engine.")

    default_query = """SELECT 
    cell_id, 
    technology, 
    backhaul_type,
    ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
    ROUND(AVG(packet_loss_pct), 2) AS avg_loss_pct,
    ROUND(AVG(throughput_dl_mbps), 1) AS avg_dl_mbps
FROM silver_cell_telemetry
GROUP BY cell_id, technology, backhaul_type
ORDER BY avg_loss_pct DESC
LIMIT 15;"""

    query = st.text_area("SQL Query:", value=default_query, height=160)

    if st.button("Execute SQL"):
        try:
            res_df = db_engine.query(query)
            st.success(f"Query returned {len(res_df)} rows.")
            st.dataframe(res_df, use_container_width=True)
        except Exception as e:
            st.error(f"SQL Execution Error: {e}")
