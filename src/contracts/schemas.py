import re
import math
from datetime import datetime
from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator


class RawTelemetryRecord(BaseModel):
    """
    3GPP Performance Management & IP Transport Telemetry Contract (v1.2.0).
    Represents a discrete 5-minute ROP (Result Output Period) measurement for a cellular sector.
    """
    timestamp: datetime = Field(..., description="Measurement ROP boundary timestamp (UTC)")
    ingestion_timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Perimeter ingestion wall-clock timestamp")
    batch_id: Optional[str] = Field(default="batch-raw-000", description="Lineage micro-batch identifier")
    source_id: Optional[str] = Field(default="pm-collector-01", description="Upstream collector identifier")
    schema_version: Optional[str] = Field(default="v1.2.0", description="Data contract schema version")

    cell_id: str = Field(..., description="Unique Cell Sector Identifier, e.g. CAI-EAST-014-S1")
    site_id: str = Field(..., description="Base Station / Tower Identifier, e.g. CAI-EAST-014")
    technology: Literal["4G_LTE", "5G_NR"]
    frequency_band_mhz: int = Field(..., ge=400, le=40000, description="Operating Carrier Frequency in MHz")
    bandwidth_mhz: float = Field(..., ge=1.4, le=400.0, description="Allocated Channel Bandwidth in MHz")

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
    sinr_db: float = Field(..., ge=-25.0, le=45.0, description="Signal to Interference-plus-Noise Ratio (dB)")
    cqi: int = Field(..., ge=1, le=15, description="Channel Quality Indicator (1-15)")

    # Reliability & Accessibility KPIs (3GPP TS 32.401)
    rrc_success_rate_pct: float = Field(..., ge=0.0, le=100.0, description="RRC Connection Setup Success Rate (%)")
    erab_drop_rate_pct: float = Field(..., ge=0.0, le=100.0, description="E-RAB / PDU Session Drop Rate (%)")

    @field_validator("cell_id")
    @classmethod
    def validate_cell_id_format(cls, v: str) -> str:
        pattern = r"^[A-Z]{3}-[A-Z0-9]+-[0-9]{3}-S[1-3]$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid Cell ID format: '{v}'. Must match pattern 'REGION-SUBREGION-NUM-S[1-3]'")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_not_future(cls, v: datetime) -> datetime:
        if v.timestamp() > datetime.now().timestamp() + 300:
            raise ValueError(f"Telemetry timestamp is in the future: {v}")
        return v

    @field_validator("latency_ms", "jitter_ms", "packet_loss_pct", "throughput_dl_mbps", "prb_utilization_dl_pct", "sinr_db", "rsrp_dbm")
    @classmethod
    def validate_no_nans_or_infinities(cls, v: float, info) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"Field '{info.field_name}' cannot be NaN or Infinite (received: {v})")
        return v


class DLQRecord(BaseModel):
    """
    Quarantined record routed to Dead-Letter Queue due to contract or schema violation.
    Preserves rejection context, error code, and raw payload without data loss.
    """
    quarantine_timestamp: datetime = Field(default_factory=datetime.utcnow)
    rejection_stage: str = Field(..., description="Pipeline stage where rejection occurred")
    error_code: str = Field(..., description="E.g., ERR_NEGATIVE_LATENCY, ERR_OUT_OF_BOUNDS_PRB")
    error_message: str = Field(..., description="Detailed explanation of rejection")
    raw_payload: Dict[str, Any] = Field(..., description="Original raw payload that failed validation")


class EnrichedCellTelemetry(RawTelemetryRecord):
    """
    Silver Layer contract: Telemetry enriched with topological dimensions,
    geospatial data, and rigorous RF engineering indicators.
    """
    region: str
    subregion: str
    backhaul_type: Literal["FIBER_10G", "MICROWAVE_1G", "SATELLITE_BACKUP"]
    azimuth_deg: int
    latitude: float
    longitude: float

    # Explicitly differentiated efficiency metrics
    theoretical_spectral_efficiency_bps_hz: float = Field(..., description="Continuous Shannon-Hartley limit log2(1+10^(SINR/10))")
    estimated_radio_efficiency_bps_hz: float = Field(..., description="Discrete 3GPP Modulation efficiency based on CQI table")
    measured_spectral_efficiency_bps_hz: float = Field(..., description="Observed Throughput / Bandwidth (bps/Hz)")
    throughput_per_user_mbps: float = Field(..., description="Average downlink bandwidth per connected user")

    # Quality & SLA
    network_quality_index: float = Field(..., ge=0.0, le=100.0, description="Normalized composite operational score")
    is_sla_compliant: bool = Field(..., description="Meets all enterprise SLA criteria")


class IncidentRecord(BaseModel):
    """
    Incident Mart contract: Diagnosed operational fault with full audit trail,
    supporting evidence, alternative causes, and calibrated confidence score.
    """
    incident_id: str
    cell_id: str
    timestamp: datetime
    severity: Literal["CRITICAL", "MAJOR", "MINOR", "NORMAL"]
    suspected_cause: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list, description="Telemetry conditions confirming the diagnosis")
    alternative_causes: List[str] = Field(default_factory=list, description="Other plausible causes evaluated")
    root_cause_summary: str
    recommended_action: str
    affected_users: int
