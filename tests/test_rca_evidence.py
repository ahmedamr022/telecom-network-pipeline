import pandas as pd
from src.analytics.rca_engine import TelecomRCAEngine


def test_rca_evidence_chain_and_alternatives():
    rca = TelecomRCAEngine()
    
    # Backhaul Bottleneck telemetry
    row = pd.Series({
        "is_anomaly": True,
        "is_sleeping_cell": False,
        "is_transport_bottleneck": True,
        "is_congested": False,
        "is_interfered": False,
        "cell_id": "CAI-EAST-003-S1",
        "timestamp": "2026-10-17 14:00:00",
        "severity": "MAJOR",
        "connected_users": 60,
        "throughput_dl_mbps": 30.0,
        "packet_loss_pct": 6.5,
        "prb_utilization_dl_pct": 40.0,
        "backhaul_utilization_pct": 96.0,
        "latency_ms": 180.0,
        "sinr_db": 15.0,
        "rsrp_dbm": -82.0
    })

    diagnosis = rca.diagnose_row(row)
    assert diagnosis is not None
    assert diagnosis.suspected_cause == "BACKHAUL_TRANSPORT_BOTTLENECK"
    assert len(diagnosis.evidence) >= 3, "Evidence chain must contain at least 3 supporting conditions"
    assert len(diagnosis.alternative_causes) >= 1, "Alternative causes must be evaluated"
    assert diagnosis.confidence_score >= 0.85
    assert any("Backhaul utilization" in e for e in diagnosis.evidence)


def test_rca_ambiguous_telemetry_returns_insufficient_evidence():
    rca = TelecomRCAEngine()
    
    # Ambiguous telemetry: slight jitter anomaly without clear single failure signature
    row = pd.Series({
        "is_anomaly": True,
        "is_sleeping_cell": False,
        "is_transport_bottleneck": False,
        "is_congested": False,
        "is_interfered": False,
        "cell_id": "ALX-COAST-002-S1",
        "timestamp": "2026-10-17 14:00:00",
        "severity": "MINOR",
        "connected_users": 40,
        "throughput_dl_mbps": 45.0,
        "packet_loss_pct": 0.8,
        "prb_utilization_dl_pct": 45.0,
        "backhaul_utilization_pct": 50.0,
        "latency_ms": 65.0,
        "sinr_db": 12.0,
        "rsrp_dbm": -88.0
    })

    diagnosis = rca.diagnose_row(row)
    assert diagnosis is not None
    assert diagnosis.suspected_cause == "INSUFFICIENT_EVIDENCE_TRANSIENT"
    assert diagnosis.confidence_score < 0.50, "Ambiguous conditions must yield low confidence"
    assert "Monitor next 2 consecutive ROP" in diagnosis.recommended_action
