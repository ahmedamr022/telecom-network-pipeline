from pathlib import Path
from typing import Optional, Any, List
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
    Guarantees idempotency via primary-key upsert deduplication.
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
            if if_exists == "replace":
                self._duck_conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                self._duck_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
            else:
                tables = [r[0] for r in self._duck_conn.execute("SHOW TABLES").fetchall()]
                if table_name not in tables:
                    self._duck_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
                else:
                    self._duck_conn.execute(f"INSERT INTO {table_name} SELECT * FROM df")

    def upsert_dataframe(self, table_name: str, df: pd.DataFrame, primary_keys: List[str]) -> None:
        """
        Idempotent write: Updates existing records or inserts new ones based on primary_keys.
        Guarantees that re-running the same batch or overlapping batches NEVER multiplies rows.
        """
        if df.empty:
            return

        clean_df = df.drop_duplicates(subset=primary_keys, keep="last")

        if self.use_postgres and self._pg_engine:
            # Staging table upsert for PostgreSQL
            staging_table = f"stg_{table_name}"
            with self._pg_engine.begin() as conn:
                clean_df.to_sql(staging_table, conn, if_exists="replace", index=False)
                pk_join = " AND ".join([f"{table_name}.{k} = {staging_table}.{k}" for k in primary_keys])
                conn.execute(text(f"""
                    DELETE FROM {table_name}
                    WHERE EXISTS (
                        SELECT 1 FROM {staging_table} WHERE {pk_join}
                    );
                """))
                conn.execute(text(f"INSERT INTO {table_name} SELECT * FROM {staging_table};"))
                conn.execute(text(f"DROP TABLE IF EXISTS {staging_table};"))
        else:
            # Idempotent staging upsert for DuckDB with automatic schema evolution
            tables = [r[0] for r in self._duck_conn.execute("SHOW TABLES").fetchall()]
            if table_name not in tables:
                self._duck_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM clean_df")
            else:
                # Evolve schema if new columns were added to the contract
                existing_cols = [c[0] for c in self._duck_conn.execute(f"DESCRIBE {table_name}").fetchall()]
                for col in clean_df.columns:
                    if col not in existing_cols:
                        col_type = "VARCHAR"
                        if pd.api.types.is_float_dtype(clean_df[col]):
                            col_type = "DOUBLE"
                        elif pd.api.types.is_integer_dtype(clean_df[col]):
                            col_type = "BIGINT"
                        elif pd.api.types.is_bool_dtype(clean_df[col]):
                            col_type = "BOOLEAN"
                        elif pd.api.types.is_datetime64_any_dtype(clean_df[col]):
                            col_type = "TIMESTAMP"
                        self._duck_conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type};")

                self._duck_conn.register("df_staging_view", clean_df)
                pk_cond = " AND ".join([f"{table_name}.{k} = df_staging_view.{k}" for k in primary_keys])
                self._duck_conn.execute(f"""
                    DELETE FROM {table_name}
                    WHERE EXISTS (
                        SELECT 1 FROM df_staging_view WHERE {pk_cond}
                    );
                """)
                self._duck_conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM df_staging_view;")
                self._duck_conn.unregister("df_staging_view")

    def close(self):
        if self._duck_conn:
            self._duck_conn.close()
        if self._pg_engine:
            self._pg_engine.dispose()


# Global DB instance
db_engine = DatabaseEngine()
