-- ==============================================================================
-- TELECOM PRODUCTION ANALYTICAL QUERIES (NOC & TIER-3 RF ENGINEERING)
-- ==============================================================================

-- 1. Identify Top 10 Worst Performing Cells (Lowest SLA Compliance)
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


-- 2. Triage Transport Backhaul Bottlenecks (Low RAN Load but High Network Delay)
-- Logic: If PRB < 50% but Latency > 100ms and Loss > 2.5%, the issue is Backhaul, not Radio.
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


-- 3. Detect Radio Frequency Co-Channel Interference (Strong RSRP but Poor SINR)
SELECT 
    cell_id,
    timestamp,
    rsrp_dbm,
    sinr_db,
    cqi,
    throughput_dl_mbps,
    erab_drop_rate_pct
FROM silver_cell_telemetry
WHERE rsrp_dbm >= -95.0 
  AND sinr_db < 0.0
ORDER BY sinr_db ASC;


-- 4. Hourly 4G vs 5G Traffic & Bandwidth Share by Region
SELECT 
    date_hour,
    region,
    technology,
    ROUND(SUM(total_volume_gb), 1) AS total_gigabytes,
    ROUND(AVG(avg_throughput_dl_mbps), 1) AS mean_throughput_mbps,
    ROUND(AVG(p95_latency_ms), 1) AS p95_latency_ms,
    ROUND(AVG(sla_compliance_rate_pct), 1) AS sla_pct
FROM gold_cell_hourly_kpi
GROUP BY date_hour, region, technology
ORDER BY date_hour DESC, region, technology;


-- 5. Root Cause Analysis (RCA) Incident Distribution & Affected Users
SELECT 
    suspected_cause,
    severity,
    COUNT(*) AS incident_count,
    ROUND(AVG(confidence_score) * 100, 1) AS avg_confidence_pct,
    SUM(affected_users) AS total_subscribers_impacted
FROM gold_network_incidents
GROUP BY suspected_cause, severity
ORDER BY incident_count DESC;
