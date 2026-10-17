import re
from datetime import datetime
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class RawTelemetryRecord(BaseModel):
    """
    3GPP Performance Management & IP Transport Telemetry Contract.
    Represents a 5-minute ROP (Result Output Period) measurement for a cellular sector.
    """
    timestamp: datetime
    cell_id: str = Field(..., description="Unique Cell Sector Identifier, e.g. CAI-EAST-014-S1")
    site_id: str = Field(..., description="Base Station / Tower Identifier, e.g. CAI-EAST-014")
    technology: Literal["4G_LTE", "5G_NR"]
    frequency_band_mhz: int = Field(..., description="Operating Carrier Frequency in MHz")
    bandwidth_mhz: float = Field(..., description="Allocated Channel Bandwidth in MHz")

    # IP Transport Performance (RFC 2544 / TWAMP RFC 5357)
    latency_ms: float = Field(..., ge=0.0, le=2000.0, description="Round-Trip Time to Core Gateway (ms)")
    jitter_ms: float = Field(..., ge=0.0, le=500.0, description="Packet Delay Variation (ms)")
    packet_loss_pct: float = Field(..., ge=0.0, le=100.0, description="Transport Packet Loss Rate (%)")
    backhaul_utilization_pct: float = Field(..., ge=0.0, le=100.0, description="Transport Link Utilization (%)")

    # Radio Access Network (RAN) Traffic & Capacity
    throughput_dl_mbps: float = Field(..., ge=0.0, le=5000.0, description="Downlink MAC/PDCP Throughput (Mbps)")
    throughput_ul_mbps: float = Field(..., ge=0.0, le=1000.0, description="Uplink MAC/PDCP Throughput (Mbps)")
    prb_utilization_dl_pct: float = Field(..., ge=0.0, le=100.0, description="Physical Resource Block DL Utilization (%)")
    prb_utilization_ul_pct: float = Field(..., ge=0.0, le=100.0, description="Physical Resource Block UL Utilization (%)")
    connected_users: int = Field(..., ge=0, le=5000, description="Active RRC Connected Subscribers")

    # Radio Channel Quality & Signal
    rsrp_dbm: float = Field(..., ge=-145.0, le=-40.0, description="Reference Signal Received Power (dBm)")
    sinr_db: float = Field(..., ge=-25.0, le=40.0, description="Signal to Interference-plus-Noise Ratio (dB)")
    cqi: int = Field(..., ge=1, le=15, description="Channel Quality Indicator (1-15)")

    # Reliability & Accessibility KPIs (3GPP TS 32.401)
    rrc_success_rate_pct: float = Field(..., ge=0.0, le=100.0, description="RRC Connection Setup Success Rate (%)")
    erab_drop_rate_pct: float = Field(..., ge=0.0, le=100.0, description="E-RAB / PDU Session Drop Rate (%)")

    @field_validator("cell_id")
    @classmethod
    def validate_cell_id_format(cls, v: str) -> str:
        # Standard telco pattern: REGION-SUBREGION-NUM-SECTOR (e.g. CAI-EAST-014-S1)
        pattern = r"^[A-Z]{3}-[A-Z0-9]+-[0-9]{3}-S[1-3]$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid Cell ID format: '{v}'. Must match pattern 'REGION-SUBREGION-NUM-S[1-3]'")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_not_future(cls, v: datetime) -> datetime:
        # Allow max 5 minutes clock skew, prevent future timestamps
        if v.timestamp() > datetime.now().timestamp() + 300:
            raise ValueError(f"Telemetry timestamp is in the future: {v}")
        return v


class DLQRecord(BaseModel):
    """
    Quarantined record routed to Dead-Letter Queue due to contract or schema violation.
    """
    quarantine_timestamp: datetime = Field(default_factory=datetime.utcnow)
    rejection_stage: str = Field(..., description="Pipeline stage where rejection occurred")
    error_code: str = Field(..., description="E.g., INVALID_SCHEMA, OUT_OF_BOUNDS, CORRUPT_PAYLOAD")
    error_message: str = Field(..., description="Detailed explanation of rejection")
    raw_payload: Dict[str, Any] = Field(..., description="Original raw payload that failed validation")


class EnrichedCellTelemetry(RawTelemetryRecord):
    """
    Silver Layer contract: Telemetry enriched with topological dimensions,
    geospatial data, and derived physical network indicators.
    """
    region: str
    subregion: str
    backhaul_type: Literal["FIBER_10G", "MICROWAVE_1G", "SATELLITE_BACKUP"]
    azimuth_deg: int
    latitude: float
    longitude: float

    # Derived Telecom Calculations
    spectral_efficiency_bps_hz: float = Field(..., description="Spectral Efficiency (Throughput DL / Bandwidth)")
    throughput_per_user_mbps: float = Field(..., description="Average downlink bandwidth per connected user")
    network_quality_index: float = Field(..., ge=0.0, le=100.0, description="Composite score of radio + transport quality")
    is_sla_compliant: bool = Field(..., description="Meets latency, packet loss, and throughput SLA")
