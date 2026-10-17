from pathlib import Path
from typing import Optional, Any
import duckdb
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import settings
from config.logging_config import logger


class DatabaseEngine:
    """
    Dual-mode Database Engine supporting both production PostgreSQL/TimescaleDB
    and embedded DuckDB for zero-dependency local execution.
    """

    def __init__(self, use_postgres: bool = False):
        self.use_postgres = use_postgres or settings.USE_POSTGRES
        self._pg_engine: Optional[Engine] = None
        self._duck_conn: Optional[duckdb.DuckDBPyConnection] = None

        if self.use_postgres:
            try:
                self._pg_engine = create_engine(
                    settings.postgres_connection_string,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True
                )
                # Test connectivity
                with self._pg_engine.connect() as conn:
                    conn.execute(text("SELECT 1;"))
                logger.info(f"Connected to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            except Exception as e:
                logger.warning(f"PostgreSQL connection failed ({e}). Falling back to DuckDB storage.")
                self.use_postgres = False

        if not self.use_postgres:
            settings.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._duck_conn = duckdb.connect(str(settings.DUCKDB_PATH))
            logger.info(f"Connected to DuckDB Lakehouse at {settings.DUCKDB_PATH}")

    def query(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Executes a SQL query and returns a Pandas DataFrame."""
        if self.use_postgres and self._pg_engine:
            with self._pg_engine.connect() as conn:
                return pd.read_sql_query(text(sql), conn, params=params)
        else:
            return self._duck_conn.execute(sql, params).fetchdf()

    def execute(self, sql: str, params: Optional[dict] = None) -> None:
        """Executes a DDL or non-query SQL command."""
        if self.use_postgres and self._pg_engine:
            with self._pg_engine.begin() as conn:
                conn.execute(text(sql), params or {})
        else:
            if params:
                self._duck_conn.execute(sql, params)
            else:
                self._duck_conn.execute(sql)

    def write_dataframe(self, table_name: str, df: pd.DataFrame, if_exists: str = "append") -> None:
        """Writes a DataFrame to the designated table in DuckDB or PostgreSQL."""
        if df.empty:
            return

        if self.use_postgres and self._pg_engine:
            df.to_sql(table_name, self._pg_engine, if_exists=if_exists, index=False, method="multi", chunksize=1000)
        else:
            # Register in DuckDB
            if if_exists == "replace":
                self._duck_conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                self._duck_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
            else:
                # Check if table exists
                tables = [r[0] for r in self._duck_conn.execute("SHOW TABLES").fetchall()]
                if table_name not in tables:
                    self._duck_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
                else:
                    self._duck_conn.execute(f"INSERT INTO {table_name} SELECT * FROM df")

    def close(self):
        if self._duck_conn:
            self._duck_conn.close()
        if self._pg_engine:
            self._pg_engine.dispose()


# Global DB instance
db_engine = DatabaseEngine()
