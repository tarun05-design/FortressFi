"""
Simulation Service: Orchestrates engine lifecycle, async simulation loop, and WebSocket streaming.

Separates business logic and market simulation mechanics from HTTP / routing infrastructure.
"""

import asyncio
import json
import logging
from typing import Any, Optional
from fastapi import WebSocket

from engine import (
    ASSET_CLASSES,
    DecisionRecord,
    GuardrailStatus,
    MarketSimulator,
    OptimizationEngine,
    Portfolio,
    RiskEngine,
    VolatilityRegime,
)

logger = logging.getLogger("argpe.service")


class SimulationService:
    """
    Central service coordinating market generation, portfolio tracking,
    risk evaluation, and live client streaming.
    """

    def __init__(self, scenario: str = "gradual_crash", seed: int = 42,
                 initial_nav: float = 100_000_000.0, tick_speed: float = 1.5):
        self.scenario: str = scenario
        self.seed: int = seed
        self.initial_nav: float = initial_nav
        self.tick_speed: float = tick_speed

        self.simulator = MarketSimulator(scenario=scenario, seed=seed)
        self.portfolio = Portfolio(initial_nav=initial_nav)
        self.optimizer = OptimizationEngine()
        self.risk_engine = RiskEngine()

        self.is_running: bool = False
        self.simulation_task: Optional[asyncio.Task] = None
        self.connected_clients: list[WebSocket] = []
        self._lock = asyncio.Lock()

    def reset(self, scenario: Optional[str] = None, seed: Optional[int] = None,
              initial_nav: Optional[float] = None, tick_speed: Optional[float] = None) -> dict[str, Any]:
        """Reset all engine components to clean initial state."""
        if self.simulation_task and not self.simulation_task.done():
            self.simulation_task.cancel()
            self.simulation_task = None
        self.is_running = False

        if scenario is not None:
            self.scenario = scenario
        if seed is not None:
            self.seed = seed
        if initial_nav is not None:
            self.initial_nav = initial_nav
        if tick_speed is not None:
            self.tick_speed = max(0.1, min(10.0, tick_speed))

        self.simulator.reset(scenario=self.scenario, seed=self.seed)
        self.portfolio.reset(initial_nav=self.initial_nav)
        self.optimizer = OptimizationEngine()
        self.risk_engine.reset()

        logger.info("Simulation service reset (scenario=%s, seed=%s, nav=$%.0fM)",
                    self.scenario, self.seed, self.initial_nav / 1e6)

        return self.get_config()

    def get_config(self) -> dict[str, Any]:
        """Return active simulation configuration and metadata."""
        return {
            'scenario': self.scenario,
            'seed': self.seed,
            'tick_speed': self.tick_speed,
            'is_running': self.is_running,
            'simulator': self.simulator.get_scenario_info(),
            'asset_names': ASSET_CLASSES,
        }

    def set_speed(self, speed: float) -> float:
        """Update simulation speed (seconds per tick)."""
        self.tick_speed = max(0.1, min(10.0, float(speed)))
        logger.info("Simulation tick speed set to %.2fs", self.tick_speed)
        return self.tick_speed

    async def start(self) -> dict[str, Any]:
        """Start the live market simulation loop in background."""
        if self.is_running:
            return {'status': 'already_running'}

        if self.simulator.current_day >= self.simulator.total_days:
            return {'status': 'scenario_complete', 'message': 'Scenario has finished. Reset to run again.'}

        self.is_running = True
        self.simulation_task = asyncio.create_task(self._simulation_loop())
        logger.info("Market simulation started (scenario=%s)", self.scenario)

        return {
            'status': 'started',
            'scenario': self.scenario,
            'tick_speed': self.tick_speed,
        }

    async def stop(self) -> dict[str, Any]:
        """Stop running simulation loop."""
        self.is_running = False
        if self.simulation_task and not self.simulation_task.done():
            self.simulation_task.cancel()
            self.simulation_task = None
        logger.info("Market simulation stopped.")
        return {'status': 'stopped'}

    async def _simulation_loop(self) -> None:
        """Continuous background execution loop."""
        while self.is_running:
            try:
                should_continue = await self.simulation_tick()
                if not should_continue:
                    break
                await asyncio.sleep(self.tick_speed)
            except asyncio.CancelledError:
                logger.debug("Simulation loop cancelled.")
                break
            except Exception as e:
                logger.exception("Error during simulation tick: %s", e)
                await asyncio.sleep(1.0)

    async def simulation_tick(self) -> bool:
        """
        Execute one discrete simulation step:
        1. Market returns generated
        2. Portfolio NAV & drift updated
        3. Risk metrics calculated
        4. Guardrails evaluated
        5. Rebalance triggered if applicable
        6. State broadcast to clients
        """
        async with self._lock:
            # 1. Market generator
            market_data = self.simulator.generate_next_day()

            if market_data['is_finished']:
                self.is_running = False
                await self.broadcast({
                    'type': 'simulation_complete',
                    'message': 'Simulation scenario has completed.',
                    'day': market_data['day'],
                })
                return False

            day = market_data['day']
            returns = market_data['returns']
            regime = market_data['regime']

            # 2. Portfolio update
            self.portfolio.update_with_returns(returns, day)

            # 3. Risk metrics
            metrics = self.risk_engine.compute_metrics(
                portfolio_returns=self.portfolio.return_history,
                current_drawdown=self.portfolio.get_current_drawdown(),
                max_drawdown=self.portfolio.get_max_drawdown(),
                weights=self.portfolio.weights,
                regime=regime,
            )

            # 4. Guardrail assessment
            guardrail_status = self.risk_engine.evaluate_guardrails(
                metrics=metrics,
                regime=regime,
                current_weights=self.portfolio.weights,
                day=day,
            )

            # 5. Response execution
            if guardrail_status.action_required and guardrail_status.target_weights is not None:
                self.portfolio.set_weights(
                    new_weights=guardrail_status.target_weights,
                    day=day,
                    action_type=f"GUARDRAIL_{guardrail_status.level}",
                    guardrail_level=guardrail_status.level,
                    explanation=guardrail_status.explanation,
                    trigger_metrics=metrics.to_dict(),
                )
            elif guardrail_status.level == "WARN":
                self.portfolio.log_warning(
                    day=day,
                    explanation=guardrail_status.explanation,
                    trigger_metrics=metrics.to_dict(),
                )
                self.portfolio.guardrail_level = "WARN"
                self._try_rebalance(day, regime)
            elif guardrail_status.level == "MONITOR":
                self.portfolio.guardrail_level = "MONITOR"
                self._try_rebalance(day, regime)

            # 6. Push state update
            await self._broadcast_tick(day, regime, guardrail_status)
            return True

    def _try_rebalance(self, day: int, regime: VolatilityRegime) -> None:
        """Attempt optimizer rebalancing if drift exceeds regime threshold."""
        if not self.optimizer.should_rebalance(self.portfolio.weights, regime):
            return

        return_history = self.simulator.get_return_history_matrix(lookback=60)
        if return_history.shape[0] < 20:
            return

        mu, cov = self.optimizer.estimate_parameters(return_history)
        result = self.optimizer.optimize(
            expected_returns=mu,
            covariance_matrix=cov,
            current_weights=self.portfolio.weights,
            regime=regime,
        )

        if result['success'] and result['turnover'] > 0.5:
            explanation = self.optimizer.generate_rebalance_explanation(
                old_weights=self.portfolio.weights,
                new_weights=result['weights'],
                regime=regime,
                opt_result=result,
            )
            self.portfolio.set_weights(
                new_weights=result['weights'],
                day=day,
                action_type="REBALANCE",
                guardrail_level=self.portfolio.guardrail_level,
                explanation=explanation,
                trigger_metrics={
                    'expected_return': result['expected_return'],
                    'expected_risk': result['expected_risk'],
                    'sharpe_estimate': result['sharpe_estimate'],
                    'turnover': result['turnover'],
                },
            )

    async def register_client(self, websocket: WebSocket) -> None:
        """Register a new WebSocket subscriber and send initial snapshot."""
        await websocket.accept()
        self.connected_clients.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self.connected_clients))

        try:
            await websocket.send_json({
                'type': 'connected',
                'portfolio': self.portfolio.get_state(),
                'config': self.get_config(),
            })
        except Exception:
            self.unregister_client(websocket)

    def unregister_client(self, websocket: WebSocket) -> None:
        """Remove a WebSocket subscriber."""
        if websocket in self.connected_clients:
            self.connected_clients.remove(websocket)
            logger.info("WebSocket client disconnected (%d remaining)", len(self.connected_clients))

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Send JSON message to all connected clients."""
        if not self.connected_clients:
            return

        message = json.dumps(data, default=str)
        dead_clients: list[WebSocket] = []

        for client in self.connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                dead_clients.append(client)

        for dead in dead_clients:
            self.unregister_client(dead)

    async def _broadcast_tick(self, day: int, regime: VolatilityRegime,
                             guardrail_status: GuardrailStatus) -> None:
        """Broadcast live tick packet."""
        data = {
            'type': 'tick',
            'day': day,
            'regime': regime.value,
            'portfolio': self.portfolio.get_state(),
            'risk_metrics': guardrail_status.metrics.to_dict(),
            'guardrail': guardrail_status.to_dict(),
            'latest_decisions': self.portfolio.get_decisions(limit=5),
        }
        await self.broadcast(data)

    def run_stress_test(self, shock_pcts: dict[str, float]) -> dict[str, Any]:
        """Perform a what-if stress scenario without state mutation."""
        shock_returns = self.simulator.apply_shock(shock_pcts)
        regime = (
            self.simulator.regime_history[-1]
            if self.simulator.regime_history
            else VolatilityRegime.NORMAL
        )

        return self.risk_engine.evaluate_scenario(
            current_weights=self.portfolio.weights,
            shock_returns=shock_returns,
            portfolio_returns=self.portfolio.return_history,
            current_nav=self.portfolio.nav,
            peak_nav=self.portfolio.peak_nav,
            regime=regime,
        )
