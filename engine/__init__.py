"""
ARGPE Engine Package
Adaptive Risk-Guardrail Portfolio Engine

Core components:
- MarketSimulator: Generates correlated multi-asset returns with regime classification
- Portfolio: Manages portfolio state, NAV history, and decision audit trail
- OptimizationEngine: Mean-Variance portfolio optimization with constraints
- RiskEngine: CVaR monitoring and tiered guardrail system
"""

from engine.config import (
    ASSET_CLASSES,
    SCENARIOS,
    ScenarioProfile,
    VolatilityRegime,
    WEIGHT_BOUNDS,
    BASE_THRESHOLDS,
    REGIME_THRESHOLD_MULTIPLIER,
    WARN_FRACTION,
    CIRCUIT_BREAK_DRAWDOWN,
    CIRCUIT_BREAK_CVAR_MULT,
    RECOVERY_DRAWDOWN,
    DEFENSIVE_WEIGHTS,
    ACT_ADJUSTMENT,
    TURNOVER_PENALTY,
    MAX_TURNOVER,
    DRIFT_THRESHOLD,
    RISK_AVERSION,
    BASE_ANNUAL_RETURNS,
    BASE_ANNUAL_VOLS,
    BASE_CORRELATION,
    STRESSED_CORRELATION,
)
from engine.models import (
    DecisionRecord,
    GuardrailStatus,
    OptimizationResult,
    RiskMetrics,
    ScenarioRequest,
    SimulationConfig,
)
from engine.market_simulator import MarketSimulator
from engine.portfolio import Portfolio
from engine.optimization_engine import OptimizationEngine
from engine.risk_engine import RiskEngine

__all__ = [
    "MarketSimulator",
    "Portfolio",
    "OptimizationEngine",
    "RiskEngine",
    "VolatilityRegime",
    "RiskMetrics",
    "GuardrailStatus",
    "DecisionRecord",
    "OptimizationResult",
    "ScenarioRequest",
    "SimulationConfig",
    "ASSET_CLASSES",
    "SCENARIOS",
    "ScenarioProfile",
    "WEIGHT_BOUNDS",
    "BASE_THRESHOLDS",
    "REGIME_THRESHOLD_MULTIPLIER",
    "WARN_FRACTION",
    "CIRCUIT_BREAK_DRAWDOWN",
    "CIRCUIT_BREAK_CVAR_MULT",
    "RECOVERY_DRAWDOWN",
    "DEFENSIVE_WEIGHTS",
    "ACT_ADJUSTMENT",
    "TURNOVER_PENALTY",
    "MAX_TURNOVER",
    "DRIFT_THRESHOLD",
    "RISK_AVERSION",
    "BASE_ANNUAL_RETURNS",
    "BASE_ANNUAL_VOLS",
    "BASE_CORRELATION",
    "STRESSED_CORRELATION",
]
