-- ==============================================================================
-- TELECOM NETWORK PERFORMANCE PLATFORM - GOLD ANALYTICAL VIEWS
-- ==============================================================================

-- 1. Real-Time Cell Health & Latest ROP Status
CREATE OR REPLACE VIEW v_active_cell_health AS
WITH latest_sample AS (
    SELECT 
        cell_id,
        MAX(timestamp) AS max_ts
    FROM silver_cell_telemetry
    GROUP BY cell_id
)
SELECT 
    t.cell_id,
    t.site_id,
    t.region,
    t.subregion,
    t.technology,
    t.backhaul_type,
    t.timestamp AS last_seen,
    t.latency_ms,
    t.packet_loss_pct,
    t.throughput_dl_mbps,
    t.prb_utilization_dl_pct,
    t.connected_users,
    t.sinr_db,
    t.network_quality_index,
    t.is_sla_compliant,
    t.is_anomaly,
    t.severity
FROM silver_cell_telemetry t
INNER JOIN latest_sample ls 
    ON t.cell_id = ls.cell_id AND t.timestamp = ls.max_ts;


-- 2. Busy-Hour (BH) PRB Capacity Analysis
-- 3GPP Standard: Busy-hour is defined as the 60-minute window having the highest traffic load.
CREATE OR REPLACE VIEW v_busy_hour_analysis AS
WITH ranked_hours AS (
    SELECT 
        cell_id,
        date_hour,
        technology,
        region,
        busy_hour_prb_dl_pct,
        avg_throughput_dl_mbps,
        peak_connected_users,
        total_volume_gb,
        ROW_NUMBER() OVER (
            PARTITION BY cell_id, CAST(date_hour AS DATE) 
            ORDER BY busy_hour_prb_dl_pct DESC
        ) AS rnk
    FROM gold_cell_hourly_kpi
)
SELECT 
    cell_id,
    date_hour AS busy_hour_timestamp,
    technology,
    region,
    busy_hour_prb_dl_pct,
    avg_throughput_dl_mbps,
    peak_connected_users,
    total_volume_gb
FROM ranked_hours
WHERE rnk = 1;


-- 3. Transport Backhaul Efficiency (Fiber vs Microwave)
CREATE OR REPLACE VIEW v_backhaul_performance_comparison AS
SELECT 
    backhaul_type,
    technology,
    COUNT(DISTINCT cell_id) AS cell_count,
    ROUND(AVG(avg_latency_ms), 1) AS mean_rtt_latency_ms,
    ROUND(AVG(p95_latency_ms), 1) AS mean_p95_latency_ms,
    ROUND(AVG(avg_jitter_ms), 2) AS mean_jitter_ms,
    ROUND(AVG(avg_packet_loss_pct), 2) AS mean_packet_loss_pct,
    ROUND(AVG(sla_compliance_rate_pct), 1) AS mean_sla_compliance_pct
FROM gold_cell_hourly_kpi
GROUP BY backhaul_type, technology;
