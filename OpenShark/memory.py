"""Small Windows memory helpers for the background OpenShark process."""

import ctypes
import os


def trim_working_set():
    """Release resident UI pages while the app is hidden in the background.

    This does not discard user settings or stop the battery monitor; Windows
    transparently reloads a page if the user opens the dashboard again.
    """
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
        psapi.EmptyWorkingSet.restype = ctypes.c_bool
        return bool(psapi.EmptyWorkingSet(kernel32.GetCurrentProcess()))
    except OSError:
        return False
