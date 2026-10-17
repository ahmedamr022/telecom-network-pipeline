from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from config.logging_config import logger


class NetworkAnomalyDetector:
    """
    Time-series and statistical anomaly detector for cellular network telemetry.
    Applies Rolling Z-score and multivariate boundary checks to isolate degraded sectors.
    """

    def __init__(self, z_score_threshold: float = 2.8):
        self.z_score_threshold = z_score_threshold

    def detect_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluates silver telemetry dataframe, annotating anomalies, severity levels,
        and statistical divergence metrics.
        """
        if df.empty:
            return df

        result_df = df.copy()

        # Sort by cell and timestamp for time-series operations
        result_df = result_df.sort_values(by=["cell_id", "timestamp"]).reset_index(drop=True)

        # 1. Rolling Baseline per Cell (or global cell-group baseline if single-snapshot)
        # Compute group statistics across cell_id (or technology/subregion if few timepoints)
        num_timestamps = result_df["timestamp"].nunique()

        if num_timestamps >= 6:
            # Multi-timestamp time-series: use rolling window per cell
            latency_rolling_mean = result_df.groupby("cell_id")["latency_ms"].transform(
                lambda x: x.rolling(window=6, min_periods=2).mean()
            )
            latency_rolling_std = result_df.groupby("cell_id")["latency_ms"].transform(
                lambda x: x.rolling(window=6, min_periods=2).std()
            ).fillna(1.0)
        else:
            # Snapshot / cross-sectional: compute baseline across technology + backhaul type
            latency_rolling_mean = result_df.groupby(["technology", "backhaul_type"])["latency_ms"].transform("mean")
            latency_rolling_std = result_df.groupby(["technology", "backhaul_type"])["latency_ms"].transform("std").fillna(2.0)

        # Latency Z-Score
        result_df["latency_zscore"] = (
            (result_df["latency_ms"] - latency_rolling_mean) / (latency_rolling_std + 1e-5)
        ).round(2)

        # 2. Composite Anomaly Flag
        is_statistical_latency_anomaly = result_df["latency_zscore"].abs() >= self.z_score_threshold
        is_high_packet_loss = result_df["packet_loss_pct"] >= 4.0
        is_prb_exhaustion = result_df["prb_utilization_dl_pct"] >= 88.0
        is_sinr_collapse = result_df["sinr_db"] <= 0.0
        is_dead_cell = result_df["is_sleeping_cell"]

        result_df["is_anomaly"] = (
            is_statistical_latency_anomaly |
            is_high_packet_loss |
            is_prb_exhaustion |
            is_sinr_collapse |
            is_dead_cell
        )

        # 3. Severity Classification (CRITICAL, MAJOR, MINOR, NORMAL)
        def assign_severity(row: pd.Series) -> str:
            if not row["is_anomaly"]:
                return "NORMAL"
            if row["is_sleeping_cell"] or row["packet_loss_pct"] >= 15.0 or row["latency_ms"] >= 200.0:
                return "CRITICAL"
            if row["prb_utilization_dl_pct"] >= 90.0 or row["sinr_db"] <= -2.0 or row["packet_loss_pct"] >= 5.0:
                return "MAJOR"
            return "MINOR"

        result_df["severity"] = result_df.apply(assign_severity, axis=1)

        anomaly_count = result_df["is_anomaly"].sum()
        logger.info(f"Anomaly Detection: {anomaly_count}/{len(result_df)} records flagged ({anomaly_count/len(result_df)*100:.1f}%)")
        return result_df
