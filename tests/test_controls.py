import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from OpenShark.profiles import ProfileStore, default_profile, validate_profile
from OpenShark.protocol import (build_buttons, build_dpi, build_polling,
                                build_power, reports_for)
from OpenShark.monitor import BatteryState, MouseMonitor


class ProtocolTests(unittest.TestCase):
    def test_report_lengths_headers_and_checksums(self):
        for model in ("R1", "X6", "X11"):
            with self.subTest(model=model):
                profile = default_profile(model)
                dpi = build_dpi(profile)
                buttons = build_buttons(profile)
                polling = build_polling(profile)
                self.assertEqual((len(dpi), dpi[:3]),
                                 (56, bytes((0x04, 0x38, 1 if model == "R1"
                                             else profile["active_stage"]))))
                self.assertEqual(int.from_bytes(dpi[50:52], "big"), sum(dpi[3:50]))
                self.assertEqual((len(buttons), buttons[:3]), (59, b"\x08\x3b\x01"))
                self.assertEqual(int.from_bytes(buttons[57:59], "big"), sum(buttons[3:57]))
                if model == "R1":
                    self.assertEqual(polling, bytes.fromhex("06 09 01 01 fe 00 00 00 00"))
                    self.assertEqual(len(reports_for(profile)), 4)
                else:
                    self.assertEqual(polling, dpi)
                    self.assertEqual(len(reports_for(profile)), 3)
                power = build_power(profile)
                self.assertEqual(len(power), 13 if model == "X6" else 15)
                self.assertEqual(int.from_bytes(power[11:13], "big"), sum(power[3:11]))

    def test_model_specific_dpi(self):
        r1 = build_dpi(default_profile("R1"))
        x6 = build_dpi(default_profile("X6"))
        x11 = build_dpi(default_profile("X11"))
        self.assertEqual(list(r1[8:14]), [0x12, 0x17, 0x1c, 0x20, 0x25, 0x2a])
        self.assertEqual(list(x6[8:14]), [0x0f, 0x17, 0x1f, 0x3f, 0x6f, 0x07])
        self.assertEqual(x6[21], 2)  # 26000 DPI high byte
        self.assertNotEqual(r1[8:14], x6[8:14])
        self.assertEqual(x11[6], 0x20)  # sixth stage uses double multiplier

    def test_r1_extreme_stages_match_documented_wire_codes(self):
        profile = default_profile("R1")
        profile["dpi"][:2] = [100, 18000]
        profile["active_stage"] = 2
        profile["angle_snap"] = True
        profile["ripple"] = True
        report = build_dpi(profile)
        self.assertEqual(report[2], 1)  # protocol command, not active stage
        self.assertEqual(report[3:5], b"\x01\x01")
        self.assertEqual(report[6:8], b"\x02\x02")
        self.assertEqual(report[8:10], b"\x02\xd3")
        self.assertEqual(report[24], 2)
        self.assertEqual(int.from_bytes(report[50:52], "big"), sum(report[3:50]))

    def test_write_without_receiver_ack_is_failure(self):
        class Device:
            def open_path(self, path): pass
            def send_feature_report(self, report): return len(report)
            def close(self): pass
        class HID:
            def enumerate(self): return [{"usage_page": 0x0b, "vendor_id": 0x1d57,
                                          "product_id": 0xfa60, "path": b"command"}]
            def device(self): return Device()
        monitor = MouseMonitor(HID())
        monitor._set_state(BatteryState(connected=True, vid=0x1d57,
                                        pid=0xfa60, model="R1"))
        with patch.object(monitor._ack_event, "wait", return_value=False):
            monitor._write_reports("R1", "dpi", [build_dpi(default_profile("R1"))])
        self.assertEqual(monitor.poll_result()[1], False)

    def test_power_and_button_values(self):
        p = default_profile("R1")
        p["response"] = 20
        p["buttons"][3] = "Clique duplo"
        power = build_power(p)
        buttons = build_buttons(p)
        self.assertEqual(power[10], 10)
        self.assertEqual(int.from_bytes(power[11:13], "big"), sum(power[3:11]))
        self.assertEqual(buttons[21], 7)  # forward physical button = wire slot 7


class ProfileTests(unittest.TestCase):
    def test_round_trip_import_and_model_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            store = ProfileStore(path)
            store.add("Jogo")
            store.current["dpi"][0] = 2400
            store.save()
            exported = Path(folder) / "jogo.json"
            store.export_file(exported)
            self.assertEqual(json.loads(exported.read_text(encoding="utf-8"))["name"], "Jogo")
            store.set_model("X6")
            self.assertEqual(store.current["name"], "Perfil 1")
            with self.assertRaises(ValueError):
                store.import_file(exported)
            reloaded = ProfileStore(path)
            reloaded.set_model("R1")
            self.assertEqual(reloaded.current["dpi"][0], 2400)

    def test_invalid_profiles_are_rejected(self):
        p = default_profile("R1")
        p["dpi"][0] = 1234
        with self.assertRaises(ValueError):
            validate_profile(p)
        p = default_profile("R1")
        p["response"] = 5
        with self.assertRaises(ValueError):
            validate_profile(p)


if __name__ == "__main__":
    unittest.main()
