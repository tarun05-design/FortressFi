"""
Domain Models and Schemas for ARGPE.

Provides typed dataclasses and Pydantic validation models for risk metrics,
guardrail statuses, portfolio decisions, and API payloads.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import numpy as np
from pydantic import BaseModel, Field

from engine.config import VolatilityRegime, ASSET_CLASSES


# ─── Risk & Guardrail Models ──────────────────────────────────────────────────

@dataclass
class RiskMetrics:
    """Computed portfolio risk metrics for a specific simulation tick."""
    var_95: float             # Value at Risk 95% (daily loss as positive %)
    cvar_95: float            # Conditional VaR 95% (daily loss as positive %)
    max_drawdown: float       # Peak-to-trough decline (positive %)
    current_drawdown: float   # Current decline from peak (positive %)
    concentration_hhi: float  # Herfindahl-Hirschman concentration index (0-100)
    regime: str               # Current volatility regime name

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to JSON-serializable dictionary."""
        return {
            'var_95': round(float(self.var_95), 4),
            'cvar_95': round(float(self.cvar_95), 4),
            'max_drawdown': round(float(self.max_drawdown), 4),
            'current_drawdown': round(float(self.current_drawdown), 4),
            'concentration_hhi': round(float(self.concentration_hhi), 2),
            'regime': self.regime,
        }


@dataclass
class GuardrailStatus:
    """Result of evaluating tiered risk guardrails."""
    level: str                                  # MONITOR | WARN | ACT | CIRCUIT_BREAK
    metrics: RiskMetrics                        # Underlying risk metrics
    breaches: list[tuple[str, float, float]]    # (metric_name, value, limit)
    thresholds: dict[str, float]                # Active regime-adjusted limits
    explanation: str                            # Plain-language explanation for dashboard
    action_required: bool                       # Whether portfolio weights should change
    target_weights: Optional[np.ndarray] = None # Recommended reallocation if action required

    def to_dict(self) -> dict[str, Any]:
        """Serialize status to JSON-serializable dictionary."""
        res: dict[str, Any] = {
            'level': self.level,
            'metrics': self.metrics.to_dict(),
            'breaches': [
                {'metric': m, 'value': round(float(v), 4), 'limit': round(float(l), 4)}
                for m, v, l in self.breaches
            ],
            'thresholds': {k: round(float(v), 4) for k, v in self.thresholds.items()},
            'explanation': self.explanation,
            'action_required': self.action_required,
        }
        if self.target_weights is not None:
            res['target_weights'] = [round(float(w), 6) for w in self.target_weights.tolist()]
        return res


# ─── Decision Audit Trail ─────────────────────────────────────────────────────

@dataclass
class DecisionRecord:
    """
    Audit record for every autonomous system decision.
    Ensures complete institutional auditability for rebalances, warnings, and overrides.
    """
    timestamp: str                         # UTC ISO timestamp
    day: int                               # Simulation day
    action_type: str                       # INIT | REBALANCE | GUARDRAIL_WARN | GUARDRAIL_ACT | CIRCUIT_BREAK
    guardrail_level: str                   # MONITOR | WARN | ACT | CIRCUIT_BREAK
    explanation: str                       # Plain-language explanation
    weights_before: list[float]            # Weight vector before decision
    weights_after: list[float]             # Weight vector after decision
    trigger_metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, day: int, action_type: str, guardrail_level: str,
               explanation: str, weights_before: list[float], weights_after: list[float],
               trigger_metrics: Optional[dict[str, Any]] = None) -> "DecisionRecord":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            day=day,
            action_type=action_type,
            guardrail_level=guardrail_level,
            explanation=explanation,
            weights_before=[round(float(w), 6) for w in weights_before],
            weights_after=[round(float(w), 6) for w in weights_after],
            trigger_metrics=trigger_metrics or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'day': self.day,
            'action_type': self.action_type,
            'guardrail_level': self.guardrail_level,
            'explanation': self.explanation,
            'weights_before': self.weights_before,
            'weights_after': self.weights_after,
            'trigger_metrics': self.trigger_metrics,
        }


# ─── Optimization Result ──────────────────────────────────────────────────────

@dataclass
class OptimizationResult:
    """Detailed output from Mean-Variance / Quadratic optimization."""
    weights: np.ndarray
    expected_return: float
    expected_risk: float
    sharpe_estimate: float
    turnover: float
    regime: str
    risk_aversion: float
    success: bool
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            'weights': [round(float(w), 6) for w in self.weights.tolist()],
            'expected_return': round(float(self.expected_return), 4),
            'expected_risk': round(float(self.expected_risk), 4),
            'sharpe_estimate': round(float(self.sharpe_estimate), 4),
            'turnover': round(float(self.turnover), 2),
            'regime': self.regime,
            'risk_aversion': float(self.risk_aversion),
            'success': self.success,
            'message': self.message,
        }


# ─── API Payloads (Pydantic) ──────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    """Payload for what-if hypothetical stress test."""
    shocks: dict[str, float] = Field(
        ...,
        description="Dictionary mapping asset name to percentage shock (e.g. {'US Equity': -25.0})"
    )


class SimulationConfig(BaseModel):
    """Payload for configuring or resetting simulation."""
    scenario: str = Field(default="gradual_crash", description="Scenario identifier")
    seed: int = Field(default=42, description="Random seed for deterministic runs")
    tick_speed: float = Field(default=1.5, ge=0.1, le=10.0, description="Seconds per simulation tick")
    initial_nav: float = Field(default=100_000_000.0, gt=0, description="Starting capital in USD")
