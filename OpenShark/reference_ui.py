"""Reference-inspired three-column device dashboard, using existing real controls."""
from pathlib import Path
import sys
import tkinter as tk
from threading import Thread
from queue import Queue, Empty
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image
from .dashboard import Dashboard as Base, BG, CARD, BORDER, TEXT, MUTED, ACCENT, GREEN
from .profiles import BUTTON_ACTIONS, BUTTON_NAMES, default_profile, validate_profile


class Dashboard(Base):
    def label(self,parent,text,size=14,color=TEXT,weight="normal",**kwargs):
        return ctk.CTkLabel(parent,text=text,text_color=color,
                            font=ctk.CTkFont(family="Segoe UI",size=size,weight=weight),**kwargs)

    def __init__(self, *args, **kwargs):
        self._stage_seen = None
        self._update_results = Queue()
        self._release = None
        super().__init__(*args, **kwargs)
        self.geometry(f"1510x950+{max(0,(self.winfo_screenwidth()-1510)//2)}+30")
        self.minsize(1200, 780)
        self.title("ATTACK SHARK — OpenShark")

    def _build_shell(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        side = ctk.CTkFrame(self, width=164, corner_radius=0, fg_color="#080D12")
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        root=Path(sys.executable if getattr(sys,"frozen",False) else __file__).resolve().parent
        logo=next((p/"Attack Shark Software/res/skins/logo_2.png" for p in (root,*root.parents)
                   if (p/"Attack Shark Software/res/skins/logo_2.png").is_file()),None)
        if logo:
            source=Image.open(logo).convert("RGBA")
            self._brand_image=ctk.CTkImage(source,source,size=(146,30))
            ctk.CTkLabel(side,text="",image=self._brand_image).pack(padx=8,pady=(26,28))
        else:
            self.label(side,"ATTACK SHARK",17,TEXT,"bold").pack(pady=(26,28))
        items = (("▣", "Dispositivo", "Visão geral"), ("◴", "Performance", "Sensor e energia"),
                 ("⌘", "Macros", "Macros"), ("▤", "Perfis", "Perfis"),
                 ("☼", "Iluminação", "Iluminação"), ("▧", "Firmware", "Firmware"),
                 ("⚙", "Configurações", "Preferências"))
        for icon, title, page in items:
            btn = ctk.CTkButton(side, text=f"{icon}   {title}", anchor="w", width=158,
                                height=56, corner_radius=0, fg_color="transparent",
                                hover_color="#24211D", text_color=MUTED,
                                font=ctk.CTkFont(family="Segoe UI", size=14),
                                command=lambda p=page: self._show_page(p))
            btn.pack(fill="x", pady=4)
            self._nav_buttons[page] = btn
        promo = ctk.CTkFrame(side, fg_color="#111A22", border_width=1,
                             border_color="#6C380D", corner_radius=12, height=210)
        promo.pack(side="bottom", fill="x", padx=13, pady=20)
        promo.pack_propagate(False)
        self.label(promo, self.store.model, 45, ACCENT, "bold").pack(anchor="w", padx=16, pady=(25, 0))
        self.label(promo, "SÉRIE\nPERFORMANCE", 13, MUTED, justify="left").pack(anchor="w", padx=16)
        self.side_battery = self.label(promo, "—", 26, GREEN, "bold")
        self.side_battery.pack(anchor="w", padx=16, pady=8)
        self.side_bar = ctk.CTkProgressBar(promo, height=4, progress_color=ACCENT)
        self.side_bar.pack(fill="x", padx=16)
        self.side_bar.set(0)

        main = ctk.CTkFrame(self, fg_color="#080F16", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(main, fg_color="transparent", height=76)
        header.grid(row=0, column=0, sticky="ew", padx=20)
        header.grid_propagate(False)
        self.page_heading = self.label(header, "", 18, TEXT, "bold")
        self.page_heading.pack(side="left")
        device = ctk.CTkFrame(header, fg_color="#0D161F", border_width=1,
                              border_color="#35475A", corner_radius=13)
        device.place(relx=.45, rely=.5, anchor="center")
        self.device_label = self.label(device,"Detectando mouse…",15,TEXT,"bold")
        self.device_label.pack(side="left",padx=14,pady=14)
        self.connection_badge = self.label(device, "●  Conectado", 12, GREEN)
        self.connection_badge.pack(side="left", padx=(0, 16))
        self.button(header, "⚙", lambda: self._show_page("Preferências"), width=42).pack(side="right", padx=(8, 0))
        self.label(header, "◎  Português (BR)", 12, MUTED).pack(side="right", padx=10)
        self.page_subtitle = self.label(main, "", 1)
        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent", scrollbar_button_color=BORDER)
        self.content.grid(row=1, column=0, sticky="nsew", padx=(14, 8), pady=(0, 8))
        self.content.grid_columnconfigure(0, weight=1)
        self.feedback = self.label(main, "Pronto", 11, MUTED, anchor="w")
        self.feedback.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 8))

    def _show_page(self, page):
        if page in ("Iluminação", "Firmware"):
            self._feedback("Este recurso não está disponível para configuração neste modelo")
            return
        super()._show_page(page)
        for name,btn in self._nav_buttons.items():
            btn.configure(fg_color="#25170E" if name==page else "transparent",
                          text_color=ACCENT if name==page else MUTED)
        if page == "Visão geral":
            self.page_heading.configure(text="")
            self._render_state(self.monitor.snapshot())

    def card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color="#101922", corner_radius=15,
                            border_color="#2C4051", border_width=1, **kwargs)

    def button(self,parent,text,command,primary=False,width=120,**kwargs):
        return ctk.CTkButton(parent,text=text,command=command,width=width,height=39,
                             corner_radius=10,fg_color="#25180F" if primary else "#141F29",
                             hover_color="#3D2718" if primary else "#263541",
                             border_width=1,border_color=ACCENT if primary else BORDER,
                             text_color=TEXT,font=ctk.CTkFont(family="Segoe UI",size=12),**kwargs)

    def _page_overview(self):
        profile = self.store.current
        grid = ctk.CTkFrame(self.content, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=26, uniform="columns")
        grid.grid_columnconfigure(1, weight=34, uniform="columns")
        grid.grid_columnconfigure(2, weight=36, uniform="columns")
        left = ctk.CTkFrame(grid, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        center = ctk.CTkFrame(grid, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=9)
        right = ctk.CTkFrame(grid, fg_color="transparent")
        right.grid(row=0, column=2, sticky="nsew", padx=(9, 0))

        buttons = self.card(left)
        buttons.pack(fill="x")
        self.label(buttons, "Botões", 22, TEXT, "bold").pack(anchor="w", padx=17, pady=(15, 12))
        self.button_menus = []
        for i, action in enumerate(profile["buttons"]):
            row = ctk.CTkFrame(buttons, fg_color="#080F14", corner_radius=10)
            row.pack(fill="x", padx=12, pady=3)
            badge=ctk.CTkFrame(row,width=31,height=31,corner_radius=16,fg_color=ACCENT)
            badge.pack(side="left",padx=7)
            badge.pack_propagate(False)
            self.label(badge,str(i+1),15,TEXT,"bold").place(relx=.5,rely=.5,anchor="center")
            menu = ctk.CTkOptionMenu(row, values=list(BUTTON_ACTIONS), height=39,
                                     fg_color="#101A23", button_color="#101A23",
                                     button_hover_color="#283744", text_color=TEXT,
                                     font=ctk.CTkFont(family="Segoe UI", size=12),
                                     command=lambda _: self._save_buttons(True))
            menu.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=5)
            menu.set(action)
            self.button_menus.append(menu)
        self.button(buttons, "Restaurar Padrão", self._reset_buttons).pack(fill="x", padx=14, pady=13)

        profiles = self.card(left)
        profiles.pack(fill="x", pady=(14, 0))
        title = ctk.CTkFrame(profiles, fg_color="transparent")
        title.pack(fill="x", padx=16, pady=14)
        self.label(title, "Perfil", 21, TEXT, "bold").pack(side="left")
        self.button(title, "+ Novo", self._add_profile, width=83).pack(side="right")
        for i, p in enumerate(self.store.profiles):
            selected = i == self.store.index
            self.button(profiles, f"{i+1}    {p['name']}",
                        lambda n=i: self._overview_profile(n), primary=selected).pack(
                            fill="x", padx=14, pady=5)
        self.button(profiles, "Gerenciar perfis  ›", lambda: self._show_page("Perfis")).pack(
            fill="x", padx=14, pady=(12, 16))

        hero = ctk.CTkFrame(center, fg_color="transparent", height=610)
        hero.pack(fill="x")
        hero.pack_propagate(False)
        self.label(hero, self.store.model, 33, "#B55222", "bold").place(x=14, y=25)
        canvas = tk.Canvas(hero, bg="#080F16", highlightthickness=0)
        canvas.place(relwidth=1, relheight=1)
        def rings(event):
            canvas.delete("all")
            w,h=event.width,event.height
            for inset,color in ((8,"#152C3D"),(18,"#203645"),(28,"#172632")):
                canvas.create_oval(inset,75,w-inset,h-35,outline=color,width=2)
            canvas.create_arc(12,78,w-12,h-35,start=150,extent=75,outline=ACCENT,width=3,style="arc")
            canvas.create_arc(12,78,w-12,h-35,start=-35,extent=65,outline=ACCENT,width=3,style="arc")
        canvas.bind("<Configure>",rings)
        art = self._original_mouse_art()
        if art:
            source=Image.open(art).convert("RGBA")
            self._mouse_image=ctk.CTkImage(source,source,size=(int(source.width*1.15),458))
            ctk.CTkLabel(hero,text="",image=self._mouse_image,fg_color="#080F16").place(
                relx=.5,rely=.53,anchor="center")
        else:
            self._draw_mouse(canvas)
        self.label(hero, "2,4 GHz  •  WIRELESS", 12, MUTED).place(relx=.5,rely=.97,anchor="center")
        battery=self.card(center)
        battery.pack(fill="x",pady=(12,0))
        self.label(battery,"Bateria",18,TEXT,"bold").pack(anchor="w",padx=18,pady=(14,0))
        self.hero_battery=self.label(battery,"—",42,GREEN,"bold")
        self.hero_battery.pack(anchor="w",padx=20)
        self.hero_bar=ctk.CTkProgressBar(battery,progress_color=GREEN,height=8)
        self.hero_bar.pack(fill="x",padx=20,pady=5)
        self.hero_bar.set(0)
        self.hero_note=self.label(battery,"Aguardando leitura",12,MUTED)
        self.hero_note.pack(anchor="w",padx=20,pady=(0,16))

        dpi=self.card(right)
        dpi.pack(fill="x")
        self.label(dpi,"DPI",22,TEXT,"bold").pack(anchor="w",padx=17,pady=(13,10))
        stages=ctk.CTkFrame(dpi,fg_color="#070D12",corner_radius=12)
        stages.pack(fill="x",padx=12)
        self.dpi_entries=[]
        self.dpi_sliders=[]
        self.dpi_labels=[]
        self.stage_buttons=[]
        self.stage_var=tk.IntVar(value=profile["active_stage"])
        maximum={"R1":18000,"X6":26000,"X11":26000}[self.store.model]
        colors=("#FF3C43","#FF8715","#E7DF00","#00DC6E","#00C9F1","#9850FF")
        for i,value in enumerate(profile["dpi"]):
            stages.grid_columnconfigure(i,weight=1,uniform="dpi")
            value_label=self.label(stages,str(value),12)
            value_label.grid(row=0,column=i,pady=(12,5))
            self.dpi_labels.append(value_label)
            slider=ctk.CTkSlider(stages,from_=100,to=maximum,orientation="vertical",
                                 height=133,width=16,progress_color=colors[i],
                                 button_color=colors[i],fg_color="#34414B",
                                 number_of_steps=(maximum-100)//(100 if self.store.model=="R1" else 50))
            slider.grid(row=1,column=i,pady=4)
            slider.set(value)
            self.dpi_sliders.append(slider)
            entry=ctk.CTkEntry(stages,width=52,height=29,justify="center",fg_color="#0C141B",
                               border_color=BORDER,font=ctk.CTkFont(size=11))
            entry.grid(row=3,column=i,padx=3,pady=(7,12))
            entry.insert(0,str(value))
            slider.configure(command=lambda n,e=entry,l=value_label: (e.delete(0,"end"),e.insert(0,str(round(n))),l.configure(text=str(round(n)))))
            def sync_entry(event,e=entry,s=slider,l=value_label):
                try:
                    n=int(e.get())
                    if not 100<=n<=maximum: return
                    s.set(n);l.configure(text=str(n))
                except ValueError: pass
            entry.bind("<FocusOut>",sync_entry)
            entry.bind("<Return>",sync_entry)
            self.dpi_entries.append(entry)
            marker=ctk.CTkButton(stages,text="",width=18,height=18,corner_radius=9,
                                 fg_color=colors[i] if i+1==self.stage_var.get() else "#070D12",
                                 border_color=colors[i],border_width=2,hover_color=colors[i],
                                 command=lambda n=i+1:self.stage_var.set(n))
            marker.grid(row=2,column=i,pady=5)
            self.stage_buttons.append(marker)
        self.stage_var.trace_add("write",lambda *_: [b.configure(fg_color=colors[n] if n+1==self.stage_var.get() else "#070D12") for n,b in enumerate(self.stage_buttons)])
        self.button(dpi,"◎   Aplicar ao mouse",lambda:self._save_dpi(True),primary=True).pack(
            fill="x",padx=13,pady=12)

        poll=self.card(right)
        poll.pack(fill="x",pady=(12,0))
        self.label(poll,"Taxa de Polling (Hz)",17,TEXT,"bold").pack(anchor="w",padx=16,pady=(13,9))
        rates=ctk.CTkFrame(poll,fg_color="transparent")
        rates.pack(fill="x",padx=12,pady=(0,14))
        for rate in (125,250,500,1000):
            self.button(rates,str(rate),lambda n=rate:self._quick_poll(n),
                        primary=rate==profile["polling"],width=60).pack(side="left",fill="x",expand=True,padx=3)
        advanced=self.card(right)
        advanced.pack(fill="x",pady=(12,0))
        self.label(advanced,"Configurações Avançadas",17,TEXT,"bold").pack(anchor="w",padx=16,pady=13)
        for title,key in (("Ângulo Snap","angle_snap"),("Controle de Ripple","ripple")):
            line=ctk.CTkFrame(advanced,fg_color="#0A1219",corner_radius=7)
            line.pack(fill="x",padx=12,pady=3)
            self.label(line,title,12,MUTED).pack(side="left",padx=10,pady=9)
            var=tk.BooleanVar(value=profile[key])
            ctk.CTkSwitch(line,text="",width=42,variable=var,progress_color=ACCENT,
                           command=lambda k=key,v=var:self._quick_flag(k,v.get())).pack(side="right",padx=7)
        self.button(advanced,"Tempo de resposta e propriedades  ›",lambda:self._show_page("Sensor e energia"),width=190).pack(
            fill="x",padx=12,pady=(9,13))
        energy=self.card(right)
        energy.pack(fill="x",pady=(12,0))
        self.label(energy,"Gerenciamento de Energia",17,TEXT,"bold").pack(anchor="w",padx=16,pady=(13,7))
        self.label(energy,f"Tempo para dormir: {profile['sleep']:g} min",13,MUTED).pack(anchor="w",padx=16,pady=5)
        self.button(energy,"Ajustar energia  ›",lambda:self._show_page("Sensor e energia")).pack(fill="x",padx=12,pady=(5,14))

    def _overview_profile(self,index):
        self.store.select(index)
        self._show_page("Visão geral")

    def _quick_poll(self,rate):
        self.store.current["polling"]=rate
        self.store.save()
        self._apply("polling")
        self._show_page("Visão geral")

    def _quick_flag(self,key,value):
        self.store.current[key]=bool(value)
        self.store.save()
        self._apply("dpi")

    def _reset_buttons(self):
        super()._reset_buttons()
        self._save_buttons(True)

    def _render_state(self,state):
        if state.model and state.model != self.store.model:
            self.store.set_model(state.model)
            self._show_page(self.page)
        self.device_label.configure(text=f"{state.model} Mouse" if state.model else "Identificando mouse…")
        token=(state.vid,state.pid,state.stage_event)
        if state.active_stage and token != self._stage_seen:
            self._stage_seen=token
            self.store.current["active_stage"]=state.active_stage
            self.store.save()
            if self.page in ("Visão geral","DPI") and hasattr(self,"stage_var"):
                self.stage_var.set(state.active_stage)
            self._feedback(f"DPI {self.store.current['dpi'][state.active_stage-1]} · estágio {state.active_stage}")
        super()._render_state(state)

    def _page_preferences(self):
        super()._page_preferences()
        from .updates import VERSION,saved_repository
        card=self.card(self.content)
        card.pack(fill="x",pady=14)
        self._section_title(card,"Atualizações do aplicativo",f"OpenShark {VERSION} · GitHub Releases")
        self.repo_entry=ctk.CTkEntry(card,placeholder_text="https://github.com/usuario/repositorio",height=38)
        self.repo_entry.pack(fill="x",padx=22,pady=7)
        self.repo_entry.insert(0,saved_repository())
        self.update_status=self.label(card,"Informe o repositório que publica o OpenShark.",12,MUTED)
        self.update_status.pack(anchor="w",padx=22,pady=5)
        actions=ctk.CTkFrame(card,fg_color="transparent")
        actions.pack(fill="x",padx=22,pady=(8,20))
        self.check_button=self.button(actions,"Verificar atualizações",self._check_updates,width=175)
        self.check_button.pack(side="left")
        self.install_button=self.button(actions,"Baixar e instalar",self._install_update,width=145,primary=True)
        self.install_button.pack(side="right")
        self.install_button.configure(state="disabled")
        tray=self.card(self.content)
        tray.pack(fill="x",pady=(0,12))
        self._section_title(tray,"Ícone perto da seta da barra de tarefas",
                            "Abra a seta e arraste o ícone OpenShark para a área ao lado dela.")
        self.button(tray,"Abrir configurações da barra",self._taskbar_settings,width=230).pack(anchor="w",padx=22,pady=(0,20))

    def _taskbar_settings(self):
        import os
        os.startfile("ms-settings:taskbar")

    def _check_updates(self):
        from .updates import check
        repo=self.repo_entry.get()
        self.check_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self._release=None
        self.update_status.configure(text="Consultando GitHub…")
        def work():
            try:self._update_results.put(("check",True,check(repo)))
            except Exception as exc:self._update_results.put(("check",False,str(exc)))
        Thread(target=work,daemon=True).start()

    def _install_update(self):
        from .updates import download
        if not self._release:return
        self.install_button.configure(state="disabled")
        self.update_status.configure(text="Baixando e verificando SHA-256…")
        release=dict(self._release)
        def work():
            try:self._update_results.put(("download",True,download(release)))
            except Exception as exc:self._update_results.put(("download",False,str(exc)))
        Thread(target=work,daemon=True).start()

    def _tick(self):
        while True:
            try:kind,success,data=self._update_results.get_nowait()
            except Empty:break
            status=getattr(self,"update_status",None)
            visible=status is not None and status.winfo_exists()
            if kind=="download" and success:
                from .updates import install
                try:install(data);self.on_close()
                except Exception as exc:self._feedback(str(exc),error=True)
            elif visible:
                self.check_button.configure(state="normal")
                if success:
                    self._release=data
                    status.configure(text=f"Versão {data['tag']} disponível" if data else "Você está na versão mais recente")
                    self.install_button.configure(state="normal" if data else "disabled")
                else:status.configure(text=f"Não foi possível atualizar: {data}")
        super()._tick()
