from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import DATABASE_URL


def get_engine() -> Engine:
    return create_engine(DATABASE_URL, pool_pre_ping=True, future=True)


def ensure_metadata_tables(engine: Engine) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS simulation_run (
        run_id VARCHAR(64) PRIMARY KEY,
        run_name VARCHAR(128) NULL,
        generated_at DATETIME NOT NULL,
        output_dir VARCHAR(512) NOT NULL,
        seed INT NOT NULL,
        status VARCHAR(32) NOT NULL,
        error_message TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))

