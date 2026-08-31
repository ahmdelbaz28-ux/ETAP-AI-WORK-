"""
tests/test_daytona_chrome_helper.py — Tests for Daytona standalone Chrome CDP helper.
"""

from unittest.mock import MagicMock, patch

import pytest

from scripts.daytona_chrome_helper import (
    get_chrome_launch_command,
    get_chrome_stop_command,
    launch_chrome_in_sandbox,
    stop_chrome_in_sandbox,
    verify_cdp_endpoint,
)


class TestDaytonaChromeHelper:
    def test_launch_command_contains_required_flags(self):
        cmd = get_chrome_launch_command(port=9222, profile_dir="/tmp/test-profile")
        assert "--remote-debugging-port=9222" in cmd
        assert "--remote-debugging-address=0.0.0.0" in cmd
        assert "--no-sandbox" in cmd
        assert "--disable-dev-shm-usage" in cmd
        assert "/tmp/test-profile" in cmd

    def test_stop_command_targets_port(self):
        cmd = get_chrome_stop_command(port=9222)
        assert "pkill" in cmd
        assert "9222" in cmd

    def test_launch_in_sandbox_calls_exec(self):
        sandbox = MagicMock()
        sandbox.exec.return_value = MagicMock(exit_code=0)
        assert launch_chrome_in_sandbox(sandbox, port=9222) is True
        sandbox.exec.assert_called_once()

    def test_stop_in_sandbox_calls_exec(self):
        sandbox = MagicMock()
        sandbox.exec.return_value = MagicMock(exit_code=0)
        assert stop_chrome_in_sandbox(sandbox, port=9222) is True
        sandbox.exec.assert_called_once()

    def test_verify_cdp_endpoint_validates_chrome_and_rejects_electron(self):
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"Browser": "Chrome/120.0.0.0", "Protocol-Version": "1.3", '
            b'"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}'
        )
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            res = verify_cdp_endpoint("http://localhost:9222")
            assert res["status"] == "online"
            assert res["is_valid_chrome"] is True

        # Test rejection of Electron
        mock_electron = MagicMock()
        mock_electron.read.return_value = (
            b'{"Browser": "Chrome/120.0.0.0", "Protocol-Version": "1.3", '
            b'"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Electron/28.0.0 Chrome/120.0.0.0 Safari/537.36"}'
        )
        mock_electron.__enter__.return_value = mock_electron

        with patch("urllib.request.urlopen", return_value=mock_electron):
            res = verify_cdp_endpoint("http://localhost:9222")
            assert res["is_valid_chrome"] is False
