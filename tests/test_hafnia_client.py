import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from src.hafnia_client import HafniaClient, build_xprotect_uri


class TestHafniaClient(unittest.TestCase):
    @patch('src.hafnia_client.requests.Session')
    def test_login_successful(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        # Mock login response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'Id': 'session-123'}
        mock_session.post.return_value = mock_response
        # Initialize client (will read env vars, set dummy values)
        with patch.dict('os.environ', {'HAFNIA_PASSWORD': 'secret'}):
            client = HafniaClient(enabled=True)
            client._ensure_logged_in()
        self.assertEqual(client.session_id, 'session-123')
        mock_session.headers.update.assert_called_with({'X-Session-Id': 'session-123'})

    @patch('src.hafnia_client.requests.Session')
    def test_submit_summary(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        # Mock login first
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {'Id': 'session-123'}
        # Mock summary submit response
        submit_response = MagicMock()
        submit_response.status_code = 200
        submit_response.json.return_value = {'Id': 'summary-456'}
        mock_session.post.side_effect = [login_response, submit_response]
        with patch.dict('os.environ', {'HAFNIA_PASSWORD': 'secret'}):
            client = HafniaClient(enabled=True)
            request_id = client.submit_summary('test prompt', 'xprotect://test')
        self.assertEqual(request_id, 'summary-456')
        # Ensure correct payload
        expected_payload = {
            'Prompt': 'test prompt',
            'VideoUris': ['xprotect://test'],
            'AiModelId': 'traffic-general'
        }
        mock_session.post.assert_called_with(
            client._url('/api/Summaries'), json=expected_payload, timeout=client.timeout
        )


class TestBuildXprotectUri(unittest.TestCase):
    """Tests for build_xprotect_uri() – no network connection required."""

    def _utc(self, **kwargs) -> datetime:
        """Return a UTC-aware datetime for 2026-10-31 with given H/M/S overrides."""
        return datetime(2026, 10, 31, tzinfo=timezone.utc).replace(**kwargs)

    def test_uri_contains_camera_id(self):
        start = self._utc(hour=10, minute=0, second=0)
        end   = self._utc(hour=10, minute=0, second=30)
        uri = build_xprotect_uri("CAMERA-GUID-123", start, end)
        self.assertIn("CAMERA-GUID-123", uri)
        self.assertTrue(uri.startswith("xprotect://localhost/cameras/CAMERA-GUID-123"))

    def test_timestamps_formatted_with_seconds_and_z_suffix(self):
        start = datetime(2026, 10, 31, 10, 5, 17, tzinfo=timezone.utc)
        end   = datetime(2026, 10, 31, 10, 5, 47, tzinfo=timezone.utc)
        uri = build_xprotect_uri("CAM", start, end)
        self.assertIn("StartTime=2026-10-31T10:05:17Z", uri)
        self.assertIn("EndTime=2026-10-31T10:05:47Z",   uri)
        # Must not contain bare +00:00 (the Gateway reads '+' as a space)
        self.assertNotIn("+00:00", uri)

    def test_seconds_are_preserved_in_uri(self):
        """Seconds must not be truncated to 00."""
        start = datetime(2026, 10, 31, 14, 30, 7,  tzinfo=timezone.utc)
        end   = datetime(2026, 10, 31, 14, 30, 59, tzinfo=timezone.utc)
        uri = build_xprotect_uri("CAM", start, end)
        self.assertIn("T14:30:07Z", uri)
        self.assertIn("T14:30:59Z", uri)

    def test_raises_when_end_equals_start(self):
        dt = datetime(2026, 10, 31, 10, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            build_xprotect_uri("CAM", dt, dt)

    def test_raises_when_end_before_start(self):
        start = datetime(2026, 10, 31, 10, 0, 30, tzinfo=timezone.utc)
        end   = datetime(2026, 10, 31, 10, 0,  0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            build_xprotect_uri("CAM", start, end)

    def test_raises_for_naive_start(self):
        naive  = datetime(2026, 10, 31, 10, 0, 0)           # no tzinfo
        aware  = datetime(2026, 10, 31, 10, 0, 30, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            build_xprotect_uri("CAM", naive, aware)

    def test_raises_for_naive_end(self):
        aware  = datetime(2026, 10, 31, 10, 0, 0,  tzinfo=timezone.utc)
        naive  = datetime(2026, 10, 31, 10, 0, 30)
        with self.assertRaises(ValueError):
            build_xprotect_uri("CAM", aware, naive)

    def test_non_utc_offset_still_accepted(self):
        """A timezone-aware datetime with a non-UTC offset should be accepted;
        the URI will reflect the actual offset-converted value."""
        from datetime import timezone as tz
        cest = tz(timedelta(hours=2))
        start = datetime(2026, 10, 31, 12, 0, 0, tzinfo=cest)   # 10:00 UTC
        end   = datetime(2026, 10, 31, 12, 0, 30, tzinfo=cest)  # 10:00:30 UTC
        uri = build_xprotect_uri("CAM", start, end)
        # The function should not raise; URI must end with Z (not an offset)
        self.assertNotIn("+02:00", uri)
        self.assertNotIn("+00:00", uri)


if __name__ == '__main__':
    unittest.main()
