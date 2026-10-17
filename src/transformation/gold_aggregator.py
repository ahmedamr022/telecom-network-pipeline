from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from config.logging_config import logger


class GoldAggregator:
    """
    Constructs business-ready, analytical Gold Layer dimensional aggregates.
    Produces hourly cell-level rollups, regional SLA scorecards, and network incident logs.
    """

    @staticmethod
    def aggregate_cell_hourly(silver_df: pd.DataFrame) -> pd.DataFrame:
        """
        Rolls up 5-minute ROP telemetry into hourly cell-level KPI summaries
        including 95th percentile latency, busy-hour PRB utilization, and total GB volume.
        """
        if silver_df.empty:
            return pd.DataFrame()

        df = silver_df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Create date_hour bucket (e.g. 2026-10-17 18:00:00)
        df["date_hour"] = df["timestamp"].dt.floor("h")

        # 5-minute interval: Throughput (Mbps) * 300 seconds / 8000 = Data Volume (Gigabytes)
        df["volume_gb"] = (df["throughput_dl_mbps"] * 300.0) / 8000.0

        group_cols = [
            "cell_id", "site_id", "date_hour", "region", "subregion",
            "technology", "frequency_band_mhz", "backhaul_type"
        ]

        def p95(x):
            return np.percentile(x, 95) if len(x) > 0 else 0.0

        hourly = df.groupby(group_cols).agg(
            sample_count=("timestamp", "count"),
            avg_latency_ms=("latency_ms", "mean"),
            p95_latency_ms=("latency_ms", p95),
            avg_jitter_ms=("jitter_ms", "mean"),
            avg_packet_loss_pct=("packet_loss_pct", "mean"),
            max_packet_loss_pct=("packet_loss_pct", "max"),
            avg_throughput_dl_mbps=("throughput_dl_mbps", "mean"),
            max_throughput_dl_mbps=("throughput_dl_mbps", "max"),
            total_volume_gb=("volume_gb", "sum"),
            avg_prb_dl_pct=("prb_utilization_dl_pct", "mean"),
            busy_hour_prb_dl_pct=("prb_utilization_dl_pct", "max"),
            avg_connected_users=("connected_users", "mean"),
            peak_connected_users=("connected_users", "max"),
            avg_rsrp_dbm=("rsrp_dbm", "mean"),
            avg_sinr_db=("sinr_db", "mean"),
            avg_spectral_efficiency=("spectral_efficiency_bps_hz", "mean"),
            avg_nqi=("network_quality_index", "mean"),
            sla_compliance_rate_pct=("is_sla_compliant", lambda x: (x.sum() / len(x)) * 100.0),
            anomaly_sample_count=("is_anomaly", "sum")
        ).reset_index()

        # Round values for analytical presentation
        float_cols = [c for c in hourly.columns if c.startswith(("avg_", "p95_", "max_", "total_", "busy_", "sla_"))]
        hourly[float_cols] = hourly[float_cols].round(2)

        logger.info(f"Gold Aggregation: generated {len(hourly)} hourly cell KPI rows.")
        return hourly

    @staticmethod
    def aggregate_regional_sla(cell_hourly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Rolls up cell performance to high-level Regional SLA Compliance scorecards.
        """
        if cell_hourly_df.empty:
            return pd.DataFrame()

        df = cell_hourly_df.copy()

        regional = df.groupby(["region", "date_hour"]).agg(
            total_monitored_cells=("cell_id", "nunique"),
            total_volume_gb=("total_volume_gb", "sum"),
            avg_regional_latency_ms=("avg_latency_ms", "mean"),
            avg_regional_packet_loss_pct=("avg_packet_loss_pct", "mean"),
            avg_regional_throughput_mbps=("avg_throughput_dl_mbps", "mean"),
            regional_sla_compliance_pct=("sla_compliance_rate_pct", "mean"),
            avg_network_quality_index=("avg_nqi", "mean"),
            total_anomalies_detected=("anomaly_sample_count", "sum")
        ).reset_index()

        float_cols = [c for c in regional.columns if c.startswith(("avg_", "total_volume", "regional_"))]
        regional[float_cols] = regional[float_cols].round(2)

        return regional
