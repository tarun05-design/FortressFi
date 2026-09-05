"""
Integration tests for FastAPI REST endpoints and WebSocket live stream.
"""

import json


class TestAPIEndpoints:
    def test_serve_dashboard_homepage(self, test_client):
        """GET / should serve the dashboard HTML with HTTP 200."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_get_portfolio_state(self, test_client):
        """GET /api/portfolio returns the active portfolio state payload."""
        response = test_client.get("/api/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert "nav" in data
        assert "weights" in data
        assert "guardrail_level" in data
        assert "cumulative_return" in data
        assert "sharpe_ratio" in data
        assert len(data["weights"]) == 6

    def test_get_history(self, test_client):
        """GET /api/history returns time-series histories for charts."""
        response = test_client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert "days" in data
        assert "nav" in data
        assert "weights" in data
        assert "returns" in data
        assert len(data["days"]) == len(data["nav"])

    def test_get_decisions(self, test_client):
        """GET /api/decisions returns the chronological audit records."""
        response = test_client.get("/api/decisions?limit=10")
        assert response.status_code == 200
        records = response.json()
        assert isinstance(records, list)
        assert len(records) >= 1
        assert "action_type" in records[0]
        assert "explanation" in records[0]

    def test_get_config(self, test_client):
        """GET /api/config returns active engine configuration."""
        response = test_client.get("/api/config")
        assert response.status_code == 200
        config = response.json()
        assert "scenario" in config
        assert "seed" in config
        assert "asset_names" in config
        assert len(config["asset_names"]) == 6

    def test_run_scenario_stress_test(self, test_client):
        """POST /api/scenario evaluates hypothetical shock without error."""
        payload = {
            "shocks": {
                "US Equity": -25.0,
                "Intl Equity": -20.0,
                "Govt Bonds": 8.0,
            }
        }
        response = test_client.post("/api/scenario", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "projected_nav" in data
        assert "projected_return_pct" in data
        assert "guardrail_response" in data

    def test_simulation_lifecycle_controls(self, test_client):
        """Test start, speed configuration, and stop endpoints."""
        # 1. Start simulation
        start_res = test_client.post("/api/simulation/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] in ["started", "already_running"]

        # 2. Adjust speed
        speed_res = test_client.post("/api/simulation/speed?speed=0.5")
        assert speed_res.status_code == 200
        assert speed_res.json()["tick_speed"] == 0.5

        # 3. Stop simulation
        stop_res = test_client.post("/api/simulation/stop")
        assert stop_res.status_code == 200
        assert stop_res.json()["status"] == "stopped"

    def test_simulation_reset(self, test_client):
        """POST /api/simulation/reset restores clean starting state."""
        reset_payload = {
            "scenario": "sudden_shock",
            "seed": 99,
            "tick_speed": 2.0,
            "initial_nav": 50_000_000.0,
        }
        response = test_client.post("/api/simulation/reset", json=reset_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reset"
        assert data["scenario"] == "sudden_shock"
        assert data["portfolio"]["nav"] == 50_000_000.0

    def test_websocket_live_stream(self, test_client):
        """WebSocket /ws/live connection handshakes and receives connected snapshot."""
        with test_client.websocket_connect("/ws/live") as websocket:
            init_msg = websocket.receive_json()
            assert init_msg["type"] == "connected"
            assert "portfolio" in init_msg
            assert "config" in init_msg

            # Test sending client command (e.g. speed change)
            websocket.send_text(json.dumps({"type": "set_speed", "speed": 0.8}))
