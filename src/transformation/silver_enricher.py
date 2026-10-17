import math
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
import numpy as np

from config.settings import settings
from config.logging_config import logger
from src.generator.topology import generate_network_topology, CellSector

# 3GPP TS 36.213 Table 7.2.3-1: 4-bit CQI to Spectral Efficiency (bits/symbol or bps/Hz)
CQI_EFFICIENCY_MAP = {
    1: 0.1523,
    2: 0.2344,
    3: 0.3770,
    4: 0.6016,
    5: 0.8770,
    6: 1.1758,
    7: 1.4766,
    8: 1.9141,
    9: 2.4063,
    10: 2.7305,
    11: 3.3223,
    12: 3.9023,
    13: 4.5234,
    14: 5.1152,
    15: 5.5547,
}


class SilverEnricher:
    """
    Transforms Bronze telemetry into curated, dimensionalized Silver datasets.
    Guarantees idempotency on (cell_id, timestamp), computes rigorous Shannon
    and 3GPP modulation efficiency indicators, and evaluates enterprise SLA bounds.
    """

    def __init__(self, topology_sectors: Optional[List[CellSector]] = None):
        self.sectors = topology_sectors or generate_network_topology()
        # Ensure 1-to-1 unique dimensional mapping to prevent join cartesian explosion
        raw_dim_df = pd.DataFrame([
            {
                "cell_id": s.cell_id,
                "region": s.region,
                "subregion": s.subregion,
                "backhaul_type": s.backhaul_type,
                "azimuth_deg": s.azimuth_deg,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "nominal_capacity_mbps": s.nominal_capacity_mbps,
            }
            for s in self.sectors
        ])
        self.dim_df = raw_dim_df.drop_duplicates(subset=["cell_id"])

    def enrich(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Enriches raw validated telemetry with network dimensions and derived KPIs.
        Guarantees strict deduplication and idempotent output.
        """
        if raw_df.empty:
            logger.warning("Empty dataframe provided to SilverEnricher.")
            return pd.DataFrame()

        df = raw_df.copy()

        # Ensure datetime format
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Idempotency Guarantee: deduplicate within batch on logical key (cell_id, timestamp)
        initial_len = len(df)
        df = df.drop_duplicates(subset=["cell_id", "timestamp"], keep="last")
        if len(df) < initial_len:
            logger.info(f"Idempotency: eliminated {initial_len - len(df)} duplicate telemetry records.")

        # Join topology dimensions safely
        df = df.merge(self.dim_df, on="cell_id", how="left")

        # Fill missing dimensions if any unmapped cells appear
        df["region"] = df["region"].fillna("UNKNOWN")
        df["subregion"] = df["subregion"].fillna("UNKNOWN")
        df["backhaul_type"] = df["backhaul_type"].fillna("FIBER_10G")
        df["azimuth_deg"] = df["azimuth_deg"].fillna(0).astype(int)
        df["latitude"] = df["latitude"].fillna(30.0444)
        df["longitude"] = df["longitude"].fillna(31.2357)

        # 1. Theoretical Continuous Shannon-Hartley Limit: log2(1 + 10^(SINR/10))
        # Note: SINR treated as proxy for SNR in AWGN channel
        sinr_linear = np.power(10.0, df["sinr_db"] / 10.0)
        df["theoretical_spectral_efficiency_bps_hz"] = np.log2(1.0 + np.maximum(0.01, sinr_linear)).round(3)

        # 2. Estimated 3GPP Modulation Efficiency via Discrete CQI Lookup Table
        df["estimated_radio_efficiency_bps_hz"] = df["cqi"].map(CQI_EFFICIENCY_MAP).fillna(1.0).round(3)

        # 3. Measured Operational Spectral Efficiency: Throughput / Bandwidth
        df["measured_spectral_efficiency_bps_hz"] = (
            df["throughput_dl_mbps"] / df["bandwidth_mhz"].replace(0, np.nan)
        ).round(3)

        # 4. Average Bandwidth Per Connected User
        df["throughput_per_user_mbps"] = (
            df["throughput_dl_mbps"] / df["connected_users"].clip(lower=1)
        ).round(3)

        # 5. Composite Network Quality Index (NQI: 0.0 - 100.0)
        # Weights: 35% Radio RF, 40% IP Transport, 25% Accessibility
        radio_score = np.clip((df["sinr_db"] + 10.0) / 35.0 * 100.0, 0.0, 100.0)
        
        transport_score = 100.0 - np.clip(
            (df["latency_ms"] / 100.0 * 40.0) + (df["packet_loss_pct"] * 12.0),
            0.0,
            100.0
        )
        
        accessibility_score = np.clip(
            df["rrc_success_rate_pct"] - (df["erab_drop_rate_pct"] * 5.0),
            0.0,
            100.0
        )

        df["network_quality_index"] = (
            0.35 * radio_score + 0.40 * transport_score + 0.25 * accessibility_score
        ).round(2)

        # 6. SLA Compliance Evaluation (3GPP / Telco Enterprise Contract)
        df["is_sla_compliant"] = (
            (df["latency_ms"] <= settings.SLA_MAX_LATENCY_MS) &
            (df["packet_loss_pct"] <= settings.SLA_MAX_PACKET_LOSS_PCT) &
            (df["throughput_dl_mbps"] >= settings.SLA_MIN_THROUGHPUT_MBPS) &
            (df["rrc_success_rate_pct"] >= settings.SLA_MIN_RRC_SUCCESS_RATE_PCT) &
            (df["erab_drop_rate_pct"] <= settings.SLA_MAX_ERAB_DROP_RATE_PCT)
        )

        # 7. Fault Indication Flags
        df["is_congested"] = df["prb_utilization_dl_pct"] >= settings.CONGESTION_PRB_THRESHOLD
        df["is_interfered"] = (df["sinr_db"] < settings.INTERFERENCE_SINR_THRESHOLD) & (df["rsrp_dbm"] >= -105.0)
        df["is_transport_bottleneck"] = (
            (df["backhaul_utilization_pct"] >= settings.BACKHAUL_SATURATION_THRESHOLD) |
            ((df["latency_ms"] > 100.0) & (df["packet_loss_pct"] > 3.0) & (df["prb_utilization_dl_pct"] < 65.0))
        )
        # Sleeping cell initial flag: requires zero/single user + zero throughput + high loss
        df["is_sleeping_cell"] = (
            (df["connected_users"] <= settings.SLEEPING_CELL_MIN_USERS) &
            (df["throughput_dl_mbps"] <= 0.1) &
            (df["packet_loss_pct"] >= 50.0)
        )

        logger.info(f"Silver enrichment complete: {len(df)} records processed. SLA pass rate: {df['is_sla_compliant'].mean() * 100:.1f}%")
        return df
