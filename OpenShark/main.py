"""OpenShark Windows entry point."""

import os
import sys
import ctypes
from threading import Event

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from OpenShark.reference_ui import Dashboard
from OpenShark.monitor import MouseMonitor
from OpenShark.tray import TrayService


def main():
    # A second listener can steal battery reports from the first instance.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    mutex = kernel32.CreateMutexW(None, False, "Local\\OpenSharkBatteryMonitor")
    if not mutex:
        raise OSError("Não foi possível criar a instância do OpenShark")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(ctypes.c_void_p(mutex))
        return
    monitor = MouseMonitor()
    show_request = Event()
    exit_request = Event()
    monitor.start()
    tray = TrayService(monitor, show_request.set, exit_request.set)
    tray.start()
    window = Dashboard(monitor, show_request, exit_request, exit_request.set)
    if "--minimized" in sys.argv:
        window.withdraw()
    try:
        window.mainloop()
    finally:
        tray.stop()
        monitor.stop()
        kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    main()
