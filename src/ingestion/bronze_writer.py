import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from config.settings import settings
from config.logging_config import logger


class BronzeStorageWriter:
    """
    Manages immutable, append-only Bronze Lakehouse storage.
    Partitions valid telemetry by year/month/day and archives DLQ quarantine payloads.
    """

    def __init__(self, bronze_dir: Optional[Path] = None, dlq_dir: Optional[Path] = None):
        self.bronze_dir = bronze_dir or settings.BRONZE_DIR
        self.dlq_dir = dlq_dir or settings.DLQ_DIR

    def write_bronze_batch(self, valid_records: List[Dict[str, Any]], batch_id: Optional[str] = None) -> Optional[Path]:
        """
        Writes valid telemetry records to partitioned Parquet files.
        Storage layout: data/bronze/year=YYYY/month=MM/day=DD/batch_<id>.parquet
        """
        if not valid_records:
            logger.warning("Bronze writer received empty record list. Skipping write.")
            return None

        batch_id = batch_id or uuid.uuid4().hex[:8]
        df = pd.DataFrame(valid_records)

        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        first_ts = df["timestamp"].iloc[0]
        year = first_ts.strftime("%Y")
        month = first_ts.strftime("%m")
        day = first_ts.strftime("%d")

        partition_path = self.bronze_dir / f"year={year}" / f"month={month}" / f"day={day}"
        partition_path.mkdir(parents=True, exist_ok=True)

        parquet_file = partition_path / f"telemetry_batch_{batch_id}.parquet"
        
        # Write columnar Parquet with snappy compression
        df.to_parquet(parquet_file, engine="pyarrow", compression="snappy", index=False)
        logger.info(f"Bronze batch stored: {len(df)} records -> {parquet_file.name} ({parquet_file.stat().st_size / 1024:.1f} KB)")
        return parquet_file

    def write_dlq_quarantine(self, quarantined_records: List[Dict[str, Any]]) -> Optional[Path]:
        """
        Appends rejected payloads to the Dead-Letter Queue JSONL log.
        """
        if not quarantined_records:
            return None

        self.dlq_dir.mkdir(parents=True, exist_ok=True)
        dlq_file = self.dlq_dir / "quarantined_records.jsonl"

        with open(dlq_file, "a", encoding="utf-8") as f:
            for record in quarantined_records:
                # Ensure datetime objects are converted to ISO string
                if isinstance(record.get("quarantine_timestamp"), datetime):
                    record["quarantine_timestamp"] = record["quarantine_timestamp"].isoformat()
                f.write(json.dumps(record, default=str) + "\n")

        logger.warning(f"DLQ Quarantine: {len(quarantined_records)} invalid payloads routed to {dlq_file.name}")
        return dlq_file
