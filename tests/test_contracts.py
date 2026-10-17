from datetime import datetime, timedelta
import pytest
from pydantic import ValidationError

from src.contracts.schemas import RawTelemetryRecord, DLQRecord
from src.ingestion.validator import TelemetryContractValidator


def test_valid_telemetry_contract():
    valid_payload = {
        "timestamp": datetime.now(),
        "cell_id": "CAI-EAST-001-S1",
        "site_id": "CAI-EAST-001",
        "technology": "4G_LTE",
        "frequency_band_mhz": 1800,
        "bandwidth_mhz": 20.0,
        "latency_ms": 18.5,
        "jitter_ms": 2.1,
        "packet_loss_pct": 0.05,
        "backhaul_utilization_pct": 35.0,
        "throughput_dl_mbps": 85.0,
        "throughput_ul_mbps": 22.0,
        "prb_utilization_dl_pct": 62.0,
        "prb_utilization_ul_pct": 34.0,
        "connected_users": 65,
        "rsrp_dbm": -85.0,
        "sinr_db": 14.5,
        "cqi": 11,
        "rrc_success_rate_pct": 99.5,
        "erab_drop_rate_pct": 0.2
    }
    record = RawTelemetryRecord(**valid_payload)
    assert record.cell_id == "CAI-EAST-001-S1"
    assert record.latency_ms == 18.5


def test_invalid_negative_latency_rejected():
    invalid_payload = {
        "timestamp": datetime.now(),
        "cell_id": "CAI-EAST-001-S1",
        "site_id": "CAI-EAST-001",
        "technology": "4G_LTE",
        "frequency_band_mhz": 1800,
        "bandwidth_mhz": 20.0,
        "latency_ms": -10.0,  # Negative latency violates RFC 2544
        "jitter_ms": 2.0,
        "packet_loss_pct": 0.1,
        "backhaul_utilization_pct": 20.0,
        "throughput_dl_mbps": 50.0,
        "throughput_ul_mbps": 10.0,
        "prb_utilization_dl_pct": 50.0,
        "prb_utilization_ul_pct": 20.0,
        "connected_users": 10,
        "rsrp_dbm": -80.0,
        "sinr_db": 10.0,
        "cqi": 10,
        "rrc_success_rate_pct": 99.0,
        "erab_drop_rate_pct": 0.1
    }
    with pytest.raises(ValidationError):
        RawTelemetryRecord(**invalid_payload)


def test_invalid_cell_id_format_rejected():
    invalid_payload = {
        "timestamp": datetime.now(),
        "cell_id": "INVALID_SITE_NAME_123",  # Malformed pattern
        "site_id": "CAI-001",
        "technology": "5G_NR",
        "frequency_band_mhz": 3500,
        "bandwidth_mhz": 100.0,
        "latency_ms": 12.0,
        "jitter_ms": 1.0,
        "packet_loss_pct": 0.0,
        "backhaul_utilization_pct": 20.0,
        "throughput_dl_mbps": 300.0,
        "throughput_ul_mbps": 60.0,
        "prb_utilization_dl_pct": 40.0,
        "prb_utilization_ul_pct": 15.0,
        "connected_users": 80,
        "rsrp_dbm": -75.0,
        "sinr_db": 22.0,
        "cqi": 14,
        "rrc_success_rate_pct": 99.8,
        "erab_drop_rate_pct": 0.05
    }
    with pytest.raises(ValidationError):
        RawTelemetryRecord(**invalid_payload)


def test_validator_routes_to_dlq():
    raw_frames = [
        # Valid
        {
            "timestamp": datetime.now(),
            "cell_id": "GZA-OCT-002-S2",
            "site_id": "GZA-OCT-002",
            "technology": "4G_LTE",
            "frequency_band_mhz": 1800,
            "bandwidth_mhz": 20.0,
            "latency_ms": 25.0,
            "jitter_ms": 3.0,
            "packet_loss_pct": 0.1,
            "backhaul_utilization_pct": 30.0,
            "throughput_dl_mbps": 45.0,
            "throughput_ul_mbps": 12.0,
            "prb_utilization_dl_pct": 40.0,
            "prb_utilization_ul_pct": 20.0,
            "connected_users": 30,
            "rsrp_dbm": -90.0,
            "sinr_db": 12.0,
            "cqi": 9,
            "rrc_success_rate_pct": 99.1,
            "erab_drop_rate_pct": 0.2
        },
        # Corrupted (PRB > 100%)
        {
            "timestamp": datetime.now(),
            "cell_id": "GZA-OCT-002-S3",
            "site_id": "GZA-OCT-002",
            "technology": "4G_LTE",
            "frequency_band_mhz": 1800,
            "bandwidth_mhz": 20.0,
            "latency_ms": 25.0,
            "jitter_ms": 3.0,
            "packet_loss_pct": 0.1,
            "backhaul_utilization_pct": 30.0,
            "throughput_dl_mbps": 45.0,
            "throughput_ul_mbps": 12.0,
            "prb_utilization_dl_pct": 145.0,  # Invalid
            "prb_utilization_ul_pct": 20.0,
            "connected_users": 30,
            "rsrp_dbm": -90.0,
            "sinr_db": 12.0,
            "cqi": 9,
            "rrc_success_rate_pct": 99.1,
            "erab_drop_rate_pct": 0.2
        }
    ]

    report = TelemetryContractValidator.validate_batch(raw_frames)
    assert report.total_records == 2
    assert report.valid_count == 1
    assert report.rejected_count == 1
    assert len(report.quarantined_records) == 1
    assert "prb_utilization_dl_pct" in report.quarantined_records[0]["error_message"]
