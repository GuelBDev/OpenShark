import json
import tempfile
import unittest
from pathlib import Path

from OpenShark.profiles import ProfileStore, default_profile, validate_profile
from OpenShark.protocol import (build_buttons, build_dpi, build_polling,
                                build_power, reports_for)


class ProtocolTests(unittest.TestCase):
    def test_report_lengths_headers_and_checksums(self):
        for model in ("R1", "X6", "X11"):
            with self.subTest(model=model):
                profile = default_profile(model)
                dpi = build_dpi(profile)
                buttons = build_buttons(profile)
                polling = build_polling(profile)
                self.assertEqual((len(dpi), dpi[:3]),
                                 (56, bytes((0x04, 0x38, profile["active_stage"]))))
                self.assertEqual(int.from_bytes(dpi[50:52], "big"), sum(dpi[3:50]))
                self.assertEqual((len(buttons), buttons[:3]), (59, b"\x08\x3b\x01"))
                self.assertEqual(int.from_bytes(buttons[57:59], "big"), sum(buttons[3:57]))
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
