import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client.gui.scan_progress import load_scan_filter_settings
from client.scanner.disk_detector import get_available_disks
from client.gui.theme import set_variant
from client.utils.formatters import format_size


FALLBACK_DISKS = [
    {
        "name": "C:\\",
        "label": "Системный диск",
        "meta": "NTFS • занято 312 ГБ из 476 ГБ",
    },
    {
        "name": "D:\\",
        "label": "Архив и проекты",
        "meta": "NTFS • занято 1.2 ТБ из 2 ТБ",
    },
    {
        "name": "E:\\",
        "label": "Медиа и бэкапы",
        "meta": "exFAT • занято 428 ГБ из 931 ГБ",
    },
]


def build_disk_options(disks: list[dict]) -> list[dict]:
    return [
        {
            "name": disk["mountpoint"],
            "label": disk.get("device") or disk["mountpoint"],
            "meta": (
                f"{disk.get('fstype', 'unknown')} • занято "
                f"{format_size(int(disk.get('used_bytes', 0)))} из "
                f"{format_size(int(disk.get('total_bytes', 0)))}"
            ),
        }
        for disk in disks
    ]


class DiskSelectScreen(QWidget):
    scan_requested = pyqtSignal(list)
    open_settings = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.disk_checks = []
        self.disk_paths = set()
        self.selected_disks: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(6)

        eyebrow = QLabel("Старт")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Что сканируем?")
        title.setObjectName("pageTitle")
        info = QLabel(
            "Выберите диск или отдельную папку для быстрой демонстрации. "
            "Файлы проверяются локально, на сервер отправляется только краткое описание."
        )
        info.setObjectName("subtitle")
        info.setWordWrap(True)

        header_layout.addWidget(eyebrow)
        header_layout.addWidget(title)
        header_layout.addWidget(info)

        content = QHBoxLayout()
        content.setSpacing(18)

        disks_card = QFrame()
        disks_card.setObjectName("contentCard")
        disks_layout = QVBoxLayout(disks_card)
        disks_layout.setContentsMargins(24, 24, 24, 24)
        disks_layout.setSpacing(18)

        disks_title = QLabel("Доступные диски")
        disks_title.setObjectName("sectionTitle")
        disks_hint = QLabel("Отметьте диски или папки, которые нужно просканировать.")
        disks_hint.setObjectName("mutedText")

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)

        for disk in self._load_disk_options():
            self._add_scan_option(
                disk["name"],
                disk["label"],
                disk["meta"],
                checked=False,
            )

        disks_layout.addWidget(disks_title)
        disks_layout.addWidget(disks_hint)
        disks_layout.addLayout(self.grid)
        disks_layout.addStretch()

        control_card = QFrame()
        control_card.setObjectName("sidePanel")
        control_layout = QVBoxLayout(control_card)
        control_layout.setContentsMargins(24, 24, 24, 24)
        control_layout.setSpacing(16)

        control_title = QLabel("Параметры запуска")
        control_title.setObjectName("sectionTitle")

        self.selected_metric = QLabel()
        self.selected_metric.setObjectName("metricValue")
        self.selection_label = QLabel()
        self.selection_label.setObjectName("metricLabel")

        self.age_badge = QLabel()
        self.age_badge.setObjectName("badge")
        self.size_badge = QLabel()
        self.size_badge.setObjectName("badge")
        self.refresh_filter_badges()

        safety_note = QLabel(
            "Для защиты удобно выбрать заранее подготовленную папку: сканирование "
            "будет быстрым, а результат останется наглядным."
        )
        safety_note.setObjectName("mutedText")
        safety_note.setWordWrap(True)

        self.settings_button = QPushButton("Настройки сканирования")
        set_variant(self.settings_button, "ghost")
        self.settings_button.clicked.connect(self.open_settings.emit)

        self.scan_button = QPushButton("Запустить сканирование")
        set_variant(self.scan_button, "accent")
        self.scan_button.clicked.connect(self.handle_scan_request)

        self.folder_button = QPushButton("Выбрать папку для демо")
        set_variant(self.folder_button, "ghost")
        self.folder_button.clicked.connect(self.choose_custom_folder)

        control_layout.addWidget(control_title)
        control_layout.addWidget(self.selected_metric)
        control_layout.addWidget(self.selection_label)
        control_layout.addSpacing(8)
        control_layout.addWidget(self.age_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        control_layout.addWidget(self.size_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        control_layout.addStretch()
        control_layout.addWidget(safety_note)
        control_layout.addWidget(self.folder_button)
        control_layout.addWidget(self.settings_button)
        control_layout.addWidget(self.scan_button)

        content.addWidget(disks_card, 5)
        content.addWidget(control_card, 3)

        footer = QLabel(
            "Совет для показа: используйте отдельную demo-папку на 250-300 файлов, "
            "чтобы не ждать полный обход диска."
        )
        footer.setObjectName("mutedText")
        footer.setWordWrap(True)

        root.addWidget(header)
        root.addLayout(content)
        root.addWidget(footer)

        self.update_selection_state()

    def update_selection_state(self, *_):
        self.selected_disks = [checkbox.text() for checkbox in self.disk_checks if checkbox.isChecked()]
        self.selected_metric.setText(str(len(self.selected_disks)))
        self.selection_label.setText("выбрано объектов")
        self.scan_button.setEnabled(bool(self.selected_disks))

    def refresh_filter_badges(self) -> None:
        min_age_months, min_size_bytes = load_scan_filter_settings()
        self.age_badge.setText(f"Старше {_format_months(min_age_months)}")
        self.size_badge.setText(f"Больше {format_size(min_size_bytes)}")

    def handle_scan_request(self):
        if not self.selected_disks:
            QMessageBox.warning(self, "Нет выбора", "Выберите хотя бы один диск для сканирования.")
            return
        self.scan_requested.emit(list(self.selected_disks))

    def choose_custom_folder(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сканирования",
        )
        if path:
            self.add_custom_scan_path(path)

    def add_custom_scan_path(self, path: str) -> None:
        cleaned = path.strip()
        if not cleaned:
            return
        normalized = os.path.normpath(cleaned)
        key = os.path.normcase(normalized)
        if key in self.disk_paths:
            self._select_only_path(normalized)
            self.update_selection_state()
            return
        self._clear_selected_paths()
        self._add_scan_option(
            normalized,
            "Выбранная папка",
            "Быстрый демонстрационный сценарий",
            checked=True,
        )
        self.update_selection_state()

    def _add_scan_option(
        self,
        path: str,
        label: str,
        meta: str,
        *,
        checked: bool,
    ) -> None:
        key = os.path.normcase(os.path.normpath(path.strip()))
        self.disk_paths.add(key)
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        checkbox = QCheckBox(path)
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(self.update_selection_state)

        label_widget = QLabel(label)
        label_widget.setObjectName("cardTitle")

        meta_widget = QLabel(meta)
        meta_widget.setObjectName("mutedText")
        meta_widget.setWordWrap(True)

        badge = QLabel("Готово")
        badge.setObjectName("successBadge")

        card_layout.addWidget(checkbox)
        card_layout.addWidget(label_widget)
        card_layout.addWidget(meta_widget)
        card_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)

        self.disk_checks.append(checkbox)
        index = len(self.disk_checks) - 1
        self.grid.addWidget(card, index // 2, index % 2)

    def _clear_selected_paths(self) -> None:
        for checkbox in self.disk_checks:
            checkbox.setChecked(False)

    def _select_only_path(self, path: str) -> None:
        target = os.path.normcase(os.path.normpath(path.strip()))
        for checkbox in self.disk_checks:
            checkbox_path = os.path.normcase(os.path.normpath(checkbox.text().strip()))
            checkbox.setChecked(checkbox_path == target)

    @staticmethod
    def _load_disk_options() -> list[dict]:
        detected = build_disk_options(get_available_disks())
        return detected or FALLBACK_DISKS


def _format_months(months: int) -> str:
    if months % 10 == 1 and months % 100 != 11:
        word = "месяца"
    elif months % 10 in {2, 3, 4} and months % 100 not in {12, 13, 14}:
        word = "месяцев"
    else:
        word = "месяцев"
    return f"{months} {word}"
