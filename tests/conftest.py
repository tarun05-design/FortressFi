"""
Shared Pytest Fixtures for ARGPE Test Suite.
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient

from engine import (
    ASSET_CLASSES,
    MarketSimulator,
    OptimizationEngine,
    Portfolio,
    RiskEngine,
    VolatilityRegime,
)
from server import app, service


@pytest.fixture
def clean_service():
    """Provides a fresh simulation service before each test."""
    service.reset(scenario="gradual_crash", seed=42, initial_nav=100_000_000.0, tick_speed=1.0)
    yield service
    service.reset()


@pytest.fixture
def test_client(clean_service):
    """FastAPI TestClient initialized with fresh service state."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def market_sim():
    """Deterministic MarketSimulator initialized with normal scenario."""
    return MarketSimulator(scenario="normal", seed=123)


@pytest.fixture
def portfolio():
    """Standard initial portfolio with $100M capital."""
    return Portfolio(initial_nav=100_000_000.0)


@pytest.fixture
def optimizer():
    """OptimizationEngine instance."""
    return OptimizationEngine()


@pytest.fixture
def risk_engine():
    """RiskEngine instance."""
    return RiskEngine()


@pytest.fixture
def synthetic_returns():
    """Synthetic returns history (100 days x 6 assets) with realistic variance."""
    rng = np.random.default_rng(999)
    # Daily returns ~ N(0.0003, 0.01)
    return rng.normal(loc=0.0003, scale=0.01, size=(100, len(ASSET_CLASSES)))
