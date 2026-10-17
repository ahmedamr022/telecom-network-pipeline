-- ==============================================================================
-- TELECOM NETWORK PERFORMANCE PLATFORM - POSTGRESQL / TIMESCALEDB SCHEMA DDL
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ------------------------------------------------------------------------------
-- 1. DIMENSION: Cell Tower & Radio Sector Topology
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_cells (
    cell_id VARCHAR(32) PRIMARY KEY,
    site_id VARCHAR(32) NOT NULL,
    region VARCHAR(16) NOT NULL,
    subregion VARCHAR(16) NOT NULL,
    technology VARCHAR(16) NOT NULL,
    frequency_band_mhz INT NOT NULL,
    bandwidth_mhz NUMERIC(5, 1) NOT NULL,
    backhaul_type VARCHAR(32) NOT NULL,
    azimuth_deg INT NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    nominal_capacity_mbps NUMERIC(7, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_cells_region ON dim_cells(region, subregion);
CREATE INDEX IF NOT EXISTS idx_dim_cells_tech ON dim_cells(technology);

-- ------------------------------------------------------------------------------
-- 2. SILVER LAYER: Cleaned, Curated, and Enriched 5-min ROP Telemetry
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver_cell_telemetry (
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    ingestion_timestamp TIMESTAMP WITHOUT TIME ZONE,
    batch_id VARCHAR(16),
    source_id VARCHAR(32),
    schema_version VARCHAR(8),

    cell_id VARCHAR(32) NOT NULL,
    site_id VARCHAR(32) NOT NULL,
    technology VARCHAR(16) NOT NULL,
    frequency_band_mhz INT NOT NULL,
    bandwidth_mhz NUMERIC(5, 1) NOT NULL,
    
    -- Transport Telemetry (RFC 2544 / RFC 5357)
    latency_ms NUMERIC(7, 2) NOT NULL,
    jitter_ms NUMERIC(6, 2) NOT NULL,
    packet_loss_pct NUMERIC(5, 2) NOT NULL,
    backhaul_utilization_pct NUMERIC(5, 2) NOT NULL,

    -- Radio Performance & Utilization
    throughput_dl_mbps NUMERIC(7, 2) NOT NULL,
    throughput_ul_mbps NUMERIC(7, 2) NOT NULL,
    prb_utilization_dl_pct NUMERIC(5, 2) NOT NULL,
    prb_utilization_ul_pct NUMERIC(5, 2) NOT NULL,
    connected_users INT NOT NULL,

    -- RF Channel Quality
    rsrp_dbm NUMERIC(5, 1) NOT NULL,
    sinr_db NUMERIC(5, 1) NOT NULL,
    cqi INT NOT NULL,

    -- Accessibility & Drops (3GPP TS 32.401)
    rrc_success_rate_pct NUMERIC(5, 2) NOT NULL,
    erab_drop_rate_pct NUMERIC(5, 2) NOT NULL,

    -- Topological Dimensions
    region VARCHAR(16) NOT NULL,
    subregion VARCHAR(16) NOT NULL,
    backhaul_type VARCHAR(32) NOT NULL,
    azimuth_deg INT NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    nominal_capacity_mbps NUMERIC(7, 2) NOT NULL,

    -- Rigorous Physics & Efficiency Metrics
    theoretical_spectral_efficiency_bps_hz NUMERIC(5, 3),
    estimated_radio_efficiency_bps_hz NUMERIC(5, 3),
    measured_spectral_efficiency_bps_hz NUMERIC(5, 3),
    throughput_per_user_mbps NUMERIC(7, 3),
    network_quality_index NUMERIC(5, 2),
    is_sla_compliant BOOLEAN NOT NULL,

    -- Anomaly & Diagnostics
    is_congested BOOLEAN NOT NULL,
    is_interfered BOOLEAN NOT NULL,
    is_transport_bottleneck BOOLEAN NOT NULL,
    is_sleeping_cell BOOLEAN NOT NULL,
    latency_zscore NUMERIC(5, 2),
    is_anomaly BOOLEAN NOT NULL,
    severity VARCHAR(16) NOT NULL,

    CONSTRAINT pk_silver_telemetry PRIMARY KEY (cell_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_silver_ts ON silver_cell_telemetry (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_silver_cell_ts ON silver_cell_telemetry (cell_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_silver_region_ts ON silver_cell_telemetry (region, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_silver_anomaly ON silver_cell_telemetry (is_anomaly, severity) WHERE is_anomaly = TRUE;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('silver_cell_telemetry', 'timestamp', if_not_exists => TRUE);
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Continuing with standard PostgreSQL table indexing.';
END $$;

-- ------------------------------------------------------------------------------
-- 3. GOLD LAYER: Hourly Cell Performance Mart
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold_cell_hourly_kpi (
    cell_id VARCHAR(32) NOT NULL,
    site_id VARCHAR(32) NOT NULL,
    date_hour TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    region VARCHAR(16) NOT NULL,
    subregion VARCHAR(16) NOT NULL,
    technology VARCHAR(16) NOT NULL,
    frequency_band_mhz INT NOT NULL,
    backhaul_type VARCHAR(32) NOT NULL,
    
    sample_count INT NOT NULL,
    avg_latency_ms NUMERIC(7, 2) NOT NULL,
    p95_latency_ms NUMERIC(7, 2) NOT NULL,
    avg_jitter_ms NUMERIC(6, 2) NOT NULL,
    avg_packet_loss_pct NUMERIC(5, 2) NOT NULL,
    max_packet_loss_pct NUMERIC(5, 2) NOT NULL,
    avg_throughput_dl_mbps NUMERIC(7, 2) NOT NULL,
    max_throughput_dl_mbps NUMERIC(7, 2) NOT NULL,
    total_volume_gb NUMERIC(9, 2) NOT NULL,
    avg_prb_dl_pct NUMERIC(5, 2) NOT NULL,
    busy_hour_prb_dl_pct NUMERIC(5, 2) NOT NULL,
    avg_connected_users NUMERIC(7, 1) NOT NULL,
    peak_connected_users INT NOT NULL,
    avg_rsrp_dbm NUMERIC(5, 1) NOT NULL,
    avg_sinr_db NUMERIC(5, 1) NOT NULL,
    avg_spectral_efficiency NUMERIC(5, 3) NOT NULL,
    avg_nqi NUMERIC(5, 2) NOT NULL,
    sla_compliance_rate_pct NUMERIC(5, 2) NOT NULL,
    anomaly_sample_count INT NOT NULL,

    CONSTRAINT pk_gold_cell_hourly PRIMARY KEY (cell_id, date_hour)
);

CREATE INDEX IF NOT EXISTS idx_gold_hourly_ts ON gold_cell_hourly_kpi (date_hour DESC);
CREATE INDEX IF NOT EXISTS idx_gold_hourly_sla ON gold_cell_hourly_kpi (sla_compliance_rate_pct ASC);

-- ------------------------------------------------------------------------------
-- 4. GOLD LAYER: Regional SLA Compliance Scorecard
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold_regional_sla (
    region VARCHAR(16) NOT NULL,
    date_hour TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    total_monitored_cells INT NOT NULL,
    total_volume_gb NUMERIC(10, 2) NOT NULL,
    avg_regional_latency_ms NUMERIC(7, 2) NOT NULL,
    avg_regional_packet_loss_pct NUMERIC(5, 2) NOT NULL,
    avg_regional_throughput_mbps NUMERIC(7, 2) NOT NULL,
    regional_sla_compliance_pct NUMERIC(5, 2) NOT NULL,
    avg_network_quality_index NUMERIC(5, 2) NOT NULL,
    total_anomalies_detected INT NOT NULL,

    CONSTRAINT pk_gold_regional_sla PRIMARY KEY (region, date_hour)
);

-- ------------------------------------------------------------------------------
-- 5. INCIDENT MART: Root Cause Analysis Diagnoses & Evidence
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold_network_incidents (
    incident_id VARCHAR(64) PRIMARY KEY,
    cell_id VARCHAR(32) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    severity VARCHAR(16) NOT NULL,
    suspected_cause VARCHAR(64) NOT NULL,
    confidence_score NUMERIC(4, 2) NOT NULL,
    evidence_json TEXT NOT NULL,
    alternative_causes_json TEXT NOT NULL,
    root_cause_summary TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    affected_users INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incidents_cell_ts ON gold_network_incidents(cell_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON gold_network_incidents(severity, timestamp DESC);
