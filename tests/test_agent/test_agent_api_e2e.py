"""E2E tests for the Agent HTTP API across all PrintExp build types.

Each test class covers a single endpoint family.  All tests run against
in-process TestClient instances backed by _FullMockBackend (no real printer
or network required).

Fixtures are defined in tests/conftest.py:
    agent_client_dtg  — DTG printer backend
    agent_client_dtf  — DTF printer backend
    agent_client_uv   — UV printer backend
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestAgentHealth:
    """GET /health — liveness probe with printer identity."""

    def test_health_dtg(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.get("/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"
        assert d["printer_type"] == "dtg"

    def test_health_dtf(self, agent_client_dtf: TestClient) -> None:
        r = agent_client_dtf.get("/health")
        assert r.status_code == 200
        assert r.json()["printer_type"] == "dtf"

    def test_health_uv(self, agent_client_uv: TestClient) -> None:
        r = agent_client_uv.get("/health")
        assert r.status_code == 200
        assert r.json()["printer_type"] == "uv"

    def test_health_includes_service_name(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/health").json()
        assert d.get("service") == "printflow-agent"

    def test_health_includes_printer_name(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/health").json()
        assert "printer_name" in d


class TestAgentStatus:
    """GET /status — live printer status snapshot."""

    def test_status_dtg_connected(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.get("/status")
        assert r.status_code == 200
        d = r.json()
        assert d["connected"] is True
        assert d["type"] == "dtg"

    def test_status_has_multiws_fields(self, agent_client_dtg: TestClient) -> None:
        """DTG status must include MULTIWS workstation fields."""
        d = agent_client_dtg.get("/status").json()
        assert "active_ws" in d
        assert "ws0_busy" in d
        assert "ws1_busy" in d

    def test_status_not_printing_initially(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/status").json()
        assert d["printing"] is False

    def test_status_dtf(self, agent_client_dtf: TestClient) -> None:
        r = agent_client_dtf.get("/status")
        assert r.status_code == 200
        assert r.json()["type"] == "dtf"

    def test_status_uv(self, agent_client_uv: TestClient) -> None:
        r = agent_client_uv.get("/status")
        assert r.status_code == 200
        assert r.json()["type"] == "uv"

    def test_status_has_ink_levels(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/status").json()
        assert isinstance(d.get("ink_levels"), dict)
        assert len(d["ink_levels"]) > 0


class TestAgentWSStatus:
    """GET /ws-status — MULTIWS dual-platen workstation state (DTG only)."""

    def test_ws_status_200(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.get("/ws-status")
        assert r.status_code == 200

    def test_ws_status_has_active_ws(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/ws-status").json()
        assert "active_ws" in d

    def test_ws_status_has_ws0_busy(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/ws-status").json()
        assert "ws0_busy" in d

    def test_ws_status_has_ws1_busy(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/ws-status").json()
        assert "ws1_busy" in d

    def test_ws_status_busy_flags_are_bool(self, agent_client_dtg: TestClient) -> None:
        d = agent_client_dtg.get("/ws-status").json()
        assert isinstance(d["ws0_busy"], bool)
        assert isinstance(d["ws1_busy"], bool)


class TestAgentJobInjection:
    """POST /jobs — inject a .prn file into the printer queue."""

    def test_inject_job_dtg_succeeds(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/jobs", json={
            "job_id": "j1",
            "order_id": "o1",
            "prn_path": "/fake/test.prn",
            "job_name": "test",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_inject_job_returns_job_id(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/jobs", json={
            "job_id": "j-abc",
            "order_id": "o1",
            "prn_path": "/fake/test.prn",
            "job_name": "id-test",
        })
        assert r.json()["job_id"] == "j-abc"

    def test_inject_job_with_workstation_none(self, agent_client_dtg: TestClient) -> None:
        """Omitting workstation (auto-allocate) should succeed."""
        r = agent_client_dtg.post("/jobs", json={
            "job_id": "j2",
            "order_id": "o2",
            "prn_path": "/fake/test.prn",
            "job_name": "ws-auto",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_inject_job_with_workstation_0(self, agent_client_dtg: TestClient) -> None:
        """DTG: inject with explicit workstation=0 should succeed."""
        r = agent_client_dtg.post("/jobs", json={
            "job_id": "j3",
            "order_id": "o3",
            "prn_path": "/fake/test.prn",
            "job_name": "ws0-test",
            "workstation": 0,
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_inject_job_with_workstation_1(self, agent_client_dtg: TestClient) -> None:
        """DTG: inject with explicit workstation=1 should succeed."""
        r = agent_client_dtg.post("/jobs", json={
            "job_id": "j4",
            "order_id": "o4",
            "prn_path": "/fake/test.prn",
            "job_name": "ws1-test",
            "workstation": 1,
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_inject_job_dtf(self, agent_client_dtf: TestClient) -> None:
        r = agent_client_dtf.post("/jobs", json={
            "job_id": "j5",
            "order_id": "o5",
            "prn_path": "/fake/test.prn",
            "job_name": "dtf-test",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_inject_job_uv(self, agent_client_uv: TestClient) -> None:
        r = agent_client_uv.post("/jobs", json={
            "job_id": "j6",
            "order_id": "o6",
            "prn_path": "/fake/test.prn",
            "job_name": "uv-test",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_inject_job_missing_required_fields_422(self, agent_client_dtg: TestClient) -> None:
        """Missing job_id/order_id/prn_path should be rejected."""
        r = agent_client_dtg.post("/jobs", json={"job_name": "incomplete"})
        assert r.status_code == 422


class TestAgentControl:
    """POST /control/{command} — named movement and print commands."""

    def test_control_pause_dtg(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/control/pause")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_control_cancel_dtf(self, agent_client_dtf: TestClient) -> None:
        r = agent_client_dtf.post("/control/cancel")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_control_home_x_uv(self, agent_client_uv: TestClient) -> None:
        r = agent_client_uv.post("/control/home_x")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_control_returns_command_name(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/control/move_left")
        assert r.json()["command"] == "move_left"

    def test_control_print_start(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/control/print_start")
        assert r.status_code == 200

    def test_control_home_y(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/control/home_y")
        assert r.status_code == 200

    def test_control_clean_dtf(self, agent_client_dtf: TestClient) -> None:
        r = agent_client_dtf.post("/control/clean")
        assert r.status_code == 200

    def test_control_flash_uv(self, agent_client_uv: TestClient) -> None:
        r = agent_client_uv.post("/control/flash")
        assert r.status_code == 200

    def test_control_unknown_command_accepted_by_mock(self, agent_client_dtg: TestClient) -> None:
        """MockBackend accepts any command string — real backends would reject unknown cmds."""
        r = agent_client_dtg.post("/control/totally_unknown_cmd")
        assert r.status_code == 200


class TestAgentFileList:
    """GET /files — list .prn/.prt files and directories."""

    def test_files_no_dir_returns_list(self, agent_client_dtg: TestClient) -> None:
        """Empty dir param returns common root locations."""
        r = agent_client_dtg.get("/files")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_files_nonexistent_dir_404(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.get("/files", params={"dir": "/nonexistent/path/xyz"})
        assert r.status_code == 404


class TestAgentPrintMode:
    """GET/POST /print-mode — UV-only print preset management."""

    def test_print_mode_not_available_on_dtg(self, agent_client_dtg: TestClient) -> None:
        """DTG agent has no print mode service — expect 404."""
        r = agent_client_dtg.get("/print-mode")
        assert r.status_code == 404

    def test_print_mode_not_available_on_dtf(self, agent_client_dtf: TestClient) -> None:
        r = agent_client_dtf.get("/print-mode")
        assert r.status_code == 404

    def test_set_print_mode_not_available_on_dtg(self, agent_client_dtg: TestClient) -> None:
        r = agent_client_dtg.post("/print-mode", json={"preset": "standard"})
        assert r.status_code == 404
