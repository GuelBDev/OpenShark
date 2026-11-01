import os
import unittest
from unittest.mock import MagicMock, patch

from OpenShark import memory


class WorkingSetTests(unittest.TestCase):
    def test_trim_is_a_safe_noop_outside_windows(self):
        with patch.object(memory.os, "name", "posix"):
            self.assertFalse(memory.trim_working_set())

    def test_trim_invokes_windows_empty_working_set(self):
        kernel32 = MagicMock()
        kernel32.GetCurrentProcess.return_value = 123
        psapi = MagicMock()
        psapi.EmptyWorkingSet.return_value = True
        with patch.object(memory.os, "name", "nt"), patch.object(memory.ctypes, "WinDLL", side_effect=[kernel32, psapi]):
            self.assertTrue(memory.trim_working_set())
        psapi.EmptyWorkingSet.assert_called_once_with(123)
