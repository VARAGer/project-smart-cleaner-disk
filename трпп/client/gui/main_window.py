from PyQt6.QtWidgets import QApplication, QFrame, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from gui.bundle_detail_widget import BundleDetailScreen
from gui.bundle_list_widget import BundleListScreen
from gui.disk_selector import DiskSelectScreen
from gui.login_window import LoginScreen
from gui.scan_progress import ScanProgressScreen
from gui.settings_widget import SettingsScreen
from gui.theme import build_stylesheet


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SmartCleaner")
        self.resize(1440, 920)
        self.setMinimumSize(1240, 820)
        self.current_theme = "dark"

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

        self.login_screen.login_successful.connect(self.show_disk_screen)
        self.disk_screen.scan_requested.connect(self.show_scan_screen)
        self.scan_screen.scan_finished.connect(self.show_bundle_list_screen)
        self.bundle_list_screen.open_settings.connect(self.show_settings_screen)
        self.bundle_list_screen.open_bundle.connect(self.show_bundle_detail_screen)
        self.bundle_detail_screen.back_requested.connect(self.show_bundle_list_screen)
        self.settings_screen.back_requested.connect(self.show_bundle_list_screen)
        self.settings_screen.theme_changed.connect(self.apply_theme)

        self.stack.setCurrentWidget(self.login_screen)
        self.apply_theme(self.current_theme)

    def apply_theme(self, theme_name: str):
        self.current_theme = theme_name
        QApplication.instance().setStyleSheet(build_stylesheet(theme_name))
        self.settings_screen.set_current_theme(theme_name)

    def show_disk_screen(self):
        self.stack.setCurrentWidget(self.disk_screen)

    def show_scan_screen(self):
        self.stack.setCurrentWidget(self.scan_screen)

    def show_bundle_list_screen(self):
        self.stack.setCurrentWidget(self.bundle_list_screen)

    def show_bundle_detail_screen(self):
        self.stack.setCurrentWidget(self.bundle_detail_screen)

    def show_settings_screen(self):
        self.stack.setCurrentWidget(self.settings_screen)
