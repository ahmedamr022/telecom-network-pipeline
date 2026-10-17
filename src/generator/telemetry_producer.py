import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from dataclasses import asdict

from src.generator.topology import generate_network_topology, CellSector
from src.generator.diurnal_model import get_diurnal_load_factor
from src.generator.anomaly_injector import TelecomAnomalyInjector


class TelecomTelemetryProducer:
    """
    High-fidelity cellular & IP transport telemetry generator.
    Simulates realistic 3GPP PM & TWAMP performance data governed by RF physics.
    """

    def __init__(self, sectors: List[CellSector] = None):
        self.sectors = sectors or generate_network_topology()
        self.injector = TelecomAnomalyInjector()

    def _generate_sector_frame(self, sector: CellSector, timestamp: datetime) -> Dict[str, Any]:
        """Generates a nominal baseline measurement frame for a single cell sector."""
        is_downtown = sector.subregion in ("DNTN", "EAST")
        load_factor = get_diurnal_load_factor(timestamp, is_business_district=is_downtown)

        # 1. Radio Frequency Channel Quality
        # RSRP varies between -115 dBm (cell edge) to -70 dBm (near tower)
        rsrp = round(random.normalvariate(-88.0, 8.0), 1)
        rsrp = max(-130.0, min(-55.0, rsrp))

        # SINR depends on RSRP and random co-channel interference
        base_sinr = (rsrp + 110.0) * 0.4 + random.normalvariate(8.0, 3.5)
        sinr = round(max(-10.0, min(32.0, base_sinr)), 1)

        # Channel Quality Indicator (CQI 1-15) mapped directly from SINR
        if sinr < -3:
            cqi = 1
        elif sinr < 0:
            cqi = 2
        elif sinr < 3:
            cqi = 4
        elif sinr < 7:
            cqi = 7
        elif sinr < 12:
            cqi = 10
        elif sinr < 18:
            cqi = 12
        else:
            cqi = 15

        # 2. Capacity & Physical Resource Block (PRB) Utilization
        # Peak users scale with diurnal factor and technology
        user_scale = 350 if sector.technology == "5G_NR" else 140
        users = int(max(4, random.normalvariate(user_scale * load_factor, 12.0)))

        prb_dl = round(min(98.0, max(5.0, (users / user_scale) * 85.0 + random.normalvariate(0, 4.0))), 1)
        prb_ul = round(min(95.0, max(4.0, prb_dl * 0.65 + random.normalvariate(0, 3.0))), 1)

        # 3. Throughput (Shannon-Hartley & Modulation Efficiency)
        # Spectral efficiency approx: log2(1 + 10^(SINR/10)) scaled by PRB
        spec_eff = max(0.4, min(7.5, math.log2(1.0 + max(0.1, 10.0 ** (sinr / 10.0)))))
        nominal_max_throughput = sector.bandwidth_mhz * spec_eff * (1.8 if sector.technology == "5G_NR" else 0.85)
        
        throughput_dl = round(max(2.0, (prb_dl / 100.0) * nominal_max_throughput + random.normalvariate(0, 3.0)), 2)
        throughput_ul = round(max(0.8, throughput_dl * 0.28 + random.normalvariate(0, 1.0)), 2)

        # 4. IP Transport & Backhaul Performance
        is_fiber = sector.backhaul_type == "FIBER_10G"
        base_latency = 12.0 if is_fiber else 32.0
        latency_noise = random.normalvariate(3.0, 1.5) if is_fiber else random.normalvariate(8.0, 3.5)
        latency = round(max(5.0, base_latency + latency_noise + (prb_dl * 0.15)), 2)

        jitter = round(max(0.5, (1.8 if is_fiber else 6.5) + random.normalvariate(0.5, 0.4)), 2)
        packet_loss = round(max(0.01, (0.05 if is_fiber else 0.35) + random.normalvariate(0.02, 0.05)), 2)

        # Backhaul utilization tracks throughput
        backhaul_util = round(min(95.0, max(5.0, (throughput_dl / sector.nominal_capacity_mbps) * 85.0)), 1)

        # 5. Accessibility & Drops (3GPP KPIs)
        rrc_success = round(max(92.0, min(100.0, 99.4 - (0.5 if sinr < 0 else 0) - random.uniform(0, 0.4))), 2)
        erab_drop = round(max(0.01, min(8.0, 0.15 + (1.2 if sinr < 0 else 0) + random.uniform(0, 0.2))), 2)

        return {
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "cell_id": sector.cell_id,
            "site_id": sector.site_id,
            "technology": sector.technology,
            "frequency_band_mhz": sector.frequency_band_mhz,
            "bandwidth_mhz": sector.bandwidth_mhz,
            "latency_ms": latency,
            "jitter_ms": jitter,
            "packet_loss_pct": packet_loss,
            "backhaul_utilization_pct": backhaul_util,
            "throughput_dl_mbps": throughput_dl,
            "throughput_ul_mbps": throughput_ul,
            "prb_utilization_dl_pct": prb_dl,
            "prb_utilization_ul_pct": prb_ul,
            "connected_users": users,
            "rsrp_dbm": rsrp,
            "sinr_db": sinr,
            "cqi": cqi,
            "rrc_success_rate_pct": rrc_success,
            "erab_drop_rate_pct": erab_drop,
        }

    def generate_snapshot(
        self,
        timestamp: datetime,
        anomaly_ratio: float = 0.05,
        corruption_ratio: float = 0.01
    ) -> List[Dict[str, Any]]:
        """
        Generates telemetry records for all network sectors at a given timestamp,
        injecting realistic anomalies and corrupted payloads for testing.
        """
        records: List[Dict[str, Any]] = []

        for sector in self.sectors:
            frame = self._generate_sector_frame(sector, timestamp)

            # Injected anomalies for specific cells
            rand_val = random.random()
            if rand_val < anomaly_ratio:
                # Randomly pick an operational anomaly
                anomaly_type = random.choice(["CONGESTION", "INTERFERENCE", "BACKHAUL", "SLEEPING"])
                if anomaly_type == "CONGESTION":
                    frame = self.injector.inject_capacity_congestion(frame)
                elif anomaly_type == "INTERFERENCE":
                    frame = self.injector.inject_radio_interference(frame)
                elif anomaly_type == "BACKHAUL":
                    frame = self.injector.inject_backhaul_bottleneck(frame)
                elif anomaly_type == "SLEEPING":
                    frame = self.injector.inject_sleeping_cell(frame)

            # Contract corruption for Dead-Letter Queue testing
            if random.random() < corruption_ratio:
                frame, _ = self.injector.inject_corrupt_contract(frame)

            records.append(frame)

        return records

    def generate_timeseries(
        self,
        start_time: datetime,
        periods: int = 24,
        interval_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """Generates continuous time-series ROP telemetry batches."""
        all_records: List[Dict[str, Any]] = []
        for i in range(periods):
            dt = start_time + timedelta(minutes=i * interval_minutes)
            snapshot = self.generate_snapshot(dt)
            all_records.extend(snapshot)
        return all_records
