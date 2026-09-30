import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _reset_persistence_breaker():
    from app import persistence_breaker

    persistence_breaker.reset()
    yield
    persistence_breaker.reset()