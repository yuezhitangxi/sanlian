from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
GENERATOR_PATH = PROJECT_DIR / "three_chain_mock_generator_v2.py"

load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:password@127.0.0.1:3306/three_chain_demo?charset=utf8mb4",
)

