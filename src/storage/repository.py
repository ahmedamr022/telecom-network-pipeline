from typing import List, Dict, Any, Optional
import pandas as pd
from src.storage.db_engine import DatabaseEngine, db_engine
from config.logging_config import logger


class TelecomRepository:
    """
    Data Access Layer (Repository Pattern) providing high-level abstraction
    for querying telemetry, aggregated marts, and network incident logs.
    """

    def __init__(self, engine: DatabaseEngine = None):
        self.engine = engine or db_engine

    def save_dim_cells(self, df: pd.DataFrame) -> None:
        """Stores static cell site topology dimensions."""
        self.engine.write_dataframe("dim_cells", df, if_exists="replace")

    def save_silver_telemetry(self, df: pd.DataFrame) -> None:
        """Appends cleaned, enriched 5-min telemetry to Silver store."""
        self.engine.write_dataframe("silver_cell_telemetry", df, if_exists="append")

    def save_gold_hourly(self, df: pd.DataFrame) -> None:
        """Appends hourly cell KPI rollups to Gold store."""
        self.engine.write_dataframe("gold_cell_hourly_kpi", df, if_exists="append")

    def save_gold_regional(self, df: pd.DataFrame) -> None:
        """Appends regional SLA scorecards to Gold store."""
        self.engine.write_dataframe("gold_regional_sla", df, if_exists="append")

    def save_incidents(self, df: pd.DataFrame) -> None:
        """Appends detected incidents & RCA diagnoses to Incident Mart."""
        self.engine.write_dataframe("gold_network_incidents", df, if_exists="append")

    def get_worst_performing_cells(self, limit: int = 10) -> pd.DataFrame:
        """
        Retrieves top degraded cells based on lowest SLA compliance and high packet loss.
        """
        sql = f"""
            SELECT 
                cell_id,
                region,
                subregion,
                technology,
                backhaul_type,
                ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
                ROUND(AVG(packet_loss_pct), 2) AS avg_packet_loss_pct,
                ROUND(AVG(throughput_dl_mbps), 1) AS avg_throughput_dl_mbps,
                ROUND(AVG(prb_utilization_dl_pct), 1) AS avg_prb_dl_pct,
                ROUND(AVG(network_quality_index), 1) AS avg_nqi,
                ROUND(AVG(CASE WHEN is_sla_compliant THEN 1.0 ELSE 0.0 END) * 100.0, 1) AS sla_compliance_pct,
                SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) AS anomaly_count
            FROM silver_cell_telemetry
            GROUP BY cell_id, region, subregion, technology, backhaul_type
            ORDER BY sla_compliance_pct ASC, avg_packet_loss_pct DESC
            LIMIT {limit};
        """
        try:
            return self.engine.query(sql)
        except Exception as e:
            logger.error(f"Error fetching worst performing cells: {e}")
            return pd.DataFrame()

    def get_recent_incidents(self, limit: int = 25) -> pd.DataFrame:
        """Retrieves recent network incidents with root cause analysis."""
        sql = f"""
            SELECT 
                incident_id,
                cell_id,
                timestamp,
                severity,
                root_cause_category,
                ROUND(confidence_score * 100, 0) AS confidence_pct,
                root_cause_summary,
                recommended_action,
                affected_users
            FROM gold_network_incidents
            ORDER BY timestamp DESC
            LIMIT {limit};
        """
        try:
            return self.engine.query(sql)
        except Exception as e:
            logger.error(f"Error fetching recent incidents: {e}")
            return pd.DataFrame()

    def get_regional_summary(self) -> pd.DataFrame:
        """Summarizes performance and health indicators by geographic region."""
        sql = """
            SELECT 
                region,
                COUNT(DISTINCT cell_id) AS monitored_cells,
                ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
                ROUND(AVG(packet_loss_pct), 2) AS avg_packet_loss_pct,
                ROUND(AVG(throughput_dl_mbps), 1) AS avg_throughput_mbps,
                ROUND(AVG(prb_utilization_dl_pct), 1) AS avg_prb_dl_pct,
                ROUND(AVG(network_quality_index), 1) AS avg_nqi,
                ROUND(AVG(CASE WHEN is_sla_compliant THEN 1.0 ELSE 0.0 END) * 100.0, 1) AS sla_compliance_pct
            FROM silver_cell_telemetry
            GROUP BY region
            ORDER BY sla_compliance_pct ASC;
        """
        try:
            return self.engine.query(sql)
        except Exception as e:
            logger.error(f"Error fetching regional summary: {e}")
            return pd.DataFrame()

    def get_cell_timeseries(self, cell_id: str) -> pd.DataFrame:
        """Retrieves time-series telemetry for a specific cell."""
        sql = f"""
            SELECT 
                timestamp,
                latency_ms,
                jitter_ms,
                packet_loss_pct,
                throughput_dl_mbps,
                prb_utilization_dl_pct,
                connected_users,
                sinr_db,
                rsrp_dbm,
                network_quality_index,
                is_sla_compliant,
                is_anomaly
            FROM silver_cell_telemetry
            WHERE cell_id = '{cell_id}'
            ORDER BY timestamp ASC;
        """
        try:
            return self.engine.query(sql)
        except Exception as e:
            logger.error(f"Error fetching cell timeseries: {e}")
            return pd.DataFrame()
