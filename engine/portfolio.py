"""
Portfolio State Manager: Central state for holdings, NAV history, and decision audit trail.

Tracks current portfolio weights and dollar values, maintains full history for charting,
and records every automated decision (rebalance, guardrail action, circuit break) with
plain-language explanations for the dashboard audit log.

Performance metrics (Sharpe, Sortino, max drawdown, cumulative return) are computed
efficiently with incremental O(1) drawdown tracking.
"""

from typing import Any, Optional
import numpy as np

from engine.config import ASSET_CLASSES
from engine.models import DecisionRecord


class Portfolio:
    """
    Manages portfolio state, NAV history, performance metrics, and decision audit trail.

    Attributes:
        weights: Current portfolio weight allocation (sums to 1.0)
        nav: Current net asset value (USD)
        initial_nav: Starting NAV for return calculations
        peak_nav: Running peak NAV for drawdown calculations
        max_drawdown: Incremental running maximum drawdown (percentage)
    """

    def __init__(self, initial_nav: float = 100_000_000.0,
                 initial_weights: Optional[np.ndarray] = None):
        """
        Initialize portfolio with starting capital and optional initial weights.

        Args:
            initial_nav: Starting net asset value (default $100M)
            initial_weights: Starting allocation weights. If None, uses default 60/40 style baseline.
        """
        self._init_state(initial_nav=initial_nav, initial_weights=initial_weights)

    def _init_state(self, initial_nav: float, initial_weights: Optional[np.ndarray] = None) -> None:
        """Internal state initializer shared by __init__ and reset."""
        self.n_assets: int = len(ASSET_CLASSES)
        self.initial_nav: float = float(initial_nav)
        self.nav: float = float(initial_nav)
        self.peak_nav: float = float(initial_nav)
        self.max_drawdown: float = 0.0

        # Initial allocation
        if initial_weights is not None:
            w = np.array(initial_weights, dtype=np.float64)
            w = np.maximum(w, 0.0)
            self.weights: np.ndarray = w / np.sum(w)
        else:
            # Default institutional multi-asset benchmark:
            # 30% US Eq, 15% Intl Eq, 25% Govt Bonds, 10% Corp Bonds, 10% Commodities, 10% Cash
            self.weights = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10], dtype=np.float64)

        # History tracking
        self.nav_history: list[float] = [self.nav]
        self.weight_history: list[np.ndarray] = [self.weights.copy()]
        self.return_history: list[float] = []  # Daily simple portfolio returns
        self.day_history: list[int] = [0]

        # Audit trail
        self.decisions: list[DecisionRecord] = []
        self.guardrail_level: str = "MONITOR"

        # Record initialization
        self._log_decision(
            day=0,
            action_type="INIT",
            guardrail_level="MONITOR",
            explanation=(
                f"Portfolio initialized with ${self.initial_nav / 1e6:.0f}M capital. "
                f"Starting allocation: {self._format_weights(self.weights)}."
            ),
            weights_before=self.weights.tolist(),
            weights_after=self.weights.tolist(),
        )

    def update_with_returns(self, daily_returns: np.ndarray, day: int) -> None:
        """
        Update portfolio state with a new day's asset returns.

        Each asset's value changes by its return, then weights are recalculated
        from the new dollar values (natural market drift).

        Args:
            daily_returns: Array of daily log-returns for each asset class
            day: Current simulation day number
        """
        # Convert log-returns to simple returns: r = exp(log_r) - 1
        simple_returns = np.exp(daily_returns) - 1.0

        # Dollar value per position
        dollar_values = self.nav * self.weights

        # Update position values with returns
        new_dollar_values = dollar_values * (1.0 + simple_returns)

        # New total NAV
        new_nav = float(np.sum(new_dollar_values))

        # Portfolio daily return
        portfolio_return = (new_nav / self.nav) - 1.0 if self.nav > 0 else 0.0

        # Update weights from dollar values (natural drift)
        if new_nav > 0:
            self.weights = np.maximum(new_dollar_values / new_nav, 0.0)
            w_sum = np.sum(self.weights)
            if w_sum > 0:
                self.weights /= w_sum

        self.nav = new_nav

        # Incremental drawdown tracking (O(1))
        if new_nav > self.peak_nav:
            self.peak_nav = new_nav
        elif self.peak_nav > 0:
            current_dd = ((self.peak_nav - new_nav) / self.peak_nav) * 100.0
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd

        # Record histories
        self.nav_history.append(new_nav)
        self.weight_history.append(self.weights.copy())
        self.return_history.append(portfolio_return)
        self.day_history.append(day)

    def set_weights(self, new_weights: np.ndarray, day: int, action_type: str,
                    guardrail_level: str, explanation: str,
                    trigger_metrics: Optional[dict[str, Any]] = None) -> None:
        """
        Set new portfolio weights (rebalance or risk override) and log the decision.

        Args:
            new_weights: New target weights (sums to 1.0)
            day: Current simulation day
            action_type: Action classification
            guardrail_level: Active guardrail level
            explanation: Plain-language explanation for audit log
            trigger_metrics: Optional metrics that triggered this action
        """
        old_weights = self.weights.copy()
        w = np.array(new_weights, dtype=np.float64)
        w = np.maximum(w, 0.0)
        w_sum = np.sum(w)
        if w_sum > 0:
            w /= w_sum
        self.weights = w

        self.guardrail_level = guardrail_level

        self._log_decision(
            day=day,
            action_type=action_type,
            guardrail_level=guardrail_level,
            explanation=explanation,
            weights_before=old_weights.tolist(),
            weights_after=self.weights.tolist(),
            trigger_metrics=trigger_metrics or {},
        )

    def _log_decision(self, day: int, action_type: str, guardrail_level: str,
                      explanation: str, weights_before: list[float], weights_after: list[float],
                      trigger_metrics: Optional[dict[str, Any]] = None) -> None:
        """Record an immutable decision in the audit trail."""
        record = DecisionRecord.create(
            day=day,
            action_type=action_type,
            guardrail_level=guardrail_level,
            explanation=explanation,
            weights_before=weights_before,
            weights_after=weights_after,
            trigger_metrics=trigger_metrics or {},
        )
        self.decisions.append(record)

    def log_warning(self, day: int, explanation: str,
                    trigger_metrics: Optional[dict[str, Any]] = None) -> None:
        """Log a WARN-level guardrail event without modifying current weights."""
        self.guardrail_level = "WARN"
        self._log_decision(
            day=day,
            action_type="GUARDRAIL_WARN",
            guardrail_level="WARN",
            explanation=explanation,
            weights_before=self.weights.tolist(),
            weights_after=self.weights.tolist(),
            trigger_metrics=trigger_metrics or {},
        )

    # ─── Performance Metrics (Vectorized & Fast) ──────────────────────────

    def get_cumulative_return(self) -> float:
        """Total return since inception as a percentage."""
        if self.initial_nav == 0:
            return 0.0
        return ((self.nav / self.initial_nav) - 1.0) * 100.0

    def get_max_drawdown(self) -> float:
        """Maximum peak-to-trough decline as a percentage (positive number = loss)."""
        return float(self.max_drawdown)

    def get_current_drawdown(self) -> float:
        """Current drawdown from peak as a percentage."""
        if self.peak_nav == 0:
            return 0.0
        return max(0.0, ((self.peak_nav - self.nav) / self.peak_nav) * 100.0)

    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Annualized Sharpe ratio computed from return history."""
        if len(self.return_history) < 5:
            return 0.0
        returns = np.array(self.return_history, dtype=np.float64)
        daily_rf = risk_free_rate / 252.0
        excess = returns - daily_rf
        vol = np.std(excess, ddof=1)
        if vol == 0 or np.isnan(vol):
            return 0.0
        return float(np.mean(excess) / vol * np.sqrt(252.0))

    def get_sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Annualized Sortino ratio (downside deviation only)."""
        if len(self.return_history) < 5:
            return 0.0
        returns = np.array(self.return_history, dtype=np.float64)
        daily_rf = risk_free_rate / 252.0
        excess = returns - daily_rf
        downside = excess[excess < 0]
        if len(downside) == 0:
            return 0.0
        downside_vol = np.std(downside, ddof=1 if len(downside) > 1 else 0)
        if downside_vol == 0 or np.isnan(downside_vol):
            return 0.0
        return float(np.mean(excess) / downside_vol * np.sqrt(252.0))

    def get_daily_pnl(self) -> float:
        """Most recent day's P&L in USD."""
        if len(self.nav_history) < 2:
            return 0.0
        return self.nav_history[-1] - self.nav_history[-2]

    def get_concentration_hhi(self) -> float:
        """
        Herfindahl-Hirschman Index: measures portfolio concentration.
        HHI = Σ(wᵢ²). Normalized to 0-100 scale.
        """
        return float(np.sum(self.weights ** 2) * 100.0)

    # ─── Drift & Turnover Calculation ─────────────────────────────────────

    def get_max_drift(self, target_weights: np.ndarray) -> float:
        """Maximum single-asset absolute drift from target weights."""
        return float(np.max(np.abs(self.weights - target_weights)))

    def get_total_turnover(self, target_weights: np.ndarray) -> float:
        """Total one-way turnover required to rebalance to target weights."""
        return float(np.sum(np.abs(self.weights - target_weights)))

    # ─── Serialization & Inspection ───────────────────────────────────────

    def _format_weights(self, weights: np.ndarray) -> str:
        """Format weights as a readable string."""
        parts = []
        for name, w in zip(ASSET_CLASSES, weights):
            if w > 0.005:
                parts.append(f"{name} {w * 100:.1f}%")
        return ", ".join(parts)

    def get_state(self) -> dict[str, Any]:
        """Return current portfolio state as a JSON-serializable dict."""
        return {
            'nav': round(self.nav, 2),
            'initial_nav': self.initial_nav,
            'weights': [round(float(w), 6) for w in self.weights.tolist()],
            'asset_names': ASSET_CLASSES,
            'guardrail_level': self.guardrail_level,
            'cumulative_return': round(self.get_cumulative_return(), 4),
            'current_drawdown': round(self.get_current_drawdown(), 4),
            'max_drawdown': round(self.get_max_drawdown(), 4),
            'sharpe_ratio': round(self.get_sharpe_ratio(), 4),
            'sortino_ratio': round(self.get_sortino_ratio(), 4),
            'daily_pnl': round(self.get_daily_pnl(), 2),
            'concentration_hhi': round(self.get_concentration_hhi(), 2),
            'day': self.day_history[-1] if self.day_history else 0,
        }

    def get_history(self) -> dict[str, Any]:
        """Return full history for charting."""
        return {
            'days': self.day_history,
            'nav': [round(n, 2) for n in self.nav_history],
            'weights': [[round(float(val), 6) for val in w] for w in self.weight_history],
            'returns': [round(r, 6) for r in self.return_history],
            'asset_names': ASSET_CLASSES,
        }

    def get_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent decisions ordered newest to oldest."""
        recent = self.decisions[-limit:] if limit else self.decisions
        return [d.to_dict() for d in reversed(recent)]

    def reset(self, initial_nav: Optional[float] = None,
              initial_weights: Optional[np.ndarray] = None) -> None:
        """Reset portfolio to initial clean state."""
        self._init_state(
            initial_nav=initial_nav if initial_nav is not None else self.initial_nav,
            initial_weights=initial_weights,
        )
