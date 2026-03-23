"""Tests for MockBackend — no real printer required."""

from __future__ import annotations

import asyncio

import pytest

from common.models.printer import PrinterType
from agent.printer.mock import MockBackend


@pytest.fixture
def backend() -> MockBackend:
    """Default mock backend with no failures."""
    return MockBackend(
        printer_type=PrinterType.DTG,
        inject_delay=0.01,  # fast for tests
        failure_rate=0.0,   # deterministic: never fail
    )


@pytest.fixture
def failing_backend() -> MockBackend:
    """Mock backend that always fails."""
    return MockBackend(
        printer_type=PrinterType.DTG,
        inject_delay=0.01,
        failure_rate=1.0,  # always fail
    )


class TestMockBackendInjectJob:
    """inject_job succeeds and fails as configured."""

    async def test_inject_job_returns_true_on_success(self, backend: MockBackend) -> None:
        result = await backend.inject_job("/fake/path/job.prn", "test-job")
        assert result is True

    async def test_inject_job_returns_false_on_failure(self, failing_backend: MockBackend) -> None:
        result = await failing_backend.inject_job("/fake/path/job.prn", "test-job")
        assert result is False

    async def test_inject_job_is_not_printing_after_completion(self, backend: MockBackend) -> None:
        await backend.inject_job("/fake/path/job.prn", "test-job")
        status = await backend.get_status()
        assert status.printing is False
        assert status.current_job is None

    async def test_inject_job_reduces_ink_levels(self, backend: MockBackend) -> None:
        """Ink levels should decrease after a successful job."""
        status_before = await backend.get_status()
        initial_levels = dict(status_before.ink_levels)

        await backend.inject_job("/fake/path/job.prn", "ink-test")

        status_after = await backend.get_status()
        # At least one channel should have decreased
        decreased = any(
            status_after.ink_levels.get(ch, 0) < initial_levels[ch]
            for ch in initial_levels
        )
        assert decreased

    async def test_failed_inject_does_not_reduce_ink(self, failing_backend: MockBackend) -> None:
        """Failed jobs should not consume ink."""
        status_before = await failing_backend.get_status()
        initial_levels = dict(status_before.ink_levels)

        await failing_backend.inject_job("/fake/path/job.prn", "fail-test")

        status_after = await failing_backend.get_status()
        assert status_after.ink_levels == initial_levels


class TestMockBackendGetStatus:
    """get_status returns plausible data."""

    async def test_get_status_connected(self, backend: MockBackend) -> None:
        status = await backend.get_status()
        assert status.connected is True

    async def test_get_status_not_printing_initially(self, backend: MockBackend) -> None:
        status = await backend.get_status()
        assert status.printing is False

    async def test_get_status_has_ink_levels(self, backend: MockBackend) -> None:
        status = await backend.get_status()
        assert isinstance(status.ink_levels, dict)
        assert len(status.ink_levels) > 0

    async def test_get_status_returns_correct_type(self, backend: MockBackend) -> None:
        status = await backend.get_status()
        assert status.type == PrinterType.DTG

    async def test_get_status_all_ink_levels_in_range(self, backend: MockBackend) -> None:
        status = await backend.get_status()
        for channel, level in status.ink_levels.items():
            assert 0.0 <= level <= 100.0, f"Ink level for {channel!r} out of range: {level}"


class TestMockBackendSendCommand:
    """send_command always returns True and is non-blocking."""

    async def test_send_command_returns_true(self, backend: MockBackend) -> None:
        result = await backend.send_command("print_start")
        assert result is True

    async def test_send_command_unknown_action_returns_true(self, backend: MockBackend) -> None:
        """Mock accepts any command string."""
        result = await backend.send_command("this_is_not_real")
        assert result is True

    async def test_send_command_is_fast(self, backend: MockBackend) -> None:
        """Should complete nearly instantly (mocked delay is 10ms)."""
        import time
        start = time.monotonic()
        await backend.send_command("home_x")
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # generous upper bound for CI
