from PyQt6.QtWidgets import QFrame, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from client.gui.bundle_detail_widget import BundleDetailScreen
from client.gui.bundle_list_widget import BundleListScreen
from client.gui.disk_selector import DiskSelectScreen
from client.gui.login_window import LoginScreen
from client.gui.scan_progress import ScanProgressScreen
from client.gui.settings_widget import SettingsScreen
from client.gui.theme_manager import ThemeManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SmartCleaner")
        self.resize(1440, 920)
        self.setMinimumSize(1240, 820)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)

        shell = QFrame()
        shell.setObjectName("shell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        shell_layout.addWidget(self.stack)
        root_layout.addWidget(shell)

        self.login_screen = LoginScreen()
        self.disk_screen = DiskSelectScreen()
        self.scan_screen = ScanProgressScreen()
        self.bundle_list_screen = BundleListScreen()
        self.bundle_detail_screen = BundleDetailScreen()
        self.settings_screen = SettingsScreen()

        self.stack.addWidget(self.login_screen)
        self.stack.addWidget(self.disk_screen)
        self.stack.addWidget(self.scan_screen)
        self.stack.addWidget(self.bundle_list_screen)
        self.stack.addWidget(self.bundle_detail_screen)
        self.stack.addWidget(self.settings_screen)

        self.theme_manager = ThemeManager(root, self.settings_screen.get_selected_theme())
        self.theme_manager.theme_applied.connect(self.handle_theme_applied)

        self.login_screen.login_successful.connect(self.show_disk_screen)
        self.login_screen.theme_requested.connect(lambda theme_name: self.theme_manager.set_theme(theme_name, animate=True))
        self.disk_screen.scan_requested.connect(self.show_scan_screen)
        self.disk_screen.open_settings.connect(self.show_settings_screen)
        self.scan_screen.scan_finished.connect(self.show_bundle_list_screen)
        self.bundle_list_screen.open_settings.connect(self.show_settings_screen)
        self.bundle_list_screen.open_bundle.connect(self.show_bundle_detail_screen)
        self.bundle_detail_screen.back_requested.connect(self.show_bundle_list_screen)
        self.settings_screen.back_requested.connect(self.restore_previous_screen)
        self.settings_screen.theme_changed.connect(lambda theme_name: self.theme_manager.set_theme(theme_name, animate=True))

        self.current_theme = self.settings_screen.get_selected_theme()
        self.previous_screen = None
        self.stack.setCurrentWidget(self.login_screen)
        self.theme_manager.set_theme(self.current_theme, animate=False)

    def apply_theme(self, theme_name: str):
        self.theme_manager.set_theme(theme_name, animate=True)

    def handle_theme_applied(self, theme_name: str):
        self.current_theme = theme_name
        self.settings_screen.set_current_theme(theme_name)
        self.login_screen.set_current_theme(theme_name, animate_toggle=False)

    def show_disk_screen(self):
        self.stack.setCurrentWidget(self.disk_screen)

    def show_scan_screen(self):
        self.stack.setCurrentWidget(self.scan_screen)

    def show_bundle_list_screen(self):
        self.stack.setCurrentWidget(self.bundle_list_screen)

    def show_bundle_detail_screen(self, bundle: dict):
        self.bundle_detail_screen.set_bundle(bundle)
        self.stack.setCurrentWidget(self.bundle_detail_screen)

    def show_settings_screen(self):
        current = self.stack.currentWidget()
        if current is not self.settings_screen:
            self.previous_screen = current
        self.stack.setCurrentWidget(self.settings_screen)

    def restore_previous_screen(self):
        if self.previous_screen is not None and self.previous_screen is not self.settings_screen:
            self.stack.setCurrentWidget(self.previous_screen)
            return
        self.stack.setCurrentWidget(self.disk_screen)
