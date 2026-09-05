"""
Unit tests for RiskEngine and 4-tier guardrail system.
"""

import numpy as np

from engine import (
    RiskMetrics,
    VolatilityRegime,
    DEFENSIVE_WEIGHTS,
)


class TestRiskEngine:
    def test_var_cvar_mathematics(self, risk_engine):
        """CVaR (Expected Shortfall) must always be greater than or equal to VaR for identical confidence."""
        # Synthetic return series with heavy negative tail
        returns = np.array([
            -0.05, -0.04, -0.035, -0.03, -0.025, -0.02,
            -0.01, -0.005, 0.001, 0.002, 0.005, 0.008,
            0.01, 0.012, 0.015, 0.018, 0.02, 0.025,
            0.03, 0.035
        ])

        var, cvar = risk_engine.compute_var_cvar(returns, confidence=0.95)
        assert var > 0.0
        assert cvar >= var

    def test_guardrail_monitor_state(self, risk_engine):
        """When all metrics are well below limits, guardrail level must be MONITOR."""
        metrics = RiskMetrics(
            var_95=1.0,           # limit is 1.8%
            cvar_95=1.5,          # limit is 2.8%
            max_drawdown=3.0,     # limit is 12%
            current_drawdown=2.0, # limit is 12%
            concentration_hhi=20.0, # limit is 35
            regime="NORMAL",
        )
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])
        status = risk_engine.evaluate_guardrails(metrics, VolatilityRegime.NORMAL, current_w, day=1)

        assert status.level == "MONITOR"
        assert status.action_required is False
        assert len(status.breaches) == 0

    def test_guardrail_warn_state(self, risk_engine):
        """When a metric reaches 80% of limit, guardrail escalates to WARN without changing weights."""
        metrics = RiskMetrics(
            var_95=1.5,           # 83% of 1.8 limit -> triggers WARN
            cvar_95=2.0,
            max_drawdown=5.0,
            current_drawdown=4.0,
            concentration_hhi=20.0,
            regime="NORMAL",
        )
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])
        status = risk_engine.evaluate_guardrails(metrics, VolatilityRegime.NORMAL, current_w, day=2)

        assert status.level == "WARN"
        assert status.action_required is False
        assert len(status.breaches) > 0

    def test_guardrail_act_state_and_derisking(self, risk_engine):
        """When a metric breaches limit, ACT triggers and redistributes capital away from equities."""
        metrics = RiskMetrics(
            var_95=2.2,           # Breaches 1.8 limit!
            cvar_95=2.0,
            max_drawdown=5.0,
            current_drawdown=4.0,
            concentration_hhi=20.0,
            regime="NORMAL",
        )
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])
        status = risk_engine.evaluate_guardrails(metrics, VolatilityRegime.NORMAL, current_w, day=3)

        assert status.level == "ACT"
        assert status.action_required is True
        assert status.target_weights is not None

        # Equities (US Eq idx 0, Intl Eq idx 1) must be reduced
        assert status.target_weights[0] < current_w[0]
        assert status.target_weights[1] < current_w[1]
        # Govt Bonds (idx 2) and Cash (idx 5) must be increased
        assert status.target_weights[2] > current_w[2]
        assert status.target_weights[5] > current_w[5]
        # Normalized to 1
        assert np.isclose(np.sum(status.target_weights), 1.0)

    def test_circuit_breaker_trigger_and_recovery(self, risk_engine):
        """Circuit breaker triggers on severe drawdown (>=12%), locks defensive position, and releases only below 8%."""
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])

        # 1. Trigger Circuit Breaker
        metrics_crash = RiskMetrics(
            var_95=3.5,
            cvar_95=6.0,
            max_drawdown=13.0,
            current_drawdown=13.0,  # Breaches 12% CIRCUIT_BREAK_DRAWDOWN
            concentration_hhi=25.0,
            regime="CRISIS",
        )
        status_crash = risk_engine.evaluate_guardrails(metrics_crash, VolatilityRegime.CRISIS, current_w, day=10)
        assert status_crash.level == "CIRCUIT_BREAK"
        assert status_crash.action_required is True
        np.testing.assert_allclose(status_crash.target_weights, DEFENSIVE_WEIGHTS)
        assert risk_engine.is_circuit_broken is True

        # 2. Lockdown persists while drawdown is still high
        metrics_persisting = RiskMetrics(
            var_95=2.0,
            cvar_95=3.0,
            max_drawdown=13.0,
            current_drawdown=10.0,  # Needs < 8% to release
            concentration_hhi=25.0,
            regime="HIGH",
        )
        status_lockdown = risk_engine.evaluate_guardrails(metrics_persisting, VolatilityRegime.HIGH, DEFENSIVE_WEIGHTS, day=11)
        assert status_lockdown.level == "CIRCUIT_BREAK"
        assert status_lockdown.action_required is False

        # 3. Recovery releases circuit breaker
        metrics_recovered = RiskMetrics(
            var_95=1.2,
            cvar_95=1.8,
            max_drawdown=13.0,
            current_drawdown=6.0,  # < 8.0% RECOVERY_DRAWDOWN
            concentration_hhi=25.0,
            regime="NORMAL",       # not CRISIS
        )
        status_recovered = risk_engine.evaluate_guardrails(metrics_recovered, VolatilityRegime.NORMAL, DEFENSIVE_WEIGHTS, day=15)
        assert status_recovered.level == "MONITOR"
        assert risk_engine.is_circuit_broken is False

    def test_scenario_stress_testing_isolation(self, risk_engine):
        """evaluate_scenario evaluates shock impact without mutating engine state."""
        current_w = np.array([0.30, 0.15, 0.25, 0.10, 0.10, 0.10])
        shock_returns = np.array([-0.25, -0.20, 0.05, -0.02, -0.15, 0.00])
        history_len_before = len(risk_engine.metrics_history)

        result = risk_engine.evaluate_scenario(
            current_weights=current_w,
            shock_returns=shock_returns,
            portfolio_returns=[-0.01, -0.005, 0.002, 0.001, -0.002],
            current_nav=100_000_000.0,
            peak_nav=100_000_000.0,
            regime=VolatilityRegime.NORMAL,
        )

        assert 'projected_nav' in result
        assert result['projected_nav'] < 100_000_000.0
        assert 'guardrail_response' in result
        # Ensure no residual metrics in history
        assert len(risk_engine.metrics_history) == history_len_before
        assert risk_engine.is_circuit_broken is False
