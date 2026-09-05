"""
Unit tests for MarketSimulator.
"""

import numpy as np
import pytest

from engine import MarketSimulator, SCENARIOS, VolatilityRegime, ASSET_CLASSES


class TestMarketSimulator:
    def test_reproducibility_with_seed(self):
        """Simulators initialized with identical seeds must generate identical return sequences."""
        sim1 = MarketSimulator(scenario="normal", seed=42)
        sim2 = MarketSimulator(scenario="normal", seed=42)

        for _ in range(20):
            res1 = sim1.generate_next_day()
            res2 = sim2.generate_next_day()
            np.testing.assert_allclose(res1['returns'], res2['returns'])
            assert res1['regime'] == res2['regime']

    def test_different_seeds_diverge(self):
        """Simulators with different seeds should generate distinct stochastic trajectories."""
        sim1 = MarketSimulator(scenario="normal", seed=42)
        sim2 = MarketSimulator(scenario="normal", seed=999)

        res1 = sim1.generate_next_day()
        res2 = sim2.generate_next_day()
        assert not np.allclose(res1['returns'], res2['returns'])

    def test_output_structure_and_types(self, market_sim):
        """Validate return contract from generate_next_day."""
        data = market_sim.generate_next_day()
        assert data['day'] == 1
        assert isinstance(data['returns'], np.ndarray)
        assert len(data['returns']) == len(ASSET_CLASSES)
        assert isinstance(data['regime'], VolatilityRegime)
        assert data['asset_names'] == ASSET_CLASSES
        assert data['is_finished'] is False
        # Cash asset return (index -1) should be non-negative
        assert data['returns'][-1] >= 0.0

    def test_all_scenarios_valid(self):
        """All pre-built scenarios can be instantiated and have non-zero days."""
        for scenario_name in SCENARIOS:
            sim = MarketSimulator(scenario=scenario_name, seed=1)
            info = sim.get_scenario_info()
            assert info['total_days'] > 0
            assert info['current_day'] == 0
            assert info['name'] is not None

    def test_invalid_scenario_raises_value_error(self):
        """Attempting to instantiate an unknown scenario should fail fast."""
        with pytest.raises(ValueError, match="Unknown scenario"):
            MarketSimulator(scenario="non_existent_scenario")

    def test_scenario_completion(self):
        """Simulator marks is_finished when simulation ticks reach total days."""
        sim = MarketSimulator(scenario="normal", seed=42)
        # Advance to the end
        for _ in range(sim.total_days):
            sim.generate_next_day()

        final = sim.generate_next_day()
        assert final['is_finished'] is True
        assert np.allclose(final['returns'], 0.0)

    def test_return_history_matrix_lookback(self, market_sim):
        """Test matrix conversion and lookback window slicing."""
        assert market_sim.get_return_history_matrix().shape == (0, len(ASSET_CLASSES))

        for _ in range(30):
            market_sim.generate_next_day()

        full_mat = market_sim.get_return_history_matrix()
        assert full_mat.shape == (30, len(ASSET_CLASSES))

        sliced_mat = market_sim.get_return_history_matrix(lookback=10)
        assert sliced_mat.shape == (10, len(ASSET_CLASSES))
        np.testing.assert_allclose(sliced_mat, full_mat[-10:])

    def test_regime_classification_under_stress(self):
        """Simulate high realized volatility to ensure regime classification escalates to CRISIS."""
        sim = MarketSimulator(scenario="normal", seed=42)
        # Artificially inject extreme equity volatility into return history
        sim._equity_returns_buffer = [0.05, -0.06, 0.07, -0.08, 0.06, -0.05] * 4
        regime = sim._classify_regime()
        assert regime in [VolatilityRegime.HIGH, VolatilityRegime.CRISIS]

    def test_apply_shock(self, market_sim):
        """Test hypothetical shock calculation logic."""
        shocks = {"US Equity": -20.0, "Govt Bonds": 5.0, "Unknown Asset": 99.0}
        res = market_sim.apply_shock(shocks)
        assert len(res) == len(ASSET_CLASSES)
        assert np.isclose(res[0], -0.20)  # US Equity at idx 0
        assert np.isclose(res[2], 0.05)   # Govt Bonds at idx 2
        assert np.isclose(res[1], 0.00)   # Intl Equity untouched

    def test_reset(self, market_sim):
        """Reset clears state, day counter, and histories."""
        for _ in range(15):
            market_sim.generate_next_day()
        assert market_sim.current_day == 15

        market_sim.reset(scenario="recovery", seed=77)
        assert market_sim.current_day == 0
        assert len(market_sim.return_history) == 0
        assert market_sim.scenario_name == "recovery"
