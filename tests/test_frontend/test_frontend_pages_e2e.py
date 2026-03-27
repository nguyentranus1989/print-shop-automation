"""E2E tests for Dashboard frontend — HTML pages and UI elements."""
from __future__ import annotations

import pytest


class TestPageRendering:
    def test_dashboard_page(self, dashboard_client):
        r = dashboard_client.get("/")
        assert r.status_code == 200
        assert "PrintFlow" in r.text

    def test_jobs_page(self, dashboard_client):
        r = dashboard_client.get("/jobs")
        assert r.status_code == 200
        assert "job-tbody" in r.text

    def test_printers_page(self, dashboard_client):
        r = dashboard_client.get("/printers")
        assert r.status_code == 200
        assert "control-grid" in r.text
        assert "printer-tabs" in r.text

    def test_printers_page_has_ws_section(self, dashboard_client):
        """WS section should exist (hidden by default, shown for DTG via JS)."""
        r = dashboard_client.get("/printers")
        assert "ws-section" in r.text
        assert "ws-select" in r.text
        assert "WS:0" in r.text
        assert "WS:1" in r.text

    def test_printers_page_has_print_mode_section(self, dashboard_client):
        """Print mode section should exist (hidden by default, shown for UV via JS)."""
        r = dashboard_client.get("/printers")
        assert "print-mode-section" in r.text
        assert "print-mode-select" in r.text

    def test_printers_page_movement_controls(self, dashboard_client):
        r = dashboard_client.get("/printers")
        assert "dpad-wrap" in r.text
        assert "sendMove" in r.text
        assert "sendControl" in r.text

    def test_analytics_page(self, dashboard_client):
        r = dashboard_client.get("/analytics")
        assert r.status_code == 200


class TestStaticAssets:
    def test_printers_js_loaded(self, dashboard_client):
        r = dashboard_client.get("/static/printers-control.js")
        assert r.status_code == 200
        assert "selectPrinterTab" in r.text
        assert "selectedWorkstation" in r.text  # MULTIWS support
        assert "onWSSelect" in r.text
        assert "loadWSStatus" in r.text

    def test_printers_css_has_ws_styles(self, dashboard_client):
        r = dashboard_client.get("/static/pages-printers.css")
        assert r.status_code == 200
        assert ".ws-badge" in r.text
        assert ".ws-dot" in r.text
        assert "ws-pulse" in r.text


class TestJobTableHTMLEscaping:
    def test_html_escape_in_job_rows(self, dashboard_client):
        """Verify that special chars in job data are HTML-escaped."""
        dashboard_client.post("/api/jobs", json={
            "order_id": '<script>alert("xss")</script>',
            "prn_path": 'C:\\path\\"with&special<chars>',
            "printer_type": "dtg",
            "notes": "<b>bold</b>"
        })
        r = dashboard_client.get("/api/jobs", headers={"hx-request": "true"})
        assert r.status_code == 200
        # Should NOT contain raw HTML tags from user data
        assert "<script>" not in r.text
        assert "<b>bold</b>" not in r.text
        # Should contain escaped versions
        assert "&lt;script&gt;" in r.text or "alert" not in r.text
        assert "&lt;b&gt;" in r.text
