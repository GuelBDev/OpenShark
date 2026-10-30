import unittest

from OpenShark.alerts import LowBatteryAlert
from OpenShark.monitor import BatteryState, device_candidate, parse_battery_event


class ProtocolTests(unittest.TestCase):
    def test_r1_x6_steps_and_x11_direct_percent(self):
        self.assertEqual(parse_battery_event([3, 0x10, 0x40, 1, 9]),
                         (0x10, 90, None))
        self.assertEqual(parse_battery_event([3, 0x85, 0x40, 1, 1]),
                         (0x85, 10, None))
        self.assertEqual(parse_battery_event([3, 0x55, 0x40, 1, 9]),
                         (0x55, 9, False))
        self.assertEqual(parse_battery_event([3, 0x55, 0x40, 3, 30]),
                         (0x55, 30, True))

    def test_invalid_reports_are_not_battery(self):
        for report in ([], [3, 0x10, 0x10, 1, 9],
                       [3, 0x10, 0x40, 1, 100], [3, 0x55, 0x40, 1, 0],
                       [3, 0x99, 0x40, 1, 9]):
            self.assertIsNone(parse_battery_event(report))

    def test_discovery_is_limited_to_battery_collection(self):
        self.assertTrue(device_candidate({"vendor_id": 0x1D57,
                                          "product_id": 0xFA60,
                                          "usage_page": 10}))
        self.assertFalse(device_candidate({"vendor_id": 0x1D57,
                                           "product_id": 0xFA60,
                                           "usage_page": 1}))


class AlertTests(unittest.TestCase):
    def test_one_notification_per_low_battery_cycle(self):
        alert = LowBatteryAlert()
        make = lambda value, charging=False: BatteryState(
            connected=True, vid=0x1D57, pid=0xFA60,
            model_code=0x55, percent=value, charging=charging)
        self.assertFalse(alert.should_notify(make(20)))
        self.assertTrue(alert.should_notify(make(10)))
        self.assertFalse(alert.should_notify(make(10)))
        self.assertFalse(alert.should_notify(make(9)))
        self.assertFalse(alert.should_notify(make(9, True)))
        self.assertTrue(alert.should_notify(make(9)))


if __name__ == "__main__":
    unittest.main()
