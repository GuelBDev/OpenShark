import unittest
from unittest.mock import patch
from io import BytesIO
import json
from OpenShark.monitor import identify_model, parse_stage_event
from OpenShark.updates import repository, version
from OpenShark import updates


class FixTests(unittest.TestCase):
    def test_model_identification_does_not_guess_shared_code(self):
        self.assertIsNone(identify_model([], 0x10))
        self.assertEqual(identify_model([{"product_string":"R1mouse"}]),"R1")
        self.assertEqual(identify_model([],0x55),"X11")

    def test_physical_dpi_event_excludes_battery_and_ack(self):
        self.assertEqual(parse_stage_event([3,16,16,6,0]),6)
        self.assertIsNone(parse_stage_event([3,16,64,3,10]))
        self.assertIsNone(parse_stage_event([3,16,80,0,4]))
        self.assertIsNone(parse_stage_event([3,16,16,0,0]))

    def test_update_repository_and_version_validation(self):
        self.assertEqual(repository("https://github.com/GuelBDev/OpenShark/"),"GuelBDev/OpenShark")
        self.assertGreater(version("v0.4.0"),version("0.3.0"))
        for value in ("https://example.com/a/b","a/b/../../c","a/b?token=1"):
            with self.assertRaises(ValueError):repository(value)

    def test_update_prefers_installer_for_installed_app(self):
        release = {"tag_name": "v0.6.0", "assets": [
            {"name": "OpenShark.exe", "browser_download_url": "https://github.com/GuelBDev/OpenShark/releases/download/v0.6.0/OpenShark.exe", "digest": "sha256:" + "a" * 64},
            {"name": "OpenShark-Setup-0.6.0.exe", "browser_download_url": "https://github.com/GuelBDev/OpenShark/releases/download/v0.6.0/OpenShark-Setup-0.6.0.exe", "digest": "sha256:" + "b" * 64},
        ]}
        with patch.object(updates, "VERSION", "0.5.0"), patch.object(updates, "urlopen", return_value=BytesIO(json.dumps(release).encode())), patch.object(updates, "SETTINGS") as settings:
            result = updates.check("GuelBDev/OpenShark")
        self.assertEqual(result["name"], "OpenShark-Setup-0.6.0.exe")
        self.assertEqual(result["sha256"], "b" * 64)
