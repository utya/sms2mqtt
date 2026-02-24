"""Unit tests for LOG_LEVEL parsing and MQTT disconnect behaviour (no exit)."""
import logging
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock heavy deps so sms2mqtt can be imported without gammu/paho installed (e.g. in CI)
for mod in ("gammu", "certifi"):
    sys.modules.setdefault(mod, MagicMock())
paho_mock = MagicMock()
sys.modules["paho"] = paho_mock
sys.modules["paho.mqtt"] = paho_mock
sys.modules["paho.mqtt.client"] = paho_mock

import sms2mqtt


class TestParseLogLevel(unittest.TestCase):
    """Tests for parse_log_level helper."""

    def test_debug(self):
        self.assertEqual(sms2mqtt.parse_log_level("DEBUG"), logging.DEBUG)
        self.assertEqual(sms2mqtt.parse_log_level("debug"), logging.DEBUG)

    def test_info(self):
        self.assertEqual(sms2mqtt.parse_log_level("INFO"), logging.INFO)
        self.assertEqual(sms2mqtt.parse_log_level("info"), logging.INFO)

    def test_warning(self):
        self.assertEqual(sms2mqtt.parse_log_level("WARNING"), logging.WARNING)
        self.assertEqual(sms2mqtt.parse_log_level("WARN"), logging.WARNING)
        self.assertEqual(sms2mqtt.parse_log_level("warn"), logging.WARNING)

    def test_error(self):
        self.assertEqual(sms2mqtt.parse_log_level("ERROR"), logging.ERROR)
        self.assertEqual(sms2mqtt.parse_log_level("error"), logging.ERROR)

    def test_invalid_fallback_to_info(self):
        self.assertEqual(sms2mqtt.parse_log_level("INVALID"), logging.INFO)
        self.assertEqual(sms2mqtt.parse_log_level(""), logging.INFO)
        self.assertEqual(sms2mqtt.parse_log_level(None), logging.INFO)
        self.assertEqual(sms2mqtt.parse_log_level("  "), logging.INFO)


class TestOnMqttDisconnect(unittest.TestCase):
    """Ensure on_mqtt_disconnect does not call exit (reconnection behaviour)."""

    def test_disconnect_does_not_call_exit(self):
        with patch.object(sys, "exit") as mock_exit:
            sms2mqtt.on_mqtt_disconnect(None, None, 0)
            mock_exit.assert_not_called()

    def test_disconnect_sets_mqtt_connected_false(self):
        sms2mqtt.mqtt_connected[0] = True
        sms2mqtt.on_mqtt_disconnect(None, None, 5)
        self.assertFalse(sms2mqtt.mqtt_connected[0])


if __name__ == "__main__":
    unittest.main()
