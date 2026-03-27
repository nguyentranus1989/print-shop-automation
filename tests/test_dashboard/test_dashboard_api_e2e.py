"""E2E tests for Dashboard API — printers, jobs, control."""
from __future__ import annotations

import pytest


class TestDashboardHealth:
    def test_health(self, dashboard_client):
        r = dashboard_client.get("/health")
        assert r.status_code == 200
        assert r.json()["service"] == "printflow-dashboard"


class TestPrinterCRUD:
    def test_register_printer(self, dashboard_client):
        r = dashboard_client.post("/api/printers", json={
            "name": "Test DTG", "agent_url": "http://localhost:9001", "printer_type": "dtg"
        })
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Test DTG"
        assert d["printer_type"] == "dtg"
        assert "id" in d

    def test_list_printers_json(self, dashboard_client):
        # Register first
        dashboard_client.post("/api/printers", json={
            "name": "P1", "agent_url": "http://localhost:9002", "printer_type": "dtf"
        })
        r = dashboard_client.get("/api/printers", headers={"Accept": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_printers_htmx(self, dashboard_client):
        """HTMX request returns HTML partial."""
        dashboard_client.post("/api/printers", json={
            "name": "P2", "agent_url": "http://localhost:9003", "printer_type": "uv"
        })
        r = dashboard_client.get("/api/printers", headers={"Accept": "text/html", "hx-request": "true"})
        assert r.status_code == 200
        # Should be HTML, not JSON
        assert "<" in r.text

    def test_delete_printer(self, dashboard_client):
        r = dashboard_client.post("/api/printers", json={
            "name": "ToDelete", "agent_url": "http://localhost:9004", "printer_type": "dtg"
        })
        pid = r.json()["id"]
        r = dashboard_client.delete(f"/api/printers/{pid}")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_update_printer(self, dashboard_client):
        r = dashboard_client.post("/api/printers", json={
            "name": "Old Name", "agent_url": "http://localhost:9005", "printer_type": "dtg"
        })
        pid = r.json()["id"]
        r = dashboard_client.patch(f"/api/printers/{pid}", json={"name": "New Name"})
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"


class TestPrinterControl:
    def _register(self, client, name, url, ptype="dtg"):
        r = client.post("/api/printers", json={"name": name, "agent_url": url, "printer_type": ptype})
        return r.json()["id"]

    def test_control_sends_command(self, dashboard_client):
        pid = self._register(dashboard_client, "CtrlTest", "http://localhost:9010")
        r = dashboard_client.post(f"/api/printers/{pid}/control", json={"command": "pause"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_control_with_workstation(self, dashboard_client):
        """DTG control with workstation param should send ws selection first."""
        pid = self._register(dashboard_client, "WSCtrl", "http://localhost:9011", "dtg")
        r = dashboard_client.post(f"/api/printers/{pid}/control", json={
            "command": "print_start", "workstation": 0
        })
        assert r.status_code == 200

    def test_control_printer_not_found(self, dashboard_client):
        r = dashboard_client.post("/api/printers/9999/control", json={"command": "pause"})
        assert r.status_code == 404


class TestJobsCRUD:
    def test_create_job(self, dashboard_client):
        r = dashboard_client.post("/api/jobs", json={
            "order_id": "ORD-001", "prn_path": "D:\\Rip\\test.prn",
            "printer_type": "dtg", "copies": 1
        })
        assert r.status_code == 200
        d = r.json()
        assert d["order_id"] == "ORD-001"
        assert d["status"] == "pending"

    def test_list_jobs_json(self, dashboard_client):
        dashboard_client.post("/api/jobs", json={
            "order_id": "ORD-002", "prn_path": "/test.prn", "printer_type": "dtf"
        })
        r = dashboard_client.get("/api/jobs")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_list_jobs_htmx_returns_html(self, dashboard_client):
        dashboard_client.post("/api/jobs", json={
            "order_id": "ORD-003", "prn_path": "/test.prn", "printer_type": "uv"
        })
        r = dashboard_client.get("/api/jobs", headers={"hx-request": "true"})
        assert r.status_code == 200
        assert "<tr>" in r.text

    def test_list_jobs_empty_htmx(self, dashboard_client):
        r = dashboard_client.get("/api/jobs", headers={"hx-request": "true"})
        assert r.status_code == 200
        assert "No jobs" in r.text

    def test_cancel_job(self, dashboard_client):
        r = dashboard_client.post("/api/jobs", json={
            "order_id": "ORD-004", "prn_path": "/test.prn", "printer_type": "dtg"
        })
        jid = r.json()["id"]
        r = dashboard_client.delete(f"/api/jobs/{jid}")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_update_job_status(self, dashboard_client):
        r = dashboard_client.post("/api/jobs", json={
            "order_id": "ORD-005", "prn_path": "/test.prn", "printer_type": "dtf"
        })
        jid = r.json()["id"]
        r = dashboard_client.patch(f"/api/jobs/{jid}", json={"status": "printing"})
        assert r.status_code == 200
        assert r.json()["status"] == "printing"


class TestHeartbeat:
    def test_heartbeat_updates_status(self, dashboard_client):
        # Register printer first
        dashboard_client.post("/api/printers", json={
            "name": "HB-Test", "agent_url": "http://localhost:9020", "printer_type": "dtg"
        })
        r = dashboard_client.post("/api/printers/heartbeat", json={
            "agent_url": "http://localhost:9020",
            "connected": True, "printing": False, "printer_type": "dtg"
        })
        assert r.status_code == 200
        assert r.json()["status"] == "online"

    def test_heartbeat_with_ws_fields(self, dashboard_client):
        dashboard_client.post("/api/printers", json={
            "name": "HB-WS", "agent_url": "http://localhost:9021", "printer_type": "dtg"
        })
        r = dashboard_client.post("/api/printers/heartbeat", json={
            "agent_url": "http://localhost:9021",
            "connected": True, "printing": True, "printer_type": "dtg",
            "active_ws": 0, "ws0_busy": True, "ws1_busy": False
        })
        assert r.status_code == 200
        assert r.json()["status"] == "printing"
