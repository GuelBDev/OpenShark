"""OpenShark desktop control panel."""

from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from threading import Event
from typing import Callable

import customtkinter as ctk
from PIL import Image

from .autostart import is_autostart_enabled, set_autostart
from .monitor import MouseMonitor
from .profiles import (BUTTON_ACTIONS, BUTTON_NAMES, MODELS, ProfileStore,
                       STAGE_COLORS, default_profile, validate_profile)


BG = "#0C1014"
SIDEBAR = "#11171D"
CARD = "#171F26"
CARD_HOVER = "#202B34"
BORDER = "#28353D"
TEXT = "#F3F5F2"
MUTED = "#91A0A7"
ACCENT = "#FF790D"
GREEN = "#19E77C"
BLUE = "#78C9F5"
RED = "#FF8A76"


class Dashboard(ctk.CTk):
    PAGES = ("Visão geral", "DPI", "Botões", "Sensor e energia", "Macros",
             "Perfis", "Preferências")

    def __init__(self, monitor: MouseMonitor, show_request: Event,
                 exit_request: Event, on_close: Callable[[], None]):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.monitor, self.show_request, self.exit_request = monitor, show_request, exit_request
        self.on_close = on_close
        self.store = ProfileStore()
        self.page = self.PAGES[0]
        self.minimize_to_tray = True
        self._last_state = None
        self._busy = False
        self._nav_buttons = {}
        self._mouse_image = None
        self.title("OpenShark — Mouse Control")
        resource_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
        icon_path = os.path.join(resource_root, "OpenShark", "openshark.ico")
        if os.path.isfile(icon_path):
            self.iconbitmap(icon_path)
        self.geometry("1190x775")
        self.minsize(1000, 650)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_shell()
        self._show_page(self.page)
        self.after(250, self._tick)

    def label(self, parent, text, size=14, color=TEXT, weight="normal", **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color,
                            font=ctk.CTkFont(family="Bahnschrift", size=size, weight=weight),
                            **kwargs)

    def button(self, parent, text, command, primary=False, width=120, **kwargs):
        return ctk.CTkButton(parent, text=text, command=command, width=width,
                             height=39, corner_radius=10,
                             fg_color=ACCENT if primary else CARD_HOVER,
                             hover_color="#FF9679" if primary else "#31414B",
                             text_color=BG if primary else TEXT,
                             font=ctk.CTkFont(family="Bahnschrift", size=14, weight="bold"),
                             **kwargs)

    def card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=18,
                            border_color=BORDER, border_width=1, **kwargs)

    def _build_shell(self):
        side = ctk.CTkFrame(self, width=224, corner_radius=0, fg_color=SIDEBAR)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=21, pady=(28, 30))
        mark = ctk.CTkFrame(brand, width=36, height=36, corner_radius=11, fg_color=ACCENT)
        mark.pack(side="left", padx=(0, 11))
        mark.pack_propagate(False)
        self.label(mark, "S", 23, BG, "bold").place(relx=.5, rely=.49, anchor="center")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left")
        self.label(brand_text, "OPENSHARK", 17, TEXT, "bold").pack(anchor="w")
        self.label(brand_text, "MOUSE CONTROL", 9, MUTED, "bold").pack(anchor="w")

        self.label(side, "DISPOSITIVO", 10, MUTED, "bold").grid(
            row=1, column=0, sticky="w", padx=25, pady=(0, 8))
        self.model_menu = ctk.CTkOptionMenu(
            side, values=list(MODELS), command=self._change_model, width=178,
            height=39, corner_radius=10, fg_color=CARD, button_color=CARD_HOVER,
            button_hover_color=BORDER, dropdown_fg_color=CARD,
            dropdown_hover_color=CARD_HOVER, text_color=TEXT,
            font=ctk.CTkFont(family="Bahnschrift", size=15, weight="bold"))
        self.model_menu.grid(row=2, column=0, padx=22, sticky="ew")
        self.model_menu.set(self.store.model)
        ctk.CTkFrame(side, height=1, fg_color=BORDER).grid(
            row=3, column=0, sticky="ew", padx=22, pady=(25, 18))
        self.label(side, "CONTROLES", 10, MUTED, "bold").grid(
            row=4, column=0, sticky="w", padx=25, pady=(0, 7))
        nav = ctk.CTkFrame(side, fg_color="transparent")
        nav.grid(row=5, column=0, sticky="nsew", padx=12)
        side.grid_rowconfigure(5, weight=1)
        icons = ("◫", "◎", "▤", "◈", "⌘", "▦", "⚙")
        for icon, page in zip(icons, self.PAGES):
            btn = ctk.CTkButton(nav, text=f"  {icon}    {page}", anchor="w",
                                width=200, height=43, corner_radius=10,
                                fg_color="transparent", hover_color=CARD_HOVER,
                                text_color=MUTED,
                                font=ctk.CTkFont(family="Bahnschrift", size=14),
                                command=lambda p=page: self._show_page(p))
            btn.pack(fill="x", pady=2)
            self._nav_buttons[page] = btn

        foot = self.card(side)
        foot.grid(row=6, column=0, sticky="ew", padx=15, pady=(0, 17))
        self.label(foot, "BATERIA WIRELESS", 10, MUTED, "bold").pack(
            anchor="w", padx=16, pady=(15, 3))
        self.side_battery = self.label(foot, "—", 27, TEXT, "bold")
        self.side_battery.pack(anchor="w", padx=16)
        self.side_bar = ctk.CTkProgressBar(foot, height=6, fg_color=BORDER,
                                           progress_color=GREEN)
        self.side_bar.pack(fill="x", padx=16, pady=(8, 17))
        self.side_bar.set(0)

        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 18))
        head.grid_columnconfigure(0, weight=1)
        self.page_heading = self.label(head, "", 31, TEXT, "bold")
        self.page_heading.grid(row=0, column=0, sticky="w")
        self.connection_badge = self.label(head, "●  Procurando receptor", 13, MUTED, "bold")
        self.connection_badge.grid(row=0, column=1, sticky="e")
        self.page_subtitle = self.label(head, "", 13, MUTED)
        self.page_subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent",
                                               scrollbar_button_color=BORDER)
        self.content.grid(row=1, column=0, sticky="nsew", padx=(31, 20), pady=(0, 12))
        self.content.grid_columnconfigure(0, weight=1)
        bottom = ctk.CTkFrame(main, fg_color=SIDEBAR, height=50, corner_radius=0)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_propagate(False)
        bottom.grid_columnconfigure(0, weight=1)
        self.feedback = self.label(bottom, "Pronto", 12, MUTED)
        self.feedback.grid(row=0, column=0, sticky="w", padx=30, pady=14)
        self.label(bottom, "2,4 GHz  •  Windows", 11, MUTED).grid(
            row=0, column=1, sticky="e", padx=30)

    def _show_page(self, page):
        self.page = page
        for name, btn in self._nav_buttons.items():
            selected = name == page
            btn.configure(fg_color=CARD_HOVER if selected else "transparent",
                          text_color=TEXT if selected else MUTED,
                          font=ctk.CTkFont(family="Bahnschrift", size=14,
                                           weight="bold" if selected else "normal"))
        for child in self.content.winfo_children():
            child.destroy()
        self.page_heading.configure(text=page)
        subtitle = {
            "Visão geral": "Seu mouse, do seu jeito.",
            "DPI": "Ajuste cada estágio de sensibilidade e escolha o ativo.",
            "Botões": "Defina a função de cada botão físico.",
            "Sensor e energia": "Desempenho, precisão e consumo.",
            "Macros": "Organize sequências para os seus perfis.",
            "Perfis": "Configurações prontas para cada uso.",
            "Preferências": "Inicialização, bandeja e notificações.",
        }[page]
        self.page_subtitle.configure(text=subtitle)
        getattr(self, "_page_" + {"Visão geral": "overview", "DPI": "dpi",
                               "Botões": "buttons", "Sensor e energia": "sensor",
                               "Macros": "macros", "Perfis": "profiles",
                               "Preferências": "preferences"}[page])()

    def _section_title(self, parent, title, subtitle=None):
        self.label(parent, title, 21, TEXT, "bold").pack(anchor="w", padx=23, pady=(21, 0))
        if subtitle:
            self.label(parent, subtitle, 12, MUTED).pack(anchor="w", padx=23, pady=(4, 14))
        else:
            ctk.CTkFrame(parent, height=12, fg_color="transparent").pack()

    def _page_overview(self):
        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=2)
        mouse = self.card(top, height=382)
        mouse.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        mouse.grid_propagate(False)
        self.label(mouse, f"ATTACK SHARK  {self.store.model}", 12, ACCENT, "bold").place(x=24, y=20)
        self.label(mouse, "Precisão que acompanha você.", 17, TEXT, "bold").place(x=24, y=43)
        image_path = self._original_mouse_art()
        if image_path:
            source = Image.open(image_path).convert("RGBA")
            self._mouse_image = ctk.CTkImage(light_image=source, dark_image=source,
                                              size=(int(source.width * 0.69), 275))
            ctk.CTkLabel(mouse, text="", image=self._mouse_image).place(
                relx=.5, rely=.57, anchor="center")
        else:
            drawing = tk.Canvas(mouse, height=260, bg=CARD, highlightthickness=0)
            drawing.place(relx=.5, rely=.57, anchor="center", relwidth=.9)
            self._draw_mouse(drawing)

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        battery = self.card(right, height=184)
        battery.pack(fill="x", pady=(0, 14))
        battery.pack_propagate(False)
        self.label(battery, "BATERIA", 11, MUTED, "bold").pack(anchor="w", padx=22, pady=(18, 0))
        self.hero_battery = self.label(battery, "—", 48, TEXT, "bold")
        self.hero_battery.pack(anchor="w", padx=20, pady=(0, 1))
        self.hero_bar = ctk.CTkProgressBar(battery, height=8, fg_color=BORDER,
                                           progress_color=GREEN)
        self.hero_bar.pack(fill="x", padx=22)
        self.hero_bar.set(0)
        self.hero_note = self.label(battery, "Aguardando leitura", 12, MUTED)
        self.hero_note.pack(anchor="w", padx=22, pady=(9, 0))
        profile = self.card(right, height=184)
        profile.pack(fill="x")
        profile.pack_propagate(False)
        self.label(profile, "PERFIL ATIVO", 11, MUTED, "bold").pack(
            anchor="w", padx=22, pady=(19, 3))
        self.label(profile, self.store.current["name"], 22, TEXT, "bold").pack(anchor="w", padx=22)
        line = ctk.CTkFrame(profile, fg_color="transparent")
        line.pack(fill="x", padx=22, pady=(16, 0))
        self.label(line, f"{self.store.current['dpi'][self.store.current['active_stage']-1]:,} DPI".replace(",", "."),
                   14, ACCENT, "bold").pack(side="left")
        self.label(line, f"{self.store.current['polling']} Hz", 14, TEXT, "bold").pack(side="right")

        quick = self.card(self.content)
        quick.pack(fill="x", pady=(16, 0))
        self._section_title(quick, "Acesso rápido", "Edite os ajustes e envie ao mouse quando quiser.")
        row = ctk.CTkFrame(quick, fg_color="transparent")
        row.pack(fill="x", padx=23, pady=(0, 22))
        self.button(row, "Editar DPI", lambda: self._show_page("DPI")).pack(side="left", padx=(0, 9))
        self.button(row, "Mapear botões", lambda: self._show_page("Botões")).pack(side="left", padx=(0, 9))
        self.button(row, "Aplicar perfil", lambda: self._apply("all"), primary=True).pack(side="right")

    def _original_mouse_art(self):
        model_dir = {"R1": "ms_3", "X6": "ms_1", "X11": "ms_4"}[self.store.model]
        start = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
        for folder in (start, *start.parents):
            candidate = folder / "Attack Shark Software" / "res" / "skins" / model_dir / "mouse.png"
            if candidate.is_file():
                return candidate
        return None

    def _draw_mouse(self, canvas):
        def draw(_=None):
            canvas.delete("all")
            width = max(canvas.winfo_width(), 300)
            cx = width / 2
            canvas.create_oval(cx-97, 18, cx+97, 248, fill="#27333B", outline="#42535C", width=2)
            canvas.create_oval(cx-82, 25, cx+82, 240, fill="#D5DCD9", outline="#FAFCF5", width=2)
            canvas.create_arc(cx-82, 25, cx+82, 225, start=42, extent=96, style="arc", outline="#AEBBB7", width=2)
            canvas.create_line(cx, 27, cx, 118, fill="#8F9E9A", width=2)
            canvas.create_line(cx-80, 116, cx+80, 116, fill="#9DA9A4", width=2)
            canvas.create_rectangle(cx-12, 44, cx+12, 84, fill="#29353D", outline="#151E22", width=2)
            canvas.create_oval(cx-6, 51, cx+6, 72, fill=ACCENT, outline="")
            canvas.create_oval(cx-87, 123, cx-73, 161, fill="#ABB7B1", outline="#82938B")
            canvas.create_oval(cx-87, 167, cx-73, 205, fill="#ABB7B1", outline="#82938B")
            for x, y, n in ((cx-35,75,"1"),(cx+36,75,"2"),(cx+26,145,"3"),
                            (cx-112,144,"4"),(cx-112,185,"5"),(cx,103,"6")):
                canvas.create_oval(x-12,y-12,x+12,y+12,fill=ACCENT,outline="")
                canvas.create_text(x,y,text=n,fill=BG,font=("Bahnschrift",11,"bold"))
        canvas.bind("<Configure>", draw)

    def _page_dpi(self):
        profile = self.store.current
        card = self.card(self.content)
        card.pack(fill="x")
        self._section_title(card, "Estágios de DPI", "Selecione um estágio e ajuste os valores em passos compatíveis com o mouse.")
        self.dpi_entries = []
        self.stage_var = tk.IntVar(value=profile["active_stage"])
        maximum = {"R1": 18000, "X6": 26000, "X11": 26000}[self.store.model]
        step = 100 if self.store.model == "R1" else 50
        for i, value in enumerate(profile["dpi"]):
            row = ctk.CTkFrame(card, fg_color=CARD_HOVER, corner_radius=12, height=60)
            row.pack(fill="x", padx=22, pady=5)
            row.pack_propagate(False)
            ctk.CTkFrame(row, width=5, fg_color=STAGE_COLORS[i], corner_radius=3).pack(
                side="left", fill="y", pady=12, padx=(14, 14))
            self.label(row, f"{i+1:02d}", 16, TEXT, "bold", width=35).pack(side="left")
            self.label(row, "DPI", 11, MUTED, "bold").pack(side="left", padx=(1, 25))
            entry = ctk.CTkEntry(row, width=120, height=36, fg_color=CARD,
                                 border_color=BORDER, text_color=TEXT, justify="center",
                                 font=ctk.CTkFont(family="Bahnschrift", size=17, weight="bold"))
            entry.pack(side="left")
            entry.insert(0, str(value))
            self.dpi_entries.append(entry)
            self.label(row, f"{step} a {maximum:,}".replace(",", "."), 11, MUTED).pack(
                side="left", padx=14)
            ctk.CTkRadioButton(row, text="Ativo", variable=self.stage_var, value=i+1,
                               fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT,
                               font=ctk.CTkFont(family="Bahnschrift", size=13)).pack(
                side="right", padx=21)
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=22, pady=(20, 22))
        self.button(foot, "Salvar no perfil", self._save_dpi).pack(side="left")
        self.button(foot, "Aplicar DPI", lambda: self._save_dpi(apply=True), primary=True).pack(side="right")

    def _save_dpi(self, apply=False):
        try:
            profile = deepcopy(self.store.current)
            profile["dpi"] = [int(entry.get().strip()) for entry in self.dpi_entries]
            profile["active_stage"] = self.stage_var.get()
            self.store.current.update(validate_profile(profile))
            self.store.save()
        except (ValueError, TypeError) as exc:
            self._feedback(f"DPI inválido: {exc}", error=True)
            return
        self._feedback("DPI salvo no perfil")
        if apply:
            self._apply("dpi")

    def _page_buttons(self):
        card = self.card(self.content)
        card.pack(fill="x")
        self._section_title(card, "Mapa de botões", "Escolha uma ação para cada botão do seu mouse.")
        self.button_menus = []
        for i, name in enumerate(BUTTON_NAMES):
            row = ctk.CTkFrame(card, fg_color=CARD_HOVER, corner_radius=12, height=60)
            row.pack(fill="x", padx=22, pady=5)
            row.pack_propagate(False)
            badge = ctk.CTkFrame(row, width=35, height=35, corner_radius=10, fg_color=ACCENT)
            badge.pack(side="left", padx=(13, 14))
            badge.pack_propagate(False)
            self.label(badge, str(i+1), 15, BG, "bold").place(relx=.5, rely=.5, anchor="center")
            self.label(row, name, 15, TEXT, "bold").pack(side="left")
            menu = ctk.CTkOptionMenu(row, values=list(BUTTON_ACTIONS), width=220,
                                     height=34, fg_color=CARD, button_color=BORDER,
                                     button_hover_color="#42515A", dropdown_fg_color=CARD,
                                     dropdown_hover_color=CARD_HOVER, text_color=TEXT)
            menu.pack(side="right", padx=17)
            menu.set(self.store.current["buttons"][i])
            self.button_menus.append(menu)
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=22, pady=(19, 22))
        self.button(foot, "Restaurar padrão", self._reset_buttons).pack(side="left")
        self.button(foot, "Aplicar botões", lambda: self._save_buttons(True), primary=True).pack(side="right")
        self.button(foot, "Salvar no perfil", self._save_buttons).pack(side="right", padx=(0, 9))

    def _save_buttons(self, apply=False):
        self.store.current["buttons"] = [menu.get() for menu in self.button_menus]
        self.store.save()
        self._feedback("Botões salvos no perfil")
        if apply:
            self._apply("buttons")

    def _reset_buttons(self):
        defaults = default_profile(self.store.model)["buttons"]
        for menu, value in zip(self.button_menus, defaults):
            menu.set(value)
        self._feedback("Padrão carregado; aplique para enviar ao mouse")

    def _page_sensor(self):
        profile = self.store.current
        card = self.card(self.content)
        card.pack(fill="x")
        self._section_title(card, "Taxa de resposta", "Frequência de comunicação do mouse com o computador.")
        self.polling_var = tk.IntVar(value=profile["polling"])
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(2, 21))
        for rate in (125, 250, 500, 1000):
            ctk.CTkRadioButton(row, text=f"{rate} Hz", value=rate, variable=self.polling_var,
                               fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT,
                               font=ctk.CTkFont(family="Bahnschrift", size=14)).pack(side="left", padx=(0, 22))
        self.button(row, "Aplicar polling", lambda: self._save_sensor("polling"), primary=True).pack(side="right")

        card2 = self.card(self.content)
        card2.pack(fill="x", pady=(14, 0))
        self._section_title(card2, "Precisão do sensor", "Refine o comportamento do movimento.")
        self.angle_var = tk.BooleanVar(value=profile["angle_snap"])
        self.ripple_var = tk.BooleanVar(value=profile["ripple"])
        for title, subtitle, var in (("Angle Snap", "Suaviza trajetórias em linha reta.", self.angle_var),
                                     ("Ripple Control", "Filtra oscilações do sensor.", self.ripple_var)):
            line = ctk.CTkFrame(card2, fg_color=CARD_HOVER, corner_radius=10)
            line.pack(fill="x", padx=22, pady=4)
            self.label(line, title, 15, TEXT, "bold").pack(anchor="w", padx=16, pady=(10, 0))
            self.label(line, subtitle, 11, MUTED).pack(anchor="w", padx=16, pady=(1, 11))
            switch = ctk.CTkSwitch(line, text="", variable=var, width=45,
                                   progress_color=ACCENT, button_color=TEXT)
            switch.place(relx=.97, rely=.5, anchor="e")
        actions = ctk.CTkFrame(card2, fg_color="transparent")
        actions.pack(fill="x", padx=22, pady=(16, 20))
        self.button(actions, "Propriedades do Windows", self._open_mouse_properties, width=190).pack(side="left")
        self.button(actions, "Aplicar sensor", lambda: self._save_sensor("dpi"), primary=True).pack(side="right")

        card3 = self.card(self.content)
        card3.pack(fill="x", pady=(14, 0))
        self._section_title(card3, "Energia e cliques", "Tempos em minutos e resposta dos botões em milissegundos.")
        self.sleep_var = tk.DoubleVar(value=profile["sleep"])
        self.deep_var = tk.IntVar(value=profile["deep_sleep"])
        self.response_var = tk.IntVar(value=profile["response"])
        for title, variable, minimum, maximum, suffix, steps in (
            ("Suspensão", self.sleep_var, .5, 30 if self.store.model == "X11" else 60,
             "min", 60 if self.store.model == "X11" else 120),
            ("Sono profundo", self.deep_var, 1, 60, "min", 60),
            ("Tempo de resposta", self.response_var, 2 if self.store.model == "X6" else 4,
             25 if self.store.model == "X6" else 50, "ms", 24),
        ):
            line = ctk.CTkFrame(card3, fg_color="transparent")
            line.pack(fill="x", padx=23, pady=8)
            self.label(line, title, 14, TEXT, "bold", width=145, anchor="w").pack(side="left")
            value = self.label(line, f"{variable.get():g} {suffix}", 13, ACCENT, "bold", width=74)
            value.pack(side="right")
            ctk.CTkSlider(line, from_=minimum, to=maximum, number_of_steps=steps-1,
                          variable=variable, progress_color=ACCENT, button_color=ACCENT,
                          button_hover_color="#FFA286", fg_color=BORDER,
                          command=lambda n, v=value, s=suffix: v.configure(text=f"{n:g} {s}")) .pack(
                              side="right", fill="x", expand=True, padx=(10, 24))
        foot = ctk.CTkFrame(card3, fg_color="transparent")
        foot.pack(fill="x", padx=22, pady=(12, 22))
        self.button(foot, "Salvar no perfil", lambda: self._save_sensor(None)).pack(side="left")
        apply_power = self.button(foot, "Aplicar energia", lambda: self._save_sensor("power"), primary=True)
        apply_power.pack(side="right")

    def _save_sensor(self, section):
        profile = self.store.current
        profile["polling"] = self.polling_var.get()
        profile["angle_snap"] = self.angle_var.get()
        profile["ripple"] = self.ripple_var.get()
        profile["sleep"] = round(self.sleep_var.get() * 2) / 2
        profile["deep_sleep"] = round(self.deep_var.get())
        profile["response"] = round(self.response_var.get())
        try:
            self.store.current.update(validate_profile(profile))
            self.store.save()
        except ValueError as exc:
            self._feedback(str(exc), error=True)
            return
        self._feedback("Ajustes salvos no perfil")
        if section:
            self._apply(section)

    def _open_mouse_properties(self):
        try:
            subprocess.Popen(["control.exe", "main.cpl"], creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:
            self._feedback(str(exc), error=True)

    def _page_macros(self):
        card = self.card(self.content)
        card.pack(fill="x")
        self._section_title(card, "Biblioteca de macros", "Sequências salvas com este perfil.")
        macros = self.store.current["macros"]
        for index, macro in enumerate(macros):
            row = ctk.CTkFrame(card, fg_color=CARD_HOVER, corner_radius=10)
            row.pack(fill="x", padx=22, pady=4)
            self.label(row, macro["name"], 15, TEXT, "bold").pack(side="left", padx=16, pady=14)
            self.label(row, f"{len(macro['actions'])} ações", 12, MUTED).pack(side="left", padx=12)
            self.button(row, "Excluir", lambda i=index: self._delete_macro(i), width=78).pack(
                side="right", padx=12, pady=7)
            self.button(row, "Editar", lambda i=index: self._edit_macro(i), width=78).pack(
                side="right", pady=7)
        if not macros:
            self.label(card, "Nenhuma macro neste perfil", 15, MUTED).pack(
                anchor="w", padx=23, pady=(5, 23))
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.pack(fill="x", padx=22, pady=(14, 22))
        self.button(foot, "+ Nova macro", self._add_macro, primary=True).pack(side="left")
        self.label(foot, "Envio de macros ao mouse indisponível neste modelo.",
                   12, MUTED).pack(side="right")

    def _add_macro(self):
        name = simpledialog.askstring("Nova macro", "Nome da macro:", parent=self)
        if not name:
            return
        self.store.current["macros"].append({"name": name[:48], "actions": []})
        self.store.save()
        self._show_page("Macros")

    def _edit_macro(self, index):
        macro = self.store.current["macros"][index]
        editor = ctk.CTkToplevel(self)
        editor.title("Editar macro")
        editor.geometry("510x475")
        editor.configure(fg_color=BG)
        editor.transient(self)
        editor.grab_set()
        self.label(editor, macro["name"], 23, TEXT, "bold").pack(anchor="w", padx=23, pady=(20, 5))
        self.label(editor, "Uma ação por linha: tecla, atraso em ms (ex.: A, 50).",
                   12, MUTED).pack(anchor="w", padx=23)
        box = ctk.CTkTextbox(editor, fg_color=CARD, border_color=BORDER,
                             border_width=1, text_color=TEXT,
                             font=ctk.CTkFont(family="Consolas", size=14))
        box.pack(fill="both", expand=True, padx=23, pady=17)
        box.insert("1.0", "\n".join(f"{a['key']}, {a['delay']}" for a in macro["actions"]))
        def save():
            actions = []
            try:
                for line in box.get("1.0", "end").splitlines():
                    if not line.strip():
                        continue
                    key, delay = [part.strip() for part in line.split(",", 1)]
                    if not key or len(key) > 24 or not 0 <= int(delay) <= 60000:
                        raise ValueError("Ação inválida")
                    actions.append({"key": key, "delay": int(delay)})
                if len(actions) > 256:
                    raise ValueError("Limite de 256 ações")
                macro["actions"] = actions
                self.store.save()
                editor.destroy()
                self._show_page("Macros")
            except (ValueError, TypeError) as exc:
                messagebox.showerror("Macro", f"Revise as ações: {exc}", parent=editor)
        self.button(editor, "Salvar macro", save, primary=True).pack(
            anchor="e", padx=23, pady=(0, 22))

    def _delete_macro(self, index):
        del self.store.current["macros"][index]
        self.store.save()
        self._show_page("Macros")

    def _page_profiles(self):
        card = self.card(self.content)
        card.pack(fill="x")
        self._section_title(card, f"Perfis do {self.store.model}",
                            "Selecione um perfil para editar ou aplicar ao mouse.")
        for index, profile in enumerate(self.store.profiles):
            selected = index == self.store.index
            row = ctk.CTkFrame(card, fg_color=CARD_HOVER if selected else CARD,
                               corner_radius=10, border_color=ACCENT if selected else BORDER,
                               border_width=1)
            row.pack(fill="x", padx=22, pady=4)
            self.label(row, profile["name"], 16, TEXT, "bold").pack(
                side="left", padx=17, pady=13)
            self.label(row, f"{profile['polling']} Hz  •  {profile['dpi'][profile['active_stage']-1]} DPI",
                       12, MUTED).pack(side="left", padx=12)
            if selected:
                self.label(row, "ATIVO", 10, ACCENT, "bold").pack(side="right", padx=17)
            else:
                self.button(row, "Selecionar", lambda i=index: self._select_profile(i),
                            width=87).pack(side="right", padx=10, pady=6)
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=22, pady=(18, 23))
        for text, command in (("+ Novo", self._add_profile), ("Renomear", self._rename_profile),
                              ("Excluir", self._delete_profile), ("Importar", self._import_profile),
                              ("Exportar", self._export_profile)):
            self.button(actions, text, command, width=94).pack(side="left", padx=(0, 7))
        self.button(actions, "Aplicar perfil", lambda: self._apply("all"),
                    primary=True, width=130).pack(side="right")
        self.button(card, "Restaurar padrão", self._reset_profile, width=138).pack(
            anchor="w", padx=22, pady=(0, 22))

    def _select_profile(self, index):
        self.store.select(index)
        self._show_page("Perfis")

    def _add_profile(self):
        name = simpledialog.askstring("Novo perfil", "Nome do perfil:", parent=self)
        if name:
            try:
                self.store.add(name)
                self._show_page("Perfis")
            except ValueError as exc:
                self._feedback(str(exc), error=True)

    def _rename_profile(self):
        name = simpledialog.askstring("Renomear perfil", "Novo nome:",
                                      initialvalue=self.store.current["name"], parent=self)
        if name and name.strip():
            self.store.current["name"] = name.strip()[:48]
            self.store.save()
            self._show_page("Perfis")

    def _delete_profile(self):
        try:
            self.store.delete()
            self._show_page("Perfis")
        except ValueError as exc:
            self._feedback(str(exc), error=True)

    def _reset_profile(self):
        name = self.store.current["name"]
        self.store.current.clear()
        self.store.current.update(default_profile(self.store.model, name))
        self.store.save()
        self._show_page("Perfis")
        self._feedback("Padrão carregado no perfil; aplique para enviar ao mouse")

    def _import_profile(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Perfil OpenShark", "*.json")])
        if path:
            try:
                self.store.import_file(path)
                self._show_page("Perfis")
            except (OSError, ValueError) as exc:
                self._feedback(f"Importação falhou: {exc}", error=True)

    def _export_profile(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            initialfile=f"{self.store.current['name']}.json",
                                            filetypes=[("Perfil OpenShark", "*.json")])
        if path:
            try:
                self.store.export_file(path)
                self._feedback("Perfil exportado")
            except OSError as exc:
                self._feedback(f"Exportação falhou: {exc}", error=True)

    def _page_preferences(self):
        card = self.card(self.content)
        card.pack(fill="x")
        self._section_title(card, "Na área de notificação", "A porcentagem aparece no ícone ao lado do relógio.")
        self.label(card, "O Windows avisa quando a bateria chega a 10%.",
                   14, TEXT).pack(anchor="w", padx=23, pady=(0, 20))
        self.autostart = ctk.CTkSwitch(card, text="Iniciar com o Windows",
                                        command=self._set_autostart, progress_color=ACCENT,
                                        button_color=TEXT,
                                        font=ctk.CTkFont(family="Bahnschrift", size=14))
        self.autostart.pack(anchor="w", padx=23, pady=(0, 16))
        if is_autostart_enabled():
            self.autostart.select()
        self.tray_switch = ctk.CTkSwitch(card, text="Fechar para a bandeja",
                                          command=lambda: setattr(self, "minimize_to_tray", bool(self.tray_switch.get())),
                                          progress_color=ACCENT, button_color=TEXT,
                                          font=ctk.CTkFont(family="Bahnschrift", size=14))
        self.tray_switch.pack(anchor="w", padx=23, pady=(0, 22))
        if self.minimize_to_tray:
            self.tray_switch.select()
        card2 = self.card(self.content)
        card2.pack(fill="x", pady=(14, 0))
        self._section_title(card2, "Dispositivo", "Informações do receptor conectado.")
        state = self.monitor.snapshot()
        self.label(card2, f"USB {state.vid:04X}:{state.pid:04X}" if state.vid is not None else "Nenhum receptor conectado",
                   15, TEXT, "bold").pack(anchor="w", padx=23, pady=(0, 14))
        self.button(card2, "Copiar ID", self._copy_id, width=112).pack(anchor="w", padx=23, pady=(0, 22))
        self.button(self.content, "Sair do OpenShark", self.on_close).pack(
            anchor="w", pady=(17, 0))

    def _copy_id(self):
        state = self.monitor.snapshot()
        if state.vid is None:
            return
        self.clipboard_clear()
        self.clipboard_append(f"VID_{state.vid:04X}&PID_{state.pid:04X}")
        self._feedback("ID copiado")

    def _set_autostart(self):
        enabled = bool(self.autostart.get())
        if not set_autostart(enabled):
            self.autostart.deselect() if enabled else self.autostart.select()
            self._feedback("Não foi possível alterar a inicialização", error=True)

    def _change_model(self, model):
        self.store.set_model(model)
        self._show_page(self.page)
        self._feedback(f"{model} selecionado")

    def _apply(self, section):
        if self._busy:
            return
        try:
            self.monitor.apply(self.store.current, section)
            self._busy = True
            self._feedback("Enviando ajustes ao mouse…")
        except (ValueError, OSError) as exc:
            self._feedback(str(exc), error=True)

    def _feedback(self, message, error=False):
        self.feedback.configure(text=message, text_color=RED if error else GREEN)

    def _tick(self):
        if self.exit_request.is_set():
            self.destroy()
            return
        if self.show_request.is_set():
            self.show_request.clear()
            self.deiconify()
            self.lift()
        state = self.monitor.snapshot()
        if state != self._last_state:
            self._render_state(state)
            self._last_state = state
        while result := self.monitor.poll_result():
            _, success, message = result
            self._busy = False
            self._feedback(message, error=not success)
        self.after(400, self._tick)

    def _render_state(self, state):
        connected = state.connected
        badge = "●  R1 por cabo" if state.wired else (
            "●  Receptor conectado" if connected else "○  Desconectado")
        self.connection_badge.configure(text=badge,
                                        text_color=BLUE if state.wired else GREEN if connected else MUTED)
        color = BLUE if state.charging else RED if state.percent is not None and state.percent <= 10 else GREEN
        label = "⚡ Carregando" if state.wired else f"{state.percent}%" if connected and state.percent is not None else "—"
        self.side_battery.configure(text=label, text_color=color,
                                    font=ctk.CTkFont(family="Segoe UI",size=15 if state.wired else 26,weight="bold"))
        self.side_bar.configure(progress_color=color)
        self.side_bar.set(1 if state.wired else state.percent / 100 if connected and state.percent is not None else 0)
        if self.page == "Visão geral" and hasattr(self, "hero_battery") and self.hero_battery.winfo_exists():
            self.hero_battery.configure(text=label, text_color=color,
                                        font=ctk.CTkFont(family="Segoe UI", size=27 if state.wired else 42, weight="bold"))
            self.hero_bar.configure(progress_color=color)
            self.hero_bar.set(1 if state.wired else state.percent / 100 if connected and state.percent is not None else 0)
            note = "Cabo USB conectado" if state.wired else "Carregando" if state.charging else (
                "Bateria baixa" if state.percent is not None and state.percent <= 10 else
                "Em uso sem fio" if state.percent is not None else
                "Aguardando leitura do mouse")
            self.hero_note.configure(text=note)

    def _close(self):
        if self.minimize_to_tray:
            self.withdraw()
        else:
            self.on_close()
