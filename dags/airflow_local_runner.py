import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dags.telecom_network_dag import (
    task_sensor_telemetry_arrival,
    task_validate_contracts_and_route_dlq,
    task_enrich_silver_telemetry,
    task_detect_anomalies_and_rca,
    task_build_gold_marts,
    task_check_sla_breaches_and_alert
)
from config.logging_config import logger


class MockTaskInstance:
    """Simulates Airflow XCom pushing and pulling for local execution."""
    def __init__(self):
        self._xcom = {}

    def xcom_push(self, key, value):
        self._xcom[key] = value

    def xcom_pull(self, task_ids):
        return self._xcom.get(task_ids)


def run_local_dag_simulation():
    """
    Executes all tasks of telecom_network_dag sequentially with mock Airflow context.
    """
    logger.info("==================================================================")
    logger.info("STARTING LOCAL AIRFLOW DAG SIMULATION: telecom_network_performance")
    logger.info("==================================================================")

    ti = MockTaskInstance()
    context = {"ti": ti, "ts": datetime.utcnow().isoformat()}

    # Task 1: Sensor
    logger.info("--> Executing Task: sensor_telemetry_arrival")
    sensor_res = task_sensor_telemetry_arrival(**context)
    ti.xcom_push("sensor_telemetry_arrival", sensor_res)

    # Task 2: Validate Contracts & DLQ
    logger.info("--> Executing Task: validate_contracts_and_route_dlq")
    val_res = task_validate_contracts_and_route_dlq(**context)
    ti.xcom_push("validate_contracts_and_route_dlq", val_res)

    # Task 3: Silver Enrichment
    logger.info("--> Executing Task: enrich_silver_telemetry")
    enrich_res = task_enrich_silver_telemetry(**context)
    ti.xcom_push("enrich_silver_telemetry", enrich_res)

    # Task 4: Anomaly Detection & RCA
    logger.info("--> Executing Task: detect_anomalies_and_rca")
    anomaly_res = task_detect_anomalies_and_rca(**context)
    ti.xcom_push("detect_anomalies_and_rca", anomaly_res)

    # Task 5: Build Gold Marts
    logger.info("--> Executing Task: build_gold_marts")
    gold_res = task_build_gold_marts(**context)
    ti.xcom_push("build_gold_marts", gold_res)

    # Task 6: SLA Alerting
    logger.info("--> Executing Task: check_sla_breaches_and_alert")
    task_check_sla_breaches_and_alert(**context)

    logger.info("==================================================================")
    logger.info("AIRFLOW DAG SIMULATION COMPLETED SUCCESSFULLY!")
    logger.info("==================================================================")


if __name__ == "__main__":
    run_local_dag_simulation()
