"""
FortressFi Server: FastAPI application with REST endpoints and WebSocket for real-time streaming.

Entry point for the Adaptive Risk-Guardrail Portfolio Engine.
Provides high-performance asynchronous API endpoints and real-time streaming to the dashboard.

Endpoints:
    GET  /                        : Dashboard UI
    GET  /api/portfolio           : Current portfolio state + metrics
    GET  /api/history             : Historical NAV, weights, returns
    GET  /api/decisions           : Decision audit log
    GET  /api/config              : Current simulation configuration
    POST /api/scenario            : What-if scenario analysis
    POST /api/simulation/start    : Start live market simulation
    POST /api/simulation/stop     : Stop simulation
    POST /api/simulation/reset    : Reset to initial state
    POST /api/simulation/speed    : Set simulation speed
    WS   /ws/live                 : Real-time portfolio state stream
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engine import ScenarioRequest, SimulationConfig
from services import SimulationService

# ─── Structured Logging Configuration ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("argpe.server")

# ─── Service Instance ─────────────────────────────────────────────────────────

service = SimulationService()


# ─── Application Lifecycle ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and graceful shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info("  FortressFi // Adaptive Risk-Guardrail Portfolio Engine")
    logger.info("  Dashboard URL: http://localhost:8000")
    logger.info("=" * 60)
    yield
    # Graceful shutdown: stop active background simulation tasks
    logger.info("Shutting down FortressFi simulation service...")
    await service.stop()


app = FastAPI(
    title="FortressFi // Adaptive Risk-Guardrail Portfolio Engine",
    description="Automated capital management with real-time risk guardrails",
    version="2.0.0",
    lifespan=lifespan,
)

# Serve static dashboard assets
app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Static UI Route ──────────────────────────────────────────────────────────

@app.get("/", summary="Dashboard Homepage")
async def serve_dashboard():
    """Serve the interactive dashboard HTML."""
    return FileResponse(
        "static/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ─── REST API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/portfolio", summary="Get Portfolio State")
async def get_portfolio():
    """Get current portfolio state including NAV, allocations, and risk-adjusted metrics."""
    return JSONResponse(service.portfolio.get_state())


@app.get("/api/history", summary="Get Time-Series History")
async def get_history():
    """Get historical time-series of NAV, asset weights, and daily returns."""
    return JSONResponse(service.portfolio.get_history())


@app.get("/api/decisions", summary="Get Decision Audit Trail")
async def get_decisions(limit: int = 100):
    """Get chronological audit log of autonomous engine decisions (newest first)."""
    return JSONResponse(service.portfolio.get_decisions(limit=limit))


@app.get("/api/config", summary="Get Engine Configuration")
async def get_config():
    """Get active market scenario parameters, simulation settings, and asset list."""
    return JSONResponse(service.get_config())


@app.post("/api/scenario", summary="Run What-If Scenario Stress Test")
async def run_scenario(request: ScenarioRequest):
    """
    Evaluate hypothetical asset shocks on portfolio metrics and guardrail response
    without modifying real simulation state.
    """
    try:
        result = service.run_stress_test(request.shocks)
        return JSONResponse(result)
    except Exception as e:
        logger.error("Scenario evaluation failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Scenario evaluation error: {str(e)}")


@app.post("/api/simulation/start", summary="Start Live Simulation")
async def start_simulation():
    """Initiate autonomous background market simulation loop."""
    result = await service.start()
    return JSONResponse(result)


@app.post("/api/simulation/stop", summary="Stop Live Simulation")
async def stop_simulation():
    """Halt background market simulation loop."""
    result = await service.stop()
    return JSONResponse(result)


@app.post("/api/simulation/reset", summary="Reset Simulation State")
async def reset_simulation(config: Optional[SimulationConfig] = None):
    """Reset simulation to initial state with optional scenario and parameter overrides."""
    try:
        if config:
            service.reset(
                scenario=config.scenario,
                seed=config.seed,
                tick_speed=config.tick_speed,
                initial_nav=config.initial_nav,
            )
        else:
            service.reset()

        # Broadcast reset event to all connected dashboard clients
        await service.broadcast({
            'type': 'reset',
            'message': 'Simulation reset to initial state.',
            'portfolio': service.portfolio.get_state(),
        })

        return JSONResponse({
            'status': 'reset',
            'scenario': service.scenario,
            'portfolio': service.portfolio.get_state(),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/simulation/speed", summary="Configure Simulation Speed")
async def set_speed(speed: float = 1.5):
    """Update simulation tick interval (seconds per day, between 0.1s and 10.0s)."""
    new_speed = service.set_speed(speed)
    return JSONResponse({'tick_speed': new_speed})


# ─── WebSocket Endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time live streaming of portfolio state,
    guardrail alerts, and rebalance receipts on each simulation tick.
    """
    await service.register_client(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get('type') == 'set_speed':
                    service.set_speed(msg.get('speed', 1.5))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        service.unregister_client(websocket)
    except Exception as e:
        logger.debug("WebSocket connection terminated: %s", e)
        service.unregister_client(websocket)


# ─── Development Server Runner ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
