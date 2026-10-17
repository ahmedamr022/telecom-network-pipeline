import random
from typing import Dict, Any, Tuple


class TelecomAnomalyInjector:
    """
    Simulates real-world cellular and transport network fault conditions
    grounded in RF physics and telecommunications engineering principles.
    """

    @staticmethod
    def inject_capacity_congestion(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Symptom: PRB exhaustion, high subscriber concurrency, bufferbloat latency.
        Radio channel is clear (high SINR), but capacity limit is reached.
        """
        record["prb_utilization_dl_pct"] = round(random.uniform(88.0, 99.0), 2)
        record["prb_utilization_ul_pct"] = round(random.uniform(75.0, 92.0), 2)
        record["connected_users"] = int(record["connected_users"] * random.uniform(2.2, 3.5))
        # Throughput caps at sector hardware ceiling
        record["throughput_dl_mbps"] = round(min(record["throughput_dl_mbps"] * 1.2, 280.0), 2)
        # Latency increases due to base station MAC scheduler queueing delay
        record["latency_ms"] = round(random.uniform(75.0, 150.0), 2)
        record["jitter_ms"] = round(random.uniform(15.0, 35.0), 2)
        record["packet_loss_pct"] = round(random.uniform(1.2, 3.5), 2)
        return record

    @staticmethod
    def inject_radio_interference(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Symptom: Co-channel or adjacent-channel RF interference.
        RSRP is acceptable, but SINR collapses, forcing modulation fallback to QPSK.
        """
        record["sinr_db"] = round(random.uniform(-8.0, 2.0), 2)  # Severe interference
        record["cqi"] = random.randint(1, 4)                     # Lowest CQI modulation
        record["packet_loss_pct"] = round(random.uniform(6.0, 18.0), 2)
        record["throughput_dl_mbps"] = round(record["throughput_dl_mbps"] * random.uniform(0.15, 0.35), 2)
        record["erab_drop_rate_pct"] = round(random.uniform(4.0, 12.0), 2)
        record["rrc_success_rate_pct"] = round(random.uniform(78.0, 91.0), 2)
        return record

    @staticmethod
    def inject_backhaul_bottleneck(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Symptom: Transport link saturation or microwave fade.
        Radio interface is completely healthy, but IP transport degrades severely.
        """
        record["backhaul_utilization_pct"] = round(random.uniform(96.0, 100.0), 2)
        record["latency_ms"] = round(random.uniform(190.0, 480.0), 2)
        record["jitter_ms"] = round(random.uniform(45.0, 110.0), 2)
        record["packet_loss_pct"] = round(random.uniform(7.0, 22.0), 2)
        record["throughput_dl_mbps"] = round(record["throughput_dl_mbps"] * random.uniform(0.20, 0.40), 2)
        return record

    @staticmethod
    def inject_sleeping_cell(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Symptom: Baseband software lockup / silent failure.
        Cell is nominally registered as active, but stops processing user plane data.
        """
        record["connected_users"] = random.randint(0, 1)
        record["throughput_dl_mbps"] = 0.0
        record["throughput_ul_mbps"] = 0.0
        record["prb_utilization_dl_pct"] = 0.0
        record["prb_utilization_ul_pct"] = 0.0
        record["packet_loss_pct"] = 100.0
        record["erab_drop_rate_pct"] = 100.0
        return record

    @staticmethod
    def inject_corrupt_contract(record: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """
        Injects intentional contract/schema violations to verify DLQ quarantine.
        """
        corruption_type = random.choice([
            "NEGATIVE_LATENCY",
            "OUT_OF_BOUNDS_PRB",
            "INVALID_CELL_ID",
            "IMPOSSIBLE_SINR"
        ])
        corrupted = dict(record)

        if corruption_type == "NEGATIVE_LATENCY":
            corrupted["latency_ms"] = -25.5
        elif corruption_type == "OUT_OF_BOUNDS_PRB":
            corrupted["prb_utilization_dl_pct"] = 185.0
        elif corruption_type == "INVALID_CELL_ID":
            corrupted["cell_id"] = "MALFORMED_SITE_NAME_XYZ"
        elif corruption_type == "IMPOSSIBLE_SINR":
            corrupted["sinr_db"] = 999.0

        return corrupted, corruption_type
