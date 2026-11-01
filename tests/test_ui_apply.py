import os
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from OpenShark import qt_ui
from OpenShark.monitor import BatteryState
from OpenShark.profiles import ProfileStore


class FakeMonitor:
    def __init__(self):
        self.sent = []
        self.results = []

    def snapshot(self):
        return BatteryState()

    def apply(self, profile, section):
        self.sent.append((profile.copy(), section))

    def poll_result(self):
        return self.results.pop(0) if self.results else None


class ApplyButtonTests(unittest.TestCase):
    def test_minimize_to_tray_trims_dashboard_working_set(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(qt_ui, "ProfileStore",
                              lambda: ProfileStore(Path(directory) / "profiles.json")), \
                 patch.object(qt_ui, "trim_working_set") as trim:
                window = qt_ui.Dashboard(FakeMonitor(), Event(), Event(), lambda: None)
                window.show()
                window.move_to_background()
                QTest.qWait(300)
                self.assertFalse(window.isVisible())
                trim.assert_called_once_with()
                window.minimize_to_tray = False
                window.close()

    def test_dpi_is_saved_only_after_confirmation(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            monitor = FakeMonitor()
            with patch.object(qt_ui, "ProfileStore",
                              lambda: ProfileStore(Path(directory) / "profiles.json")):
                window = qt_ui.Dashboard(monitor, Event(), Event(), lambda: None)
            window.show()
            app.processEvents()
            window.dpi_values[0].setValue(100)
            QTest.mouseClick(window.apply_button, Qt.LeftButton)
            self.assertEqual(monitor.sent[-1][0]["dpi"][0], 100)
            self.assertEqual(window.store.current["dpi"][0], 800)
            self.assertFalse(window.apply_button.isEnabled())
            monitor.results.append(("dpi", False, "Sem ACK"))
            window.tick()
            self.assertEqual(window.store.current["dpi"][0], 800)
            QTest.mouseClick(window.apply_button, Qt.LeftButton)
            monitor.results.append(("dpi", True, "ACK"))
            window.tick()
            self.assertEqual(window.store.current["dpi"][0], 100)
            self.assertTrue(window.apply_button.isEnabled())
            window.minimize_to_tray = False
            window.close()
