import time
import sys
from pathlib import Path
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.generator.telemetry_producer import TelecomTelemetryProducer
from src.generator.topology import generate_network_topology
from src.ingestion.validator import TelemetryContractValidator
from src.ingestion.bronze_writer import BronzeStorageWriter
from src.transformation.silver_enricher import SilverEnricher
from src.analytics.anomaly_detector import NetworkAnomalyDetector
from src.analytics.rca_engine import TelecomRCAEngine
from src.transformation.gold_aggregator import GoldAggregator
from src.storage.db_engine import DatabaseEngine

console = Console()


def run_benchmark(batch_sizes=[500, 2000, 10000]):
    console.print("\n[bold cyan]===========================================================[/bold cyan]")
    console.print("[bold cyan] TELECOM DATA PIPELINE HARDWARE PERFORMANCE BENCHMARK       [/bold cyan]")
    console.print("[bold cyan]===========================================================[/bold cyan]\n")

    topo = generate_network_topology()
    producer = TelecomTelemetryProducer(topo)
    enricher = SilverEnricher(topo)
    detector = NetworkAnomalyDetector()
    rca = TelecomRCAEngine()

    table = Table(title="Measured Execution Benchmarks", show_header=True, header_style="bold green")
    table.add_column("Telemetry Records", justify="right")
    table.add_column("Contract Validation", justify="right")
    table.add_column("Silver Enrichment", justify="right")
    table.add_column("Anomaly & RCA", justify="right")
    table.add_column("Gold Aggregations", justify="right")
    table.add_column("Total Time", justify="right")
    table.add_column("Throughput (events/s)", justify="right", style="bold yellow")

    for size in batch_sizes:
        # Generate data
        periods = max(1, size // len(topo))
        raw_data = producer.generate_timeseries(datetime.now(), periods=periods)[:size]
        actual_size = len(raw_data)

        # 1. Validation
        t0 = time.perf_counter()
        report = TelemetryContractValidator.validate_batch(raw_data)
        t_val = time.perf_counter() - t0

        valid_df = pd.DataFrame(report.valid_records)

        # 2. Enrichment
        t0 = time.perf_counter()
        silver_df = enricher.enrich(valid_df)
        t_enrich = time.perf_counter() - t0

        # 3. Anomaly & RCA
        t0 = time.perf_counter()
        scored_df = detector.detect_anomalies(silver_df)
        incidents_df = rca.diagnose_dataframe(scored_df)
        t_rca = time.perf_counter() - t0

        # 4. Gold
        t0 = time.perf_counter()
        hourly_df = GoldAggregator.aggregate_cell_hourly(scored_df)
        regional_df = GoldAggregator.aggregate_regional_sla(hourly_df)
        t_gold = time.perf_counter() - t0

        total_time = t_val + t_enrich + t_rca + t_gold
        eps = actual_size / total_time if total_time > 0 else 0

        table.add_row(
            f"{actual_size:,}",
            f"{t_val:.3f} s",
            f"{t_enrich:.3f} s",
            f"{t_rca:.3f} s",
            f"{t_gold:.3f} s",
            f"{total_time:.3f} s",
            f"{eps:,.0f} evt/s"
        )

    console.print(table)
    console.print("\n[bold green][OK] Benchmark completed successfully.[/bold green]\n")


if __name__ == "__main__":
    run_benchmark()
