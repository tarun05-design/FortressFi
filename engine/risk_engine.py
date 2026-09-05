"""
Risk Guardrail Engine: CVaR monitoring and tiered guardrail response system.

Computes risk metrics each tick (VaR, CVaR, drawdown, concentration) and classifies
the portfolio's risk status into one of four institutional guardrail levels:

    🟢 MONITOR       : All metrics within bounds, normal operation
    🟡 WARN          : Any metric approaching limit (>80%), tighten sensitivity
    🔴 ACT           : Any metric breaches limit, force proportional de-risking
    ⚫ CIRCUIT_BREAK  : Severe breach, override to defensive allocation

CVaR is computed via historical simulation (sort returns, mean of worst α%).
Thresholds are dynamically regime-adjusted: limits tighten in high volatility and crisis.
"""

from typing import Any, Optional
import numpy as np

from engine.config import (
    ASSET_CLASSES,
    BASE_THRESHOLDS,
    REGIME_THRESHOLD_MULTIPLIER,
    WARN_FRACTION,
    CIRCUIT_BREAK_DRAWDOWN,
    CIRCUIT_BREAK_CVAR_MULT,
    RECOVERY_DRAWDOWN,
    DEFENSIVE_WEIGHTS,
    ACT_ADJUSTMENT,
    WEIGHT_BOUNDS,
    VolatilityRegime,
)
from engine.models import RiskMetrics, GuardrailStatus


class RiskEngine:
    """
    Multi-metric risk monitoring with tiered guardrail response.

    Evaluates portfolio risk each tick and escalates through guardrail levels:
    MONITOR → WARN → ACT → CIRCUIT_BREAK
    """

    def __init__(self):
        self.is_circuit_broken: bool = False
        self.circuit_break_day: Optional[int] = None
        self.metrics_history: list[dict[str, Any]] = []

    def compute_var_cvar(self, portfolio_returns: np.ndarray,
                         confidence: float = 0.95) -> tuple[float, float]:
        """
        Compute VaR and CVaR (Expected Shortfall) via historical simulation.

        VaR: The loss at the (1 - confidence) quantile.
        CVaR: The conditional expected loss beyond VaR.
        Both returned as positive percentages (e.g. 2.5 means a 2.5% daily loss).

        Args:
            portfolio_returns: Array of daily simple portfolio returns
            confidence: Confidence level (default 0.95)

        Returns:
            (var_95, cvar_95) as positive percentage floats
        """
        if len(portfolio_returns) < 5:
            return 0.0, 0.0

        sorted_returns = np.sort(portfolio_returns)
        # Quantile index
        var_index = max(1, int(np.floor((1.0 - confidence) * len(sorted_returns))))

        # VaR is the negative of the return at quantile
        var = max(0.0, -float(sorted_returns[var_index - 1]) * 100.0)

        # CVaR is the average loss of all observations up to var_index
        tail_returns = sorted_returns[:var_index]
        cvar = max(0.0, -float(np.mean(tail_returns)) * 100.0)

        return var, cvar

    def compute_metrics(self, portfolio_returns: list[float],
                        current_drawdown: float, max_drawdown: float,
                        weights: np.ndarray,
                        regime: VolatilityRegime) -> RiskMetrics:
        """
        Compute all portfolio risk metrics for the current tick.

        Args:
            portfolio_returns: List of daily returns
            current_drawdown: Current drawdown from peak (%)
            max_drawdown: Max drawdown from peak (%)
            weights: Current portfolio weight vector
            regime: Active volatility regime

        Returns:
            RiskMetrics dataclass
        """
        lookback = min(60, len(portfolio_returns))
        if lookback >= 5:
            recent_returns = np.array(portfolio_returns[-lookback:], dtype=np.float64)
            var_95, cvar_95 = self.compute_var_cvar(recent_returns)
        else:
            var_95, cvar_95 = 0.0, 0.0

        concentration = float(np.sum(np.asarray(weights, dtype=np.float64) ** 2) * 100.0)

        return RiskMetrics(
            var_95=var_95,
            cvar_95=cvar_95,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            concentration_hhi=concentration,
            regime=regime.value,
        )

    def evaluate_guardrails(self, metrics: RiskMetrics,
                            regime: VolatilityRegime,
                            current_weights: np.ndarray,
                            day: int) -> GuardrailStatus:
        """
        Evaluate guardrail thresholds and determine response level:
        MONITOR, WARN, ACT, or CIRCUIT_BREAK.

        Args:
            metrics: Current risk metrics
            regime: Current volatility regime
            current_weights: Active allocation weights
            day: Simulation day index

        Returns:
            GuardrailStatus detailing action, breaches, and target allocation if needed
        """
        multiplier = REGIME_THRESHOLD_MULTIPLIER.get(regime, 1.0)
        thresholds = {k: float(v * multiplier) for k, v in BASE_THRESHOLDS.items()}

        self.metrics_history.append(metrics.to_dict())

        # ─── 1. Check Circuit Breaker Recovery ─────────────────────────────
        if self.is_circuit_broken:
            if metrics.current_drawdown < RECOVERY_DRAWDOWN and regime != VolatilityRegime.CRISIS:
                self.is_circuit_broken = False
                self.circuit_break_day = None
                return GuardrailStatus(
                    level="MONITOR",
                    metrics=metrics,
                    breaches=[],
                    thresholds=thresholds,
                    explanation=(
                        f"[CIRCUIT BREAKER RELEASED]: Drawdown recovered to "
                        f"{metrics.current_drawdown:.1f}% (below {RECOVERY_DRAWDOWN}% threshold) "
                        f"and volatility regime is {regime.value}. Resuming normal operation."
                    ),
                    action_required=False,
                )
            else:
                lockdown_duration = (day - self.circuit_break_day) if self.circuit_break_day is not None else 0
                return GuardrailStatus(
                    level="CIRCUIT_BREAK",
                    metrics=metrics,
                    breaches=[("circuit_break_active", metrics.current_drawdown, RECOVERY_DRAWDOWN)],
                    thresholds=thresholds,
                    explanation=(
                        f"[CIRCUIT BREAKER ACTIVE] (day {lockdown_duration} of lockdown). "
                        f"Drawdown at {metrics.current_drawdown:.1f}% "
                        f"(needs < {RECOVERY_DRAWDOWN}% to release). "
                        f"Regime: {regime.value}. Maintaining defensive allocation."
                    ),
                    action_required=False,
                )

        # ─── 2. Check Circuit Breaker Trigger ──────────────────────────────
        cvar_limit = thresholds['cvar_95'] * CIRCUIT_BREAK_CVAR_MULT
        if metrics.current_drawdown >= CIRCUIT_BREAK_DRAWDOWN or metrics.cvar_95 >= cvar_limit:
            self.is_circuit_broken = True
            self.circuit_break_day = day

            trigger_reasons: list[str] = []
            if metrics.current_drawdown >= CIRCUIT_BREAK_DRAWDOWN:
                trigger_reasons.append(
                    f"drawdown hit {metrics.current_drawdown:.1f}% (limit: {CIRCUIT_BREAK_DRAWDOWN}%)"
                )
            if metrics.cvar_95 >= cvar_limit:
                trigger_reasons.append(
                    f"CVaR hit {metrics.cvar_95:.2f}% (limit: {cvar_limit:.2f}%)"
                )

            return GuardrailStatus(
                level="CIRCUIT_BREAK",
                metrics=metrics,
                breaches=[("circuit_break", metrics.current_drawdown, CIRCUIT_BREAK_DRAWDOWN)],
                thresholds=thresholds,
                explanation=(
                    f"[CIRCUIT BREAKER TRIGGERED] {' and '.join(trigger_reasons)}. "
                    f"Moving to defensive allocation: {self._format_defensive_weights()}. "
                    f"Optimization suspended until drawdown drops below {RECOVERY_DRAWDOWN}%."
                ),
                action_required=True,
                target_weights=DEFENSIVE_WEIGHTS.copy(),
            )

        # ─── 3. Check ACT-level Breaches ──────────────────────────────────
        breaches: list[tuple[str, float, float]] = []
        metric_checks = [
            ('var_95', metrics.var_95, thresholds['var_95']),
            ('cvar_95', metrics.cvar_95, thresholds['cvar_95']),
            ('max_drawdown', metrics.max_drawdown, thresholds['max_drawdown']),
            ('concentration_hhi', metrics.concentration_hhi, thresholds['concentration_hhi']),
        ]

        for name, value, limit in metric_checks:
            if value >= limit:
                breaches.append((name, value, limit))

        if breaches:
            target_weights = self._compute_derisked_weights(current_weights)
            breach_descs = [f"{name} at {val:.2f}% (limit: {lim:.2f}%)" for name, val, lim in breaches]

            return GuardrailStatus(
                level="ACT",
                metrics=metrics,
                breaches=breaches,
                thresholds=thresholds,
                explanation=(
                    f"[GUARDRAIL ACT] Breach detected -- {'; '.join(breach_descs)}. "
                    f"Forcing de-risk: reducing equity exposure by "
                    f"{ACT_ADJUSTMENT['equity_reduction'] * 100:.0f}%, redistributing to bonds and cash."
                ),
                action_required=True,
                target_weights=target_weights,
            )

        # ─── 4. Check WARN-level Approaches ───────────────────────────────
        warnings: list[tuple[str, float, float]] = []
        for name, value, limit in metric_checks:
            if value >= limit * WARN_FRACTION:
                warnings.append((name, value, limit))

        if warnings:
            warn_descs = []
            for name, val, lim in warnings:
                pct_of_limit = (val / lim) * 100.0 if lim > 0 else 0.0
                warn_descs.append(f"{name} at {val:.2f}% ({pct_of_limit:.0f}% of {lim:.2f}% limit)")

            return GuardrailStatus(
                level="WARN",
                metrics=metrics,
                breaches=warnings,
                thresholds=thresholds,
                explanation=(
                    f"[GUARDRAIL WARN] Approaching limits -- {'; '.join(warn_descs)}. "
                    f"Tightening rebalancing sensitivity. Regime: {regime.value}."
                ),
                action_required=False,
            )

        # ─── 5. Normal Operation: MONITOR ─────────────────────────────────
        return GuardrailStatus(
            level="MONITOR",
            metrics=metrics,
            breaches=[],
            thresholds=thresholds,
            explanation=(
                f"[MONITOR] All risk metrics within bounds. "
                f"VaR: {metrics.var_95:.2f}%, CVaR: {metrics.cvar_95:.2f}%, "
                f"Drawdown: {metrics.current_drawdown:.2f}%, HHI: {metrics.concentration_hhi:.1f}. "
                f"Regime: {regime.value}."
            ),
            action_required=False,
        )

    def _compute_derisked_weights(self, current_weights: np.ndarray) -> np.ndarray:
        """
        Compute de-risked weights for ACT-level response.
        Reduces equities and commodities, reallocating capital to govt bonds and cash.
        """
        new_weights = np.array(current_weights, dtype=np.float64)

        equity_indices = [0, 1]  # US Equity, Intl Equity
        freed_capital = 0.0

        for idx in equity_indices:
            reduction = new_weights[idx] * ACT_ADJUSTMENT['equity_reduction']
            new_weights[idx] -= reduction
            freed_capital += reduction

        # Also reduce commodities (index 4) by half of equity reduction factor
        commodity_reduction = new_weights[4] * (ACT_ADJUSTMENT['equity_reduction'] * 0.5)
        new_weights[4] -= commodity_reduction
        freed_capital += commodity_reduction

        # Reallocate freed capital: 60% Govt Bonds (idx 2), 40% Cash (idx 5)
        new_weights[2] += freed_capital * 0.60
        new_weights[5] += freed_capital * 0.40

        # Enforce bounds
        for i, name in enumerate(ASSET_CLASSES):
            min_w, max_w = WEIGHT_BOUNDS[name]
            new_weights[i] = np.clip(new_weights[i], min_w, max_w)

        # Renormalize
        w_sum = np.sum(new_weights)
        if w_sum > 0:
            new_weights /= w_sum

        return new_weights

    def _format_defensive_weights(self) -> str:
        """Format defensive allocation for summary text."""
        parts = []
        for name, w in zip(ASSET_CLASSES, DEFENSIVE_WEIGHTS):
            if w > 0.01:
                parts.append(f"{name} {w * 100:.0f}%")
        return ", ".join(parts)

    def evaluate_scenario(self, current_weights: np.ndarray,
                          shock_returns: np.ndarray,
                          portfolio_returns: list[float],
                          current_nav: float,
                          peak_nav: float,
                          regime: VolatilityRegime) -> dict[str, Any]:
        """
        Evaluate a hypothetical stress test scenario (what-if analysis).
        Applies shock returns without mutating real portfolio state.
        """
        w = np.asarray(current_weights, dtype=np.float64)
        simple_shock = np.exp(shock_returns) - 1.0

        dollar_values = current_nav * w
        new_values = dollar_values * (1.0 + simple_shock)
        projected_nav = float(np.sum(new_values))

        projected_return = (projected_nav / current_nav) - 1.0 if current_nav > 0 else 0.0
        projected_weights = new_values / projected_nav if projected_nav > 0 else w

        projected_drawdown = max(0.0, ((peak_nav - projected_nav) / peak_nav) * 100.0) if peak_nav > 0 else 0.0

        # Augment returns with projected shock
        augmented_returns = list(portfolio_returns) + [projected_return]
        var, cvar = self.compute_var_cvar(np.array(augmented_returns[-60:], dtype=np.float64))

        projected_hhi = float(np.sum(projected_weights ** 2) * 100.0)

        projected_metrics = RiskMetrics(
            var_95=var,
            cvar_95=cvar,
            max_drawdown=max(projected_drawdown, 0.0),
            current_drawdown=projected_drawdown,
            concentration_hhi=projected_hhi,
            regime=regime.value,
        )

        # Preserve engine state prior to hypothetical evaluation
        prev_circuit_broken = self.is_circuit_broken
        prev_circuit_break_day = self.circuit_break_day

        guardrail_result = self.evaluate_guardrails(
            projected_metrics, regime, projected_weights, day=-1
        )

        # Undo side-effects of hypothetical evaluation
        self.is_circuit_broken = prev_circuit_broken
        self.circuit_break_day = prev_circuit_break_day
        if len(self.metrics_history) > 0:
            self.metrics_history.pop()

        return {
            'projected_nav': round(projected_nav, 2),
            'projected_return_pct': round(projected_return * 100.0, 4),
            'projected_weights': [round(float(val), 6) for val in projected_weights.tolist()],
            'projected_pnl': round(projected_nav - current_nav, 2),
            'projected_metrics': projected_metrics.to_dict(),
            'guardrail_response': guardrail_result.to_dict(),
            'asset_names': ASSET_CLASSES,
        }

    def reset(self) -> None:
        """Reset risk engine state."""
        self.is_circuit_broken = False
        self.circuit_break_day = None
        self.metrics_history = []
