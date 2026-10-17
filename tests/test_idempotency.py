import pandas as pd
from datetime import datetime
import duckdb
from src.storage.db_engine import DatabaseEngine
from src.storage.repository import TelecomRepository


def test_silver_upsert_idempotency(tmp_path):
    """
    Verifies that inserting the exact same telemetry batch multiple times
    or inserting overlapping records NEVER multiplies table rows.
    """
    db_path = tmp_path / "idempotent_lakehouse.duckdb"
    engine = DatabaseEngine(use_postgres=False)
    engine._duck_conn = duckdb.connect(str(db_path))
    repo = TelecomRepository(engine)

    batch_ts = datetime(2026, 10, 17, 14, 0, 0)
    sample_df = pd.DataFrame([
        {
            "timestamp": batch_ts,
            "cell_id": "CAI-EAST-001-S1",
            "site_id": "CAI-EAST-001",
            "region": "CAI",
            "subregion": "EAST",
            "technology": "4G_LTE",
            "backhaul_type": "FIBER_10G",
            "latency_ms": 20.0,
            "jitter_ms": 2.0,
            "packet_loss_pct": 0.05,
            "throughput_dl_mbps": 80.0,
            "prb_utilization_dl_pct": 50.0,
            "network_quality_index": 85.0,
            "is_sla_compliant": True,
            "is_anomaly": False
        },
        {
            "timestamp": batch_ts,
            "cell_id": "CAI-EAST-001-S2",
            "site_id": "CAI-EAST-001",
            "region": "CAI",
            "subregion": "EAST",
            "technology": "4G_LTE",
            "backhaul_type": "FIBER_10G",
            "latency_ms": 21.0,
            "jitter_ms": 2.1,
            "packet_loss_pct": 0.05,
            "throughput_dl_mbps": 75.0,
            "prb_utilization_dl_pct": 48.0,
            "network_quality_index": 84.0,
            "is_sla_compliant": True,
            "is_anomaly": False
        }
    ])

    # First write
    repo.save_silver_telemetry(sample_df)
    count1 = engine.query("SELECT COUNT(*) AS cnt FROM silver_cell_telemetry").iloc[0]["cnt"]
    assert count1 == 2

    # Second write: exact same batch replayed
    repo.save_silver_telemetry(sample_df)
    count2 = engine.query("SELECT COUNT(*) AS cnt FROM silver_cell_telemetry").iloc[0]["cnt"]
    assert count2 == 2, "Idempotency failed: duplicate rows created on retry!"

    # Third write: modified metric value on existing primary key (cell_id, timestamp)
    updated_df = sample_df.copy()
    updated_df.loc[0, "latency_ms"] = 99.9
    repo.save_silver_telemetry(updated_df)
    count3 = engine.query("SELECT COUNT(*) AS cnt FROM silver_cell_telemetry").iloc[0]["cnt"]
    assert count3 == 2, "Row count changed on upsert!"

    # Verify updated value took effect
    row = engine.query("SELECT latency_ms FROM silver_cell_telemetry WHERE cell_id = 'CAI-EAST-001-S1'").iloc[0]
    assert row["latency_ms"] == 99.9
