"""Windows notification-area icon and low-battery balloon."""

from threading import Event, Thread
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import Menu, MenuItem

from .alerts import LowBatteryAlert
from .autostart import is_autostart_enabled, set_autostart
from .monitor import MouseMonitor


def create_battery_icon(percent: Optional[int], charging: bool = False) -> Image.Image:
    image = Image.new("RGBA", (64, 64), "#111713")
    draw = ImageDraw.Draw(image)
    color = ("#70CFFF" if charging else "#F3A76B" if percent is not None
             and percent <= 10 else "#D5F279")
    draw.rounded_rectangle((3, 3, 60, 60), radius=13, outline=color, width=3)
    if charging and percent is None:
        draw.polygon([(35,9),(17,36),(29,36),(24,55),(47,27),(34,27)],fill=color)
        return image
    label = "⚡" if charging and percent is None else "–" if percent is None else str(percent)
    font_size = 38 if len(label) <= 2 else 29
    try:
        font = ImageFont.truetype("bahnschrift.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
    bounds = draw.textbbox((0, 0), label, font=font)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    draw.text(((64 - width) / 2, (64 - height) / 2 - bounds[1] - 2), label,
              font=font, fill=color)
    return image


class TrayService:
    def __init__(self, monitor: MouseMonitor, on_show: Callable[[], None],
                 on_exit: Callable[[], None]):
        self.monitor = monitor
        self.on_show = on_show
        self.on_exit = on_exit
        self.icon: Optional[pystray.Icon] = None
        self._stop = Event()
        self._icon_thread: Optional[Thread] = None
        self._refresh_thread: Optional[Thread] = None
        self._alert = LowBatteryAlert()

    def start(self):
        self._stop.clear()
        self._icon_thread = Thread(target=self._run_icon, daemon=True)
        self._refresh_thread = Thread(target=self._refresh, daemon=True)
        self._icon_thread.start()
        self._refresh_thread.start()

    def stop(self):
        self._stop.set()
        if self.icon:
            self.icon.stop()
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2)

    def _run_icon(self):
        menu = Menu(
            MenuItem("Abrir OpenShark", lambda icon, item: self.on_show(), default=True),
            Menu.SEPARATOR,
            MenuItem("Iniciar com o Windows", self._toggle_autostart,
                     checked=lambda item: is_autostart_enabled()),
            Menu.SEPARATOR,
            MenuItem("Sair", lambda icon, item: self.on_exit()),
        )
        self.icon = pystray.Icon("OpenShark", create_battery_icon(None),
                                 "OpenShark · procurando mouse", menu)
        self.icon.run()

    def _toggle_autostart(self, icon, item):
        set_autostart(not is_autostart_enabled())

    def _refresh(self):
        previous = None
        while not self._stop.wait(0.5):
            if not self.icon or not self.icon.visible:
                continue
            state = self.monitor.snapshot()
            signature = (state.connected, state.name, state.percent, state.charging)
            if signature != previous:
                self.icon.icon = create_battery_icon(state.percent if state.connected else None,
                                                     state.charging)
                if not state.connected:
                    self.icon.title = "OpenShark · mouse desconectado"
                elif state.wired:
                    self.icon.title = "Attack Shark · carregando pelo cabo USB"
                elif state.percent is None:
                    self.icon.title = f"{state.name} · bateria sem leitura"
                else:
                    power = " · carregando" if state.charging else ""
                    self.icon.title = f"{state.name} · {state.percent}%{power}"
                previous = signature
            if self._alert.should_notify(state):
                try:
                    self.icon.notify(
                        f"{state.name} está com {state.percent}% de bateria. Conecte o cabo para recarregar.",
                        "Bateria baixa · OpenShark",
                    )
                except Exception as exc:
                    print(f"[OpenShark] Notificação indisponível: {exc}")
