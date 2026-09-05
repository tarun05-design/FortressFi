"""
Unit tests for Portfolio state manager and performance math.
"""

import numpy as np

from engine import Portfolio, ASSET_CLASSES


class TestPortfolio:
    def test_initialization(self, portfolio):
        """Initial state should reflect starting capital, benchmark weights, and init audit log."""
        assert portfolio.nav == 100_000_000.0
        assert portfolio.initial_nav == 100_000_000.0
        assert portfolio.peak_nav == 100_000_000.0
        assert portfolio.max_drawdown == 0.0
        assert len(portfolio.weights) == len(ASSET_CLASSES)
        assert np.isclose(np.sum(portfolio.weights), 1.0)
        assert len(portfolio.decisions) == 1
        assert portfolio.decisions[0].action_type == "INIT"

    def test_custom_weights_initialization(self):
        """Custom initial weights must be properly normalized."""
        custom_w = [0.2, 0.2, 0.2, 0.2, 0.1, 0.1]
        p = Portfolio(initial_nav=50_000_000.0, initial_weights=np.array(custom_w))
        assert p.nav == 50_000_000.0
        np.testing.assert_allclose(p.weights, custom_w)

    def test_natural_drift_update(self, portfolio):
        """Asset price changes should shift portfolio weights naturally according to simple returns."""
        initial_weights = portfolio.weights.copy()
        # Returns: +10% on US Equity (idx 0), 0% on others
        returns = np.zeros(len(ASSET_CLASSES))
        returns[0] = np.log(1.10)  # simple return of +10%

        portfolio.update_with_returns(returns, day=1)

        # Total NAV should increase by initial_weight[0] * 10%
        expected_nav = 100_000_000.0 * (1.0 + initial_weights[0] * 0.10)
        assert np.isclose(portfolio.nav, expected_nav)

        # US Equity weight should drift upwards relative to others
        assert portfolio.weights[0] > initial_weights[0]
        assert np.isclose(np.sum(portfolio.weights), 1.0)

    def test_incremental_drawdown_tracking(self, portfolio):
        """Verify incremental O(1) drawdown matches peak-to-trough mathematics."""
        # Day 1: Market goes up (+10%)
        portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * np.log(1.10), day=1)
        peak_1 = portfolio.nav
        assert portfolio.peak_nav == peak_1
        assert portfolio.get_current_drawdown() == 0.0
        assert portfolio.get_max_drawdown() == 0.0

        # Day 2: Market drops (-20%)
        portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * np.log(0.80), day=2)
        assert portfolio.peak_nav == peak_1
        assert np.isclose(portfolio.get_current_drawdown(), 20.0, atol=1e-3)
        assert np.isclose(portfolio.get_max_drawdown(), 20.0, atol=1e-3)

        # Day 3: Market rebounds (+10%), not reaching peak
        portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * np.log(1.10), day=3)
        assert portfolio.peak_nav == peak_1
        assert portfolio.get_current_drawdown() < 20.0
        assert np.isclose(portfolio.get_max_drawdown(), 20.0, atol=1e-3)

    def test_sharpe_and_sortino_metrics(self, portfolio):
        """Verify Sharpe and Sortino ratio computations."""
        # Before sufficient data, metrics should be 0.0
        assert portfolio.get_sharpe_ratio() == 0.0
        assert portfolio.get_sortino_ratio() == 0.0

        # Feed 20 days of steady positive returns (+0.1% daily)
        for d in range(1, 25):
            portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * 0.001, day=d)

        assert portfolio.get_sharpe_ratio() > 0.0
        # If there are no downside returns below risk-free rate, Sortino is 0.0 (by definition)
        # Now introduce a couple negative days to test downside vol
        portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * -0.01, day=26)
        portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * -0.015, day=27)

        sortino = portfolio.get_sortino_ratio()
        assert sortino != 0.0

    def test_hhi_concentration(self, portfolio):
        """HHI should be 100/N for equal allocation, and 100 for a single asset."""
        n = len(ASSET_CLASSES)
        # Equal weights
        equal_w = np.ones(n) / n
        portfolio.weights = equal_w
        assert np.isclose(portfolio.get_concentration_hhi(), (1.0 / n) * 100.0)

        # Single asset
        single_w = np.zeros(n)
        single_w[0] = 1.0
        portfolio.weights = single_w
        assert np.isclose(portfolio.get_concentration_hhi(), 100.0)

    def test_decision_audit_trail(self, portfolio):
        """Verify recording of rebalancing and warning decisions with audit logs."""
        target_w = np.array([0.2, 0.2, 0.2, 0.2, 0.1, 0.1])
        portfolio.set_weights(
            new_weights=target_w,
            day=5,
            action_type="REBALANCE",
            guardrail_level="MONITOR",
            explanation="Rebalance triggered",
            trigger_metrics={'drift': 0.07},
        )

        assert len(portfolio.decisions) == 2
        last_rec = portfolio.decisions[-1]
        assert last_rec.action_type == "REBALANCE"
        assert last_rec.day == 5
        np.testing.assert_allclose(portfolio.weights, target_w)

        # Test warning
        portfolio.log_warning(day=6, explanation="Approaching VaR limit")
        assert len(portfolio.decisions) == 3
        assert portfolio.guardrail_level == "WARN"
        assert portfolio.decisions[-1].action_type == "GUARDRAIL_WARN"

    def test_state_and_history_serialization(self, portfolio):
        """Verify get_state and get_history return JSON-serializable dictionaries."""
        state = portfolio.get_state()
        assert 'nav' in state
        assert 'weights' in state
        assert 'guardrail_level' in state
        assert 'current_drawdown' in state

        history = portfolio.get_history()
        assert len(history['days']) == len(history['nav'])
        assert len(history['weights']) == len(history['nav'])

    def test_reset(self, portfolio):
        """Reset should clear return history and restore starting capital."""
        portfolio.update_with_returns(np.ones(len(ASSET_CLASSES)) * 0.05, day=1)
        assert portfolio.nav > portfolio.initial_nav

        portfolio.reset(initial_nav=200_000_000.0)
        assert portfolio.nav == 200_000_000.0
        assert len(portfolio.return_history) == 0
        assert portfolio.max_drawdown == 0.0
