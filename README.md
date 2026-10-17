<div align="center">

# TelcoPulse | Telecom Network Performance Pipeline

**An end-to-end cellular network telemetry pipeline with perimeter contract enforcement, Medallion Lakehouse storage, automated Root Cause Analysis (RCA), and real-time NOC observability.**

<br />

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-Hypertables-FDB515?style=flat-square&logo=timescale&logoColor=black)](https://www.timescale.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1+-FFF000?style=flat-square&logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Apache Airflow](https://img.shields.io/badge/Airflow-2.8+-017CEE?style=flat-square&logo=apache-airflow&logoColor=white)](https://airflow.apache.org/)
[![Grafana](https://img.shields.io/badge/Grafana-10.0+-F46800?style=flat-square&logo=grafana&logoColor=white)](https://grafana.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

</div>

---

## Executive Summary

Cellular telecommunications networks operate under strict Service Level Agreements (SLAs: **99.9% uptime**, **< 50ms RTT latency**, **< 1.0% packet loss**). Telemetry is generated at continuous 5-minute Result Output Periods (ROPs) across thousands of base station sectors (4G LTE eNodeBs and 5G NR gNodeBs).

In production telecommunications:
1. **Network failures are multidimensional**: High latency and packet loss can stem from physical radio frequency interference (bad SINR), capacity exhaustion (Physical Resource Block PRB saturation), or transport backhaul congestion (Microwave link degradation). A naive dashboard cannot distinguish between these failure modes without physics-grounded correlation.
2. **Defensive Ingestion is mandatory**: Corrupted or out-of-bounds telemetry payloads (e.g., negative latency, impossible PRB percentages, malformed sector identifiers) must be isolated into a **Dead-Letter Queue (DLQ)** without halting the analytical stream.
3. **Storage must support both streaming and heavy analytical rollups**: The platform implements a **Medallion Architecture** using partitioned Parquet files (Bronze), schema-enforced relational tables with continuous indexing (Silver), and pre-computed dimensional rollups for NOC engineers (Gold).

---

## Architecture Overview

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      CELLULAR TELEMETRY PRODUCER                       │
 │  4G/5G Radio Cells (eNodeB/gNodeB) • IP Backhaul (Fiber 10G / MW 1G)   │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ 5-minute ROP Batches
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │               PERIMETER VALIDATION & CONTRACT ENFORCEMENT              │
 │          RFC 2544 / RFC 5357 Transport & 3GPP TS 32.401 Rules          │
 └───────────────────┬───────────────────────────────┬────────────────────┘
                     │ Valid Payload                 │ Corrupt / Out-of-Bounds
                     ▼                               ▼
       ┌───────────────────────────┐   ┌───────────────────────────┐
       │       BRONZE LAYER        │   │     DEAD-LETTER QUEUE     │
       │ Append-only Parquet Lake  │   │  Quarantined JSONL Stream │
       │ year=YYYY/month=MM/day=DD │   │   Error Codes & Auditing  │
       └─────────────┬─────────────┘   └───────────────────────────┘
                     │
                     ▼
       ┌───────────────────────────────────────────────────────────┐
       │                       SILVER LAYER                        │
       │ • RAN Topology Dimensions Join (Region, Azimuth, Media)   │
       │ • Shannon-Hartley Spectral Efficiency (bps/Hz)            │
       │ • Composite Network Quality Index (NQI: 0-100)            │
       │ • SLA Compliance Flags & Idempotent Deduplication         │
       └─────────────┬───────────────────────────────┬─────────────┘
                     │                               │
                     ▼                               ▼
       ┌───────────────────────────┐   ┌───────────────────────────┐
       │   STATISTICAL ANOMALY     │   │   EXPERT ROOT CAUSE       │
       │        DETECTOR           │   │    ANALYSIS (RCA)         │
       │ Rolling Z-Score & Latency │   │ Congestion vs Transport   │
       │ Deviation (95th / 99th)   │   │ Interference vs Sleeping  │
       └─────────────┬─────────────┘   └─────────────┬─────────────┘
                     │                               │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
       ┌───────────────────────────────────────────────────────────┐
       │                        GOLD LAYER                         │
       │ • gold_cell_hourly_kpi: Hourly rollups, P95 latency, BH   │
       │ • gold_regional_sla: Executive SLA compliance by region   │
       │ • gold_network_incidents: Diagnosed alerts & remediations │
       └─────────────────────────────┬─────────────────────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
       ┌───────────────────────────┐   ┌───────────────────────────┐
       │    STREAMLIT NOC CENTER   │   │     GRAFANA DASHBOARDS    │
       │ • Geographic Tower Map    │   │ • Real-time SLA Counters  │
       │ • Multi-Axis Time-Series  │   │ • Throughput Time-Series  │
       │ • Incident RCA Inspector  │   │ • Transport Delay & Loss  │
       │ • In-Browser SQL Console  │   │ • Incident Drill-Down     │
       └───────────────────────────┘   └───────────────────────────┘
```

---

## Telecommunications Domain Realism

### 1. Key Performance Indicators (KPIs) Governed by RF Physics

| Category | Metric | Standards Reference | Operational Threshold |
| :--- | :--- | :--- | :--- |
| **Transport** | `latency_ms` | RFC 2544 / TWAMP RFC 5357 | Nominal $< 35\text{ms}$, SLA Breach $> 50\text{ms}$ |
| **Transport** | `packet_loss_pct` | ITU-T Y.1540 / RFC 2544 | Nominal $< 0.1\%$, SLA Breach $> 1.0\%$ |
| **Transport** | `jitter_ms` | RFC 3393 Packet Delay Variation | Nominal $< 5\text{ms}$, Alert $> 20\text{ms}$ |
| **Radio Capacity** | `prb_utilization_dl_pct` | 3GPP TS 36.314 | Nominal $< 75\%$, Congestion Alarm $> 85\%$ |
| **Radio Quality** | `sinr_db` | Signal-to-Interference-plus-Noise | Good $> 12\text{ dB}$, Interference Alarm $< 0\text{ dB}$ |
| **Radio Signal** | `rsrp_dbm` | Reference Signal Received Power | Nominal $-85\text{ dBm}$, Cell Fringe $< -115\text{ dBm}$ |
| **Spectral Efficiency** | `bps_hz` | Shannon-Hartley Theorem proxy | Nominal $2.0 - 5.5\text{ bps/Hz}$ |
| **Accessibility** | `rrc_success_rate_pct` | 3GPP Radio Accessibility | SLA Target $\ge 98.0\%$ |
| **Retainability** | `erab_drop_rate_pct` | 3GPP Session Drop Rate | SLA Target $\le 1.5\%$ |

### 2. Domain-Governed Root Cause Analysis (RCA) Matrix

Telecommunications Network Operations Centers (NOC) require deterministic root cause identification rather than un-auditable guesses:

| Fault Classification | Primary Symptoms | Root Cause Mechanism | Prescriptive Operational Action |
| :--- | :--- | :--- | :--- |
| `BASEBAND_HARDWARE_LOCKUP` | Connected users $\le 1$, Throughput $= 0$, Loss $= 100\%$ | Baseband DSP lockup or RF transceiver freeze (*Sleeping Cell*) | Execute automated remote power-cycle on Baseband Board (BBU/gNodeB). |
| `BACKHAUL_TRANSPORT_BOTTLENECK` | Latency $> 100\text{ms}$, Loss $> 3\%$, Backhaul Util $\ge 90\%$, Radio PRB $< 65\%$ | Transport transmission link saturation or Microwave rain fade | Reroute IP/MPLS traffic to secondary transport ring or inspect Microwave alignment. |
| `RAN_CAPACITY_CONGESTION` | PRB DL $\ge 85\%$, High users, High latency, Clear SINR ($> 10\text{ dB}$) | Frequency resource block exhaustion due to subscriber demand | Activate dynamic Inter-Frequency Load Balancing (IFLB) to offload to adjacent bands. |
| `RF_INTERFERENCE` | Low SINR ($< 0\text{ dB}$), Strong RSRP ($-80\text{ dBm}$), CQI $\le 4$ | Co-channel or adjacent-channel inter-cell interference | Audit neighboring cell PCI (Physical Cell Identity) planning for MOD3 collisions. |
| `RADIO_COVERAGE_HOLE` | Severe attenuation (RSRP $< -115\text{ dBm}$), high drop rate | Building shadowing or distance from cell site | Increase transmission power by +2 dB or dispatch field team for micro-cell rollout. |

---

## Measured Hardware Benchmarks

The benchmarks below were measured on actual runs using the included benchmark suite (`scripts/benchmark.py`) on Windows 10 (AMD Ryzen 16 logical cores, Python 3.11):

| Telemetry Records Processed | Contract Validation | Silver Layer Enrichment | Anomaly & RCA Engine | Gold Mart Aggregations | Total Pipeline Latency | End-to-End Processing Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **480 records** | 0.007 s | 0.014 s | 0.013 s | 0.034 s | **0.068 s** | **7,089 events/sec** |
| **1,980 records** | 0.030 s | 0.010 s | 0.013 s | 0.034 s | **0.087 s** | **22,754 events/sec** |
| **9,960 records** | 0.158 s | 0.010 s | 0.012 s | 0.035 s | **0.215 s** | **46,343 events/sec** |

*To reproduce these benchmarks on your machine, execute `python scripts/benchmark.py`.*

---

## Repository Structure

```text
telecom-network-pipeline/
├── config/
│   ├── settings.py                # Environment-driven Pydantic V2 settings & SLA bounds
│   └── logging_config.py          # Structured telemetry logger with ISO timestamps
├── data/
│   ├── bronze/                    # Partitioned immutable Parquet (year=YYYY/month=MM/day=DD/)
│   ├── silver/                    # Cleaned & dimensionalized telemetry
│   ├── gold/                      # Hourly rollups, regional scorecards & incident marts
│   ├── dlq/                       # Dead-Letter Queue quarantined payloads (JSONL)
│   └── topology/                  # Cell sector topology metadata
├── sql/
│   ├── 01_init_postgres.sql       # PostgreSQL / TimescaleDB DDL, hypertables & indexes
│   ├── 02_gold_aggregates.sql     # Analytical views (Busy Hour, Backhaul comparison)
│   └── 03_telco_kpi_queries.sql   # Production queries (Top 10 worst cells, bottleneck triage)
├── src/
│   ├── contracts/
│   │   └── schemas.py             # Strict Pydantic contracts for 3GPP PM & transport frames
│   ├── generator/
│   │   ├── topology.py            # Generates realistic multi-region cellular topology
│   │   ├── diurnal_model.py       # Diurnal traffic curve (commute spikes, evening peak)
│   │   ├── anomaly_injector.py    # Injects telecom fault scenarios & contract corruptions
│   │   └── telemetry_producer.py  # Physics-governed telemetry generator
│   ├── ingestion/
│   │   ├── validator.py           # Perimeter validation & DLQ quarantine router
│   │   └── bronze_writer.py       # Partitioned columnar Parquet lakehouse writer
│   ├── transformation/
│   │   ├── silver_enricher.py     # Spectral efficiency, Composite NQI & SLA evaluation
│   │   └── gold_aggregator.py     # Hourly cell rollups, P95 latency & regional marts
│   ├── analytics/
│   │   ├── anomaly_detector.py    # Rolling Z-score & multivariate statistical detector
│   │   └── rca_engine.py          # Deterministic Root Cause Analysis (RCA) diagnostic engine
│   ├── storage/
│   │   ├── db_engine.py           # Dual storage engine (PostgreSQL/TimescaleDB + DuckDB)
│   │   └── repository.py          # Repository pattern for telemetry & incident queries
│   └── cli.py                     # Rich CLI to trigger pipeline stages & inspect metrics
├── dags/
│   ├── telecom_network_dag.py     # Production Apache Airflow DAG (5-min ROP schedule)
│   └── airflow_local_runner.py    # Standalone Airflow DAG simulation runner with mock XCom
├── dashboards/
│   ├── app.py                     # High-density Streamlit NOC Operations Console
│   ├── grafana_telecom_dashboard.json # Production Grafana dashboard definition
│   └── provisioning/              # Auto-provisioning configs for Grafana datasources & providers
├── docker/
│   ├── Dockerfile                 # Multi-stage production container
│   └── docker-compose.yml         # Full stack: TimescaleDB, Grafana & Pipeline runner
├── scripts/
│   ├── run_pipeline.py            # Executable one-line pipeline runner
│   ├── benchmark.py               # Hardware benchmarking suite
│   └── start_dashboard.ps1        # PowerShell script to launch Streamlit NOC
├── tests/
│   ├── test_contracts.py          # Contract boundary & DLQ isolation tests
│   ├── test_transformations.py    # Spectral efficiency & SLA calculation tests
│   ├── test_rca_engine.py         # Automated Root Cause Analysis classification tests
│   └── test_storage.py            # Storage engine & repository query tests
├── .gitignore
├── Makefile
├── requirements.txt
└── README.md
```

---

## Quickstart Guide

### 1. Local Python Environment (Zero Cloud / Zero Docker Needed)

The pipeline is built with a dual-storage adapter. You can run the entire platform locally using DuckDB and Streamlit with zero external server dependencies:

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/telecom-network-pipeline.git
cd telecom-network-pipeline

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run automated test suite (100% passing)
pytest tests -v

# 5. Execute the full end-to-end pipeline (generates 12 periods = 1 hour of telemetry)
python scripts/run_pipeline.py --periods 12

# 6. Launch the interactive NOC Operations Console
streamlit run dashboards/app.py
```

### 2. Production Docker Deployment (TimescaleDB + Grafana)

To run the complete production stack with TimescaleDB, Grafana, and automated pipeline execution:

```bash
# Start TimescaleDB, Grafana, and the Pipeline container
docker compose -f docker/docker-compose.yml up -d

# Open Grafana in your browser:
# URL: http://localhost:3000
# User: admin | Pass: admin
# Dashboard 'Telecom Network Performance & Observability' is automatically provisioned!
```

---

## Production SQL Analytical Queries

The included `sql/03_telco_kpi_queries.sql` contains production queries used by Tier-3 Network Optimization and Data Engineering teams:

### Query: Triage Transport Backhaul Bottlenecks
Identifies cells where high latency and packet loss originate from transport saturation rather than radio interference:

```sql
SELECT 
    cell_id,
    backhaul_type,
    timestamp,
    latency_ms,
    packet_loss_pct,
    backhaul_utilization_pct,
    prb_utilization_dl_pct,
    sinr_db
FROM silver_cell_telemetry
WHERE prb_utilization_dl_pct < 50.0 
  AND (latency_ms > 100.0 OR packet_loss_pct > 2.5 OR backhaul_utilization_pct > 90.0)
ORDER BY latency_ms DESC;
```

### Query: Identify Top 10 Worst Performing Cells by SLA Non-Compliance
```sql
SELECT 
    cell_id,
    site_id,
    region,
    technology,
    backhaul_type,
    ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
    ROUND(AVG(packet_loss_pct), 2) AS avg_packet_loss_pct,
    ROUND(AVG(throughput_dl_mbps), 1) AS avg_throughput_mbps,
    ROUND(AVG(CASE WHEN is_sla_compliant THEN 1.0 ELSE 0.0 END) * 100.0, 1) AS sla_compliance_pct,
    COUNT(CASE WHEN is_anomaly THEN 1 END) AS anomaly_events
FROM silver_cell_telemetry
GROUP BY cell_id, site_id, region, technology, backhaul_type
ORDER BY sla_compliance_pct ASC, avg_packet_loss_pct DESC
LIMIT 10;
```

---

## Engineering Design Decisions

1. **Why Medallion Architecture over Single Relational Table?**
   - **Bronze**: Guarantees raw, immutable auditability. If an anomaly detection rule changes or a new SLA metric is introduced, raw Parquet partitions can be replayed from the perimeter without data loss.
   - **Silver**: Decouples cleaning, deduplication, and topological enrichment from analytical aggregations.
   - **Gold**: Pre-computes hourly rollups and SLA scorecards so NOC dashboards load in $< 50\text{ms}$ rather than scanning millions of raw telemetry rows.

2. **Why DuckDB + PostgreSQL Dual Support?**
   - For enterprise production and high-concurrency dashboards, **PostgreSQL with TimescaleDB hypertables** offers robust timeseries indexing and Grafana connectivity.
   - For local development, continuous integration, and portfolio review, **DuckDB** provides zero-overhead, vectorized columnar execution directly from Parquet files without requiring developers to install or configure external database servers.

3. **Defensive Dead-Letter Queue (DLQ) vs Silent Record Dropping**:
   - Dropping corrupted frames silently blinds data engineers to upstream sensor calibration failures or firmware bugs. Quarantining bad payloads to `data/dlq/quarantined_records.jsonl` with error codes (`ERR_NEGATIVE_LATENCY`, `ERR_OUT_OF_BOUNDS_PRB`) provides immediate perimeter observability.

---

## Author & License

Built by **Ahmed Amr** as an open-source telecommunications and data engineering portfolio project.

Licensed under the [MIT License](LICENSE).
