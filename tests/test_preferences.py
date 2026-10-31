import json
import os
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from OpenShark import preferences, qt_ui
from OpenShark.monitor import BatteryState
from OpenShark.profiles import ProfileStore


class FakeMonitor:
    def snapshot(self):
        return BatteryState()

    def poll_result(self):
        return None


class PreferencesTests(unittest.TestCase):
    def test_new_preferences_require_onboarding_and_persist_choices(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
                preferences, "SETTINGS", Path(folder) / "preferences.json"):
            self.assertFalse(preferences.load()["onboarding_complete"])
            saved = preferences.save({"onboarding_complete": True,
                                      "start_with_windows": True,
                                      "battery_in_taskbar": True})
            self.assertEqual(saved, preferences.load())
            self.assertEqual(json.loads(preferences.SETTINGS.read_text())["battery_in_taskbar"], True)

    def test_first_run_choices_enable_background_services(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            prefs = {"onboarding_complete": False, "start_with_windows": False,
                     "battery_in_taskbar": False}
            with patch.object(qt_ui, "ProfileStore",
                              lambda: ProfileStore(Path(folder) / "profiles.json")), \
                 patch.object(qt_ui, "set_autostart", return_value=True) as startup, \
                 patch.object(qt_ui, "save_preferences", side_effect=lambda value: value), \
                 patch.object(qt_ui.QDialog, "exec", return_value=qt_ui.QDialog.Accepted):
                window = qt_ui.Dashboard(FakeMonitor(), Event(), Event(), lambda: None,
                                         lambda enabled: calls.append(enabled), prefs)
                window.show_onboarding()
            self.assertTrue(window.preferences["onboarding_complete"])
            self.assertTrue(window.preferences["start_with_windows"])
            self.assertTrue(window.preferences["battery_in_taskbar"])
            startup.assert_called_once_with(True)
            self.assertEqual(calls, [True])
            window.minimize_to_tray = False
            window.close()
