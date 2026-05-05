from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.theme import refresh_style, set_variant


BUNDLE_FIXTURES = [
    {
        "name": "Review Bundle",
        "age": "Исключённые файлы старше 30 дней",
        "files": 342,
        "size": "2.1 ГБ",
        "review": True,
        "preview": [
            ("draft_notes_2023.docx", "2.4 МБ", "Документы", "92%"),
            ("vacation_2019.mov", "1.8 ГБ", "Видео", "88%"),
            ("setup_old.msi", "45.6 МБ", "Приложения", "91%"),
        ],
    },
    {
        "name": "Март 2024",
        "age": "Файлы старше 12 месяцев",
        "files": 1248,
        "size": "12.4 ГБ",
        "review": False,
        "preview": [
            ("old_report_2021.docx", "2.4 МБ", "Документы", "92%"),
            ("movie_2018.mp4", "1.8 ГБ", "Видео", "90%"),
            ("archive_backup.zip", "512 МБ", "Архивы", "88%"),
        ],
    },
    {
        "name": "Февраль 2024",
        "age": "Файлы старше 13 месяцев",
        "files": 982,
        "size": "8.7 ГБ",
        "review": False,
        "preview": [
            ("legacy_invoice.xlsx", "1.2 МБ", "Документы", "94%"),
            ("music_album_2017.mp3", "112 МБ", "Аудио", "85%"),
            ("unused_iso.iso", "3.1 ГБ", "Другое", "87%"),
        ],
    },
    {
        "name": "Январь 2024",
        "age": "Файлы старше 14 месяцев",
        "files": 756,
        "size": "6.1 ГБ",
        "review": False,
        "preview": [
            ("screenshot_2020.png", "1.1 МБ", "Изображения", "87%"),
            ("installer_old.exe", "78.5 МБ", "Приложения", "94%"),
            ("session_dump.tmp", "1.2 ГБ", "Временные", "95%"),
        ],
    },
]


class BundleCard(QFrame):
    selected = pyqtSignal(dict)
    open_requested = pyqtSignal(dict)

    def __init__(self, bundle: dict):
        super().__init__()
        self.bundle = bundle
        self.setObjectName("bundleCard")
        self.setProperty("review", bundle["review"])
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        icon = QLabel("◉" if bundle["review"] else "◎")
        icon.setObjectName("warningBadge" if bundle["review"] else "badge")

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        title = QLabel(bundle["name"])
        title.setObjectName("cardTitle")
        subtitle = QLabel(bundle["age"])
        subtitle.setObjectName("mutedText")
        meta = QLabel(f"{bundle['files']} файлов  •  {bundle['size']}")
        meta.setObjectName("metricLabel")

        info_layout.addWidget(title)
        info_layout.addWidget(subtitle)
        info_layout.addWidget(meta)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)

        self.open_button = QPushButton("Открыть")
        set_variant(self.open_button, "accent")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.bundle))

        self.skip_button = QPushButton("Пропустить")
        set_variant(self.skip_button, "warning" if bundle["review"] else "ghost")
        self.skip_button.clicked.connect(self.show_skip_hint)

        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.skip_button)
        button_layout.addStretch()

        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(info_layout, 1)
        layout.addLayout(button_layout)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        refresh_style(self)

    def mousePressEvent(self, event):
        self.selected.emit(self.bundle)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.open_requested.emit(self.bundle)
        super().mouseDoubleClickEvent(event)

    def show_skip_hint(self):
        title = "Review bundle" if self.bundle["review"] else "Пропуск"
        text = (
            "В review-бандле файл можно будет пометить как `protected`, "
            "в обычных бандлах — как `skip`."
            if self.bundle["review"]
            else "Маркер пропуска будет привязан к файлам после подключения реальных данных."
        )
        QMessageBox.information(self, title, text)


class BundleListScreen(QWidget):
    open_bundle = pyqtSignal()
    open_settings = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.cards = []
        self.selected_bundle = None

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(6)

        eyebrow = QLabel("Bundles")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Список бандлов")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Экран визуально приближен к референсу: слева список периодов, справа "
            "краткая сводка по выбранному бандлу. При этом `BundleDetailScreen` остаётся "
            "отдельным шагом навигации, как требует app.md."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        header_layout.addWidget(eyebrow)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        content = QHBoxLayout()
        content.setSpacing(18)

        left_panel = QFrame()
        left_panel.setObjectName("contentCard")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(24, 24, 24, 24)
        left_layout.setSpacing(16)

        left_title_row = QHBoxLayout()
        left_title = QLabel("Бандлы к просмотру")
        left_title.setObjectName("sectionTitle")
        left_hint = QLabel("Review-бандл всегда отображается первым.")
        left_hint.setObjectName("warningBadge")
        left_title_row.addWidget(left_title)
        left_title_row.addStretch()
        left_title_row.addWidget(left_hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(14)

        for bundle in BUNDLE_FIXTURES:
            card = BundleCard(bundle)
            card.selected.connect(self.select_bundle)
            card.open_requested.connect(self.handle_open_bundle)
            self.cards.append(card)
            container_layout.addWidget(card)
        container_layout.addStretch()
        scroll.setWidget(container)

        left_layout.addLayout(left_title_row)
        left_layout.addWidget(scroll)

        right_panel = QFrame()
        right_panel.setObjectName("sidePanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 24, 24, 24)
        right_layout.setSpacing(16)

        panel_title = QLabel("Сводка по выборке")
        panel_title.setObjectName("sectionTitle")

        self.bundle_name = QLabel()
        self.bundle_name.setObjectName("cardTitle")
        self.bundle_subtitle = QLabel()
        self.bundle_subtitle.setObjectName("mutedText")
        self.bundle_stats = QLabel()
        self.bundle_stats.setObjectName("metricLabel")

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(["Файл", "Размер", "Категория", "Confidence"])
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setMinimumHeight(250)

        self.open_button = QPushButton("Открыть бандл")
        set_variant(self.open_button, "accent")
        self.open_button.clicked.connect(self.open_bundle.emit)

        self.settings_button = QPushButton("Настройки")
        set_variant(self.settings_button, "ghost")
        self.settings_button.clicked.connect(self.open_settings.emit)

        self.delete_button = QPushButton("Удалить выбранные бандлы")
        set_variant(self.delete_button, "danger")
        self.delete_button.clicked.connect(self.show_delete_hint)

        summary = QLabel("Всего: 4 бандла, 3 328 файлов, 29.3 ГБ")
        summary.setObjectName("mutedText")

        right_layout.addWidget(panel_title)
        right_layout.addWidget(self.bundle_name)
        right_layout.addWidget(self.bundle_subtitle)
        right_layout.addWidget(self.bundle_stats)
        right_layout.addWidget(self.preview_table)
        right_layout.addStretch()
        right_layout.addWidget(summary)
        right_layout.addWidget(self.open_button)
        right_layout.addWidget(self.settings_button)
        right_layout.addWidget(self.delete_button)

        content.addWidget(left_panel, 5)
        content.addWidget(right_panel, 4)

        root.addWidget(header)
        root.addLayout(content)

        self.select_bundle(BUNDLE_FIXTURES[0])

    def select_bundle(self, bundle: dict):
        self.selected_bundle = bundle
        self.bundle_name.setText(bundle["name"])
        self.bundle_subtitle.setText(bundle["age"])
        self.bundle_stats.setText(f"{bundle['files']} файлов  •  {bundle['size']}  •  confidence ready")

        for card in self.cards:
            card.set_selected(card.bundle["name"] == bundle["name"])

        self.preview_table.setRowCount(len(bundle["preview"]))
        for row, (filename, size, category, confidence) in enumerate(bundle["preview"]):
            self.preview_table.setItem(row, 0, QTableWidgetItem(filename))
            self.preview_table.setItem(row, 1, QTableWidgetItem(size))
            category_item = QTableWidgetItem(category)
            confidence_item = QTableWidgetItem(confidence)
            confidence_item.setForeground(QColor("#52d58a") if int(confidence[:-1]) >= 90 else QColor("#f4b74b"))
            self.preview_table.setItem(row, 2, category_item)
            self.preview_table.setItem(row, 3, confidence_item)
        self.preview_table.resizeColumnsToContents()

    def handle_open_bundle(self, bundle: dict):
        self.select_bundle(bundle)
        self.open_bundle.emit()

    def show_delete_hint(self):
        QMessageBox.information(
            self,
            "Массовое удаление",
            "Кнопка оставлена на экране списка по требованиям app.md. "
            "Реальное удаление будет вызываться после подключения данных и диалога подтверждения."
        )
