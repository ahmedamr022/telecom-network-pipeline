<div align="center">

# TelcoPulse | Telecom Network Performance Pipeline

**An end-to-end cellular network telemetry pipeline with perimeter contract enforcement, Medallion Lakehouse storage, multi-evidence Root Cause Analysis (RCA), and real-time NOC observability.**

<br />

[![CI Pipeline](https://github.com/ahmedamr022/telecom-network-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmedamr022/telecom-network-pipeline/actions)
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
2. **Defensive Ingestion is mandatory**: Corrupted, out-of-bounds, or NaN/Inf telemetry payloads (negative latency, impossible PRB percentages, malformed sector identifiers) must be isolated into a **Dead-Letter Queue (DLQ)** without halting the analytical stream.
3. **Storage must guarantee Idempotency**: Re-processing overlapping batches or recovering from interrupted runs must never multiply rows. Upsert logic on `(cell_id, timestamp)` guarantees strict state consistency.

> [!NOTE]
> **Standards & Data Catalog**: For detailed formula derivations and RFC mapping, refer to:
> - [`docs/standards_mapping.md`](docs/standards_mapping.md) — 3GPP TS 32.401, RFC 2544, RFC 3393 implementation scopes.
> - [`docs/data_dictionary.md`](docs/data_dictionary.md) — Complete metric catalog, units, P95 derivation, and NQI formulation.

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
       │ • Shannon Theoretical vs. 3GPP Discrete Modulation (MCS)  │
       │ • Composite Network Quality Index (NQI: 0-100)            │
       │ • Strict Upsert Idempotency on (cell_id, timestamp)       │
       └─────────────┬───────────────────────────────┬─────────────┘
                     │                               │
                     ▼                               ▼
       ┌───────────────────────────┐   ┌───────────────────────────┐
       │   STATISTICAL ANOMALY     │   │   MULTI-EVIDENCE ROOT     │
       │        DETECTOR           │   │   CAUSE ANALYSIS (RCA)    │
       │ Rolling Z-Score & Latency │   │ Evidence Chains, Calib.   │
       │ Deviation (95th / 99th)   │   │ Confidence, Alternatives  │
       └─────────────┬─────────────┘   └─────────────┬─────────────┘
                     │                               │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
       ┌───────────────────────────────────────────────────────────┐
       │                        GOLD LAYER                         │
       │ • gold_cell_hourly_kpi: Hourly rollups, empirical P95, BH │
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
       │ • Read-Only SQL Console   │   │ • Incident Drill-Down     │
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
| **Shannon Efficiency** | `theoretical_spectral_efficiency` | Continuous limit: $\log_2(1+10^{\text{SINR}/10})$ | Theoretical upper bound ($0.4 - 7.5\text{ bps/Hz}$) |
| **Modulation Efficiency** | `estimated_radio_efficiency` | 3GPP TS 36.213 Table 7.2.3-1 | Discrete CQI table ($0.15 - 5.55\text{ bps/Hz}$) |
| **Accessibility** | `rrc_success_rate_pct` | 3GPP Radio Accessibility | SLA Target $\ge 98.0\%$ |
| **Retainability** | `erab_drop_rate_pct` | 3GPP Session Drop Rate | SLA Target $\le 1.5\%$ |

### 2. Multi-Evidence Root Cause Analysis (RCA) Decision Framework

Rather than naive single-variable rules, TelcoPulse evaluates an **evidence chain**, reviews **alternative causes**, and outputs a **calibrated confidence score**:

| Fault Classification | Supporting Evidence Chain | Alternative Causes Evaluated | Confidence | Prescriptive Operational Action |
| :--- | :--- | :--- | :--- | :--- |
| `BASEBAND_HARDWARE_LOCKUP` | Users $\le 1$, Throughput $= 0$, Loss $= 100\%$ | Off-peak zero demand (ruled out: loss 100%), Fiber severance (ruled out: site peers alive) | $96\%$ | Execute automated remote power-cycle on Baseband Board (BBU/gNodeB). |
| `BACKHAUL_TRANSPORT_BOTTLENECK` | Backhaul Util $\ge 90\%$, Latency $> 100\text{ms}$, Loss $> 2.5\%$, PRB $< 65\%$ | Radio interface congestion (ruled out: PRB low), Core UPF delay | $94\%$ | Reroute IP/MPLS traffic to secondary transport ring or inspect Microwave alignment. |
| `RAN_CAPACITY_CONGESTION` | PRB DL $\ge 85\%$, Concurrency high, SINR $\ge 6\text{ dB}$ | External RF jamming (ruled out: SINR clear), Transport bottleneck | $91\%$ | Activate dynamic Inter-Frequency Load Balancing (IFLB) to offload to adjacent bands. |
| `RF_INTERFERENCE` | SINR $\le 0\text{ dB}$, RSRP $\ge -105\text{ dBm}$, CQI $\le 4$ | Weak coverage hole (ruled out: RSRP sufficient), Antenna VSWR fault | $89\%$ | Audit neighboring cell PCI (Physical Cell Identity) planning for MOD3 collisions. |
| `INSUFFICIENT_EVIDENCE_TRANSIENT` | Jitter burst or transient deviation without clear single-fault signature | Transient IP burst, user mobility spike, sensor clock skew | $45\%$ | Monitor next 2 consecutive ROPs. If persistent, trigger active TWAMP probe. |

---

## Measured Hardware Benchmarks (Reproducible Methodology)

Benchmarks were measured using `scripts/benchmark.py` across 5 trials (1 warm-up, 4 timed runs) on Windows 10 (AMD Ryzen 16 logical cores, CPython 3.11.9, DuckDB 1.5, PyArrow 26.0):

| Telemetry Records Processed | Median Latency | P95 Latency | Peak Memory (RAM) | Throughput (Median) | Execution State |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **480 records** | **299.4 ms** | 319.1 ms | 0.93 MB | **1,603 events/sec** | PASSED |
| **1,980 records** | **399.5 ms** | 422.2 ms | 2.09 MB | **4,956 events/sec** | PASSED |
| **9,960 records** | **1,013.7 ms** | 1,036.5 ms | 9.23 MB | **9,825 events/sec** | PASSED |

*To reproduce these figures on your machine: `python scripts/benchmark.py`.*

---

## Repository Structure

```text
telecom-network-pipeline/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI running Pytest on Push / PR
├── config/
│   ├── settings.py                # Environment-driven Pydantic V2 settings & SLA bounds
│   └── logging_config.py          # Structured telemetry logger with ISO timestamps
├── docs/
│   ├── standards_mapping.md       # 3GPP TS 32.401, RFC 2544, RFC 3393 implementation scopes
│   └── data_dictionary.md         # Complete metric catalog, units, P95 derivation, and NQI
├── data/
│   ├── bronze/                    # Partitioned immutable Parquet (year=YYYY/month=MM/day=DD/)
│   ├── silver/                    # Cleaned, deduplicated & dimensionalized telemetry
│   ├── gold/                      # Hourly rollups, empirical P95, regional scorecards & incidents
│   ├── dlq/                       # Dead-Letter Queue quarantined payloads (JSONL)
│   └── topology/                  # Cell sector topology metadata
├── sql/
│   ├── 01_init_postgres.sql       # PostgreSQL / TimescaleDB DDL, hypertables & indexes
│   ├── 02_gold_aggregates.sql     # Analytical views (Busy Hour, Backhaul comparison)
│   └── 03_telco_kpi_queries.sql   # Production queries (Top 10 worst cells, bottleneck triage)
├── src/
│   ├── contracts/
│   │   └── schemas.py             # Pydantic contracts with NaN/Inf checks & lineage fields
│   ├── generator/
│   │   ├── topology.py            # Multi-region 4G/5G cellular topology generator
│   │   ├── diurnal_model.py       # Diurnal traffic curve (commute spikes, evening peak)
│   │   ├── anomaly_injector.py    # Injects telecom fault scenarios & contract corruptions
│   │   └── telemetry_producer.py  # Physics-governed telemetry generator
│   ├── ingestion/
│   │   ├── validator.py           # Perimeter validation & DLQ quarantine router
│   │   └── bronze_writer.py       # Partitioned columnar Parquet lakehouse writer
│   ├── transformation/
│   │   ├── silver_enricher.py     # Idempotent upsert, Shannon vs 3GPP MCS, Composite NQI
│   │   └── gold_aggregator.py     # Hourly rollups, empirical P95, partial-hour detection
│   ├── analytics/
│   │   ├── anomaly_detector.py    # Rolling Z-score & multivariate statistical detector
│   │   └── rca_engine.py          # Multi-evidence Root Cause Analysis (RCA) diagnostic engine
│   ├── storage/
│   │   ├── db_engine.py           # Dual storage engine (PostgreSQL + DuckDB) with upsert
│   │   └── repository.py          # Idempotent repository pattern for queries
│   └── cli.py                     # Rich CLI to trigger pipeline stages & inspect metrics
├── dags/
│   ├── telecom_network_dag.py     # Production Apache Airflow DAG (5-min ROP schedule)
│   └── airflow_local_runner.py    # Standalone Airflow DAG simulation runner with mock XCom
├── dashboards/
│   ├── app.py                     # High-density Streamlit NOC console with Read-Only SQL
│   ├── grafana_telecom_dashboard.json # Production Grafana dashboard definition
│   └── provisioning/              # Auto-provisioning configs for Grafana datasources & providers
├── docker/
│   ├── Dockerfile                 # Multi-stage production container
│   └── docker-compose.yml         # Full stack: TimescaleDB, Grafana & Pipeline runner
├── scripts/
│   ├── run_pipeline.py            # Executable pipeline runner
│   ├── benchmark.py               # Reproducible benchmarking suite
│   └── start_dashboard.ps1        # PowerShell script to launch Streamlit NOC
├── tests/
│   ├── test_contracts.py          # Contract boundary, NaN/Inf rejection & DLQ tests
│   ├── test_idempotency.py        # Replay & retry idempotency verification tests
│   ├── test_transformations.py    # Shannon vs 3GPP MCS efficiency & SLA tests
│   ├── test_rca_engine.py         # Automated Root Cause Analysis classification tests
│   ├── test_rca_evidence.py       # Multi-evidence chain & ambiguous condition tests
│   ├── test_gold_p95.py           # Empirical P95 distribution & partial-hour tests
│   ├── test_sql_security.py       # SQL console read-only guardrail tests
│   └── test_storage.py            # Storage engine & repository query tests
├── .gitignore
├── Makefile
├── requirements.txt
└── README.md
```

---

## Quickstart Guide

### 1. Local Python Environment (Zero Cloud / Zero Docker Needed)

```bash
# 1. Clone the repository
git clone https://github.com/ahmedamr022/telecom-network-pipeline.git
cd telecom-network-pipeline

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run automated test suite (18/18 passing)
pytest tests -v

# 5. Execute the full end-to-end pipeline (12 periods = 1 hour of telemetry)
python scripts/run_pipeline.py --periods 12

# 6. Launch the interactive NOC Operations Console
streamlit run dashboards/app.py
```

### 2. Production Docker Deployment (TimescaleDB + Grafana)

```bash
docker compose -f docker/docker-compose.yml up -d

# Open Grafana in your browser:
# URL: http://localhost:3000 (User: admin | Pass: admin)
```

---

## Transparent Engineering Disclosures

1. **Synthetic Telemetry Simulator**: Current telemetry data is synthesized by `src/generator/telemetry_producer.py` using physical RF models and 3GPP PM specifications. It is designed for repeatable fault injection and pipeline stress testing, and is not a direct tap from a commercial live operator.
2. **RFC 2544 / RFC 3393 Ingestion**: TelcoPulse ingests telemetry counters adhering to RFC definitions; it does not execute active RFC traffic generator sweeps.
3. **Database Portability**: The platform supports PostgreSQL/TimescaleDB and embedded DuckDB with identical analytical schemas and guaranteed upsert idempotency.

---

## Author & License

Built by **Ahmed Amr** as an open-source telecommunications and data engineering portfolio project.

Licensed under the [MIT License](LICENSE).
