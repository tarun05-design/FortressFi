"""
Unit tests for OptimizationEngine.
"""

import numpy as np

from engine import VolatilityRegime, ASSET_CLASSES, WEIGHT_BOUNDS, MAX_TURNOVER


class TestOptimizationEngine:
    def test_optimizer_convergence_across_regimes(self, optimizer, synthetic_returns):
        """SLSQP optimizer must converge successfully across all market volatility regimes."""
        mu, cov = optimizer.estimate_parameters(synthetic_returns)
        current_w = np.ones(len(ASSET_CLASSES)) / len(ASSET_CLASSES)

        for regime in VolatilityRegime:
            res = optimizer.optimize(
                expected_returns=mu,
                covariance_matrix=cov,
                current_weights=current_w,
                regime=regime,
            )
            assert res['success'] is True
            assert isinstance(res['weights'], list)
            assert len(res['weights']) == len(ASSET_CLASSES)
            assert res['regime'] == regime.value

    def test_constraint_satisfaction(self, optimizer, synthetic_returns):
        """Optimal weights must strictly obey sum-to-1, bounds, and turnover limits."""
        mu, cov = optimizer.estimate_parameters(synthetic_returns)
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])

        res = optimizer.optimize(
            expected_returns=mu,
            covariance_matrix=cov,
            current_weights=current_w,
            regime=VolatilityRegime.NORMAL,
        )

        weights = np.array(res['weights'])

        # 1. Sum to 1
        assert np.isclose(np.sum(weights), 1.0, atol=1e-5)

        # 2. Individual asset bounds
        for i, name in enumerate(ASSET_CLASSES):
            min_w, max_w = WEIGHT_BOUNDS[name]
            assert weights[i] >= min_w - 1e-5
            assert weights[i] <= max_w + 1e-5

        # 3. Turnover constraint
        turnover = np.sum(np.abs(weights - current_w))
        assert turnover <= MAX_TURNOVER + 1e-4

    def test_regime_adaptive_risk_aversion(self, optimizer):
        """In CRISIS regime, higher risk aversion (lambda=12) must produce lower portfolio risk and higher defensive allocation than in LOW (lambda=2)."""
        from engine import BASE_ANNUAL_RETURNS, BASE_ANNUAL_VOLS, BASE_CORRELATION
        mu = BASE_ANNUAL_RETURNS
        D = np.diag(BASE_ANNUAL_VOLS)
        cov = D @ BASE_CORRELATION @ D
        current_w = np.ones(len(ASSET_CLASSES)) / len(ASSET_CLASSES)

        res_low = optimizer.optimize(mu, cov, current_w, VolatilityRegime.LOW)
        res_crisis = optimizer.optimize(mu, cov, current_w, VolatilityRegime.CRISIS)

        w_low = np.array(res_low['weights'])
        w_crisis = np.array(res_crisis['weights'])

        # Expected portfolio volatility must be lower in CRISIS than in LOW
        assert res_crisis['expected_risk'] < res_low['expected_risk']

        # Defensive assets (Govt Bonds idx 2 + Cash idx 5) must be significantly higher in CRISIS
        defensive_low = w_low[2] + w_low[5]
        defensive_crisis = w_crisis[2] + w_crisis[5]
        assert defensive_crisis > defensive_low

    def test_drift_gating(self, optimizer):
        """should_rebalance must return False for small drift, and True for large drift."""
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])
        optimizer.last_optimal_weights = current_w.copy()

        # Very small drift (0.5%)
        small_drift_w = current_w + np.array([0.005, -0.005, 0.0, 0.0, 0.0, 0.0])
        assert optimizer.should_rebalance(small_drift_w, VolatilityRegime.NORMAL) is False

        # Large drift (7%)
        large_drift_w = current_w + np.array([0.07, -0.07, 0.0, 0.0, 0.0, 0.0])
        assert optimizer.should_rebalance(large_drift_w, VolatilityRegime.NORMAL) is True

    def test_vectorized_parameter_estimation(self, optimizer, synthetic_returns):
        """Vectorized estimate_parameters produces positive semi-definite covariance matrix."""
        mu, cov = optimizer.estimate_parameters(synthetic_returns, halflife=60)

        assert len(mu) == len(ASSET_CLASSES)
        assert cov.shape == (len(ASSET_CLASSES), len(ASSET_CLASSES))

        # Check symmetry
        np.testing.assert_allclose(cov, cov.T, atol=1e-8)

        # Check positive semi-definiteness: eigenvalues >= 0
        eigvals = np.linalg.eigvalsh(cov)
        assert np.all(eigvals >= -1e-8)

    def test_explanation_generation(self, optimizer):
        """Rebalance explanation includes formatted asset changes."""
        old_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])
        new_w = np.array([0.25, 0.15, 0.30, 0.10, 0.10, 0.10])
        opt_res = {
            'expected_return': 7.5,
            'expected_risk': 11.2,
            'turnover': 10.0,
            'risk_aversion': 3.0,
        }
        explanation = optimizer.generate_rebalance_explanation(
            old_w, new_w, VolatilityRegime.NORMAL, opt_res
        )
        assert "Optimizer rebalanced portfolio" in explanation
        assert "Govt Bonds +5.0%" in explanation
        assert "US Equity -5.0%" in explanation
