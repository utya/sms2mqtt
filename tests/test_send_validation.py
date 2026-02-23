"""Unit tests for send payload parsing and validation (no MQTT/Gammu)."""
import sys
import unittest
from unittest.mock import MagicMock

# Mock heavy deps so sms2mqtt can be imported without gammu/paho installed (e.g. in CI)
for mod in ("gammu", "certifi"):
    sys.modules.setdefault(mod, MagicMock())
paho_mock = MagicMock()
sys.modules["paho"] = paho_mock
sys.modules["paho.mqtt"] = paho_mock
sys.modules["paho.mqtt.client"] = paho_mock

import sms2mqtt


class TestValidateSendPayload(unittest.TestCase):
    """Tests for validate_send_payload — JSON decode, UTF-8, number/text validation."""

    def test_valid_number_and_text_returns_success(self):
        payload = b'{"number": "+79001234567", "text": "Hello"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNone(err)
        self.assertEqual(number, "+79001234567")
        self.assertEqual(text, "Hello")

    def test_valid_case_insensitive_keys(self):
        payload = b'{"NUMBER": "123", "TEXT": "Hi"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNone(err)
        self.assertEqual(number, "123")
        self.assertEqual(text, "Hi")

    def test_missing_number_returns_error(self):
        payload = b'{"text": "No number"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIsNone(number)
        self.assertIsNone(text)
        self.assertIn("result", err)
        self.assertIn("payload", err)
        self.assertIn("no number", err["result"].lower())

    def test_missing_text_returns_error(self):
        payload = b'{"number": "+7900"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("result", err)
        self.assertIn("payload", err)
        self.assertIn("no text", err["result"].lower())

    def test_number_not_string_returns_error(self):
        payload = b'{"number": 123, "text": "Hi"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("no number", err["result"].lower())

    def test_number_empty_string_returns_error(self):
        payload = b'{"number": "", "text": "Hi"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("no number", err["result"].lower())

    def test_number_whitespace_only_returns_error(self):
        payload = b'{"number": "   ", "text": "Hi"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("no number", err["result"].lower())

    def test_text_not_string_returns_error(self):
        payload = b'{"number": "+7900", "text": 42}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("result", err)
        self.assertIn("payload", err)
        self.assertIn("no text", err["result"].lower())

    def test_invalid_json_returns_error(self):
        payload = b'{"number": "123", "text": invalid}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("result", err)
        self.assertIn("payload", err)
        self.assertIn("decode", err["result"].lower())
        self.assertIn("json", err["result"].lower())

    def test_non_utf8_returns_error_with_safe_payload(self):
        payload = b'\xff\xfe not valid UTF-8 \x80'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNotNone(err)
        self.assertIn("result", err)
        self.assertIn("payload", err)
        self.assertIsInstance(err["payload"], str)

    def test_semicolon_separated_numbers_accepted(self):
        payload = b'{"number": "+7900;+7901", "text": "Multi"}'
        number, text, err = sms2mqtt.validate_send_payload(payload)
        self.assertIsNone(err)
        self.assertEqual(number, "+7900;+7901")
        self.assertEqual(text, "Multi")


if __name__ == "__main__":
    unittest.main()
