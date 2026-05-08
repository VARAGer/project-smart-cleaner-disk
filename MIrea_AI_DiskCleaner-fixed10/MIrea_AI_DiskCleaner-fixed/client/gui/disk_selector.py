from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client.gui.theme import set_variant


DISK_FIXTURES = [
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


class DiskSelectScreen(QWidget):
    scan_requested = pyqtSignal()
    open_settings = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.disk_checks = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(6)

        eyebrow = QLabel("Disk Select")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Выбор дисков")
        title.setObjectName("pageTitle")
        info = QLabel(
            "Экран оставлен в роли `DiskSelectScreen` из app.md: позже сюда "
            "подключится реальный список дисков через `psutil`, а пока дизайн "
            "уже подготовлен под карточки и массовый запуск сканирования."
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
        disks_hint = QLabel("Отметьте тома, которые нужно просканировать.")
        disks_hint.setObjectName("mutedText")

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        for index, disk in enumerate(DISK_FIXTURES):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 18, 18, 18)
            card_layout.setSpacing(10)

            checkbox = QCheckBox(disk["name"])
            checkbox.setChecked(index < 2)
            checkbox.stateChanged.connect(self.update_selection_state)

            label = QLabel(disk["label"])
            label.setObjectName("cardTitle")

            meta = QLabel(disk["meta"])
            meta.setObjectName("mutedText")
            meta.setWordWrap(True)

            badge = QLabel("Готов к анализу")
            badge.setObjectName("successBadge")

            card_layout.addWidget(checkbox)
            card_layout.addWidget(label)
            card_layout.addWidget(meta)
            card_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)

            self.disk_checks.append(checkbox)
            grid.addWidget(card, index // 2, index % 2)

        disks_layout.addWidget(disks_title)
        disks_layout.addWidget(disks_hint)
        disks_layout.addLayout(grid)
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

        age_badge = QLabel("Мин. возраст: 6 месяцев")
        age_badge.setObjectName("badge")
        size_badge = QLabel("Мин. размер: 1 КБ")
        size_badge.setObjectName("badge")

        safety_note = QLabel(
            "Системные каталоги и расширения из `SKIP_DIRS`/`SYSTEM_EXTENSIONS` "
            "будут отфильтрованы на клиенте до любого обращения к backend."
        )
        safety_note.setObjectName("mutedText")
        safety_note.setWordWrap(True)

        self.settings_button = QPushButton("Настройки сканирования")
        set_variant(self.settings_button, "ghost")
        self.settings_button.clicked.connect(self.open_settings.emit)

        self.scan_button = QPushButton("Запустить сканирование")
        set_variant(self.scan_button, "accent")
        self.scan_button.clicked.connect(self.handle_scan_request)

        preview_button = QPushButton("Показать план анализа")
        set_variant(preview_button, "ghost")
        preview_button.clicked.connect(self.show_plan_hint)

        control_layout.addWidget(control_title)
        control_layout.addWidget(self.selected_metric)
        control_layout.addWidget(self.selection_label)
        control_layout.addSpacing(8)
        control_layout.addWidget(age_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        control_layout.addWidget(size_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        control_layout.addStretch()
        control_layout.addWidget(safety_note)
        control_layout.addWidget(preview_button)
        control_layout.addWidget(self.settings_button)
        control_layout.addWidget(self.scan_button)

        content.addWidget(disks_card, 5)
        content.addWidget(control_card, 3)

        footer = QLabel(
            "Дизайн соответствует структуре проекта: этот экран только подготавливает "
            "выбор дисков и переход к `ScanProgressScreen`, не смешивая его с логикой анализа."
        )
        footer.setObjectName("mutedText")
        footer.setWordWrap(True)

        root.addWidget(header)
        root.addLayout(content)
        root.addWidget(footer)

        self.update_selection_state()

    def update_selection_state(self):
        selected = [checkbox.text() for checkbox in self.disk_checks if checkbox.isChecked()]
        self.selected_metric.setText(str(len(selected)))
        self.selection_label.setText("выбрано дисков")
        self.scan_button.setEnabled(bool(selected))

    def handle_scan_request(self):
        if not any(checkbox.isChecked() for checkbox in self.disk_checks):
            QMessageBox.warning(self, "Нет выбора", "Выберите хотя бы один диск для сканирования.")
            return
        self.scan_requested.emit()

    def show_plan_hint(self):
        QMessageBox.information(
            self,
            "План анализа",
            "После выбора дисков приложение выполнит локальное сканирование, применит фильтры и только затем разобьёт кандидатов на батчи для backend."
        )
