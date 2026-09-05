"""
Market Simulator: Generates realistic multi-asset returns with regime-aware dynamics.

Produces daily log-returns for 6 asset classes using multivariate normal draws with
Cholesky-decomposed correlation structure. Volatility regimes (Low/Normal/High/Crisis)
are classified from rolling realized vol of the equity sleeve, and correlation matrices
shift toward higher cross-asset correlation during stress (modeling the real phenomenon
of "correlations go to 1 in a crash").

Pre-built scenario profiles (normal, gradual_crash, sudden_shock, recovery) set
drift/vol parameters to produce recognizable market narratives.
"""

from typing import Any, Optional
import numpy as np

from engine.config import (
    ASSET_CLASSES,
    BASE_ANNUAL_RETURNS,
    BASE_ANNUAL_VOLS,
    BASE_CORRELATION,
    STRESSED_CORRELATION,
    REGIME_THRESHOLDS,
    SCENARIOS,
    ScenarioProfile,
    VolatilityRegime,
)


class MarketSimulator:
    """
    Generates correlated multi-asset daily returns with volatility regime classification.

    Uses Cholesky decomposition for correlated draws from multivariate normal distribution.
    Regime is classified from rolling realized volatility of the equity sleeve.
    Correlation matrix blends toward stressed correlations during High/Crisis regimes.
    """

    def __init__(self, scenario: str = "gradual_crash", seed: Optional[int] = 42):
        """
        Initialize the market simulator.

        Args:
            scenario: One of 'normal', 'gradual_crash', 'sudden_shock', 'recovery'
            seed: Random seed for reproducibility (None for non-deterministic)
        """
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}. Choose from {list(SCENARIOS.keys())}")

        self.scenario_name = scenario
        self.scenario: ScenarioProfile = SCENARIOS[scenario]
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.n_assets: int = len(ASSET_CLASSES)

        # Build schedule of daily parameters
        self._build_schedule()

        # State tracking
        self.current_day: int = 0
        self.return_history: list[np.ndarray] = []  # Daily return vectors
        self.regime_history: list[VolatilityRegime] = []
        # Fast array buffer for equity returns to optimize regime classification
        self._equity_returns_buffer: list[float] = []

    def _build_schedule(self) -> None:
        """Pre-compute daily return multipliers and vol multipliers from scenario phases."""
        self.daily_return_mult: list[float] = []
        self.daily_vol_mult: list[float] = []

        for num_days, ret_mult, vol_mult in self.scenario.phases:
            self.daily_return_mult.extend([ret_mult] * num_days)
            self.daily_vol_mult.extend([vol_mult] * num_days)

        self.total_days: int = len(self.daily_return_mult)

    def _get_correlation_matrix(self, regime: VolatilityRegime) -> np.ndarray:
        """
        Blend base and stressed correlation matrices based on current regime.

        In normal/low regimes, use base correlations.
        In high/crisis regimes, blend toward stressed correlations.
        """
        blend_weights = {
            VolatilityRegime.LOW: 0.0,
            VolatilityRegime.NORMAL: 0.0,
            VolatilityRegime.HIGH: 0.4,
            VolatilityRegime.CRISIS: 0.8,
        }
        w = blend_weights.get(regime, 0.0)
        if w == 0.0:
            return BASE_CORRELATION
        return (1.0 - w) * BASE_CORRELATION + w * STRESSED_CORRELATION

    def _classify_regime(self) -> VolatilityRegime:
        """
        Classify current volatility regime from rolling 20-day realized vol of equity.

        Uses the US Equity (index 0) returns to compute rolling realized volatility,
        annualized by multiplying by sqrt(252).
        """
        hist_len = len(self._equity_returns_buffer)
        if hist_len < 5:
            return VolatilityRegime.NORMAL

        lookback = min(20, hist_len)
        recent_returns = np.array(self._equity_returns_buffer[-lookback:], dtype=np.float64)

        # Annualized realized volatility
        realized_vol = float(np.std(recent_returns, ddof=1 if lookback > 1 else 0) * np.sqrt(252.0))

        # Classify into regime
        for regime, (low, high) in REGIME_THRESHOLDS.items():
            if low <= realized_vol < high:
                return regime

        return VolatilityRegime.CRISIS

    def generate_next_day(self) -> dict[str, Any]:
        """
        Generate the next day's returns for all asset classes.

        Returns:
            dict with keys:
                - 'day': int, current simulation day
                - 'returns': np.ndarray of daily log-returns for each asset
                - 'regime': VolatilityRegime classification
                - 'asset_names': list of asset class names
                - 'is_finished': bool, whether scenario has ended
        """
        if self.current_day >= self.total_days:
            return {
                'day': self.current_day,
                'returns': np.zeros(self.n_assets, dtype=np.float64),
                'regime': self._classify_regime(),
                'asset_names': ASSET_CLASSES,
                'is_finished': True,
            }

        # Multipliers for today
        ret_mult = self.daily_return_mult[self.current_day]
        vol_mult = self.daily_vol_mult[self.current_day]

        # Classify regime based on history before today's shock
        regime = self._classify_regime()

        # Daily drift and volatility vectors
        daily_mu = (BASE_ANNUAL_RETURNS * ret_mult) / 252.0
        daily_sigma = (BASE_ANNUAL_VOLS * vol_mult) / np.sqrt(252.0)

        # Build covariance: Cov_ij = sigma_i * sigma_j * Corr_ij
        corr_matrix = self._get_correlation_matrix(regime)
        cov_matrix = np.outer(daily_sigma, daily_sigma) * corr_matrix

        # Generate correlated draws via Cholesky with fast fallback
        try:
            L = np.linalg.cholesky(cov_matrix)
        except np.linalg.LinAlgError:
            # Add small diagonal regularization (jitter) if non-positive definite
            cov_reg = cov_matrix + np.eye(self.n_assets) * 1e-8
            try:
                L = np.linalg.cholesky(cov_reg)
            except np.linalg.LinAlgError:
                # Fallback to diagonal standard deviations
                L = np.diag(daily_sigma)

        z = self.rng.standard_normal(self.n_assets)
        returns = daily_mu + L @ z

        # Cash return floor (cash cannot have negative returns)
        returns[-1] = abs(returns[-1])

        # Update historical state
        self.return_history.append(returns)
        self._equity_returns_buffer.append(float(returns[0]))
        self.regime_history.append(regime)
        self.current_day += 1

        return {
            'day': self.current_day,
            'returns': returns,
            'regime': regime,
            'asset_names': ASSET_CLASSES,
            'is_finished': False,
        }

    def get_return_history_matrix(self, lookback: Optional[int] = None) -> np.ndarray:
        """
        Get return history as a (T x N) matrix.

        Args:
            lookback: Number of recent days to include. None = all history.

        Returns:
            np.ndarray of shape (T, N) where T is days, N is assets
        """
        if not self.return_history:
            return np.empty((0, self.n_assets), dtype=np.float64)

        if lookback is not None:
            data = self.return_history[-lookback:]
        else:
            data = self.return_history

        return np.array(data, dtype=np.float64)

    def apply_shock(self, shock_pcts: dict[str, float]) -> np.ndarray:
        """
        Apply hypothetical percentage shocks to compute scenario returns.
        Does NOT modify internal simulator state.

        Args:
            shock_pcts: Dict mapping asset name to shock percentage
                        e.g., {"US Equity": -25.0, "Govt Bonds": 5.0}

        Returns:
            np.ndarray of single-day returns representing the shock
        """
        shock_returns = np.zeros(self.n_assets, dtype=np.float64)
        for asset_name, pct in shock_pcts.items():
            if asset_name in ASSET_CLASSES:
                idx = ASSET_CLASSES.index(asset_name)
                # Ensure input is numeric and convert percentage to decimal return
                try:
                    shock_returns[idx] = float(pct) / 100.0
                except (ValueError, TypeError):
                    shock_returns[idx] = 0.0
        return shock_returns

    def reset(self, scenario: Optional[str] = None, seed: Optional[int] = 42) -> None:
        """Reset simulator to initial state, optionally with a new scenario."""
        if scenario is not None:
            if scenario not in SCENARIOS:
                raise ValueError(f"Unknown scenario: {scenario}")
            self.scenario_name = scenario
            self.scenario = SCENARIOS[scenario]
            self._build_schedule()

        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.current_day = 0
        self.return_history = []
        self.regime_history = []
        self._equity_returns_buffer = []

    def get_scenario_info(self) -> dict[str, Any]:
        """Return current scenario metadata."""
        return {
            'name': self.scenario.name,
            'description': self.scenario.description,
            'total_days': self.total_days,
            'current_day': self.current_day,
            'available_scenarios': list(SCENARIOS.keys()),
        }
