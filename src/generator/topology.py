import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class CellSector:
    cell_id: str
    site_id: str
    region: str
    subregion: str
    technology: str
    frequency_band_mhz: int
    bandwidth_mhz: float
    backhaul_type: str
    azimuth_deg: int
    latitude: float
    longitude: float
    nominal_capacity_mbps: float


def generate_network_topology() -> List[CellSector]:
    """
    Constructs a realistic cellular radio access network (RAN) topology
    spanning multiple metropolitan regions, subregions, and transport backhauls.
    """
    regions_config = [
        {
            "region": "CAI",
            "subregion": "EAST",
            "base_lat": 30.0750,
            "base_lon": 31.3500,
            "num_sites": 6,
            "backhauls": ["FIBER_10G", "FIBER_10G", "MICROWAVE_1G"]
        },
        {
            "region": "CAI",
            "subregion": "DNTN",
            "base_lat": 30.0444,
            "base_lon": 31.2357,
            "num_sites": 5,
            "backhauls": ["FIBER_10G", "FIBER_10G", "FIBER_10G"]
        },
        {
            "region": "GZA",
            "subregion": "OCT",
            "base_lat": 29.9700,
            "base_lon": 30.9500,
            "num_sites": 5,
            "backhauls": ["FIBER_10G", "MICROWAVE_1G", "MICROWAVE_1G"]
        },
        {
            "region": "ALX",
            "subregion": "COAST",
            "base_lat": 31.2001,
            "base_lon": 29.9187,
            "num_sites": 4,
            "backhauls": ["FIBER_10G", "MICROWAVE_1G"]
        }
    ]

    sectors: List[CellSector] = []

    for reg_cfg in regions_config:
        reg = reg_cfg["region"]
        subreg = reg_cfg["subregion"]
        base_lat = reg_cfg["base_lat"]
        base_lon = reg_cfg["base_lon"]
        backhauls = reg_cfg["backhauls"]

        for site_idx in range(1, reg_cfg["num_sites"] + 1):
            site_num_str = f"{site_idx:03d}"
            site_id = f"{reg}-{subreg}-{site_num_str}"
            
            # Alternate 4G LTE and 5G NR deployment
            is_5g = (site_idx % 2 == 0)
            technology = "5G_NR" if is_5g else "4G_LTE"
            freq_band = 3500 if is_5g else 1800
            bandwidth = 100.0 if is_5g else 20.0
            nominal_cap = 1200.0 if is_5g else 300.0
            backhaul = backhauls[(site_idx - 1) % len(backhauls)]

            # Slight geo offset for each tower
            site_lat = base_lat + (site_idx * 0.008) - 0.02
            site_lon = base_lon + (site_idx * 0.009) - 0.02

            # 3 Sectors per site (Tri-sector directional antennas: 0°, 120°, 240°)
            for sec_idx, azimuth in enumerate([0, 120, 240], start=1):
                cell_id = f"{site_id}-S{sec_idx}"
                sector = CellSector(
                    cell_id=cell_id,
                    site_id=site_id,
                    region=reg,
                    subregion=subreg,
                    technology=technology,
                    frequency_band_mhz=freq_band,
                    bandwidth_mhz=bandwidth,
                    backhaul_type=backhaul,
                    azimuth_deg=azimuth,
                    latitude=round(site_lat, 6),
                    longitude=round(site_lon, 6),
                    nominal_capacity_mbps=nominal_cap
                )
                sectors.append(sector)

    return sectors


def save_topology_to_file(filepath: Path) -> List[Dict[str, Any]]:
    """Persists topology metadata to JSON for join operations."""
    sectors = generate_network_topology()
    dict_list = [asdict(s) for s in sectors]
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(dict_list, f, indent=2)
    return dict_list


if __name__ == "__main__":
    from config.settings import settings
    topo = save_topology_to_file(settings.TOPOLOGY_DIR / "cell_topology.json")
    print(f"Generated {len(topo)} cell sectors across {len(set(c['site_id'] for c in topo))} sites.")
