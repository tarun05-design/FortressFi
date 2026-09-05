"""
FortressFi Configuration: Centralized parameters for simulation, optimization, and risk guardrails.

This module houses all mathematical, structural, and regulatory constants
governing the FortressFi platform.
"""

from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class VolatilityRegime(str, Enum):
    """Market volatility regime classifications."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRISIS = "CRISIS"


# ─── Asset Class Universe ───────────────────────────────────────────────────────

ASSET_CLASSES: list[str] = [
    "US Equity",
    "Intl Equity",
    "Govt Bonds",
    "Corp Bonds",
    "Commodities",
    "Cash",
]

# Annualized expected returns (base drift prior to scenario scaling)
BASE_ANNUAL_RETURNS: np.ndarray = np.array([0.10, 0.08, 0.03, 0.045, 0.05, 0.02], dtype=np.float64)

# Annualized volatilities
BASE_ANNUAL_VOLS: np.ndarray = np.array([0.18, 0.22, 0.06, 0.08, 0.20, 0.005], dtype=np.float64)

# Base correlation matrix (normal market conditions)
# Structured so equities correlate, bonds hedge, commodities partially diversify
BASE_CORRELATION: np.ndarray = np.array([
    [1.00,  0.75, -0.20,  0.10,  0.30,  0.00],  # US Equity
    [0.75,  1.00, -0.15,  0.05,  0.35,  0.00],  # Intl Equity
    [-0.20, -0.15,  1.00,  0.60, -0.10,  0.05],  # Govt Bonds
    [0.10,  0.05,  0.60,  1.00,  0.05,  0.05],  # Corp Bonds
    [0.30,  0.35, -0.10,  0.05,  1.00,  0.00],  # Commodities
    [0.00,  0.00,  0.05,  0.05,  0.00,  1.00],  # Cash
], dtype=np.float64)

# Stressed correlation matrix (crisis regime: cross-asset correlations spike)
STRESSED_CORRELATION: np.ndarray = np.array([
    [1.00, 0.90, 0.10, 0.50, 0.60, 0.00],  # US Equity
    [0.90, 1.00, 0.15, 0.45, 0.65, 0.00],  # Intl Equity
    [0.10, 0.15, 1.00, 0.70, 0.20, 0.05],  # Govt Bonds
    [0.50, 0.45, 0.70, 1.00, 0.40, 0.05],  # Corp Bonds
    [0.60, 0.65, 0.20, 0.40, 1.00, 0.00],  # Commodities
    [0.00, 0.00, 0.05, 0.05, 0.00, 1.00],  # Cash
], dtype=np.float64)


# ─── Scenario Profiles ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScenarioProfile:
    """Configuration for a deterministic or stochastic market scenario."""
    name: str
    description: str
    # Each phase: (num_days, return_multiplier, vol_multiplier)
    phases: list[tuple[int, float, float]] = field(default_factory=list)


SCENARIOS: dict[str, ScenarioProfile] = {
    "normal": ScenarioProfile(
        name="Normal Markets",
        description="Steady markets with typical volatility and modest positive returns.",
        phases=[
            (252, 1.0, 1.0),
        ]
    ),
    "gradual_crash": ScenarioProfile(
        name="Gradual Crash",
        description="Markets slowly deteriorate, then crash, then partially recover.",
        phases=[
            (60, 1.0, 1.0),      # 60 days normal
            (40, 0.3, 1.5),      # 40 days deteriorating (lower returns, higher vol)
            (20, -3.0, 3.0),     # 20 days crash (negative returns, very high vol)
            (30, -1.0, 2.5),     # 30 days continued stress
            (50, 0.5, 1.8),      # 50 days early recovery
            (52, 1.0, 1.2),      # 52 days late recovery
        ]
    ),
    "sudden_shock": ScenarioProfile(
        name="Sudden Shock",
        description="Markets are calm, then experience a sharp sudden crash and quick recovery.",
        phases=[
            (80, 1.2, 0.8),      # 80 days calm bull market
            (5, -8.0, 5.0),      # 5-day violent crash
            (15, -2.0, 3.5),     # 15 days aftershock
            (40, 0.0, 2.0),      # 40 days stabilization
            (112, 1.0, 1.0),     # 112 days recovery to normal
        ]
    ),
    "recovery": ScenarioProfile(
        name="Recovery Rally",
        description="Starting from stressed conditions, markets steadily recover.",
        phases=[
            (30, -1.0, 2.5),     # 30 days of remaining stress
            (60, 0.5, 1.8),      # 60 days early recovery
            (80, 1.5, 1.0),      # 80 days strong recovery
            (82, 1.2, 0.8),      # 82 days bull continuation
        ]
    ),
}


# ─── Volatility Regime Thresholds ─────────────────────────────────────────────
# Based on annualized equity volatility (rolling 20-day realized vol * sqrt(252))

REGIME_THRESHOLDS: dict[VolatilityRegime, tuple[float, float]] = {
    VolatilityRegime.LOW: (0.0, 0.12),              # < 12% annualized
    VolatilityRegime.NORMAL: (0.12, 0.20),          # 12-20%
    VolatilityRegime.HIGH: (0.20, 0.35),            # 20-35%
    VolatilityRegime.CRISIS: (0.35, float('inf')),  # > 35%
}


# ─── Optimization Constraints & Hyperparameters ──────────────────────────────

# Per-asset allocation bounds: (min_weight, max_weight)
WEIGHT_BOUNDS: dict[str, tuple[float, float]] = {
    "US Equity":    (0.00, 0.45),
    "Intl Equity":  (0.00, 0.35),
    "Govt Bonds":   (0.05, 0.60),   # Must hold at least 5% in govt bonds (liquidity)
    "Corp Bonds":   (0.00, 0.30),
    "Commodities":  (0.00, 0.25),
    "Cash":         (0.05, 0.50),   # Must hold at least 5% cash (liquidity floor)
}

# Risk aversion parameter λ by regime
RISK_AVERSION: dict[VolatilityRegime, float] = {
    VolatilityRegime.LOW: 2.0,
    VolatilityRegime.NORMAL: 3.0,
    VolatilityRegime.HIGH: 6.0,
    VolatilityRegime.CRISIS: 12.0,
}

# Turnover penalty coefficient γ in objective function
TURNOVER_PENALTY: float = 0.005

# Maximum one-way turnover allowed per rebalance
MAX_TURNOVER: float = 0.40

# Drift threshold by regime: only rebalance if max single-asset drift exceeds this
DRIFT_THRESHOLD: dict[VolatilityRegime, float] = {
    VolatilityRegime.LOW: 0.06,     # 6%
    VolatilityRegime.NORMAL: 0.05,  # 5%
    VolatilityRegime.HIGH: 0.03,    # 3%
    VolatilityRegime.CRISIS: 0.02,  # 2%
}


# ─── Risk Guardrail Parameters ────────────────────────────────────────────────

# Base limits (normal regime): expressed as positive percentages
BASE_THRESHOLDS: dict[str, float] = {
    'var_95': 1.8,             # VaR 95% daily loss limit (%)
    'cvar_95': 2.8,            # CVaR 95% daily loss limit (%)
    'max_drawdown': 12.0,      # Maximum drawdown from peak (%)
    'concentration_hhi': 35.0, # Max HHI concentration (100 = single asset)
}

# Regime multiplier for limits (limits tighten when multiplier < 1.0)
REGIME_THRESHOLD_MULTIPLIER: dict[VolatilityRegime, float] = {
    VolatilityRegime.LOW: 1.2,     # More permissive in calm markets
    VolatilityRegime.NORMAL: 1.0,  # Standard baseline
    VolatilityRegime.HIGH: 0.75,   # Tighter limits
    VolatilityRegime.CRISIS: 0.60, # Tightly constrained
}

# Fraction of limit where WARN level is triggered
WARN_FRACTION: float = 0.80

# Hard circuit breaker conditions
CIRCUIT_BREAK_DRAWDOWN: float = 12.0   # Current drawdown >= 12% triggers circuit break
CIRCUIT_BREAK_CVAR_MULT: float = 2.0   # CVaR >= 2x regime limit triggers circuit break
RECOVERY_DRAWDOWN: float = 8.0         # Drawdown must recover below 8% to exit circuit break

# Defensive allocation during circuit break
DEFENSIVE_WEIGHTS: np.ndarray = np.array([0.10, 0.05, 0.45, 0.10, 0.05, 0.25], dtype=np.float64)

# ACT allocation adjustments (proportional de-risking)
ACT_ADJUSTMENT: dict[str, any] = {
    'equity_reduction': 0.30,        # Reduce equities by 30%
    'safe_redistribution': True,     # Proportionally allocate to bonds and cash
}
