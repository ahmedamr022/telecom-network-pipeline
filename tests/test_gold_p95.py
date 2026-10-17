import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.transformation.gold_aggregator import GoldAggregator


def test_gold_p95_empirical_accuracy():
    """
    Verifies that P95 is computed over raw empirical distribution
    rather than distorted through pre-aggregated averages.
    """
    base_time = datetime(2026, 10, 17, 10, 0, 0)
    
    # 12 samples (1 full hour at 5-min intervals)
    # Right-skewed latencies: 11 normal samples (20ms) and 1 extreme outlier (200ms)
    latencies = [20.0] * 11 + [200.0]
    
    records = []
    for i, lat in enumerate(latencies):
        records.append({
            "timestamp": base_time + timedelta(minutes=i * 5),
            "cell_id": "CAI-EAST-001-S1",
            "site_id": "CAI-EAST-001",
            "region": "CAI",
            "subregion": "EAST",
            "technology": "4G_LTE",
            "frequency_band_mhz": 1800,
            "backhaul_type": "FIBER_10G",
            "latency_ms": lat,
            "jitter_ms": 2.0,
            "packet_loss_pct": 0.1,
            "throughput_dl_mbps": 50.0,
            "prb_utilization_dl_pct": 45.0,
            "connected_users": 30,
            "rsrp_dbm": -85.0,
            "sinr_db": 15.0,
            "theoretical_spectral_efficiency_bps_hz": 4.0,
            "network_quality_index": 85.0,
            "is_sla_compliant": (lat < 50.0),
            "is_anomaly": (lat > 100.0)
        })

    silver_df = pd.DataFrame(records)
    hourly_df = GoldAggregator.aggregate_cell_hourly(silver_df)

    assert not hourly_df.empty
    row = hourly_df.iloc[0]

    # Mean latency is (11*20 + 200) / 12 = 35.0 ms
    assert row["avg_latency_ms"] == 35.0

    # True 95th percentile should be > 100 ms (capturing the tail)
    assert row["p95_latency_ms"] >= 100.0, f"P95 ({row['p95_latency_ms']}) must reflect tail latency!"
    
    # Full hour should not be marked partial
    assert row["sample_count"] == 12
    assert row["is_partial_hour"] == False


def test_gold_partial_hour_flagging():
    """Verifies that incomplete hours (e.g. only 3 samples) are flagged."""
    base_time = datetime(2026, 10, 17, 10, 0, 0)
    records = []
    for i in range(3):  # Only 3 samples instead of 12
        records.append({
            "timestamp": base_time + timedelta(minutes=i * 5),
            "cell_id": "CAI-EAST-001-S1",
            "site_id": "CAI-EAST-001",
            "region": "CAI",
            "subregion": "EAST",
            "technology": "4G_LTE",
            "frequency_band_mhz": 1800,
            "backhaul_type": "FIBER_10G",
            "latency_ms": 25.0,
            "jitter_ms": 2.0,
            "packet_loss_pct": 0.1,
            "throughput_dl_mbps": 50.0,
            "prb_utilization_dl_pct": 45.0,
            "connected_users": 30,
            "rsrp_dbm": -85.0,
            "sinr_db": 15.0,
            "theoretical_spectral_efficiency_bps_hz": 4.0,
            "network_quality_index": 85.0,
            "is_sla_compliant": True,
            "is_anomaly": False
        })

    hourly_df = GoldAggregator.aggregate_cell_hourly(pd.DataFrame(records))
    assert hourly_df.iloc[0]["is_partial_hour"] == True
    assert hourly_df.iloc[0]["sample_count"] == 3
