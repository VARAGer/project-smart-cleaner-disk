from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from client.api_client import SmartCleanerApiClient
from client.gui.bundle_detail_widget import BundleDetailScreen
from client.gui.bundle_list_widget import BundleListScreen
from client.gui.disk_selector import DiskSelectScreen
from client.gui.login_window import LoginScreen
from client.gui.scan_progress import ScanProgressScreen
from client.gui.settings_widget import SettingsScreen
from client.gui.theme_manager import ThemeManager
from client.pipeline.analysis_pipeline import build_bundles_from_database


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SmartCleaner")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

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

        self.api_client = SmartCleanerApiClient()
        self.login_screen = LoginScreen(self.api_client)
        self.disk_screen = DiskSelectScreen()
        self.scan_screen = ScanProgressScreen(self.api_client)
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
        self.disk_screen.scan_requested.connect(self.start_scan)
        self.disk_screen.open_settings.connect(self.show_settings_screen)
        self.scan_screen.scan_finished.connect(self.show_bundle_list_screen)
        self.scan_screen.back_requested.connect(self.show_disk_screen)
        self.bundle_list_screen.open_settings.connect(self.show_settings_screen)
        self.bundle_list_screen.open_bundle.connect(self.show_bundle_detail_screen)
        self.bundle_list_screen.back_requested.connect(self.show_disk_screen)
        self.bundle_list_screen.all_bundles_resolved.connect(self.show_disk_screen)
        self.bundle_detail_screen.back_requested.connect(self.return_to_bundle_list)
        self.bundle_detail_screen.bundle_resolved.connect(self.handle_detail_bundle_resolved)
        self.settings_screen.back_requested.connect(self.restore_previous_screen)
        self.settings_screen.theme_changed.connect(lambda theme_name: self.theme_manager.set_theme(theme_name, animate=True))

        self.current_theme = self.settings_screen.get_selected_theme()
        self.previous_screen = None
        self.last_scan_targets: list[str] = []
        self.last_bundle_signature: tuple | None = None
        self.bundle_refresh_timer = QTimer(self)
        self.bundle_refresh_timer.setInterval(10_000)
        self.bundle_refresh_timer.timeout.connect(self.refresh_bundle_list_from_database)
        self.bundle_refresh_timer.start()
        self.stack.setCurrentWidget(self.login_screen)
        self.theme_manager.set_theme(self.current_theme, animate=False)

    def apply_theme(self, theme_name: str):
        self.theme_manager.set_theme(theme_name, animate=True)

    def handle_theme_applied(self, theme_name: str):
        self.current_theme = theme_name
        self.settings_screen.set_current_theme(theme_name)
        self.login_screen.set_current_theme(theme_name)

    def show_disk_screen(self):
        self.disk_screen.refresh_filter_badges()
        self.stack.setCurrentWidget(self.disk_screen)

    def start_scan(self, selected_disks: list[str]):
        if not self.scan_screen.start_scan(selected_disks):
            self.stack.setCurrentWidget(self.scan_screen)
            return
        self.last_scan_targets = list(selected_disks)
        self.bundle_list_screen.set_allowed_roots(self.last_scan_targets)
        self.bundle_detail_screen.set_allowed_roots(self.last_scan_targets)
        self.stack.setCurrentWidget(self.scan_screen)

    def show_bundle_list_screen(self, bundles: list[dict] | None = None):
        if bundles is not None:
            self.last_bundle_signature = self._bundle_signature(bundles)
            self.bundle_list_screen.set_allowed_roots(self.last_scan_targets)
            self.bundle_list_screen.set_bundles(bundles)
        self.stack.setCurrentWidget(self.bundle_list_screen)

    def show_bundle_detail_screen(self, bundle: dict):
        self.bundle_detail_screen.set_allowed_roots(self.last_scan_targets)
        self.bundle_detail_screen.set_bundle(bundle)
        self.stack.setCurrentWidget(self.bundle_detail_screen)

    def return_to_bundle_list(self):
        self.reload_bundle_list_from_database()
        self.stack.setCurrentWidget(self.bundle_list_screen)

    def show_settings_screen(self):
        current = self.stack.currentWidget()
        if current is not self.settings_screen:
            self.previous_screen = current
        self.stack.setCurrentWidget(self.settings_screen)

    def refresh_bundle_list_from_database(self):
        if self.stack.currentWidget() is self.disk_screen:
            self.show_expired_review_bundles_if_any()
            return
        if self.stack.currentWidget() is not self.bundle_list_screen:
            return
        self.reload_bundle_list_from_database()

    def reload_bundle_list_from_database(self):
        if not self.last_scan_targets:
            return []
        bundles = build_bundles_from_database(disk_labels=self.last_scan_targets)
        signature = self._bundle_signature(bundles)
        if signature == self.last_bundle_signature:
            return bundles
        self.last_bundle_signature = signature
        self.bundle_list_screen.set_bundles(bundles)
        return bundles

    def handle_detail_bundle_resolved(self):
        bundles = self.reload_bundle_list_from_database()
        if bundles:
            self.stack.setCurrentWidget(self.bundle_list_screen)
            return
        self.show_disk_screen()

    def show_expired_review_bundles_if_any(self):
        if not self.last_scan_targets:
            return
        bundles = build_bundles_from_database(disk_labels=self.last_scan_targets)
        if not bundles:
            return
        signature = self._bundle_signature(bundles)
        if signature == self.last_bundle_signature:
            return
        self.last_bundle_signature = signature
        self.bundle_list_screen.set_allowed_roots(self.last_scan_targets)
        self.bundle_list_screen.set_bundles(bundles)
        self.stack.setCurrentWidget(self.bundle_list_screen)

    @staticmethod
    def _bundle_signature(bundles: list[dict]) -> tuple:
        return tuple(
            (
                bundle.get("bundle_id", ""),
                tuple(file_info.get("file_id", "") for file_info in bundle.get("files", [])),
            )
            for bundle in bundles
        )

    def restore_previous_screen(self):
        if self.previous_screen is not None and self.previous_screen is not self.settings_screen:
            self.stack.setCurrentWidget(self.previous_screen)
            return
        self.stack.setCurrentWidget(self.disk_screen)

    def closeEvent(self, event):
        self.api_client.close()
        super().closeEvent(event)
