"""Tests for received SMS publish: QoS 1, no delete on publish failure, stuck_status dedupe."""

import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mock heavy deps so mqtt_layer can be imported without gammu (e.g. in CI)
for mod in ("gammu", "certifi"):
    sys.modules.setdefault(mod, MagicMock())
paho_mock = MagicMock()
sys.modules["paho"] = paho_mock
sys.modules["paho.mqtt"] = paho_mock
sys.modules["paho.mqtt.client"] = paho_mock

import mqtt_layer  # noqa: E402


def _single_sms_linked():
    """One single-part SMS as returned by link_sms (NoUDH)."""
    return [
        [
            {
                "UDH": {"Type": "NoUDH"},
                "DateTime": "2026-02-25 12:00:00",
                "Number": "900",
                "Text": "Test message",
                "Location": 1,
            }
        ]
    ]


def _incomplete_multipart_linked():
    """Incomplete multipart: 1 part received, 2 expected (as returned by link_sms)."""
    return [
        [
            {
                "UDH": {"Type": "ConcatenatedAutoTextLong", "AllParts": 2, "PartNumber": 1},
                "DateTime": "2026-02-25 12:36:56",
                "Number": "gosuslugi",
                "Text": "Part1",
                "Location": 100001,
            }
        ]
    ]


class TestReceivedPublish(unittest.TestCase):
    """Publish received SMS with QoS 1; do not delete from modem when publish fails."""

    def test_single_sms_publish_called_with_qos_1(self):
        ctx = SimpleNamespace(
            config=SimpleNamespace(prefix="test"),
            client=MagicMock(),
            gammusm=MagicMock(),
            stuck_sms_detected=False,
            last_stuck_sms=[],
            last_stuck_locations=None,
        )
        ctx.client.publish.return_value = MagicMock(rc=0, mid=1)

        with patch.object(mqtt_layer, "gammu_io") as gio:
            gio.fetch_sms_batch.return_value = [[{"UDH": {"Type": "NoUDH"}, "DateTime": "2026-02-25 12:00:00", "Number": "900", "Text": "Test", "Location": 1}]]
            gio.link_sms.return_value = _single_sms_linked()

            mqtt_layer.loop_sms_receive(ctx)

        ctx.client.publish.assert_called_once()
        call_kw = ctx.client.publish.call_args
        self.assertEqual(call_kw[0][0], "test/received")
        self.assertEqual(call_kw[1].get("qos"), 1, "received SMS must be published with qos=1")
        gio.delete_sms.assert_called_once_with(ctx.gammusm, 0, 1)

    def test_single_sms_delete_skipped_when_publish_fails(self):
        ctx = SimpleNamespace(
            config=SimpleNamespace(prefix="test"),
            client=MagicMock(),
            gammusm=MagicMock(),
            stuck_sms_detected=False,
            last_stuck_sms=[],
            last_stuck_locations=None,
        )
        # rc != 0: e.g. MQTT_ERR_NO_CONN (4)
        ctx.client.publish.return_value = MagicMock(rc=4, mid=0)

        with patch.object(mqtt_layer, "gammu_io") as gio:
            gio.fetch_sms_batch.return_value = [[{"UDH": {"Type": "NoUDH"}, "DateTime": "2026-02-25 12:00:00", "Number": "900", "Text": "Test", "Location": 1}]]
            gio.link_sms.return_value = _single_sms_linked()

            mqtt_layer.loop_sms_receive(ctx)

        ctx.client.publish.assert_called_once()
        gio.delete_sms.assert_not_called()

    def test_stuck_status_published_once_for_same_incomplete_multipart(self):
        """Stuck_status is published only once per stuck set; second loop does not republish."""
        ctx = SimpleNamespace(
            config=SimpleNamespace(prefix="test"),
            client=MagicMock(),
            gammusm=MagicMock(),
            stuck_sms_detected=False,
            last_stuck_sms=[],
            last_stuck_locations=None,
        )
        ctx.client.publish.return_value = MagicMock(rc=0, mid=1)

        with patch.object(mqtt_layer, "gammu_io") as gio:
            gio.fetch_sms_batch.return_value = [[{"UDH": {"AllParts": 2}, "Location": 100001}]]
            gio.link_sms.return_value = _incomplete_multipart_linked()

            mqtt_layer.loop_sms_receive(ctx)
            mqtt_layer.loop_sms_receive(ctx)

        stuck_calls = [
            c for c in ctx.client.publish.call_args_list
            if c[0][0] == "test/stuck_status"
        ]
        self.assertEqual(len(stuck_calls), 1, "stuck_status must be published exactly once for same incomplete set")
        payload = json.loads(stuck_calls[0][0][1])
        self.assertEqual(payload["status"], "stuck")
        self.assertEqual(payload["received_parts"], 1)
        self.assertEqual(payload["expected_parts"], 2)
        self.assertEqual(payload["number"], "gosuslugi")
        self.assertEqual(payload["locations"], [100001])


if __name__ == "__main__":
    unittest.main()
