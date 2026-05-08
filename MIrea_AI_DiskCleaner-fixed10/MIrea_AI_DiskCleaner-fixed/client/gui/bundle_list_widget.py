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

from client.gui.demo_data import get_demo_bundles
from client.gui.theme import refresh_style, set_variant
from client.utils.utils import format_size


class BundleCard(QFrame):
    selected = pyqtSignal(dict)
    open_requested = pyqtSignal(dict)

    def __init__(self, bundle: dict):
        super().__init__()
        self.bundle = bundle
        self.setObjectName("bundleCard")
        self.setProperty("review", bundle["review"])
        self.setProperty("selected", False)
        self.setMinimumHeight(154)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        icon = QLabel("◉" if bundle["review"] else "◎")
        icon.setObjectName("warningBadge" if bundle["review"] else "badge")
        icon.setFixedWidth(48)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        title = QLabel(bundle["name"])
        title.setObjectName("cardTitle")
        subtitle = QLabel(bundle["description"])
        subtitle.setObjectName("mutedText")
        meta = QLabel(
            f"{len(bundle['files'])} файлов  •  {format_size(bundle['total_size_bytes'])}"
        )
        meta.setObjectName("metricLabel")

        info_layout.addWidget(title)
        info_layout.addWidget(subtitle)
        info_layout.addWidget(meta)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)

        self.open_button = QPushButton("Открыть")
        self.open_button.setFixedHeight(48)
        set_variant(self.open_button, "accent")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.bundle))

        self.skip_button = QPushButton("Пропустить")
        self.skip_button.setFixedHeight(44)
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
    open_bundle = pyqtSignal(dict)
    open_settings = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.cards = []
        self.selected_bundle = None
        self.bundles = self.prepare_bundles()

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(32, 28, 32, 28)
        header_layout.setSpacing(8)

        eyebrow = QLabel("BUNDLES")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Список бандлов")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Слева находится список бандлов, справа — живая сводка по выбранному набору. "
            "При открытии дальше передаётся сам bundle, а не пустой сигнал."
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

        for bundle in self.bundles:
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
        right_layout.setSpacing(14)

        panel_title = QLabel("Сводка по выборке")
        panel_title.setObjectName("sectionTitle")

        self.bundle_name = QLabel()
        self.bundle_name.setObjectName("cardTitle")
        self.bundle_subtitle = QLabel()
        self.bundle_subtitle.setObjectName("mutedText")
        self.bundle_stats = QLabel()
        self.bundle_stats.setObjectName("metricLabel")

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(
            ["Файл", "Размер", "Категория", "Confidence"]
        )
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setMinimumHeight(170)
        self.preview_table.setMaximumHeight(220)

        self.open_button = QPushButton("Открыть бандл")
        self.open_button.setFixedHeight(50)
        set_variant(self.open_button, "accent")
        self.open_button.clicked.connect(self.emit_selected_bundle)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setFixedHeight(46)
        set_variant(self.settings_button, "ghost")
        self.settings_button.clicked.connect(self.open_settings.emit)

        self.delete_button = QPushButton("Удалить выбранные бандлы")
        self.delete_button.setFixedHeight(50)
        set_variant(self.delete_button, "danger")
        self.delete_button.clicked.connect(self.show_delete_hint)

        self.summary = QLabel()
        self.summary.setObjectName("mutedText")

        right_layout.addWidget(panel_title)
        right_layout.addWidget(self.bundle_name)
        right_layout.addWidget(self.bundle_subtitle)
        right_layout.addWidget(self.bundle_stats)
        right_layout.addWidget(self.preview_table)
        right_layout.addSpacing(4)
        right_layout.addWidget(self.summary)
        right_layout.addWidget(self.open_button)
        right_layout.addWidget(self.settings_button)
        right_layout.addWidget(self.delete_button)
        right_layout.addStretch()

        content.addWidget(left_panel, 5)
        content.addWidget(right_panel, 4)

        root.addWidget(header)
        root.addLayout(content)

        self.update_summary()
        self.select_bundle(self.bundles[0])

    def prepare_bundles(self) -> list[dict]:
        bundles = get_demo_bundles()
        for bundle in bundles:
            bundle["total_size_bytes"] = sum(file["size_bytes"] for file in bundle["files"])
        return bundles

    def update_summary(self):
        total_files = sum(len(bundle["files"]) for bundle in self.bundles)
        total_size = sum(bundle["total_size_bytes"] for bundle in self.bundles)
        self.summary.setText(
            f"Всего: {len(self.bundles)} бандла, {total_files} файлов, {format_size(total_size)}"
        )

    def select_bundle(self, bundle: dict):
        self.selected_bundle = bundle
        self.bundle_name.setText(bundle["name"])
        self.bundle_subtitle.setText(bundle["description"])
        self.bundle_stats.setText(
            f"{len(bundle['files'])} файлов  •  {format_size(bundle['total_size_bytes'])}"
        )

        for card in self.cards:
            card.set_selected(card.bundle["bundle_id"] == bundle["bundle_id"])

        preview_files = bundle["files"][:3]
        self.preview_table.setRowCount(len(preview_files))
        for row, file_info in enumerate(preview_files):
            self.preview_table.setItem(row, 0, QTableWidgetItem(file_info["filename"]))
            self.preview_table.setItem(row, 1, QTableWidgetItem(format_size(file_info["size_bytes"])))
            self.preview_table.setItem(row, 2, QTableWidgetItem(file_info["category"]))
            confidence_item = QTableWidgetItem(f"{int(file_info['confidence'] * 100)}%")
            confidence_item.setForeground(
                QColor("#44dc8c") if file_info["confidence"] >= 0.9 else QColor("#f0c56f")
            )
            self.preview_table.setItem(row, 3, confidence_item)
        self.preview_table.resizeColumnsToContents()

    def emit_selected_bundle(self):
        if not self.selected_bundle:
            QMessageBox.information(self, "Нет выбора", "Сначала выберите бандл.")
            return
        self.open_bundle.emit(self.selected_bundle)

    def handle_open_bundle(self, bundle: dict):
        self.select_bundle(bundle)
        self.open_bundle.emit(bundle)

    def show_delete_hint(self):
        QMessageBox.information(
            self,
            "Массовое удаление",
            "Кнопка оставлена на экране списка по требованиям app.md. "
            "Реальное удаление будет вызываться после подключения данных и диалога подтверждения."
        )