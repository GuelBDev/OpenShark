"""Attack Shark wireless battery monitor and acknowledged HID feature writes.

The observed Telink-family dongle emits 03 <model> 40 <power> <level>, where
level is a 0..10 step. Other models are shown only when they expose this event.
"""

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import hashlib
from threading import Event, Lock, Thread
from queue import Empty, Queue
import time
from typing import Optional

import hid


KNOWN_IDS = {(0x1D57, 0xFA60), (0x1D57, 0xFA61), (0x1D57, 0xFA62), (0x1D57, 0xFA65)}
EVENT_USAGE_PAGE = 0x000A
COMMAND_USAGE_PAGE = 0x000B
MODEL_NAMES = {0x10: "Attack Shark R1", 0x55: "Attack Shark X11",
               0x85: "Attack Shark X6"}


@dataclass(frozen=True)
class BatteryState:
    connected: bool = False
    wired: bool = False
    name: str = "Nenhum mouse conectado"
    vid: Optional[int] = None
    pid: Optional[int] = None
    model_code: Optional[int] = None
    percent: Optional[int] = None
    charging: Optional[bool] = None
    last_seen: Optional[float] = None
    model: Optional[str] = None
    active_stage: Optional[int] = None
    stage_event: int = 0


def parse_stage_event(raw):
    if len(raw) >= 5 and raw[0] == 3 and raw[2] == 0x10 and 1 <= raw[3] <= 6:
        return raw[3]
    return None


def identify_model(descriptors, code=None):
    if code == 0x55:
        return "X11"
    if code == 0x85:
        return "X6"
    names = " ".join(str(d.get("product_string") or "") for d in descriptors).lower()
    if "x11" in names:
        return "X11"
    if "x6" in names:
        return "X6"
    if "r1" in names:
        return "R1"
    return None


def parse_battery_event(raw):
    """Return (model_code, percent, charging) for documented status shapes."""
    if len(raw) < 5 or raw[0] != 0x03 or raw[2] != 0x40:
        return None
    model, sub, level = raw[1], raw[3], raw[4]
    charging = (True if sub == 0x03 else False) if model == 0x55 else None
    if model in (0x10, 0x85) and sub in (0x01, 0x02, 0x03) and 1 <= level <= 10:
        return model, min(100, level * 10), charging
    if model == 0x55 and 1 <= level <= 100:
        return model, 100 if sub == 0x02 else level, charging
    return None


def device_candidate(descriptor):
    identity = (
        descriptor.get("vendor_id"), descriptor.get("product_id")
    )
    name = " ".join(
        str(descriptor.get(key) or "")
        for key in ("manufacturer_string", "product_string")
    ).lower()
    return (identity in KNOWN_IDS or "attack shark" in name) and descriptor.get(
        "usage_page"
    ) == EVENT_USAGE_PAGE


class MouseMonitor:
    def __init__(self, hid_module=hid):
        self._hid = hid_module
        self._state = BatteryState()
        self._lock = Lock()
        self._stop = Event()
        self._thread: Optional[Thread] = None
        self._write_lock = Lock()
        self._ack_lock = Lock()
        self._awaiting_ack = False
        self._ack_event = Event()
        self._results = Queue()
        self._identity_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenShark" / "devices.json"
        try:
            self._identities = json.loads(self._identity_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._identities = {}

    def _identify(self, descriptor, descriptors, code=None):
        key = hashlib.sha256(descriptor["path"]).hexdigest()
        model = identify_model(descriptors, code)
        if model:
            self._identities[key] = model
            receivers = [d for d in descriptors if device_candidate(d) and d.get("product_id") != 0xFA61]
            if len(receivers) == 1:
                self._identities[hashlib.sha256(receivers[0]["path"]).hexdigest()] = model
            try:
                self._identity_path.parent.mkdir(parents=True, exist_ok=True)
                self._identity_path.write_text(json.dumps(self._identities), encoding="utf-8")
            except OSError:
                pass
        return model or self._identities.get(key)

    def snapshot(self) -> BatteryState:
        with self._lock:
            return self._state

    def poll_result(self):
        try:
            return self._results.get_nowait()
        except Empty:
            return None

    def apply(self, profile, section="all"):
        """Queue one application; UI reads (section, success, message) results."""
        from copy import deepcopy
        from .protocol import reports_for
        from .profiles import validate_profile
        profile = validate_profile(deepcopy(profile))
        reports = reports_for(profile, section)
        Thread(target=self._write_reports, args=(profile["model"], section, reports),
               name="OpenShark config", daemon=True).start()

    def _write_reports(self, model, section, reports):
        with self._write_lock:
            device = None
            try:
                state = self.snapshot()
                if not state.connected or state.vid is None:
                    raise RuntimeError("Mouse desconectado")
                descriptors = self._hid.enumerate()
                # A wired mouse can expose its command collection on a PID different
                # from the battery/event collection. Select the command interface that
                # belongs to the same physical mouse by matching the vendor first.
                candidates = [d for d in descriptors
                              if d.get("usage_page") == COMMAND_USAGE_PAGE
                              and d.get("vendor_id") == state.vid
                              and d.get("product_id") == state.pid]
                if not candidates and not state.wired and state.pid is not None:
                    candidates = [d for d in descriptors
                                  if d.get("usage_page") == COMMAND_USAGE_PAGE
                                  and d.get("vendor_id") == state.vid]
                if not candidates:
                    raise RuntimeError("Interface de configuração HID não encontrada")
                device = self._hid.device()
                device.open_path(candidates[0]["path"])
                for report in reports:
                    with self._ack_lock:
                        self._ack_event.clear()
                        self._awaiting_ack = not state.wired
                    count = device.send_feature_report(report)
                    if count != len(report):
                        raise RuntimeError(f"Falha na escrita HID para o relatório {report[0]:02X}")
                    if not state.wired and not self._ack_event.wait(1.5):
                        raise RuntimeError(f"Receptor não confirmou o relatório {report[0]:02X}")
                    with self._ack_lock:
                        self._awaiting_ack = False
                    time.sleep(0.04)
                message = ("Comando enviado pelo USB; confirme o efeito no mouse" if state.wired
                           else "Receptor confirmou os ajustes; confira o efeito no mouse")
                self._results.put((section, True, message))
            except Exception as exc:
                self._results.put((section, False, str(exc)))
            finally:
                with self._ack_lock:
                    self._awaiting_ack = False
                if device:
                    try:
                        device.close()
                    except Exception:
                        pass

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="OpenShark HID", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _set_state(self, state):
        with self._lock:
            self._state = state

    def _run(self):
        while not self._stop.is_set():
            try:
                descriptors = self._hid.enumerate()
                candidates = [d for d in descriptors if device_candidate(d)]
            except Exception as exc:
                print(f"[OpenShark] Falha ao procurar HID: {exc}")
                candidates = []
            if not candidates:
                self._set_state(BatteryState())
                self._stop.wait(2)
                continue

            descriptor = candidates[0]
            device = None
            try:
                device = self._hid.device()
                device.open_path(descriptor["path"])
                device.set_nonblocking(True)
                name = descriptor.get("product_string") or "Attack Shark"
                if name.lower() == "2.4g wireless device":
                    name = "Attack Shark · 2,4 GHz"
                state = BatteryState(
                    connected=True,
                    wired=any(d.get("vendor_id") == 0x1D57 and d.get("product_id") == 0xFA61
                              for d in descriptors),
                    name=name,
                    vid=descriptor.get("vendor_id"),
                    pid=descriptor.get("product_id"),
                    model=self._identify(descriptor, descriptors),
                )
                state = replace(state, charging=True if state.wired else None)
                self._set_state(state)
                next_presence_check = 0.0
                while not self._stop.is_set():
                    if time.monotonic() >= next_presence_check:
                        descriptors = self._hid.enumerate()
                        paths = {d.get("path") for d in descriptors}
                        if descriptor["path"] not in paths:
                            break
                        wired = any(d.get("vendor_id") == 0x1D57 and d.get("product_id") == 0xFA61
                                    for d in descriptors)
                        if wired != state.wired:
                            state = replace(state, wired=wired,
                                            model=self._identify(descriptor, descriptors, state.model_code),
                                            charging=True if wired else None)
                            self._set_state(state)
                        next_presence_check = time.monotonic() + 3
                    raw = device.read(64)
                    stage = parse_stage_event(raw) if raw else None
                    if stage is not None:
                        state = replace(state, active_stage=stage, stage_event=state.stage_event+1,
                                        model_code=raw[1], model=self._identify(descriptor, descriptors, raw[1]))
                        self._set_state(state)
                    if raw and len(raw) >= 5 and raw[0] == 3 and raw[2] == 0x50:
                        with self._ack_lock:
                            if self._awaiting_ack:
                                self._ack_event.set()
                    parsed = parse_battery_event(raw) if raw else None
                    if parsed:
                        code, percent, charging = parsed
                        display_name = MODEL_NAMES.get(code, name)
                        state = replace(state, name=display_name, model_code=code, percent=percent,
                                        charging=True if state.wired else charging,
                                        model=self._identify(descriptor, descriptors, code), last_seen=time.time())
                        self._set_state(state)
                    self._stop.wait(0.1)
            except Exception as exc:
                print(f"[OpenShark] Telemetria HID indisponível: {exc}")
            finally:
                if device:
                    try:
                        device.close()
                    except Exception:
                        pass
                self._set_state(BatteryState())
            self._stop.wait(1)
