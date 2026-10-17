import re
import pytest


def validate_read_only_query(query: str) -> bool:
    """Read-only security validator used in Streamlit console."""
    clean_q = query.strip()
    forbidden_pattern = r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|REPLACE|ATTACH|DETACH|GRANT|REVOKE|COPY|PRAGMA)\b"
    
    if re.search(forbidden_pattern, clean_q, re.IGNORECASE):
        return False
    if not re.match(r"^\s*(SELECT|WITH)\b", clean_q, re.IGNORECASE):
        return False
    return True


def test_sql_security_allows_select():
    assert validate_read_only_query("SELECT * FROM silver_cell_telemetry LIMIT 10;") == True
    assert validate_read_only_query("WITH cte AS (SELECT cell_id FROM silver_cell_telemetry) SELECT * FROM cte;") == True


def test_sql_security_blocks_destructive_commands():
    assert validate_read_only_query("DROP TABLE silver_cell_telemetry;") == False
    assert validate_read_only_query("DELETE FROM gold_network_incidents WHERE 1=1;") == False
    assert validate_read_only_query("UPDATE silver_cell_telemetry SET latency_ms = 0;") == False
    assert validate_read_only_query("INSERT INTO dim_cells VALUES ('hacked');") == False
    assert validate_read_only_query("TRUNCATE TABLE silver_cell_telemetry;") == False
    assert validate_read_only_query("ATTACH 'evil.db' AS evil;") == False
    assert validate_read_only_query("PRAGMA show_tables;") == False
