"""
Optimization Engine: Mean-Variance portfolio optimization with SLSQP and analytical gradients.

Maximizes a quadratic risk-adjusted return objective:
    maximize  μᵀw - (λ/2) × wᵀΣw - γ × turnover_penalty(w)

Subject to:
    - Weights sum to 1 (fully invested): Σ wᵢ = 1
    - Per-asset bounds: min_wᵢ ≤ wᵢ ≤ max_wᵢ
    - Maximum turnover limit: Σ |wᵢ - wᵢ_current| ≤ MAX_TURNOVER

The risk aversion parameter λ adapts to the current volatility regime.
Includes vectorized parameter estimation and analytical gradient evaluations for
fast, high-precision convergence.
"""

from typing import Any, Optional
import numpy as np
from scipy.optimize import minimize

from engine.config import (
    ASSET_CLASSES,
    WEIGHT_BOUNDS,
    RISK_AVERSION,
    TURNOVER_PENALTY,
    MAX_TURNOVER,
    DRIFT_THRESHOLD,
    VolatilityRegime,
)
from engine.models import OptimizationResult


class OptimizationEngine:
    """
    Mean-Variance portfolio optimizer using scipy SLSQP.

    Finds optimal weights that maximize risk-adjusted returns subject to constraints.
    The optimizer adapts to market regimes through the risk aversion parameter λ.
    """

    def __init__(self):
        self.n_assets: int = len(ASSET_CLASSES)
        self.bounds: list[tuple[float, float]] = [WEIGHT_BOUNDS[name] for name in ASSET_CLASSES]
        self.last_optimal_weights: Optional[np.ndarray] = None

    def should_rebalance(self, current_weights: np.ndarray, regime: VolatilityRegime) -> bool:
        """
        Determine if rebalancing is warranted based on drift from last optimal weights.

        Only triggers rebalance if maximum single-asset drift exceeds the
        regime-adjusted threshold, avoiding unnecessary transaction churn.

        Args:
            current_weights: Current portfolio weights
            regime: Active volatility regime

        Returns:
            True if rebalancing should be executed
        """
        if self.last_optimal_weights is None:
            return True

        threshold = DRIFT_THRESHOLD.get(regime, 0.05)
        max_drift = float(np.max(np.abs(current_weights - self.last_optimal_weights)))
        return max_drift > threshold

    def optimize(self, expected_returns: np.ndarray, covariance_matrix: np.ndarray,
                 current_weights: np.ndarray, regime: VolatilityRegime) -> dict[str, Any]:
        """
        Run Mean-Variance quadratic optimization to determine optimal portfolio weights.

        Objective:
            minimize - ( μᵀw - (λ/2) wᵀΣw - γ Σ s(wᵢ - wᵢ_current) )
        where s(x) is a smooth pseudo-Huber approximation to |x| with analytical gradient.

        Args:
            expected_returns: Annualized expected returns vector (length N)
            covariance_matrix: Annualized covariance matrix (N x N)
            current_weights: Current portfolio weights (length N)
            regime: Current volatility regime

        Returns:
            dict with optimal weights, expected return, risk, Sharpe, turnover, etc.
        """
        risk_aversion = RISK_AVERSION.get(regime, 3.0)
        mu = np.asarray(expected_returns, dtype=np.float64)
        cov = np.asarray(covariance_matrix, dtype=np.float64)
        w0 = np.asarray(current_weights, dtype=np.float64)

        eps = 1e-4  # Smooth Huber regularization parameter

        # ─── Objective & Analytical Gradient ──────────────────────────────
        def objective(w: np.ndarray) -> float:
            port_return = float(np.dot(mu, w))
            port_variance = float(np.dot(w, cov @ w))
            diff = w - w0
            # Smooth L1 penalty: sqrt(dx^2 + eps^2) - eps
            smooth_turnover = float(np.sum(np.sqrt(diff ** 2 + eps ** 2) - eps))
            val = -(port_return - (risk_aversion / 2.0) * port_variance - TURNOVER_PENALTY * smooth_turnover)
            return val

        def objective_grad(w: np.ndarray) -> np.ndarray:
            # d/dw [-(mu^T w - (lambda/2) w^T Cov w - gamma * smooth_turnover)]
            # = -(mu - lambda * Cov @ w - gamma * diff / sqrt(diff^2 + eps^2))
            diff = w - w0
            d_turnover = diff / np.sqrt(diff ** 2 + eps ** 2)
            grad = -(mu - risk_aversion * (cov @ w) - TURNOVER_PENALTY * d_turnover)
            return grad

        # ─── Constraints ──────────────────────────────────────────────────
        constraints = [
            # Fully invested constraint: sum(w) = 1.0
            {'type': 'eq', 'fun': lambda w: float(np.sum(w) - 1.0), 'jac': lambda w: np.ones_like(w)},
            # Maximum one-way turnover limit
            {'type': 'ineq', 'fun': lambda w: float(MAX_TURNOVER - np.sum(np.abs(w - w0)))},
        ]

        # Warm start from current allocation
        x0 = w0.copy()

        result = minimize(
            objective,
            x0=x0,
            jac=objective_grad,
            method='SLSQP',
            bounds=self.bounds,
            constraints=constraints,
            options={'maxiter': 500, 'ftol': 1e-6},
        )

        if result.success:
            optimal_weights = result.x.copy()
            # Clean up tiny floating point residuals and renormalize
            optimal_weights = np.maximum(optimal_weights, 0.0)
            optimal_weights /= np.sum(optimal_weights)
            self.last_optimal_weights = optimal_weights.copy()
        else:
            # Fallback to current weights if solver fails
            optimal_weights = w0.copy()

        # Compute portfolio metrics
        port_return = float(np.dot(mu, optimal_weights))
        port_risk = float(np.sqrt(max(0.0, np.dot(optimal_weights, cov @ optimal_weights))))
        sharpe = port_return / port_risk if port_risk > 1e-6 else 0.0
        turnover = float(np.sum(np.abs(optimal_weights - w0)))

        opt_result = OptimizationResult(
            weights=optimal_weights,
            expected_return=round(port_return * 100.0, 4),
            expected_risk=round(port_risk * 100.0, 4),
            sharpe_estimate=round(sharpe, 4),
            turnover=round(turnover * 100.0, 2),
            regime=regime.value,
            risk_aversion=risk_aversion,
            success=bool(result.success),
            message=str(result.message),
        )

        return opt_result.to_dict()

    def estimate_parameters(self, return_history: np.ndarray,
                            halflife: int = 60) -> tuple[np.ndarray, np.ndarray]:
        """
        Estimate annualized expected returns and covariance matrix from return history.

        Uses exponentially-weighted decay so recent observations carry more weight.
        Fully vectorized NumPy implementation for high execution speed.

        Args:
            return_history: (T x N) matrix of daily returns
            halflife: Exponential decay halflife in days (default 60)

        Returns:
            (expected_returns, covariance_matrix): annualized
        """
        T, N = return_history.shape

        if T < 10:
            return np.ones(N, dtype=np.float64) * 0.03, np.eye(N, dtype=np.float64) * 0.01

        # Exponential decay weights
        decay = np.log(2.0) / halflife
        weights = np.exp(-decay * np.arange(T)[::-1])
        weights /= np.sum(weights)

        # Weighted mean returns (annualized)
        mu = np.average(return_history, axis=0, weights=weights) * 252.0

        # Vectorized weighted covariance
        deviations = return_history - np.average(return_history, axis=0, weights=weights)
        # Cov_ij = sum_t (w_t * dev_ti * dev_tj) = (deviations * weights[:, None]).T @ deviations
        cov = (deviations * weights[:, None]).T @ deviations * 252.0

        # Guarantee numerical positive semi-definiteness
        eigvals = np.linalg.eigvalsh(cov)
        min_eig = float(np.min(eigvals))
        if min_eig < 1e-8:
            cov += np.eye(N, dtype=np.float64) * (abs(min_eig) + 1e-8)

        return mu, cov

    def generate_rebalance_explanation(self, old_weights: np.ndarray,
                                       new_weights: np.ndarray,
                                       regime: VolatilityRegime,
                                       opt_result: dict[str, Any]) -> str:
        """
        Generate a plain-language explanation for an automated rebalance.

        Args:
            old_weights: Allocation prior to rebalance
            new_weights: Target allocation post rebalance
            regime: Current market volatility regime
            opt_result: Optimization result dict

        Returns:
            Human-readable audit explanation
        """
        changes = np.asarray(new_weights) - np.asarray(old_weights)
        increases: list[str] = []
        decreases: list[str] = []

        for i, name in enumerate(ASSET_CLASSES):
            change_pct = changes[i] * 100.0
            if change_pct > 0.5:
                increases.append(f"{name} +{change_pct:.1f}%")
            elif change_pct < -0.5:
                decreases.append(f"{name} {change_pct:.1f}%")

        parts = [
            f"Optimizer rebalanced portfolio (regime: {regime.value}, "
            f"risk aversion: {opt_result['risk_aversion']:.1f})."
        ]

        if increases:
            parts.append(f"Increased: {', '.join(increases)}.")
        if decreases:
            parts.append(f"Reduced: {', '.join(decreases)}.")

        parts.append(
            f"Expected return: {opt_result['expected_return']:.2f}%, "
            f"risk: {opt_result['expected_risk']:.2f}%, "
            f"turnover: {opt_result['turnover']:.1f}%."
        )

        return " ".join(parts)
