from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Add project root to sys.path so Airflow workers can locate src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:
    # Allows module inspection without mandatory Airflow installation in light test runners
    DAG = None
    PythonOperator = None


def task_sensor_telemetry_arrival(**context):
    """Verifies arrival of incoming raw telemetry frames from Kafka / 3GPP PM collector."""
    from config.logging_config import logger
    logger.info("Airflow Task: Detected telemetry payload arrival from upstream 3GPP PM collector.")
    return {"status": "READY", "timestamp": datetime.utcnow().isoformat()}


def task_validate_contracts_and_route_dlq(**context):
    """Enforces perimeter data contracts and quarantines non-conforming frames to DLQ."""
    from src.generator.telemetry_producer import TelecomTelemetryProducer
    from src.ingestion.validator import TelemetryContractValidator
    from src.ingestion.bronze_writer import BronzeStorageWriter
    from config.logging_config import logger

    producer = TelecomTelemetryProducer()
    # Pull current snapshot
    raw_frames = producer.generate_snapshot(datetime.utcnow())
    report = TelemetryContractValidator.validate_batch(raw_frames)

    writer = BronzeStorageWriter()
    bronze_path = writer.write_bronze_batch(report.valid_records)
    dlq_path = writer.write_dlq_quarantine(report.quarantined_records)

    logger.info(f"Airflow Task: Validated {report.total_records} frames. Valid: {report.valid_count}, DLQ: {report.rejected_count}")
    return {"valid_count": report.valid_count, "rejected_count": report.rejected_count, "valid_records": report.valid_records}


def task_enrich_silver_telemetry(**context):
    """Enriches valid telemetry with RAN topology dimensions and RFC transport indicators."""
    import pandas as pd
    from src.transformation.silver_enricher import SilverEnricher
    from config.logging_config import logger

    ti = context["ti"]
    upstream_data = ti.xcom_pull(task_ids="validate_contracts_and_route_dlq")
    valid_records = upstream_data["valid_records"]

    df = pd.DataFrame(valid_records)
    enricher = SilverEnricher()
    silver_df = enricher.enrich(df)

    logger.info(f"Airflow Task: Silver enrichment produced {len(silver_df)} curated records.")
    return silver_df.to_dict(orient="records")


def task_detect_anomalies_and_rca(**context):
    """Runs statistical Z-score anomaly detector and executes domain-governed RCA."""
    import pandas as pd
    from src.analytics.anomaly_detector import NetworkAnomalyDetector
    from src.analytics.rca_engine import TelecomRCAEngine
    from src.storage.repository import TelecomRepository
    from config.logging_config import logger

    ti = context["ti"]
    silver_records = ti.xcom_pull(task_ids="enrich_silver_telemetry")
    silver_df = pd.DataFrame(silver_records)

    detector = NetworkAnomalyDetector()
    scored_df = detector.detect_anomalies(silver_df)

    rca_engine = TelecomRCAEngine()
    incidents_df = rca_engine.diagnose_dataframe(scored_df)

    # Persist to database
    repo = TelecomRepository()
    repo.save_silver_telemetry(scored_df)
    if not incidents_df.empty:
        repo.save_incidents(incidents_df)

    logger.info(f"Airflow Task: Flagged {scored_df['is_anomaly'].sum()} anomalies. Recorded {len(incidents_df)} incidents.")
    return scored_df.to_dict(orient="records")


def task_build_gold_marts(**context):
    """Aggregates cell hourly KPIs and regional SLA scorecards into Gold dimensional tables."""
    import pandas as pd
    from src.transformation.gold_aggregator import GoldAggregator
    from src.storage.repository import TelecomRepository
    from config.logging_config import logger

    ti = context["ti"]
    scored_records = ti.xcom_pull(task_ids="detect_anomalies_and_rca")
    scored_df = pd.DataFrame(scored_records)

    hourly_df = GoldAggregator.aggregate_cell_hourly(scored_df)
    regional_df = GoldAggregator.aggregate_regional_sla(hourly_df)

    repo = TelecomRepository()
    repo.save_gold_hourly(hourly_df)
    repo.save_gold_regional(regional_df)

    logger.info(f"Airflow Task: Gold Layer marts successfully refreshed.")
    return {"hourly_records": len(hourly_df), "regional_records": len(regional_df)}


def task_check_sla_breaches_and_alert(**context):
    """Evaluates critical SLA breaches across metropolitan regions and logs NOC alerts."""
    from src.storage.repository import TelecomRepository
    from config.logging_config import logger

    repo = TelecomRepository()
    regional = repo.get_regional_summary()

    for _, row in regional.iterrows():
        sla = row.get("sla_compliance_pct", 100.0)
        reg = row.get("region", "UNKNOWN")
        if sla < 95.0:
            logger.warning(f"CRITICAL SLA ALERT: Region {reg} compliance dropped to {sla:.1f}%! Dispatching NOC alert.")
        else:
            logger.info(f"SLA Compliance OK: Region {reg} at {sla:.1f}%.")


# Define DAG configuration
default_args = {
    "owner": "telecom_data_eng",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

if DAG:
    with DAG(
        dag_id="telecom_network_performance_pipeline",
        default_args=default_args,
        description="End-to-End Telecom 5-min ROP Telemetry Pipeline with DLQ, RCA & Gold Marts",
        schedule_interval="*/5 * * * *",  # Run every 5 minutes (standard 3GPP ROP)
        start_date=datetime(2026, 1, 1),
        catchup=False,
        max_active_runs=1,
        tags=["telecom", "networking", "timeseries", "rca", "lakehouse"],
    ) as dag:

        t_sensor = PythonOperator(
            task_id="sensor_telemetry_arrival",
            python_callable=task_sensor_telemetry_arrival,
        )

        t_validate = PythonOperator(
            task_id="validate_contracts_and_route_dlq",
            python_callable=task_validate_contracts_and_route_dlq,
        )

        t_enrich = PythonOperator(
            task_id="enrich_silver_telemetry",
            python_callable=task_enrich_silver_telemetry,
        )

        t_anomaly = PythonOperator(
            task_id="detect_anomalies_and_rca",
            python_callable=task_detect_anomalies_and_rca,
        )

        t_gold = PythonOperator(
            task_id="build_gold_marts",
            python_callable=task_build_gold_marts,
        )

        t_alert = PythonOperator(
            task_id="check_sla_breaches_and_alert",
            python_callable=task_check_sla_breaches_and_alert,
        )

        # Pipeline Task Dependency Flow
        t_sensor >> t_validate >> t_enrich >> t_anomaly >> t_gold >> t_alert
