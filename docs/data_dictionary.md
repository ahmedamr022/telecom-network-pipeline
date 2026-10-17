# TelcoPulse | Telecom Data Dictionary & Metric Catalog

This document defines the schema, data types, physical units, and analytical derivations across all Medallion Lakehouse tiers.

---

## 1. Perimeter & Bronze Layer (Raw Ingestion)

Storage Layout: `data/bronze/year=YYYY/month=MM/day=DD/telemetry_batch_<id>.parquet`

| Field Name | Type | Unit | Nullable | Description & Constraints |
| :--- | :--- | :--- | :--- | :--- |
| `event_timestamp` | `TIMESTAMP` | ISO 8601 UTC | No | The 5-minute ROP interval boundary when telemetry was sampled. |
| `ingestion_timestamp`| `TIMESTAMP`| ISO 8601 UTC | No | The physical wall-clock timestamp when the perimeter validator processed the frame. |
| `batch_id` | `VARCHAR(16)`| Hex UUID | No | Identifier of the ingestion micro-batch for lineage and auditing. |
| `source_id` | `VARCHAR(32)`| Identifier | No | Collector or probe source identifier (e.g., `kafka-cai-pm-gw01`). |
| `schema_version` | `VARCHAR(8)` | SemVer | No | Version of data contract used during perimeter validation (`v1.2.0`). |
| `cell_id` | `VARCHAR(32)`| String | No | Sector ID matching `^[A-Z]{3}-[A-Z0-9]+-[0-9]{3}-S[1-3]$`. |
| `site_id` | `VARCHAR(32)`| String | No | Tower / base station node identifier (e.g., `CAI-EAST-001`). |
| `technology` | `VARCHAR(16)`| Category | No | Cellular radio technology: `4G_LTE` or `5G_NR`. |
| `frequency_band_mhz`| `INT` | $\text{MHz}$ | No | Operating carrier frequency (e.g., 1800, 3500). |
| `bandwidth_mhz` | `NUMERIC(5,1)`| $\text{MHz}$ | No | Allocated carrier bandwidth (10.0, 20.0, 100.0). |
| `latency_ms` | `NUMERIC(7,2)`| $\text{ms}$ | No | Round-trip IP transport probe delay ($0.0 \le x \le 2000.0$). |
| `jitter_ms` | `NUMERIC(6,2)`| $\text{ms}$ | No | RFC 3393 packet delay variation ($0.0 \le x \le 500.0$). |
| `packet_loss_pct` | `NUMERIC(5,2)`| $\%$ | No | IP transport packet drop rate ($0.0 \le x \le 100.0\%$). |
| `backhaul_utilization_pct` | `NUMERIC(5,2)` | $\%$ | No | Percentage of transport bearer capacity consumed ($0.0 - 100.0\%$). |
| `throughput_dl_mbps` | `NUMERIC(7,2)` | $\text{Mbps}$ | No | Downlink MAC/PDCP user-plane bit rate ($0.0 - 5000.0$). |
| `throughput_ul_mbps` | `NUMERIC(7,2)` | $\text{Mbps}$ | No | Uplink MAC/PDCP user-plane bit rate ($0.0 - 1000.0$). |
| `prb_utilization_dl_pct` | `NUMERIC(5,2)` | $\%$ | No | Downlink Physical Resource Block utilization ($0.0 - 100.0\%$). |
| `prb_utilization_ul_pct` | `NUMERIC(5,2)` | $\%$ | No | Uplink Physical Resource Block utilization ($0.0 - 100.0\%$). |
| `connected_users` | `INT` | Count | No | Concurrently active RRC connected subscribers ($0 - 5000$). |
| `rsrp_dbm` | `NUMERIC(5,1)`| $\text{dBm}$ | No | Reference Signal Received Power ($-140.0 \le x \le -40.0$). |
| `sinr_db` | `NUMERIC(5,1)`| $\text{dB}$ | No | Signal-to-Interference-plus-Noise Ratio ($-20.0 \le x \le 40.0$). |
| `cqi` | `INT` | Index (1-15)| No | 3GPP TS 36.213 Channel Quality Indicator. |
| `rrc_success_rate_pct` | `NUMERIC(5,2)`| $\%$ | No | Accessibility setup success percentage ($0.0 - 100.0\%$). |
| `erab_drop_rate_pct` | `NUMERIC(5,2)`| $\%$ | No | Retainability session abnormal termination rate ($0.0 - 100.0\%$). |

---

## 2. Silver Layer (`silver_cell_telemetry`)

Primary Logical Key: `(cell_id, timestamp)` — Enforced via Upsert Deduplication.

Enriched dimensions and calculated engineering fields:

| Field Name | Type | Unit | Formula / Rule |
| :--- | :--- | :--- | :--- |
| `region` | `VARCHAR(16)`| Text | Topological dimension (e.g., `CAI`, `ALX`, `GZA`). |
| `subregion` | `VARCHAR(16)`| Text | Topological zone (e.g., `EAST`, `DNTN`, `OCT`). |
| `backhaul_type` | `VARCHAR(32)`| Text | Transmission link media: `FIBER_10G` or `MICROWAVE_1G`. |
| `azimuth_deg` | `INT` | Degrees | Antenna pointing angle ($0^\circ, 120^\circ, 240^\circ$). |
| `latitude`, `longitude` | `NUMERIC(9,6)`| Coordinates | Geospatial tower location. |
| `theoretical_spectral_efficiency_bps_hz` | `NUMERIC(5,3)`| $\text{bps/Hz}$ | $\log_2(1 + 10^{\text{sinr\_db}/10})$ (Shannon Continuous Limit). |
| `estimated_radio_efficiency_bps_hz` | `NUMERIC(5,3)`| $\text{bps/Hz}$ | Discrete 3GPP Table lookup based on CQI index. |
| `measured_spectral_efficiency_bps_hz` | `NUMERIC(5,3)`| $\text{bps/Hz}$ | $\frac{\text{throughput\_dl\_mbps}}{\text{bandwidth\_mhz}}$ |
| `throughput_per_user_mbps` | `NUMERIC(7,3)`| $\text{Mbps}$ | $\frac{\text{throughput\_dl\_mbps}}{\max(1, \text{connected\_users})}$ |
| `network_quality_index` (NQI) | `NUMERIC(5,2)`| Score (0-100)| Multi-dimensional weighted composite score (see Section 4). |
| `is_sla_compliant` | `BOOLEAN` | Bool | `latency <= 50 AND loss <= 1.0% AND throughput >= 15 AND rrc >= 98% AND drop <= 1.5%`. |
| `is_congested` | `BOOLEAN` | Bool | `prb_utilization_dl_pct >= 85.0%`. |
| `is_interfered` | `BOOLEAN` | Bool | `sinr_db < 0.0 AND rsrp_dbm >= -105.0 dBm`. |
| `is_transport_bottleneck` | `BOOLEAN` | Bool | `backhaul_utilization_pct >= 90.0% OR (latency > 100 AND loss > 3.0% AND prb < 65%)`. |
| `is_sleeping_cell` | `BOOLEAN` | Bool | `users <= 1 AND throughput <= 0.1 AND loss >= 50.0%` (evaluated across consecutive ROPs). |

---

## 3. Gold Layer Aggregations

### Table: `gold_cell_hourly_kpi`
Primary Key: `(cell_id, date_hour)`

- `avg_latency_ms`: Arithmetic mean of round-trip latency across valid samples in the hour.
- `p95_latency_ms`: **True 95th Percentile** calculated directly over the empirical distribution of individual 5-min samples within the hourly bucket (never computed from pre-averaged numbers).
- `busy_hour_prb_dl_pct`: Peak PRB utilization observed during the hour (identifying the Time-Consistent Busy Hour).
- `sla_compliance_rate_pct`: Percentage of 5-minute ROP samples meeting all SLA terms during that 60-minute window ($\frac{N_{\text{compliant}}}{N_{\text{total}}} \times 100\%$).
- `total_volume_gb`: Integral of downlink data volume:
  $$\text{Volume [GB]} = \sum \frac{\text{Throughput [Mbps]} \times 300\text{ seconds}}{8,000}$$

---

## 4. Network Quality Index (NQI) Formulation & Sensitivity

The **Composite Network Quality Index (NQI)** is a normalized metric ($0.0 - 100.0$) quantifying sector operational health:

$$\text{NQI} = 0.35 \times S_{\text{Radio}} + 0.40 \times S_{\text{Transport}} + 0.25 \times S_{\text{Accessibility}}$$

Where sub-scores are bounded in $[0, 100]$:
1. **Radio Sub-score ($S_{\text{Radio}}$)**:
   $$S_{\text{Radio}} = \text{clamp}\left(\frac{\text{SINR}_{\text{dB}} + 10}{35} \times 100, 0, 100\right)$$
   - SINR $\ge 25\text{ dB} \implies 100$
   - SINR $= 10\text{ dB} \implies 57$
   - SINR $\le -10\text{ dB} \implies 0$

2. **Transport Sub-score ($S_{\text{Transport}}$)**:
   $$S_{\text{Transport}} = 100 - \text{clamp}\left(\frac{\text{Latency}_{\text{ms}}}{100} \times 40 + \text{Loss}_{\%} \times 12, 0, 100\right)$$
   - Latency $15\text{ms}$, Loss $0.05\% \implies 100 - (6 + 0.6) = 93.4$
   - Latency $150\text{ms}$, Loss $5.0\% \implies 100 - (60 + 60) = 0$

3. **Accessibility Sub-score ($S_{\text{Accessibility}}$)**:
   $$S_{\text{Accessibility}} = \text{clamp}\left(\text{RRC}_{\%} - (\text{Drop}_{\%} \times 5), 0, 100\right)$$

### Sensitivity Behavior:
- A pure transport fault (Latency $200\text{ms}$, Loss $8\%$) immediately drops $S_{\text{Transport}}$ from $\approx 95$ to $0$, pulling global NQI down by $\approx 38$ points.
- A radio interference event (SINR $-5\text{ dB}$) drops $S_{\text{Radio}}$ from $80$ to $14$, pulling global NQI down by $\approx 23$ points.
- Missing values default to neutral median baseline rather than dropping rows, preventing distorted zero-drops.
