"""
OpenShark - Windows Auto-Start Manager
Manages Registry Run entry for starting minimized to tray with Windows.
"""

import sys
import winreg
import os

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "OpenSharkMouse"


def is_autostart_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enable: bool) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        if enable:
            # Determine path to launch
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --minimized'
            else:
                main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
                python_exe = sys.executable
                if os.path.basename(python_exe).lower() == "python.exe":
                    silent_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
                    if os.path.isfile(silent_exe):
                        python_exe = silent_exe
                cmd = f'"{python_exe}" "{main_py}" --minimized'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"[AutoStart] Registry error: {e}")
        return False

