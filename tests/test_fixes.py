import unittest
from OpenShark.monitor import identify_model, parse_stage_event
from OpenShark.updates import repository, version


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
