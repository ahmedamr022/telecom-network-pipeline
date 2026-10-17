import pandas as pd
from datetime import datetime
import duckdb
from src.storage.db_engine import DatabaseEngine
from src.storage.repository import TelecomRepository


def test_storage_and_repository_queries(tmp_path):
    # Use temporary duckdb database
    db_path = tmp_path / "test_lakehouse.duckdb"
    engine = DatabaseEngine(use_postgres=False)
    engine._duck_conn = duckdb.connect(str(db_path))
    repo = TelecomRepository(engine)

    # Insert test silver records
    sample_df = pd.DataFrame([
        {
            "timestamp": datetime.now(),
            "cell_id": "CAI-EAST-001-S1",
            "site_id": "CAI-EAST-001",
            "region": "CAI",
            "subregion": "EAST",
            "technology": "4G_LTE",
            "backhaul_type": "FIBER_10G",
            "latency_ms": 22.0,
            "jitter_ms": 2.0,
            "packet_loss_pct": 0.05,
            "throughput_dl_mbps": 75.0,
            "prb_utilization_dl_pct": 50.0,
            "network_quality_index": 88.0,
            "is_sla_compliant": True,
            "is_anomaly": False
        },
        {
            "timestamp": datetime.now(),
            "cell_id": "CAI-EAST-002-S1",
            "site_id": "CAI-EAST-002",
            "region": "CAI",
            "subregion": "EAST",
            "technology": "4G_LTE",
            "backhaul_type": "MICROWAVE_1G",
            "latency_ms": 130.0,
            "jitter_ms": 15.0,
            "packet_loss_pct": 5.2,
            "throughput_dl_mbps": 12.0,
            "prb_utilization_dl_pct": 35.0,
            "network_quality_index": 42.0,
            "is_sla_compliant": False,
            "is_anomaly": True
        }
    ])

    repo.save_silver_telemetry(sample_df)

    # Test worst performing cells
    worst_df = repo.get_worst_performing_cells(limit=5)
    assert not worst_df.empty
    assert worst_df.iloc[0]["cell_id"] == "CAI-EAST-002-S1"
    assert worst_df.iloc[0]["sla_compliance_pct"] == 0.0

    # Test regional summary
    reg_df = repo.get_regional_summary()
    assert not reg_df.empty
    assert reg_df.iloc[0]["region"] == "CAI"
    assert reg_df.iloc[0]["monitored_cells"] == 2
