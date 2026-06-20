import sys
import os
import json
import ctypes
import psutil

from PyQt6.QtWidgets import *
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import QListWidgetItem, QStyle, QMenu, QSlider, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QSystemTrayIcon

import win32gui
import winreg

APP_NAME = "PrismControl"

BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), APP_NAME)
os.makedirs(BASE_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

user32 = ctypes.windll.user32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
LWA_ALPHA = 0x2


def set_transparency(hwnd, alpha):
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)


def get_icon(path):
    try:
        large, small = win32gui.ExtractIconEx(path, 0)
        if large:
            hicon = large[0]
            win32gui.DestroyIcon(small[0])
            return QIcon(QPixmap.fromWinHICON(hicon))
    except:
        pass
    return QIcon()


class PrismControl(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PrismControl")
        self.resize(980, 560)

        self.apps = {}
        self.selected_app = None

        self.setup_icons()
        self.load_config()
        self.init_ui()
        self.init_tray()

        self.timer = QTimer()
        self.timer.timeout.connect(self.apply_effects)
        self.timer.start(500)
        
    def set_startup(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PrismControl"
        exe_path = sys.executable

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)

            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass

            winreg.CloseKey(key)
        except:
            pass


    def is_startup_enabled(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PrismControl"

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except:
            return False
        
    def show_toast(self, title, message, icon=QSystemTrayIcon.MessageIcon.Information):
        if hasattr(self, "tray"):
            self.tray.showMessage(title, message, icon, 3000)
            
    def toggle_startup(self):
        enabled = self.is_startup_enabled()
        self.set_startup(not enabled)
        self.update_startup_button()

    def setup_icons(self):
        icon_path = os.path.join(os.path.dirname(__file__), "PrismControl.ico")
        self.app_icon = QIcon(icon_path)
        self.setWindowIcon(self.app_icon)
        return self.app_icon
        
    def update_startup_button(self):
        if self.is_startup_enabled():
            self.startup_btn.setText("Disable Startup")
        else:
            self.startup_btn.setText("Enable Startup")

    def init_ui(self):
        self.root = QWidget()
        self.setCentralWidget(self.root)

        self.main = QHBoxLayout(self.root)

        self.setStyleSheet("""
        QMainWindow { background-color: #121212; }

        QListWidget {
            background-color: #1e1e1e;
            border-radius: 8px;
            padding: 4px;
            color: white;
        }

        QLineEdit {
            background-color: #1e1e1e;
            border-radius: 6px;
            padding: 6px;
            color: white;
        }

        QPushButton {
            background-color: #2a2a2a;
            border-radius: 6px;
            padding: 6px;
            color: white;
        }

        QPushButton:hover {
            background-color: #3a3a3a;
        }

        QSlider::groove:horizontal {
            height: 6px;
            background: #333;
            border-radius: 3px;
        }

        QSlider::handle:horizontal {
            width: 14px;
            background: white;
            margin: -5px 0;
            border-radius: 7px;
        }
        """)

        self.left = QWidget()
        self.left.setFixedWidth(260)
        self.left_layout = QVBoxLayout(self.left)

        title = QLabel("PrismControl")
        self.left_layout.addWidget(title)

        self.process_search = QLineEdit()
        self.process_search.setPlaceholderText("Search processes...")
        self.process_search.textChanged.connect(self.refresh_processes)
        self.left_layout.addWidget(self.process_search)

        self.process_list = QListWidget()
        self.left_layout.addWidget(self.process_list)

        self.add_btn = QPushButton("Add Process")
        self.add_btn.clicked.connect(self.add_app)
        self.left_layout.addWidget(self.add_btn)

        self.main.addWidget(self.left)

        self.right = QWidget()
        self.right_layout = QVBoxLayout(self.right)

        self.app_search = QLineEdit()
        self.app_search.setPlaceholderText("Search added apps...")
        self.app_search.textChanged.connect(self.refresh_apps)
        self.right_layout.addWidget(self.app_search)

        self.app_list = QListWidget()
        self.app_list.itemDoubleClicked.connect(self.select_app)
        self.right_layout.addWidget(self.app_list)

        self.toggle_btn = QPushButton("Toggle ON/OFF")
        self.toggle_btn.clicked.connect(self.toggle_app)
        self.right_layout.addWidget(self.toggle_btn)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 255)
        self.slider.valueChanged.connect(self.update_alpha)

        self.right_layout.addWidget(QLabel("Transparency"))
        self.right_layout.addWidget(self.slider)

        self.remove_btn = QPushButton("Remove App")
        self.remove_btn.clicked.connect(self.remove_app)
        self.right_layout.addWidget(self.remove_btn)

        self.startup_btn = QPushButton()
        self.startup_btn.clicked.connect(self.toggle_startup)

        self.update_startup_button()

        self.right_layout.addWidget(self.startup_btn)

        self.main.addWidget(self.right)

        self.refresh_processes()
        self.refresh_apps()

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.app_icon)

        menu = QMenu()

        show_action = QAction("Show")
        show_action.triggered.connect(self.show_window)

        exit_action = QAction("Exit")
        exit_action.triggered.connect(self.exit_app)

        menu.addAction(show_action)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.setVisible(True)

        self.tray.activated.connect(self.tray_clicked)

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide_to_tray()
            else:
                self.show_window()

    def hide_to_tray(self):
        self.hide()
        self.show_toast("PrismControl", "Running in system tray")

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide_to_tray()

    def exit_app(self):
        self.save_config()
        QApplication.quit()

    def refresh_processes(self):
        self.process_list.clear()

        query = self.process_search.text().lower()
        seen = set()

        for p in psutil.process_iter(['name']):
            name = p.info['name']
            if name:
                name = name.lower()
                if name not in seen and query in name:
                    seen.add(name)
                    self.process_list.addItem(name)

    def add_app(self):
        item = self.process_list.currentItem()
        if not item:
            return

        name = item.text()

        try:
            exe = None
            for p in psutil.process_iter(['name', 'exe']):
                if p.info['name'] and p.info['name'].lower() == name:
                    exe = p.info.get("exe")
                    break

            self.apps[name] = {
                "alpha": 200,
                "enabled": True,
                "icon": exe
            }
        except:
            self.apps[name] = {
                "alpha": 200,
                "enabled": True,
                "icon": ""
            }

        self.refresh_apps()
        self.save_config()

    def refresh_apps(self):
        self.app_list.clear()

        query = self.app_search.text().lower()

        for app, data in self.apps.items():
            if query in app:
                state = "ON" if data["enabled"] else "OFF"
                item = QListWidgetItem(f"{app} | {state} | {data['alpha']}")

                if data.get("icon"):
                    item.setIcon(get_icon(data["icon"]))

                self.app_list.addItem(item)

    def select_app(self, item):
        app = item.text().split("|")[0].strip()
        self.selected_app = app

        if app in self.apps:
            self.slider.setValue(self.apps[app]["alpha"])

    def toggle_app(self):
        if self.selected_app:
            self.apps[self.selected_app]["enabled"] = not self.apps[self.selected_app]["enabled"]
            self.refresh_apps()
            self.save_config()

    def update_alpha(self, value):
        if self.selected_app:
            self.apps[self.selected_app]["alpha"] = value
            self.refresh_apps()
            self.save_config()

    def remove_app(self):
        if self.selected_app and self.selected_app in self.apps:
            del self.apps[self.selected_app]
            self.selected_app = None
            self.refresh_apps()
            self.save_config()

    def apply_effects(self):
        def enum(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                try:
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                    proc = psutil.Process(pid.value).name().lower()

                    if proc in self.apps:
                        data = self.apps[proc]
                        if data["enabled"]:
                            set_transparency(hwnd, data["alpha"])
                        else:
                            set_transparency(hwnd, 255)
                except:
                    pass
            return True

        CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(CALLBACK(enum), 0)

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.apps, f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.apps = json.load(f)


app = QApplication(sys.argv)
window = PrismControl()
window.show()
sys.exit(app.exec())