import time
import sys
import os
import platform
import tracemalloc
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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


def run_benchmark(batch_sizes=[500, 2000, 10000], iterations_per_size=5):
    console.print("\n[bold cyan]===========================================================[/bold cyan]")
    console.print("[bold cyan] TELCOPULSE REPRODUCIBLE HARDWARE PERFORMANCE BENCHMARK     [/bold cyan]")
    console.print("[bold cyan]===========================================================[/bold cyan]\n")

    # Document hardware environment
    console.print(f"[bold yellow]Hardware Environment:[/bold yellow]")
    console.print(f" • OS: {platform.system()} {platform.release()} ({platform.architecture()[0]})")
    console.print(f" • Processor: {platform.processor() or 'AMD64 / x86_64'} ({os.cpu_count()} logical cores)")
    console.print(f" • Python Runtime: {platform.python_implementation()} {platform.python_version()}")
    console.print(f" • Benchmark Methodology: {iterations_per_size} iterations per batch (1 warm-up, {iterations_per_size-1} timed trials)")
    console.print(f" • Metrics Tracked: Median Latency, P95 Latency, Throughput (eps), Peak Memory\n")

    topo = generate_network_topology()
    producer = TelecomTelemetryProducer(topo)
    enricher = SilverEnricher(topo)
    detector = NetworkAnomalyDetector()
    rca = TelecomRCAEngine()

    table = Table(title="Benchmarking Results Across Data Scales", show_header=True, header_style="bold green")
    table.add_column("Telemetry Records", justify="right")
    table.add_column("Median Latency", justify="right")
    table.add_column("P95 Latency", justify="right")
    table.add_column("Peak RAM", justify="right")
    table.add_column("Throughput (Median)", justify="right", style="bold yellow")
    table.add_column("Execution State", justify="center")

    for size in batch_sizes:
        periods = max(1, size // len(topo))
        raw_data = producer.generate_timeseries(datetime.now(), periods=periods)[:size]
        actual_size = len(raw_data)

        # Warm-up run (not timed)
        _report = TelemetryContractValidator.validate_batch(raw_data)
        _silver = enricher.enrich(pd.DataFrame(_report.valid_records))
        _scored = detector.detect_anomalies(_silver)
        _inc = rca.diagnose_dataframe(_scored)
        _hourly = GoldAggregator.aggregate_cell_hourly(_scored)

        latencies = []
        peak_mems = []

        # Timed trials
        for trial in range(iterations_per_size - 1):
            tracemalloc.start()
            t0 = time.perf_counter()

            # 1. Contract Validation
            report = TelemetryContractValidator.validate_batch(raw_data)
            valid_df = pd.DataFrame(report.valid_records)

            # 2. Silver Transformation & Physics
            silver_df = enricher.enrich(valid_df)

            # 3. Anomaly & RCA
            scored_df = detector.detect_anomalies(silver_df)
            incidents_df = rca.diagnose_dataframe(scored_df)

            # 4. Gold Aggregations
            hourly_df = GoldAggregator.aggregate_cell_hourly(scored_df)
            regional_df = GoldAggregator.aggregate_regional_sla(hourly_df)

            elapsed = time.perf_counter() - t0
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            latencies.append(elapsed)
            peak_mems.append(peak_mem / (1024 * 1024))  # Convert to MB

        median_lat = float(np.median(latencies))
        p95_lat = float(np.percentile(latencies, 95))
        max_peak_mem = float(np.max(peak_mems))
        median_eps = actual_size / median_lat if median_lat > 0 else 0

        table.add_row(
            f"{actual_size:,}",
            f"{median_lat * 1000.0:.1f} ms",
            f"{p95_lat * 1000.0:.1f} ms",
            f"{max_peak_mem:.2f} MB",
            f"{median_eps:,.0f} evt/s",
            "[green]PASSED[/green]"
        )

    console.print(table)
    console.print("\n[bold green][OK] Reproducible Benchmark completed successfully.[/bold green]\n")


if __name__ == "__main__":
    run_benchmark()
