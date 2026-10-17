import pandas as pd
from src.analytics.rca_engine import TelecomRCAEngine


def test_rca_sleeping_cell_diagnosis():
    rca = TelecomRCAEngine()
    row = pd.Series({
        "is_anomaly": True,
        "is_sleeping_cell": True,
        "cell_id": "CAI-EAST-001-S1",
        "timestamp": "2026-10-17 12:00:00",
        "severity": "CRITICAL",
        "connected_users": 0,
        "throughput_dl_mbps": 0.0,
        "packet_loss_pct": 100.0,
        "prb_utilization_dl_pct": 0.0,
        "latency_ms": 500.0,
        "sinr_db": 10.0,
        "rsrp_dbm": -85.0
    })

    diagnosis = rca.diagnose_row(row)
    assert diagnosis is not None
    assert diagnosis.suspected_cause == "BASEBAND_HARDWARE_LOCKUP"
    assert diagnosis.severity == "CRITICAL"
    assert "power-cycle" in diagnosis.recommended_action.lower()


def test_rca_backhaul_bottleneck_diagnosis():
    rca = TelecomRCAEngine()
    row = pd.Series({
        "is_anomaly": True,
        "is_sleeping_cell": False,
        "is_transport_bottleneck": True,
        "is_congested": False,
        "is_interfered": False,
        "cell_id": "GZA-OCT-004-S2",
        "timestamp": "2026-10-17 12:00:00",
        "severity": "MAJOR",
        "connected_users": 55,
        "throughput_dl_mbps": 25.0,
        "packet_loss_pct": 8.5,
        "prb_utilization_dl_pct": 32.0,  # Uncongested radio
        "backhaul_utilization_pct": 98.0, # Saturated transport
        "latency_ms": 220.0,             # High transport delay
        "sinr_db": 16.0,
        "rsrp_dbm": -82.0
    })

    diagnosis = rca.diagnose_row(row)
    assert diagnosis is not None
    assert diagnosis.suspected_cause == "BACKHAUL_TRANSPORT_BOTTLENECK"
    assert "reroute" in diagnosis.recommended_action.lower()


def test_rca_capacity_congestion_diagnosis():
    rca = TelecomRCAEngine()
    row = pd.Series({
        "is_anomaly": True,
        "is_sleeping_cell": False,
        "is_transport_bottleneck": False,
        "is_congested": True,
        "is_interfered": False,
        "cell_id": "CAI-DNTN-002-S1",
        "timestamp": "2026-10-17 12:00:00",
        "severity": "MAJOR",
        "connected_users": 280,
        "throughput_dl_mbps": 180.0,
        "packet_loss_pct": 1.2,
        "prb_utilization_dl_pct": 96.0,  # PRB saturated
        "backhaul_utilization_pct": 60.0,
        "latency_ms": 85.0,
        "sinr_db": 18.0,                # Clear radio signal
        "rsrp_dbm": -78.0
    })

    diagnosis = rca.diagnose_row(row)
    assert diagnosis is not None
    assert diagnosis.suspected_cause == "RAN_CAPACITY_CONGESTION"
    assert "load balancing" in diagnosis.recommended_action.lower()
