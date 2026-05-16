from __future__ import annotations

import importlib.util
from types import ModuleType

from .config import GENERATOR_PATH


def load_generator_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("three_chain_mock_generator_v2", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generator module from {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

