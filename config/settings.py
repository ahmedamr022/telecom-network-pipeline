import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base repository directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    Production configuration for Telecom Network Performance Data Pipeline.
    Loads from environment variables or defaults to local lakehouse paths.
    """
    APP_NAME: str = "Telecom Network Performance Pipeline"
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"

    # Data Storage Paths
    BASE_DATA_DIR: Path = BASE_DIR / "data"
    BRONZE_DIR: Path = BASE_DATA_DIR / "bronze"
    SILVER_DIR: Path = BASE_DATA_DIR / "silver"
    GOLD_DIR: Path = BASE_DATA_DIR / "gold"
    DLQ_DIR: Path = BASE_DATA_DIR / "dlq"
    TOPOLOGY_DIR: Path = BASE_DATA_DIR / "topology"
    
    # DuckDB local storage path
    DUCKDB_PATH: Path = BASE_DATA_DIR / "telecom_lakehouse.duckdb"

    # Database Configuration (PostgreSQL / TimescaleDB)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "telecom_db"
    POSTGRES_USER: str = "telco_admin"
    POSTGRES_PASSWORD: str = "telco_secure_pass"
    USE_POSTGRES: bool = False  # Set to True when running with Postgres/TimescaleDB container

    @property
    def postgres_connection_string(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Telecom SLA & Quality Thresholds
    SLA_MAX_LATENCY_MS: float = 50.0          # Max acceptable RTT latency for 4G/5G transport
    SLA_MAX_PACKET_LOSS_PCT: float = 1.0       # Max acceptable packet loss rate (%)
    SLA_MIN_THROUGHPUT_MBPS: float = 15.0      # Minimum acceptable user DL throughput (Mbps)
    SLA_MIN_RRC_SUCCESS_RATE_PCT: float = 98.0 # Minimum radio accessibility rate (%)
    SLA_MAX_ERAB_DROP_RATE_PCT: float = 1.5    # Maximum call drop rate (%)

    # Network Anomaly Detection Thresholds (3GPP / ITU-T Standards)
    CONGESTION_PRB_THRESHOLD: float = 85.0     # PRB utilization above 85% indicates capacity exhaustion
    INTERFERENCE_SINR_THRESHOLD: float = 0.0   # SINR below 0 dB indicates severe co-channel interference
    HIGH_PACKET_LOSS_THRESHOLD: float = 4.0    # Packet loss > 4% triggers transport alarm
    BACKHAUL_SATURATION_THRESHOLD: float = 90.0# Backhaul bandwidth > 90%
    SLEEPING_CELL_MIN_USERS: int = 2           # Less than 2 users during active hours flags silent failure

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure directories exist
for path in [
    settings.BRONZE_DIR,
    settings.SILVER_DIR,
    settings.GOLD_DIR,
    settings.DLQ_DIR,
    settings.TOPOLOGY_DIR,
]:
    path.mkdir(parents=True, exist_ok=True)
