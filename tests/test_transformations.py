import pandas as pd
from datetime import datetime
from src.transformation.silver_enricher import SilverEnricher
from src.generator.topology import generate_network_topology


def test_silver_enrichment_calculations():
    topo = generate_network_topology()
    enricher = SilverEnricher(topo)

    sample_raw = pd.DataFrame([{
        "timestamp": datetime.now(),
        "cell_id": topo[0].cell_id,
        "site_id": topo[0].site_id,
        "technology": topo[0].technology,
        "frequency_band_mhz": topo[0].frequency_band_mhz,
        "bandwidth_mhz": 20.0,
        "latency_ms": 22.0,
        "jitter_ms": 2.5,
        "packet_loss_pct": 0.05,
        "backhaul_utilization_pct": 30.0,
        "throughput_dl_mbps": 80.0,
        "throughput_ul_mbps": 20.0,
        "prb_utilization_dl_pct": 55.0,
        "prb_utilization_ul_pct": 25.0,
        "connected_users": 40,
        "rsrp_dbm": -82.0,
        "sinr_db": 15.0,
        "cqi": 12,
        "rrc_success_rate_pct": 99.6,
        "erab_drop_rate_pct": 0.1
    }])

    enriched_df = enricher.enrich(sample_raw)

    assert not enriched_df.empty
    row = enriched_df.iloc[0]

    # Measured Spectral Efficiency = 80.0 Mbps / 20.0 MHz = 4.0 bps/Hz
    assert row["measured_spectral_efficiency_bps_hz"] == 4.0

    # Theoretical Shannon limit log2(1 + 10^(15/10)) = log2(1 + 31.62) = ~5.028 bps/Hz
    assert 4.8 <= row["theoretical_spectral_efficiency_bps_hz"] <= 5.2

    # Estimated 3GPP Modulation Efficiency (CQI 12 = 3.902 bps/Hz)
    assert row["estimated_radio_efficiency_bps_hz"] == 3.902

    # Throughput per user = 80.0 / 40 = 2.0 Mbps
    assert row["throughput_per_user_mbps"] == 2.0

    # NQI score should be healthy (> 70)
    assert 70.0 <= row["network_quality_index"] <= 100.0

    # Healthy conditions should pass SLA
    assert row["is_sla_compliant"] == True
    assert row["is_congested"] == False


def test_sla_non_compliance_detection():
    topo = generate_network_topology()
    enricher = SilverEnricher(topo)

    # Degraded sample (high latency 120ms, packet loss 4.5%)
    sample_degraded = pd.DataFrame([{
        "timestamp": datetime.now(),
        "cell_id": topo[0].cell_id,
        "site_id": topo[0].site_id,
        "technology": topo[0].technology,
        "frequency_band_mhz": topo[0].frequency_band_mhz,
        "bandwidth_mhz": 20.0,
        "latency_ms": 125.0,       # Exceeds SLA (50ms)
        "jitter_ms": 18.0,
        "packet_loss_pct": 4.5,     # Exceeds SLA (1.0%)
        "backhaul_utilization_pct": 95.0,
        "throughput_dl_mbps": 8.0,  # Below SLA min (15 Mbps)
        "throughput_ul_mbps": 2.0,
        "prb_utilization_dl_pct": 40.0,
        "prb_utilization_ul_pct": 20.0,
        "connected_users": 20,
        "rsrp_dbm": -88.0,
        "sinr_db": 12.0,
        "cqi": 10,
        "rrc_success_rate_pct": 95.0,
        "erab_drop_rate_pct": 2.5
    }])

    enriched = enricher.enrich(sample_degraded)
    row = enriched.iloc[0]

    assert row["is_sla_compliant"] == False
    assert row["is_transport_bottleneck"] == True
