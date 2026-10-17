import argparse
import sys
from datetime import datetime, timedelta

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table

from config.settings import settings
from config.logging_config import logger
from src.generator.topology import save_topology_to_file, generate_network_topology
from src.generator.telemetry_producer import TelecomTelemetryProducer
from src.ingestion.validator import TelemetryContractValidator
from src.ingestion.bronze_writer import BronzeStorageWriter
from src.transformation.silver_enricher import SilverEnricher
from src.analytics.anomaly_detector import NetworkAnomalyDetector
from src.analytics.rca_engine import TelecomRCAEngine
from src.transformation.gold_aggregator import GoldAggregator
from src.storage.repository import TelecomRepository
import pandas as pd

console = Console()


def run_pipeline(periods: int = 12, anomaly_ratio: float = 0.06):
    """
    Executes the complete End-to-End Telecom Network Data Pipeline:
    Generator -> Perimeter Validation & DLQ -> Bronze Lakehouse -> Silver Enrichment
    -> Statistical Anomaly Detection & RCA Engine -> Gold Marts -> Storage Engine.
    """
    console.print("\n[bold cyan]===========================================================[/bold cyan]")
    console.print("[bold cyan] TELECOM NETWORK PERFORMANCE DATA PIPELINE & OBSERVABILITY [/bold cyan]")
    console.print("[bold cyan]===========================================================[/bold cyan]\n")

    repo = TelecomRepository()

    # Step 1: Topology
    with console.status("[yellow]1. Loading & Verifying Network Topology...[/yellow]"):
        topo_path = settings.TOPOLOGY_DIR / "cell_topology.json"
        topo_sectors = generate_network_topology()
        save_topology_to_file(topo_path)
        dim_df = pd.DataFrame([s.__dict__ for s in topo_sectors])
        repo.save_dim_cells(dim_df)
    console.print(f"[green][OK] Topology initialized:[/green] {len(topo_sectors)} sectors across {dim_df['site_id'].nunique()} sites.")

    # Step 2: Telemetry Generation
    producer = TelecomTelemetryProducer(topo_sectors)
    start_time = datetime.now() - timedelta(minutes=periods * 5)
    with console.status(f"[yellow]2. Generating {periods} ROP periods (5-min telemetry snapshots)...[/yellow]"):
        raw_frames = producer.generate_timeseries(start_time, periods=periods, interval_minutes=5)
    console.print(f"[green][OK] Telemetry generated:[/green] {len(raw_frames)} raw measurement frames.")

    # Step 3: Contract Validation & DLQ
    with console.status("[yellow]3. Validating Perimeter Data Contracts...[/yellow]"):
        report = TelemetryContractValidator.validate_batch(raw_frames)
        bronze_writer = BronzeStorageWriter()
        bronze_path = bronze_writer.write_bronze_batch(report.valid_records)
        dlq_path = bronze_writer.write_dlq_quarantine(report.quarantined_records)
    console.print(f"[green][OK] Ingestion Contract Validation:[/green] {report.valid_count} valid ({report.validity_rate_pct:.1f}%), {report.rejected_count} quarantined to DLQ.")

    # Step 4: Silver Enrichment
    with console.status("[yellow]4. Performing Silver Enrichment & RFC Calculations...[/yellow]"):
        valid_df = pd.DataFrame(report.valid_records)
        enricher = SilverEnricher(topo_sectors)
        silver_df = enricher.enrich(valid_df)
    console.print(f"[green][OK] Silver Enrichment:[/green] Joined dimensions, computed Spectral Efficiency & Composite NQI.")

    # Step 5: Statistical Anomaly Detection & RCA
    with console.status("[yellow]5. Running Time-Series Anomaly Detector & Root Cause Analysis (RCA)...[/yellow]"):
        detector = NetworkAnomalyDetector()
        scored_df = detector.detect_anomalies(silver_df)
        rca_engine = TelecomRCAEngine()
        incidents_df = rca_engine.diagnose_dataframe(scored_df)
        
        # Persist to Silver and Incident stores
        repo.save_silver_telemetry(scored_df)
        if not incidents_df.empty:
            repo.save_incidents(incidents_df)
    console.print(f"[green][OK] Anomaly Detection & RCA:[/green] Flagged {scored_df['is_anomaly'].sum()} anomalies, generated {len(incidents_df)} diagnostic root causes.")

    # Step 6: Gold Layer Aggregations
    with console.status("[yellow]6. Computing Gold Hourly Rollups & Regional Scorecards...[/yellow]"):
        hourly_df = GoldAggregator.aggregate_cell_hourly(scored_df)
        regional_df = GoldAggregator.aggregate_regional_sla(hourly_df)
        
        repo.save_gold_hourly(hourly_df)
        repo.save_gold_regional(regional_df)
    console.print(f"[green][OK] Gold Marts Updated:[/green] {len(hourly_df)} hourly cell rollups, {len(regional_df)} regional scorecards.")

    # Display KPI Summary Table
    console.print("\n[bold green]Network Regional Performance Summary:[/bold green]")
    summary_df = repo.get_regional_summary()
    if not summary_df.empty:
        table = Table(title="Regional SLA & Transport Performance", show_header=True, header_style="bold magenta")
        for col in summary_df.columns:
            table.add_column(col.replace("_", " ").title())
        for _, row in summary_df.iterrows():
            table.add_row(*[str(val) for val in row.values])
        console.print(table)

    # Display Recent Incidents Table
    incidents_sample = repo.get_recent_incidents(limit=5)
    if not incidents_sample.empty:
        console.print("\n[bold red]Recent Network Incidents & Root Causes:[/bold red]")
        inc_table = Table(title="Active Incidents (RCA Feed)", show_header=True, header_style="bold red")
        inc_table.add_column("Cell ID", style="cyan")
        inc_table.add_column("Severity", style="bold")
        inc_table.add_column("Root Cause", style="yellow")
        inc_table.add_column("Confidence", justify="right")
        inc_table.add_column("Recommended Action")
        for _, inc in incidents_sample.iterrows():
            inc_table.add_row(
                str(inc["cell_id"]),
                str(inc["severity"]),
                str(inc["root_cause_category"]),
                f"{inc['confidence_pct']}%",
                str(inc["recommended_action"])[:50] + "..."
            )
        console.print(inc_table)

    console.print("\n[bold green] Pipeline executed successfully![/bold green]\n")


def main():
    # If options like --periods are provided without explicit 'run' subcommand, inject 'run'
    if len(sys.argv) > 1 and sys.argv[1] not in ["run", "worst-cells", "incidents", "-h", "--help"]:
        sys.argv.insert(1, "run")

    parser = argparse.ArgumentParser(description="Telecom Network Performance Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", help="Pipeline commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute complete ETL & Analytics Pipeline")
    run_parser.add_argument("--periods", type=int, default=12, help="Number of 5-min ROP periods to process (default 12 = 1 hr)")
    run_parser.add_argument("--anomaly-rate", type=float, default=0.06, help="Synthetic anomaly injection probability (default 0.06)")

    # Command: worst-cells
    subparsers.add_parser("worst-cells", help="List top 10 degraded cells")

    # Command: incidents
    subparsers.add_parser("incidents", help="List recent network incidents with RCA")

    args = parser.parse_args()

    if args.command == "run" or args.command is None:
        periods = getattr(args, "periods", 12)
        anomaly_rate = getattr(args, "anomaly_rate", 0.06)
        run_pipeline(periods=periods, anomaly_ratio=anomaly_rate)
    elif args.command == "worst-cells":
        repo = TelecomRepository()
        df = repo.get_worst_performing_cells(10)
        print(df.to_string(index=False))
    elif args.command == "incidents":
        repo = TelecomRepository()
        df = repo.get_recent_incidents(15)
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
