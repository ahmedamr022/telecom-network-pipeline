from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from pydantic import ValidationError

from src.contracts.schemas import RawTelemetryRecord, DLQRecord


@dataclass
class ValidationReport:
    total_records: int
    valid_count: int
    rejected_count: int
    valid_records: List[Dict[str, Any]]
    quarantined_records: List[Dict[str, Any]]

    @property
    def validity_rate_pct(self) -> float:
        return (self.valid_count / self.total_records * 100.0) if self.total_records > 0 else 100.0


class TelemetryContractValidator:
    """
    Enforces perimeter data contracts on raw incoming telemetry frames.
    Validates physical boundaries (RFC 2544, 3GPP TS 32.401) and isolates
    corrupted or malformed records into the Dead-Letter Queue (DLQ).
    """

    @staticmethod
    def validate_batch(raw_frames: List[Dict[str, Any]]) -> ValidationReport:
        valid_records: List[Dict[str, Any]] = []
        quarantined: List[Dict[str, Any]] = []

        for frame in raw_frames:
            try:
                # Schema and domain boundary validation
                validated_model = RawTelemetryRecord(**frame)
                valid_records.append(validated_model.model_dump())
            except ValidationError as ve:
                # Extract first error details
                err_detail = ve.errors()[0]
                field_name = ".".join(str(loc) for loc in err_detail["loc"])
                err_msg = err_detail["msg"]
                err_type = err_detail["type"]

                dlq_entry = DLQRecord(
                    quarantine_timestamp=datetime.utcnow(),
                    rejection_stage="PERIMETER_CONTRACT_VALIDATION",
                    error_code=f"ERR_{err_type.upper()}",
                    error_message=f"Field '{field_name}': {err_msg}",
                    raw_payload=frame
                )
                quarantined.append(dlq_entry.model_dump())
            except Exception as e:
                dlq_entry = DLQRecord(
                    quarantine_timestamp=datetime.utcnow(),
                    rejection_stage="PERIMETER_UNEXPECTED_FAILURE",
                    error_code="ERR_UNKNOWN_PARSING_FAILURE",
                    error_message=str(e),
                    raw_payload=frame
                )
                quarantined.append(dlq_entry.model_dump())

        return ValidationReport(
            total_records=len(raw_frames),
            valid_count=len(valid_records),
            rejected_count=len(quarantined),
            valid_records=valid_records,
            quarantined_records=quarantined
        )
