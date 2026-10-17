from typing import List, Dict, Any, Optional
import pandas as pd
from dataclasses import dataclass


@dataclass
class IncidentDiagnosis:
    incident_id: str
    cell_id: str
    timestamp: str
    severity: str
    root_cause_category: str
    confidence_score: float
    root_cause_summary: str
    recommended_action: str
    affected_users: int


class TelecomRCAEngine:
    """
    Expert Root Cause Analysis (RCA) engine for telecommunications networks.
    Applies deterministic domain rules based on 3GPP RAN performance, RF physics,
    and IP transport telemetry.
    """

    @classmethod
    def diagnose_row(cls, row: pd.Series) -> Optional[IncidentDiagnosis]:
        """Diagnoses a single anomalous telemetry record."""
        if not row.get("is_anomaly", False):
            return None

        cell_id = str(row["cell_id"])
        ts_str = str(row["timestamp"])
        severity = str(row.get("severity", "MINOR"))
        users = int(row.get("connected_users", 0))
        inc_id = f"INC-{cell_id}-{ts_str.replace(' ', 'T')}"

        # 1. Sleeping Cell / Silent Hardware Crash
        if row.get("is_sleeping_cell", False) or (users <= 1 and row["throughput_dl_mbps"] <= 0.1 and row["packet_loss_pct"] >= 50.0):
            return IncidentDiagnosis(
                incident_id=inc_id,
                cell_id=cell_id,
                timestamp=ts_str,
                severity="CRITICAL",
                root_cause_category="BASEBAND_HARDWARE_LOCKUP",
                confidence_score=0.98,
                root_cause_summary="Cell is nominally active but user-plane traffic has collapsed to zero with 100% loss. Baseband DSP or RF transceiver locked.",
                recommended_action="Execute automated remote power-cycle on Baseband Board (BBU/gNodeB). If unresponsive, dispatch Field Technician for board replacement.",
                affected_users=max(users, 50)
            )

        # 2. Backhaul Transport Bottleneck / Microwave Rain Fade
        if row.get("is_transport_bottleneck", False) or (row["backhaul_utilization_pct"] >= 92.0 and row["prb_utilization_dl_pct"] < 65.0):
            return IncidentDiagnosis(
                incident_id=inc_id,
                cell_id=cell_id,
                timestamp=ts_str,
                severity=severity,
                root_cause_category="BACKHAUL_TRANSPORT_BOTTLENECK",
                confidence_score=0.94,
                root_cause_summary=f"Radio access is uncongested (PRB {row['prb_utilization_dl_pct']:.1f}%), but transport backhaul reached {row['backhaul_utilization_pct']:.1f}% with high RTT ({row['latency_ms']:.1f}ms) and packet loss ({row['packet_loss_pct']:.1f}%).",
                recommended_action=f"Reroute IP/MPLS traffic to secondary transport ring or inspect Microwave link alignment/weather attenuation.",
                affected_users=users
            )

        # 3. Capacity Exhaustion / PRB Congestion
        if row.get("is_congested", False) and row["sinr_db"] >= 8.0:
            return IncidentDiagnosis(
                incident_id=inc_id,
                cell_id=cell_id,
                timestamp=ts_str,
                severity=severity,
                root_cause_category="RAN_CAPACITY_CONGESTION",
                confidence_score=0.91,
                root_cause_summary=f"Severe physical resource block saturation (DL PRB {row['prb_utilization_dl_pct']:.1f}%) driven by {users} concurrent subscribers. Radio channel quality is clear (SINR {row['sinr_db']:.1f} dB).",
                recommended_action="Activate dynamic Inter-Frequency Load Balancing (IFLB) to offload subscribers to overlapping carrier frequencies or split sector.",
                affected_users=users
            )

        # 4. Severe Co-Channel / External RF Interference
        if row.get("is_interfered", False) or (row["sinr_db"] <= 0.0 and row["rsrp_dbm"] >= -105.0):
            return IncidentDiagnosis(
                incident_id=inc_id,
                cell_id=cell_id,
                timestamp=ts_str,
                severity=severity,
                root_cause_category="RF_INTERFERENCE",
                confidence_score=0.88,
                root_cause_summary=f"Adequate received signal power (RSRP {row['rsrp_dbm']:.1f} dBm) but severely degraded SINR ({row['sinr_db']:.1f} dB), dropping CQI to {int(row['cqi'])}.",
                recommended_action="Audit neighboring cell PCI (Physical Cell Identity) planning for MOD3 collisions or adjust Remote Electrical Tilt (RET) by -2 degrees.",
                affected_users=users
            )

        # 5. Cell-Edge Weak Coverage
        if row["rsrp_dbm"] <= -118.0:
            return IncidentDiagnosis(
                incident_id=inc_id,
                cell_id=cell_id,
                timestamp=ts_str,
                severity=severity,
                root_cause_category="RADIO_COVERAGE_HOLE",
                confidence_score=0.85,
                root_cause_summary=f"Severe signal attenuation at cell fringe (RSRP {row['rsrp_dbm']:.1f} dBm), causing elevated drop rates ({row['erab_drop_rate_pct']:.1f}%).",
                recommended_action="Increase base station maximum transmit power by +2 dB or evaluate small-cell micro-site deployment.",
                affected_users=users
            )

        # Default Generic Anomaly
        return IncidentDiagnosis(
            incident_id=inc_id,
            cell_id=cell_id,
            timestamp=ts_str,
            severity=severity,
            root_cause_category="TRANSIENT_NETWORK_DEGRADATION",
            confidence_score=0.65,
            root_cause_summary=f"Elevated latency ({row['latency_ms']:.1f}ms) or packet loss ({row['packet_loss_pct']:.1f}%) exceeding baseline thresholds.",
            recommended_action="Monitor next 2 consecutive ROPs. If persistent, trigger active ICMP/TWAMP probe session.",
            affected_users=users
        )

    def diagnose_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Runs RCA diagnostics over an entire dataframe of telemetry records."""
        if df.empty:
            return pd.DataFrame()

        diagnoses: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            diag = self.diagnose_row(row)
            if diag:
                diagnoses.append(diag.__dict__)

        return pd.DataFrame(diagnoses)
