"""Tests for WM_COMMAND button ID maps and controller dispatch logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from common.protocols.wm_command import (
    DTG_BUTTONS,
    DTF_BUTTONS,
    UV_BUTTONS,
    WM_COMMAND,
    WMCommandController,
)


class TestButtonIdMaps:
    """Verify that button maps contain required actions and valid control IDs."""

    _REQUIRED_ACTIONS = {
        "move_left",
        "move_right",
        "move_ahead",
        "move_back",
        "print_start",
        "pause",
        "cancel",
        "home_x",
        "home_y",
        "clean",
        "flash",
    }

    def test_dtg_has_all_required_actions(self) -> None:
        assert self._REQUIRED_ACTIONS.issubset(DTG_BUTTONS.keys())

    def test_dtf_has_all_required_actions(self) -> None:
        assert self._REQUIRED_ACTIONS.issubset(DTF_BUTTONS.keys())

    def test_uv_has_all_required_actions(self) -> None:
        assert self._REQUIRED_ACTIONS.issubset(UV_BUTTONS.keys())

    def test_dtg_all_ids_are_nonzero_ints(self) -> None:
        for action, ctrl_id in DTG_BUTTONS.items():
            assert isinstance(ctrl_id, int), f"{action} ctrl_id is not int"
            assert ctrl_id != 0, f"{action} ctrl_id is zero"

    def test_dtf_overrides_clean_id(self) -> None:
        """DTF clean control ID differs from DTG."""
        assert DTF_BUTTONS["clean"] != DTG_BUTTONS["clean"]

    def test_uv_movement_ids_differ_from_dtg(self) -> None:
        """UV movement IDs should differ from DTG (different builds)."""
        for action in ["move_left", "move_right", "move_ahead", "move_back"]:
            assert DTG_BUTTONS[action] != UV_BUTTONS[action], (
                f"UV and DTG should have different ctrl_id for '{action}'"
            )

    def test_uv_has_z_controls(self) -> None:
        assert "z_up" in UV_BUTTONS
        assert "z_down" in UV_BUTTONS
        assert "z_axis" in UV_BUTTONS

    def test_wm_command_constant(self) -> None:
        assert WM_COMMAND == 0x0111


class TestWMCommandController:
    """Test controller dispatch with mocked Win32 calls."""

    def _make_controller(self, hwnd: int = 0xABCD) -> WMCommandController:
        ctrl = WMCommandController(buttons=DTG_BUTTONS)
        ctrl._hwnd = hwnd  # inject pre-found hwnd to skip EnumWindows
        return ctrl

    def test_send_named_looks_up_correct_ctrl_id(self) -> None:
        """send_named passes the right ctrl_id to send_command."""
        ctrl = self._make_controller()
        with patch.object(ctrl, "send_command", return_value=True) as mock_send:
            ctrl.send_named("print_start")
            mock_send.assert_called_once_with(DTG_BUTTONS["print_start"])

    def test_unknown_action_raises_key_error(self) -> None:
        ctrl = self._make_controller()
        with pytest.raises(KeyError, match="unknown_action"):
            ctrl.send_named("unknown_action")

    def test_convenience_methods_delegate_to_send_named(self) -> None:
        ctrl = self._make_controller()
        actions_and_methods = [
            ("move_left", ctrl.move_left),
            ("move_right", ctrl.move_right),
            ("move_ahead", ctrl.move_ahead),
            ("move_back", ctrl.move_back),
            ("print_start", ctrl.print_start),
            ("pause", ctrl.pause),
            ("cancel", ctrl.cancel),
            ("home_x", ctrl.home_x),
            ("home_y", ctrl.home_y),
            ("clean", ctrl.clean),
            ("flash", ctrl.flash),
        ]
        for action, method in actions_and_methods:
            with patch.object(ctrl, "send_command", return_value=True) as mock_send:
                method()
                mock_send.assert_called_once_with(DTG_BUTTONS[action])

    def test_send_command_returns_false_when_no_hwnd(self) -> None:
        """If window not found, send_command should return False (not crash)."""
        ctrl = WMCommandController()
        ctrl._hwnd = None
        # Mock find_printexp_window to also return None
        with patch.object(ctrl, "find_printexp_window", return_value=None):
            result = ctrl.send_command(DTG_BUTTONS["print_start"])
        assert result is False

    def test_send_command_calls_post_message_on_windows(self) -> None:
        """On mock Windows, PostMessageW should be called with correct args."""
        ctrl = self._make_controller(hwnd=0x1234)
        mock_user32 = MagicMock()
        mock_user32.PostMessageW.return_value = 1  # success

        with patch("common.protocols.win32_window_helpers.load_user32", return_value=(None, mock_user32)):
            with patch("common.protocols.wm_command.post_message", side_effect=lambda hwnd, msg, wp, lp: mock_user32.PostMessageW(hwnd, msg, wp, lp)):
                ctrl.send_command(DTG_BUTTONS["print_start"])

        mock_user32.PostMessageW.assert_called_once_with(
            0x1234,
            WM_COMMAND,
            DTG_BUTTONS["print_start"],
            0,
        )
