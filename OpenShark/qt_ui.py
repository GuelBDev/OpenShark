"""Qt desktop UI with painted gradients, light and geometry from the supplied reference."""
import math
import os
from pathlib import Path
import sys
import json
from queue import Queue, Empty
from threading import Thread

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QLinearGradient,
                           QRadialGradient, QPixmap, QFont, QPainterPath, QIcon, QIntValidator)
from PySide6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QSpinBox, QSlider,
    QStackedWidget, QScrollArea, QCheckBox, QInputDialog, QFileDialog,
    QMessageBox, QMenu, QPlainTextEdit, QLineEdit, QDialog, QDialogButtonBox)
from .profiles import ProfileStore, BUTTON_ACTIONS, default_profile, validate_profile
from .autostart import is_autostart_enabled, set_autostart
from .preferences import save as save_preferences
from . import updates

ORANGE = "#ff790d"
COLORS = ("#ff3c3f", "#ff8213", "#e1df00", "#00e167", "#00caf4", "#974bff")
STYLE = '''
QWidget { color:#eef2f7; font-family:'Segoe UI'; font-size:13px; background:transparent; }
QDialog { background:#101922; }
QLabel { border:0; background:transparent; }
QPushButton,QComboBox,QSpinBox,QPlainTextEdit,QLineEdit {
 background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #15212b,stop:.45 #0d151c,stop:1 #090f14);
 border:1px solid #293a47; border-radius:10px; padding:8px 12px; }
QPushButton:hover,QComboBox:hover { border-color:#617383; background:#202c36; }
QPushButton:pressed { background:#382317; border-color:#ff790d; }
QPushButton:checked,QPushButton[accent="true"] {
 border-color:#ff790d; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #422715,stop:.45 #1c1511,stop:1 #0c1014); }
QPushButton:disabled {color:#5b6875;border-color:#24303a;}
QComboBox { padding-right:25px; }
QComboBox::drop-down { border:0; width:24px; }
QComboBox QAbstractItemView {background:#101a23;selection-background-color:#422715;}
QSpinBox {padding:5px;border-radius:7px;selection-background-color:#85410c;}
QSpinBox QLineEdit {border:0;padding:0;margin:0;background:transparent;min-width:24px;}
QSpinBox::up-button,QSpinBox::down-button {width:0;}
QCheckBox { spacing:8px; color:#b7c4d2; }
QCheckBox::indicator {width:34px;height:18px;border-radius:9px;border:1px solid #485461;
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #34414c,stop:1 #111820);}
QCheckBox::indicator:checked {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff5a00,stop:1 #ffa24b);border-color:#ff8a26;}
QSlider::groove:horizontal {height:6px;border-radius:3px;background:#26333e;}
QSlider::sub-page:horizontal {border-radius:3px;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff5a00,stop:1 #ff9b45);}
QSlider::handle:horizontal {width:14px;height:14px;margin:-4px 0;border-radius:7px;background:#fff0e7;border:1px solid #ffb67e;}
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical {width:5px;background:transparent;}
QScrollBar::handle:vertical {background:#263b49;border-radius:2px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QMenu {background:#101a23;border:1px solid #354758;}
QMenu::item {padding:9px 20px;}
QMenu::item:selected {background:#593015;}
'''


def art_path(relative):
    start=Path(sys.executable if getattr(sys,"frozen",False) else __file__).resolve().parent
    bundled=Path(getattr(sys,"_MEIPASS",start))
    packaged=bundled/"OpenShark/vendor_art"/relative
    if packaged.is_file():return packaged
    for root in (start,*start.parents):
        path=root/"Attack Shark Software"/"res"/"skins"/relative
        if path.is_file():return path
    return None


def mouse_icon(index):
    pix=QPixmap(26,30);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#8696a3"),1.2));p.setBrush(QColor("#111920"));p.drawRoundedRect(QRectF(5,2,16,25),7,7)
    if index in (0,1):
        p.setPen(Qt.NoPen);p.setBrush(QColor("#cf5d21"));p.drawRoundedRect(QRectF(6 if index==0 else 14,4,6,9),2,2)
    p.setPen(QPen(QColor("#8696a3"),1));p.drawLine(13,3,13,13);p.drawLine(6,14,20,14)
    p.setBrush(QColor("#fe8527" if index==2 else "#9ba7b0"));p.drawRoundedRect(QRectF(11,6,4,7),2,2)
    p.end();return QIcon(pix)


def label(text,size=13,color="#eef2f7",bold=False):
    w=QLabel(text)
    w.setStyleSheet(f"font-size:{size}px;color:{color};font-weight:{600 if bold else 400};")
    return w


def button(text,callback=None,accent=False):
    w=QPushButton(text)
    w.setCursor(Qt.PointingHandCursor)
    w.setProperty("accent",accent)
    w.setMinimumHeight(34)
    if callback:w.clicked.connect(callback)
    return w


class Panel(QFrame):
    def __init__(self,title=None):
        super().__init__()
        self.box=QVBoxLayout(self)
        self.box.setContentsMargins(16,13,16,14)
        self.box.setSpacing(9)
        if title:self.box.addWidget(label(title,18,bold=True))

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(self.rect()).adjusted(.6,.6,-.6,-.6)
        path=QPainterPath();path.addRoundedRect(rect,14,14)
        base=QLinearGradient(rect.topLeft(),rect.bottomRight())
        for at,color in ((0,"#19212b"),(.35,"#080e13"),(.72,"#060a0e"),(1,"#10202e")):base.setColorAt(at,QColor(color))
        p.fillPath(path,base);p.setClipPath(path)
        sheen=QRadialGradient(QPointF(rect.width()*.9,0),rect.width()*.85)
        sheen.setColorAt(0,QColor(70,109,146,58));sheen.setColorAt(1,QColor(0,0,0,0));p.fillRect(rect,sheen)
        glow=QRadialGradient(QPointF(5,rect.height()+40),180)
        glow.setColorAt(0,QColor(198,76,23,30));glow.setColorAt(1,QColor(0,0,0,0));p.fillRect(rect,glow)
        p.setClipping(False)
        pen=QLinearGradient(rect.topLeft(),rect.bottomRight());pen.setColorAt(0,QColor("#385066"));pen.setColorAt(.5,QColor("#1b2a36"));pen.setColorAt(1,QColor("#334e63"))
        p.setPen(QPen(QBrush(pen),1));p.drawPath(path)
        if self.height()>260:
            p.setClipPath(path);p.setPen(QPen(QColor(47,76,99,45),1))
            for offset in (0,17,34):
                p.drawLine(QPointF(rect.width()*.40,rect.height()-18-offset),QPointF(rect.width()*.78,rect.height()-42-offset))
                p.drawLine(QPointF(rect.width()*.78,rect.height()-42-offset),QPointF(rect.width()+15,rect.height()-120-offset))


class Backdrop(QWidget):
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor("#03080c"))
        for x,y,r,c in ((.53,0,.40,(31,59,91,95)),(.5,1,.34,(12,54,88,65)),(.13,1,.25,(119,45,13,55))):
            g=QRadialGradient(QPointF(self.width()*x,self.height()*y),self.width()*r)
            g.setColorAt(0,QColor(*c));g.setColorAt(1,QColor(0,0,0,0));p.fillRect(self.rect(),g)


class MouseScene(QWidget):
    def __init__(self,model):
        super().__init__();self.model=model;self.setMinimumSize(290,440)
        self.pix=QPixmap()
        self.set_model(model)

    def set_model(self,model):
        self.model=model
        path=art_path({"R1":"ms_3","X6":"ms_1","X11":"ms_4"}[model]+"/mouse.png")
        self.pix=QPixmap(str(path)) if path else QPixmap();self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
        w,h=self.width(),self.height();cx=w/2;cy=h*.48;r=min(w*.48,h*.43)
        halo=QRadialGradient(QPointF(cx,cy),r*1.15)
        halo.setColorAt(0,QColor(27,39,51,30));halo.setColorAt(.7,QColor(249,102,12,14));halo.setColorAt(1,QColor(0,0,0,0))
        p.fillRect(self.rect(),halo)
        p.setPen(QPen(QColor("#1a3345"),1));p.drawEllipse(QPointF(cx,cy),r,r*1.18)
        for a in range(0,360,2):
            rad=math.radians(a);length=9 if a%10==0 else 4
            p.setPen(QPen(QColor(64,98,123,100 if a<200 else 55),1))
            p.drawLine(QPointF(cx+math.cos(rad)*r,cy+math.sin(rad)*r*1.18),QPointF(cx+math.cos(rad)*(r+length),cy+math.sin(rad)*(r*1.18+length)))
        ring=QRectF(cx-r,cy-r*1.18,r*2,r*2.36)
        for width,alpha in ((13,8),(7,22),(3,230)):
            p.setPen(QPen(QColor(255,110,20,alpha),width))
            p.drawArc(ring,156*16,42*16);p.drawArc(ring,-22*16,42*16)
        p.setPen(QColor("#773b24"));p.setFont(QFont("Segoe UI",25,QFont.Bold,True));p.drawText(12,48,self.model)
        p.setPen(QColor("#20384b"));p.setFont(QFont("Segoe UI",15,QFont.Bold,True));p.drawText(w-110,38,"ATTACK");p.drawText(w-93,57,"SHARK")
        # Technical floor grid, deliberately subtle under the product.
        p.setPen(QPen(QColor(41,72,92,40),1))
        for n in range(-7,8):p.drawLine(QPointF(cx+n*25,h*.83),QPointF(cx+n*48,h))
        for n in range(7):p.drawLine(QPointF(12,h*.83+n*14),QPointF(w-12,h*.83+n*14))
        height=min(h*.82,550);width=height*(self.pix.width()/self.pix.height() if not self.pix.isNull() else .56)
        target=QRectF(cx-width/2,cy-height/2,width,height)
        warm=QRadialGradient(QPointF(cx,cy+height*.35),width*.8)
        warm.setColorAt(0,QColor(255,111,33,42));warm.setColorAt(1,QColor(0,0,0,0));p.fillRect(self.rect(),warm)
        if not self.pix.isNull():
            p.drawPixmap(target,self.pix,QRectF(self.pix.rect()))
            if self.model=="R1":
                # Repaint numbered hotspots in the reference's orange finish.
                for x,y,n in ((55,74,1),(163,74,2),(110,70,3),(17,147,4),(20,211,5),(110,145,6)):
                    point=QPointF(target.x()+x/225*width,target.y()+y/398*height);radius=12*width/225
                    g=QRadialGradient(point,radius*1.7);g.setColorAt(0,QColor(255,125,18,150));g.setColorAt(1,QColor(255,80,0,0))
                    p.setPen(Qt.NoPen);p.setBrush(g);p.drawEllipse(point,radius*1.7,radius*1.7)
                    grad=QLinearGradient(point-QPointF(0,radius),point+QPointF(0,radius));grad.setColorAt(0,QColor("#ff9b32"));grad.setColorAt(1,QColor("#ff6000"))
                    p.setBrush(grad);p.setPen(QPen(QColor("#ffe6bf"),1));p.drawEllipse(point,radius,radius)
                    p.setPen(Qt.white);p.setFont(QFont("Segoe UI",11,QFont.Bold));p.drawText(QRectF(point.x()-radius,point.y()-radius,radius*2,radius*2),Qt.AlignCenter,str(n))
                p.setFont(QFont("Segoe UI",30,QFont.Bold,True));p.setPen(QColor("#17222b"));p.drawText(QRectF(cx-30,target.y()+height*.80,60,45),Qt.AlignCenter,"A")
        else:
            shape=QPainterPath();shape.moveTo(cx,target.top())
            shape.cubicTo(target.left()+width*.10,target.top(),target.left(),target.top()+height*.10,target.left(),target.top()+height*.25)
            shape.lineTo(target.left()+width*.035,target.top()+height*.63)
            shape.cubicTo(target.left()+width*.06,target.bottom()-height*.07,target.left()+width*.28,target.bottom(),cx,target.bottom())
            shape.cubicTo(target.right()-width*.28,target.bottom(),target.right()-width*.06,target.bottom()-height*.07,target.right()-width*.035,target.top()+height*.63)
            shape.lineTo(target.right(),target.top()+height*.25)
            shape.cubicTo(target.right(),target.top()+height*.10,target.right()-width*.10,target.top(),cx,target.top());shape.closeSubpath()
            g=QLinearGradient(target.topLeft(),target.bottomRight());g.setColorAt(0,QColor("#fffdf7"));g.setColorAt(.6,QColor("#cdd2d6"));g.setColorAt(1,QColor("#939ba1"));p.fillPath(shape,g)
            p.setPen(QPen(QColor("#39434b"),1.5));p.drawLine(QPointF(cx,target.top()+2),QPointF(cx,target.top()+height*.26))
            wheel=QRectF(cx-width*.07,target.top()+height*.09,width*.14,height*.11)
            p.setPen(QPen(QColor("#252d33"),1));p.setBrush(QColor("#252d33"));p.drawRoundedRect(wheel,5,5)
            p.setPen(QPen(QColor("#ff790d"),2));p.drawLine(QPointF(cx,wheel.top()+3),QPointF(cx,wheel.bottom()-3))
            p.setPen(QPen(QColor("#39434b"),1.4));p.drawArc(QRectF(target.left()+width*.02,target.top()+height*.21,width*.96,height*.48),190*16,160*16)
            p.setPen(QPen(QColor(255,121,13,170),2));p.drawLine(QPointF(target.left()+1,target.top()+height*.22),QPointF(target.left()+1,target.top()+height*.57))
            for sy in (.39,.52):
                side=QRectF(target.left()-width*.015,target.top()+height*sy,width*.09,height*.075)
                p.setPen(QPen(QColor("#3c454c"),1));p.setBrush(QColor("#78858d"));p.drawRoundedRect(side,4,4)


class DpiSlider(QSlider):
    def __init__(self,color,maximum,step):
        super().__init__(Qt.Vertical);self.setRange(100,maximum);self.setSingleStep(step);self.setPageStep(step)
        self.setFixedHeight(140);self.setFixedWidth(29)
        self.setStyleSheet(f'''QSlider::groove:vertical {{width:6px;border-radius:3px;background:#364049;}}
        QSlider::add-page:vertical {{border-radius:3px;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {color},stop:1 {color});}}
        QSlider::handle:vertical {{height:12px;width:12px;margin:0 -4px;background:#fff;border:2px solid {color};border-radius:7px;}}''')


class Toggle(QCheckBox):
    def __init__(self,text):
        super().__init__(text);self.setMinimumHeight(26);self.setMinimumWidth(158);self.setCursor(Qt.PointingHandCursor)
    def hitButton(self,pos):return self.rect().contains(pos)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor("#b5c4d2"));p.drawText(QRectF(0,0,self.width()-45,self.height()),Qt.AlignVCenter,self.text())
        track=QRectF(self.width()-40,(self.height()-22)/2,39,22)
        g=QLinearGradient(track.topLeft(),track.bottomRight());g.setColorAt(0,QColor("#ff5a00" if self.isChecked() else "#46515b"));g.setColorAt(1,QColor("#ff9a32" if self.isChecked() else "#111921"))
        p.setBrush(g);p.setPen(QPen(QColor("#ff8b28" if self.isChecked() else "#4d5862"),1));p.drawRoundedRect(track,11,11)
        p.setPen(Qt.NoPen);p.setBrush(QColor("#f4f5f6"));p.drawEllipse(QPointF(track.right()-11 if self.isChecked() else track.left()+11,track.center().y()),8.5,8.5)


class DpiInput(QLineEdit):
    valueChanged=Signal(int)
    def __init__(self):
        super().__init__();self._value=100;self._maximum=26000
        self.setStyleSheet("padding:3px 0;border:1px solid #293a47;border-radius:7px;background:#080e13;")
        self.editingFinished.connect(lambda:self.setValue(self.value()))
    def setRange(self,minimum,maximum):self.setMaximum(maximum)
    def setMaximum(self,maximum):self._maximum=maximum;self.setValidator(QIntValidator(100,maximum,self))
    def setSingleStep(self,step):self._step=step
    def setButtonSymbols(self,symbols):pass
    def value(self):
        try:return min(self._maximum,max(100,int(self.text())))
        except ValueError:return self._value
    def setValue(self,n):
        n=min(self._maximum,max(100,int(n)));changed=n!=self._value;self._value=n;self.setText(str(n))
        if changed:self.valueChanged.emit(n)


class Dashboard(QWidget):
    def __init__(self,monitor,show_request,exit_request,on_close,set_tray_enabled=lambda enabled:None,preferences=None):
        super().__init__();self.monitor=monitor;self.show_request=show_request;self.exit_request=exit_request;self.on_close=on_close;self.set_tray_enabled=set_tray_enabled
        self.preferences=preferences or {"onboarding_complete":True,"start_with_windows":is_autostart_enabled(),"battery_in_taskbar":True}
        self.store=ProfileStore();self.minimize_to_tray=self.preferences["battery_in_taskbar"];self.last=None;self.stage_seen=None;self.busy=False;self.pending_dpi=None
        self.update_queue=Queue();self.release=None
        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint)
        self.setWindowTitle("ATTACK SHARK — OpenShark")
        self.resize(1536,980);self.setMinimumSize(1220,790)
        self.setStyleSheet(STYLE)
        icon=Path(getattr(sys,"_MEIPASS",Path(__file__).parent.parent))/"OpenShark/openshark.ico"
        self.setWindowIcon(QIcon(str(icon)))
        QApplication.instance().setWindowIcon(QIcon(str(icon)))
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0)
        self.back=Backdrop();outer.addWidget(self.back)
        root=QVBoxLayout(self.back);root.setContentsMargins(0,0,14,9);root.setSpacing(0)
        header=QHBoxLayout();header.setContentsMargins(20,12,8,8);header.setSpacing(12)
        logo=QLabel();path=art_path("logo_2.png")
        if path:
            original=QPixmap(str(path));word=original.copy(60,0,original.width()-60,original.height())
            paint=QPainter(word);paint.setCompositionMode(QPainter.CompositionMode_SourceIn);paint.fillRect(word.rect(),QColor("#f7f8fa"));paint.end()
            paint=QPainter(original);paint.drawPixmap(60,0,word);paint.end()
            logo.setPixmap(original.scaled(235,50,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:logo.setText("ATTACK SHARK");logo.setStyleSheet("font-size:24px;font-weight:bold;font-style:italic;")
        logo.setFixedWidth(310);header.addWidget(logo);header.addStretch()
        device=Panel();device.box.setContentsMargins(15,3,20,3)
        self.device_name=label("R1 Mouse",15,bold=True);self.device_status=label("● Conectado",12,"#9fb6cb")
        device.box.addWidget(self.device_name);device.box.addWidget(self.device_status)
        device.setFixedSize(278,62);header.addWidget(device);header.addStretch()
        header.addWidget(button("◎  Português (BR)"));header.addWidget(button("⚙",lambda:self.navigate("Configurações")))
        header.addWidget(button("—",self.showMinimized));header.addWidget(button("×",self.close))
        root.addLayout(header)
        row=QHBoxLayout();row.setSpacing(14)
        sidebar=QWidget();sidebar.setFixedWidth(184);nav=QVBoxLayout(sidebar);nav.setContentsMargins(12,8,0,0);nav.setSpacing(6)
        self.nav={}
        for glyph,name in (("▣","Dispositivo"),("⌘","Macros"),("⚙","Configurações")):
            b=button(name,lambda checked=False,n=name:self.navigate(n));b.setCheckable(True);b.setFixedHeight(61)
            icon_pixmap=QPixmap(20,20);icon_pixmap.fill(Qt.transparent)
            painter=QPainter(icon_pixmap);painter.setPen(QColor("#b3c0cd"));painter.setFont(QFont("Segoe UI Symbol",15))
            painter.drawText(icon_pixmap.rect(),Qt.AlignCenter,glyph);painter.end()
            b.setIcon(QIcon(icon_pixmap));b.setIconSize(icon_pixmap.size())
            b.setStyleSheet('''QPushButton{border:0;border-left:4px solid transparent;border-radius:0;text-align:left;color:#b3c0cd;padding-left:19px;background:transparent;font-size:14px;}
            QPushButton:checked{border-left-color:#ff790d;color:#ff8b25;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #54280e,stop:.2 #26170d,stop:1 #070d11);}''')
            nav.addWidget(b);self.nav[name]=b
        nav.addStretch()
        row.addWidget(sidebar)
        self.stack=QStackedWidget();row.addWidget(self.stack,1);root.addLayout(row,1)
        self.home=self.build_home();self.stack.addWidget(self.home)
        self.settings=self.build_settings();self.stack.addWidget(self.settings)
        self.macros=self.build_macros();self.stack.addWidget(self.macros)
        self.feedback=label("",11,"#93a7b8");self.feedback.setContentsMargins(198,3,0,0);root.addWidget(self.feedback)
        self.navigate("Dispositivo");self.render(self.monitor.snapshot())
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(150)
        QTimer.singleShot(1000, lambda: self.check_updates(automatic=True))
        QTimer.singleShot(350, self.show_onboarding)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and event.position().y()<80:self.windowHandle().startSystemMove()

    def build_home(self):
        home=QWidget();layout=QHBoxLayout(home);layout.setContentsMargins(0,2,0,0);layout.setSpacing(18)
        left=QVBoxLayout();left.setSpacing(14)
        buttons=Panel("Botões");buttons.box.setSpacing(7);self.button_menus=[]
        for i,action in enumerate(self.store.current["buttons"]):
            line=QHBoxLayout();line.setSpacing(12)
            badge=label(str(i+1),16,bold=True);badge.setAlignment(Qt.AlignCenter);badge.setFixedSize(34,34)
            badge.setStyleSheet("border-radius:17px;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ffb24b,stop:.4 #ff8317,stop:1 #f95a00);color:white;font-size:16px;")
            line.addWidget(badge);combo=QComboBox()
            for name in BUTTON_ACTIONS:combo.addItem(mouse_icon(i),name)
            combo.setCurrentText(action);combo.setMinimumHeight(43)
            chevron=(Path(getattr(sys,"_MEIPASS",Path(__file__).parent.parent))/"OpenShark/assets/chevron.svg").as_posix()
            combo.setStyleSheet(f'QComboBox::down-arrow {{image:url("{chevron}");width:14px;height:10px;}}')
            combo.currentTextChanged.connect(lambda text,n=i:self.remap(n,text));line.addWidget(combo,1);buttons.box.addLayout(line);self.button_menus.append(combo)
        buttons.box.addWidget(button("Restaurar Padrão",self.reset_buttons));left.addWidget(buttons)
        self.profiles_panel=Panel();self.profile_box=self.profiles_panel.box
        self.fill_profiles();left.addWidget(self.profiles_panel,1)
        leftw=QWidget();leftw.setLayout(left);layout.addWidget(leftw,27)

        middle=QVBoxLayout();middle.setSpacing(12)
        self.scene=MouseScene(self.store.model);middle.addWidget(self.scene,1)
        view=QHBoxLayout();view.addStretch();view.addWidget(label("2D",13,ORANGE,True));view.addWidget(label("   •   2,4 GHz / USB",12,"#7d94a9"));view.addStretch();middle.addLayout(view)
        battery=Panel("Bateria");battery.setMinimumHeight(150)
        inner=QFrame();inner.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #050a0d,stop:1 #090f14);border-radius:12px;}")
        batrow=QHBoxLayout(inner);batrow.setContentsMargins(16,12,16,12)
        self.battery_icon=label("▰",44,"#1aff84",True);batrow.addWidget(self.battery_icon)
        self.battery_text=label("—",29,bold=True);batrow.addWidget(self.battery_text);batrow.addStretch()
        batdetails=QVBoxLayout();self.battery_note=label("Aguardando leitura",12,"#a8bdcc");batdetails.addWidget(self.battery_note);self.battery_connection=label("● Wireless",12,"#18ed7c");batdetails.addWidget(self.battery_connection);batrow.addLayout(batdetails)
        battery.box.addWidget(inner);middle.addWidget(battery)
        midw=QWidget();midw.setLayout(middle);layout.addWidget(midw,35)

        right=QVBoxLayout();right.setSpacing(12)
        dpi=Panel();head=QHBoxLayout();head.addWidget(label("DPI",22,bold=True));head.addStretch();head.addWidget(label("SEIS ESTÁGIOS",10,"#8295a7"));dpi.box.addLayout(head)
        stageframe=QFrame();stageframe.setStyleSheet("QFrame{background:#050b0f;border-radius:12px;}")
        stages=QHBoxLayout(stageframe);stages.setContentsMargins(7,12,7,9);stages.setSpacing(8)
        self.dpi_values=[];self.dpi_sliders=[];self.stage_markers=[]
        maximum={"R1":18000,"X6":26000,"X11":26000}[self.store.model];step=100 if self.store.model=="R1" else 50
        self.dpi_labels=[]
        for i,value in enumerate(self.store.current["dpi"]):
            col=QVBoxLayout();col.setAlignment(Qt.AlignHCenter);col.setSpacing(8)
            title=label(str(value),14);title.setAlignment(Qt.AlignCenter);col.addWidget(title);self.dpi_labels.append(title)
            slider=DpiSlider(COLORS[i],maximum,step);slider.setValue(value);col.addWidget(slider,0,Qt.AlignHCenter)
            marker=button("",lambda checked=False,n=i:self.select_stage(n+1));marker.setFixedSize(12,12);marker.setMinimumHeight(12);col.addWidget(marker,0,Qt.AlignHCenter);self.stage_markers.append(marker)
            spin=DpiInput();spin.setRange(100,maximum);spin.setSingleStep(step);spin.setValue(value);spin.setAlignment(Qt.AlignCenter);spin.setFixedHeight(30);spin.setMinimumWidth(48)
            slider.valueChanged.connect(lambda n,s=spin,l=title:s.setValue(round(n/s._step)*s._step))
            spin.valueChanged.connect(lambda n,s=slider,l=title:(s.setValue(n),l.setText(str(n))))
            col.addWidget(spin);self.dpi_values.append(spin);self.dpi_sliders.append(slider);stages.addLayout(col,1)
        dpi.box.addWidget(stageframe)
        actions=QHBoxLayout();self.apply_button=button("Aplicar DPI ao mouse",self.apply_dpi,True);actions.addWidget(self.apply_button,1);actions.addWidget(button("↶",self.reset_dpi));dpi.box.addLayout(actions);right.addWidget(dpi)
        polling=Panel("Taxa de Polling (Hz)");rates=QHBoxLayout();self.poll_buttons={}
        for rate in (125,250,500,1000):
            b=button(str(rate),lambda checked=False,r=rate:self.poll(r));b.setCheckable(True);rates.addWidget(b,1);self.poll_buttons[rate]=b
        polling.box.addLayout(rates);right.addWidget(polling)
        advanced=Panel("Configurações Avançadas");advgrid=QGridLayout();advgrid.setHorizontalSpacing(12);advgrid.setVerticalSpacing(8)
        self.angle=Toggle("Ângulo Snap");self.ripple=Toggle("Controle de Ripple")
        self.angle.toggled.connect(lambda value:self.flag("angle_snap",value));self.ripple.toggled.connect(lambda value:self.flag("ripple",value))
        advgrid.addWidget(self.angle,0,0);advgrid.addWidget(self.ripple,1,0)
        advgrid.addWidget(label("Key Response Time",12,"#a6b9cc"),0,1)
        self.response=QComboBox();self.response.addItems([f"{v} ms" for v in range(4,51,2)]);advgrid.addWidget(self.response,0,2)
        advgrid.addWidget(button("Propriedades do Windows",lambda:os.startfile("main.cpl")),2,0,1,2)
        advgrid.addWidget(button("Aplicar",self.apply_power),2,2);advanced.box.addLayout(advgrid);right.addWidget(advanced)
        power=Panel("Gerenciamento de Energia");energyrow=QHBoxLayout();energyrow.addWidget(label("Modo de conexão",12,"#a6b9cc"));energyrow.addStretch();self.power_mode=label("Wireless",12);energyrow.addWidget(self.power_mode);power.box.addLayout(energyrow)
        self.sleep=QSlider(Qt.Horizontal);self.sleep.setRange(1,120)
        sleep_row=QHBoxLayout();sleep_row.addWidget(label("Tempo para dormir",12,"#a6b9cc"));sleep_row.addWidget(self.sleep,1);self.sleep_label=label("5 min",12);sleep_row.addWidget(self.sleep_label)
        self.sleep.valueChanged.connect(lambda value:self.sleep_label.setText(f"{value/2:g} min"));self.sleep.sliderReleased.connect(self.apply_power);power.box.addLayout(sleep_row)
        deep=QHBoxLayout();deep.addWidget(label("Sono profundo",12,"#a6b9cc"));self.deep_sleep=QSpinBox();self.deep_sleep.setRange(1,60);self.deep_sleep.setFixedWidth(62);deep.addWidget(self.deep_sleep);deep.addWidget(label("minutos",12,"#a6b9cc"));deep.addStretch();deep.addWidget(button("Aplicar energia",self.apply_power));power.box.addLayout(deep)
        right.addWidget(power);right.addStretch()
        rightw=QWidget();rightw.setLayout(right);layout.addWidget(rightw,36)
        self.load_profile();return home

    def fill_profiles(self):
        while self.profile_box.count():
            item=self.profile_box.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child=item.layout().takeAt(0)
                    if child.widget():child.widget().deleteLater()
        heading=QWidget();row=QHBoxLayout(heading);row.setContentsMargins(0,0,0,0);row.addWidget(label("Perfil",21,bold=True));row.addStretch();row.addWidget(button("＋ Novo Perfil",self.new_profile));self.profile_box.addWidget(heading)
        for i,profile in enumerate(self.store.profiles):
            line=QWidget();r=QHBoxLayout(line);r.setContentsMargins(0,0,0,0);r.setSpacing(6)
            b=button(f"{i+1}      {profile['name']}",lambda checked=False,n=i:self.choose_profile(n),i==self.store.index);b.setMinimumHeight(47);r.addWidget(b,1)
            menu=button("⋮",lambda checked=False,n=i:self.profile_menu(n));menu.setFixedWidth(34);r.addWidget(menu);self.profile_box.addWidget(line)
        self.profile_box.addStretch()
        tools=QWidget();row=QHBoxLayout(tools);row.setContentsMargins(0,0,0,0);row.addWidget(button("Importar",self.import_profile));row.addWidget(button("Exportar",self.export_profile));self.profile_box.addWidget(tools)

    def load_profile(self):
        p=self.store.current
        for spin,slider,n in zip(self.dpi_values,self.dpi_sliders,p["dpi"]):
            maximum={"R1":18000,"X6":26000,"X11":26000}[self.store.model]
            spin.setMaximum(maximum);slider.setMaximum(maximum);spin.setSingleStep(100 if self.store.model=="R1" else 50);spin.setValue(n)
        for combo,text in zip(self.button_menus,p["buttons"]):combo.blockSignals(True);combo.setCurrentText(text);combo.blockSignals(False)
        for check,key in ((self.angle,"angle_snap"),(self.ripple,"ripple")):
            check.blockSignals(True);check.setChecked(p[key]);check.blockSignals(False)
        self.response.clear();self.response.addItems([f"{v} ms" for v in (range(2,26) if self.store.model=="X6" else range(4,51,2))]);self.response.setCurrentText(f"{p['response']} ms")
        self.sleep.setValue(int(p["sleep"]*2));self.deep_sleep.setValue(p["deep_sleep"])
        self.update_selection()

    def update_selection(self):
        for i,b in enumerate(self.stage_markers):b.setStyleSheet(f"border:2px solid {COLORS[i]};border-radius:6px;padding:0;background:{COLORS[i] if i+1==self.store.current['active_stage'] else '#080e13'};")
        for rate,b in self.poll_buttons.items():b.setChecked(rate==self.store.current["polling"])

    def select_stage(self,n):self.store.current["active_stage"]=n;self.store.save();self.update_selection()

    def apply_dpi(self):
        p=dict(self.store.current);p["dpi"]=[s.value() for s in self.dpi_values]
        try:
            validated=validate_profile(p)
            if self.apply("dpi",validated):
                self.pending_dpi=(self.store.model,self.store.index,validated)
        except ValueError as e:self.feedback.setText(str(e))

    def reset_dpi(self):
        for spin,n in zip(self.dpi_values,default_profile(self.store.model)["dpi"]):spin.setValue(n)

    def reset_buttons(self):
        self.store.current["buttons"]=default_profile(self.store.model)["buttons"];self.store.save();self.load_profile();self.apply("buttons")

    def remap(self,i,text):self.store.current["buttons"][i]=text;self.store.save();self.apply("buttons")
    def poll(self,rate):self.store.current["polling"]=rate;self.store.save();self.update_selection();self.apply("polling")
    def flag(self,key,value):self.store.current[key]=value;self.store.save();self.apply("dpi")

    def apply_power(self):
        self.store.current.update(response=int(self.response.currentText().split()[0]),sleep=self.sleep.value()/2,deep_sleep=self.deep_sleep.value());self.store.save();self.apply("power")

    def apply(self,section,profile=None):
        if self.busy:
            self.feedback.setText("Aguarde o ajuste anterior terminar")
            return False
        try:
            self.monitor.apply(profile if profile is not None else self.store.current,section)
            self.busy=True;self.apply_button.setEnabled(False);self.feedback.setText("Enviando ajustes ao mouse…")
            return True
        except Exception as e:
            self.feedback.setText(str(e))
            return False

    def choose_profile(self,i):self.store.select(i);self.load_profile();self.fill_profiles()
    def new_profile(self):
        text,ok=QInputDialog.getText(self,"Novo perfil","Nome do perfil:")
        if ok and text:
            try:self.store.add(text);self.fill_profiles();self.load_profile()
            except ValueError as e:self.feedback.setText(str(e))

    def profile_menu(self,i):
        menu=QMenu(self);rename=menu.addAction("Renomear");reset=menu.addAction("Restaurar padrão");delete=menu.addAction("Excluir");apply=menu.addAction("Aplicar perfil")
        action=menu.exec(self.cursor().pos())
        if not action:return
        self.store.select(i)
        if action==rename:
            text,ok=QInputDialog.getText(self,"Renomear perfil","Nome:",text=self.store.current["name"])
            if ok and text:self.store.current["name"]=text[:48];self.store.save()
        elif action==reset:self.store.current.update(default_profile(self.store.model,self.store.current["name"]));self.store.save()
        elif action==delete:
            try:self.store.delete()
            except ValueError as e:self.feedback.setText(str(e))
        elif action==apply:self.apply("all")
        self.load_profile();self.fill_profiles()

    def import_profile(self):
        path,_=QFileDialog.getOpenFileName(self,"Importar perfil","","JSON (*.json)")
        if path:
            try:self.store.import_file(path);self.load_profile();self.fill_profiles()
            except Exception as e:self.feedback.setText(str(e))

    def export_profile(self):
        path,_=QFileDialog.getSaveFileName(self,"Exportar perfil",self.store.current["name"]+".json","JSON (*.json)")
        if path:self.store.export_file(path)

    def build_settings(self):
        page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(25,20,25,20)
        box.addWidget(label("Configurações",28,bold=True))
        panel=Panel("Inicialização e bandeja")
        self.auto_start=QCheckBox("Iniciar com o Windows");self.auto_start.setChecked(self.preferences["start_with_windows"]);self.auto_start.toggled.connect(self.set_auto_start);panel.box.addWidget(self.auto_start)
        self.taskbar_battery=QCheckBox("Exibir bateria na área de notificação");self.taskbar_battery.setChecked(self.preferences["battery_in_taskbar"]);self.taskbar_battery.toggled.connect(self.set_taskbar_battery);panel.box.addWidget(self.taskbar_battery)
        panel.box.addWidget(label("A bateria é atualizada automaticamente na área de notificação do Windows.",14,"#a1b4c5"));box.addWidget(panel)
        update=Panel(f"Atualizações • OpenShark {updates.VERSION}")
        from PySide6.QtWidgets import QLineEdit
        self.repo=QLineEdit(updates.saved_repository());update.box.addWidget(self.repo)
        self.update_label=label("GitHub Releases",13,"#a1b4c5");update.box.addWidget(self.update_label)
        actions=QHBoxLayout();self.check_button=button("Verificar atualizações",self.check_updates);self.install_button=button("Baixar e instalar",self.install_update,True);self.install_button.setEnabled(False);actions.addWidget(self.check_button);actions.addWidget(self.install_button);update.box.addLayout(actions);box.addWidget(update)
        box.addStretch();box.addWidget(button("Sair do OpenShark",self.on_close));return page

    def save_preferences(self):
        self.preferences["onboarding_complete"]=True
        self.preferences=save_preferences(self.preferences)

    def set_auto_start(self,enabled):
        if set_autostart(enabled):
            self.preferences["start_with_windows"]=enabled;self.save_preferences()
        else:
            self.feedback.setText("Não foi possível alterar a inicialização do Windows")
            self.auto_start.blockSignals(True);self.auto_start.setChecked(not enabled);self.auto_start.blockSignals(False)

    def set_taskbar_battery(self,enabled):
        self.preferences["battery_in_taskbar"]=enabled
        self.minimize_to_tray=enabled
        self.set_tray_enabled(enabled)
        self.save_preferences()

    def show_onboarding(self):
        if self.preferences["onboarding_complete"]:
            return
        dialog=QDialog(self);dialog.setWindowTitle("Configuração inicial");dialog.setModal(True);dialog.setMinimumWidth(440)
        box=QVBoxLayout(dialog);box.addWidget(label("Como você quer usar o OpenShark?",22,bold=True))
        box.addWidget(label("Você poderá mudar estas opções depois em Configurações.",13,"#a1b4c5"))
        start=QCheckBox("Iniciar o OpenShark junto com o Windows");start.setChecked(True);box.addWidget(start)
        battery=QCheckBox("Exibir a bateria na área de notificação do Windows");battery.setChecked(True);box.addWidget(battery)
        buttons=QDialogButtonBox(QDialogButtonBox.Save);buttons.accepted.connect(dialog.accept);box.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted:
            return
        self.preferences["start_with_windows"]=start.isChecked()
        self.preferences["battery_in_taskbar"]=battery.isChecked()
        if not set_autostart(start.isChecked()):
            self.preferences["start_with_windows"]=False
            self.feedback.setText("A inicialização com o Windows não pôde ser configurada")
        self.minimize_to_tray=battery.isChecked()
        self.set_tray_enabled(battery.isChecked())
        self.save_preferences()
        if hasattr(self,"auto_start"):
            self.auto_start.blockSignals(True);self.auto_start.setChecked(self.preferences["start_with_windows"]);self.auto_start.blockSignals(False)
            self.taskbar_battery.blockSignals(True);self.taskbar_battery.setChecked(self.preferences["battery_in_taskbar"]);self.taskbar_battery.blockSignals(False)

    def build_macros(self):
        page=QWidget();box=QVBoxLayout(page);box.setContentsMargins(25,20,25,20);box.addWidget(label("Macros",28,bold=True))
        box.addWidget(label("Biblioteca local do perfil • envio ao firmware indisponível",14,"#a1b4c5"))
        self.macro_name=QComboBox();self.macro_name.currentIndexChanged.connect(self.load_macro);box.addWidget(self.macro_name)
        self.macro_editor=QPlainTextEdit();self.macro_editor.setPlaceholderText("Uma ação por linha: A, 50");box.addWidget(self.macro_editor,1)
        actions=QHBoxLayout();actions.addWidget(button("Nova macro",self.new_macro));actions.addWidget(button("Salvar",self.save_macro));actions.addWidget(button("Excluir",self.delete_macro));box.addLayout(actions);return page

    def refresh_macros(self):
        self.macro_name.blockSignals(True);self.macro_name.clear();self.macro_name.addItems([m["name"] for m in self.store.current["macros"]]);self.macro_name.blockSignals(False);self.load_macro()
    def load_macro(self,*args):
        i=self.macro_name.currentIndex()
        if hasattr(self,"macro_editor"):self.macro_editor.setPlainText("\n".join(f"{a['key']}, {a['delay']}" for a in self.store.current["macros"][i]["actions"]) if i>=0 else "")
    def new_macro(self):
        text,ok=QInputDialog.getText(self,"Nova macro","Nome:")
        if ok and text:self.store.current["macros"].append({"name":text[:48],"actions":[]});self.store.save();self.refresh_macros()
    def save_macro(self):
        i=self.macro_name.currentIndex()
        if i<0:return
        try:
            actions=[]
            for line in self.macro_editor.toPlainText().splitlines():
                if not line.strip():continue
                key,delay=line.split(",",1);delay=int(delay.strip())
                if not key.strip() or not 0<=delay<=60000:raise ValueError("Ação inválida")
                actions.append({"key":key.strip()[:24],"delay":delay})
            if len(actions)>256:raise ValueError("Limite de 256 ações")
            self.store.current["macros"][i]["actions"]=actions;self.store.save();self.feedback.setText("Macro salva no perfil")
        except ValueError as e:self.feedback.setText(str(e))
    def delete_macro(self):
        i=self.macro_name.currentIndex()
        if i>=0:del self.store.current["macros"][i];self.store.save();self.refresh_macros()

    def navigate(self,name):
        for n,b in self.nav.items():b.setChecked(n==name)
        self.stack.setCurrentIndex(1 if name=="Configurações" else 2 if name=="Macros" else 0)
        if self.stack.currentIndex()==0:self.scene.update()
        if name=="Macros":self.refresh_macros()

    def check_updates(self, automatic=False):
        repo=self.repo.text();self.check_button.setEnabled(False);self.install_button.setEnabled(False);self.update_label.setText("Consultando GitHub…")
        def work():
            try:self.update_queue.put(("automatic" if automatic else "check",True,updates.check(repo)))
            except Exception as e:self.update_queue.put(("automatic" if automatic else "check",False,str(e)))
        Thread(target=work,daemon=True).start()
    def install_update(self):
        if not self.release:return
        self.install_button.setEnabled(False);self.update_label.setText("Baixando e verificando SHA-256…")
        def work():
            try:self.update_queue.put(("download",True,updates.download(self.release)))
            except Exception as e:self.update_queue.put(("download",False,str(e)))
        Thread(target=work,daemon=True).start()

    def render(self,state):
        if state.model and state.model!=self.store.model:
            self.store.set_model(state.model);self.load_profile();self.fill_profiles();self.scene.set_model(state.model)
        self.device_name.setText(f"{state.model} Mouse" if state.model else "Identificando mouse…")
        self.device_status.setText("●  Carregando · USB" if state.wired else "●  Conectado" if state.connected else "○  Desconectado")
        self.device_status.setStyleSheet("color:#71c9f8;" if state.wired else "color:#13e67b;")
        self.battery_text.setText("Carregando" if state.wired else f"{state.percent}%" if state.percent is not None else "—")
        self.battery_text.setStyleSheet(f"font-size:{22 if state.wired else 29}px;font-weight:600;")
        self.battery_icon.setText("ϟ" if state.wired else "▰")
        self.battery_note.setText("Cabo USB conectado" if state.wired else "Bateria wireless" if state.percent is not None else "Aguardando leitura")
        self.battery_connection.setText("● Carregando" if state.wired else "● Em uso sem fio" if state.connected else "Desconectado")
        self.power_mode.setText("USB · Carregando" if state.wired else "Wireless · 2,4 GHz")
        token=(state.vid,state.pid,state.stage_event)
        if state.active_stage and token!=self.stage_seen:
            self.stage_seen=token;self.select_stage(state.active_stage)
            self.feedback.setText(f"DPI {self.store.current['dpi'][state.active_stage-1]} · estágio {state.active_stage}")

    def tick(self):
        if self.exit_request.is_set():QApplication.instance().quit();return
        if self.show_request.is_set():self.show_request.clear();self.showNormal();self.raise_();self.activateWindow()
        state=self.monitor.snapshot()
        if state!=self.last:self.render(state);self.last=state
        while result:=self.monitor.poll_result():
            self.busy=False;self.apply_button.setEnabled(True)
            if result[0]=="dpi" and self.pending_dpi:
                model,index,profile=self.pending_dpi
                if result[1] and self.store.model==model and self.store.index==index:
                    self.store.current.update(profile);self.store.save()
                self.pending_dpi=None
            self.feedback.setText(result[2])
        while True:
            try:kind,success,data=self.update_queue.get_nowait()
            except Empty:break
            if kind=="download" and success:
                try:updates.install(data);self.on_close()
                except Exception as e:self.update_label.setText(str(e))
            else:
                self.check_button.setEnabled(True)
                if success:
                    self.release=data;self.update_label.setText(f"Versão {data['tag']} disponível" if data else "Você está na versão mais recente");self.install_button.setEnabled(bool(data))
                    if kind=="automatic" and data and QMessageBox.question(self,"Atualização disponível",f"OpenShark {data['tag']} está disponível. Deseja atualizar agora?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.install_update()
                else:self.update_label.setText(str(data))

    def closeEvent(self,event):
        if self.minimize_to_tray:event.ignore();self.hide()
        else:self.on_close();event.accept()
