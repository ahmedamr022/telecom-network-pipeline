# 3GPP & IETF RFC Standards Implementation Mapping

This document provides a transparent, rigorous mapping between published telecommunications standards and the specific metrics, boundaries, and mathematical formulations implemented in **TelcoPulse**.

---

## 1. 3GPP Performance Management (3GPP TS 32.401 / TS 36.314 / TS 38.314)

| 3GPP Standard | Clause / Counter Name | Pipeline Implementation Metric | Definition & Unit | Fidelity / Scope in TelcoPulse |
| :--- | :--- | :--- | :--- | :--- |
| **3GPP TS 32.401** | Section 4: Result Output Period (ROP) | 5-minute telemetry intervals (`timestamp`, `date_hour`) | Performance counters aggregated into discrete 5-minute sampling windows. | **Full**: Mimics 3GPP bulk PM data export intervals. |
| **3GPP TS 36.314** | Section 4.1.1: PRB Utilization (DL/UL) | `prb_utilization_dl_pct`, `prb_utilization_ul_pct` | Percentage of Physical Resource Blocks (PRBs) actively allocated for user-plane data ($0.0 - 100.0\%$). | **Full**: Core capacity KPI; $\ge 85\%$ triggers capacity congestion triage. |
| **3GPP TS 36.214** | Section 5.1.1: RSRP | `rsrp_dbm` | Reference Signal Received Power in $\text{dBm}$ ($-140.0$ to $-44.0\text{ dBm}$). | **Full**: Measures RF coverage signal strength at cell receivers. |
| **3GPP TS 36.214** | Section 5.1.3: SINR / RS-SINR | `sinr_db` | Signal-to-Interference-plus-Noise Ratio in $\text{dB}$ ($-20.0$ to $+35.0\text{ dB}$). | **Proxy**: Used for RF quality and spectral efficiency modeling. |
| **3GPP TS 36.213** | Table 7.2.3-1: 4-bit CQI Table | `cqi` | Channel Quality Indicator ($1 - 15$) mapping channel state to modulation (QPSK, 16QAM, 64QAM, 256QAM). | **Standard Table**: Directly maps SINR thresholds to 3GPP CQI efficiency. |
| **3GPP TS 32.450** | Section 6.1: Radio Accessibility | `rrc_success_rate_pct` | $\frac{\text{Successful RRC Setup Connections}}{\text{Attempted RRC Connections}} \times 100\%$ | **Standard KPI**: Accessibility target $\ge 98.0\%$. |
| **3GPP TS 32.450** | Section 6.2: Radio Retainability | `erab_drop_rate_pct` | $\frac{\text{Abnormally Released E-RABs}}{\text{Total Active E-RABs}} \times 100\%$ | **Standard KPI**: Retainability target $\le 1.5\%$. |

---

## 2. IETF IP Transport Performance (RFC 2544 / RFC 3393 / RFC 5357)

| RFC Standard | Section / RFC Title | Pipeline Implementation Metric | Definition & Unit | Scope & Disclosure in TelcoPulse |
| :--- | :--- | :--- | :--- | :--- |
| **RFC 2544** | Section 26.1 - 26.3: Benchmarking Methodology | `latency_ms`, `packet_loss_pct`, `throughput_dl_mbps` | Round-Trip Time ($\text{ms}$), frame loss rate ($\%$), and sustained throughput ($\text{Mbps}$). | **Inspired / Telemetry Ingestion**: TelcoPulse ingests RFC 2544-compliant probe counters emitted by backhaul gateways; it does **not** execute active RFC 2544 tester sweeps itself. |
| **RFC 3393** | IP Packet Delay Variation Metric (IPDV) | `jitter_ms` | Statistical variation in packet arrival delay across consecutive UDP probes ($\text{ms}$). | **Standard Metric**: Monitored on backhaul links to catch transport degradation before full loss occurs. |
| **RFC 5357** | TWAMP (Two-Way Active Measurement Protocol) | `latency_ms`, `jitter_ms` | Timestamped two-way IP probe packets exchanged between base station and Core UPF. | **Transport Telemetry Source**: Nominal source of backhaul latency & jitter metrics. |
| **ITU-T Y.1540** | IP Packet Transfer Performance | `is_sla_compliant` | International SLA standard for IP transport quality of service. | **SLA Boundary**: Latency $\le 50\text{ms}$, Loss $\le 1.0\%$, Throughput $\ge 15\text{Mbps}$. |

---

## 3. Mathematical Formulations & Physics Distinctions

### 3.1 Shannon-Hartley Capacity vs. Actual Radio Efficiency
In TelcoPulse, we explicitly distinguish between:

1. **Theoretical Shannon-Hartley Spectral Efficiency** (`theoretical_spectral_efficiency_bps_hz`):
   $$\eta_{\text{Shannon}} = \log_2\left(1 + 10^{\frac{\text{SINR}_{\text{dB}}}{10}}\right) \quad [\text{bps/Hz}]$$
   *Note*: Represents the continuous mathematical upper bound of an AWGN channel with SINR treated as an SNR proxy.

2. **Estimated Radio Efficiency via 3GPP Modulation Tables** (`estimated_radio_efficiency_bps_hz`):
   Actual LTE/5G networks cannot achieve unconstrained Shannon limits due to discrete Modulation and Coding Schemes (MCS), cyclic prefix overhead, and channel estimation losses:
   - CQI 1 (QPSK 1/3) $\implies \approx 0.15\text{ bps/Hz}$
   - CQI 6 (16-QAM 1/2) $\implies \approx 1.18\text{ bps/Hz}$
   - CQI 10 (64-QAM 3/4) $\implies \approx 2.73\text{ bps/Hz}$
   - CQI 15 (256-QAM 9/10) $\implies \approx 5.55\text{ bps/Hz}$

3. **Measured Effective Spectral Efficiency** (`measured_spectral_efficiency_bps_hz`):
   $$\eta_{\text{measured}} = \frac{\text{Throughput}_{\text{DL}} \ [\text{Mbps}]}{\text{Channel Bandwidth} \ [\text{MHz}]} \quad [\text{bps/Hz}]$$

---

## 4. Multi-Evidence Root Cause Analysis (RCA) Decision Framework

TelcoPulse avoids simplistic single-variable conclusions. Every incident diagnosis requires a triad:
- **Suspected Cause**: The primary categorized failure mode.
- **Evidence**: Mathematical telemetry conditions that confirm the hypothesis.
- **Alternative Causes**: Other network anomalies that share similar symptoms but were ruled out or remain plausible.
- **Calibrated Confidence Score**: Calculated via Bayesian evidence weights, outputting `UNKNOWN` when telemetry is contradictory or insufficient.
