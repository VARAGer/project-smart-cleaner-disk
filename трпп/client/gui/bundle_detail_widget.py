from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.theme import set_variant


FILE_FIXTURES = [
    {
        "filename": "old_report_2021.docx",
        "size": "2.4 МБ",
        "category": "Документы",
        "confidence": 0.92,
        "reason": "Старый документ, не открывался давно",
    },
    {
        "filename": "vacation_photo_2019.jpg",
        "size": "4.1 МБ",
        "category": "Изображения",
        "confidence": 0.89,
        "reason": "Старое изображение вне активных каталогов",
    },
    {
        "filename": "installer_old.exe",
        "size": "78.5 МБ",
        "category": "Приложения",
        "confidence": 0.94,
        "reason": "Старый установщик, не запускался длительное время",
    },
    {
        "filename": "movie_2018.mp4",
        "size": "1.8 ГБ",
        "category": "Видео",
        "confidence": 0.90,
        "reason": "Большой медиафайл с низкой активностью",
    },
    {
        "filename": "project_notes_current.txt",
        "size": "32 КБ",
        "category": "Документы",
        "confidence": 0.38,
        "reason": "Низкая уверенность, файл может быть актуальным",
    },
]


class BundleDetailScreen(QWidget):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.checkboxes = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(10)

        eyebrow = QLabel("Bundle Detail")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Содержимое бандла")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Таблица ниже уже отражает структуру из app.md: чекбокс выбора, размер, "
            "категория, confidence и причина. Low-confidence файл снят по умолчанию."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        badges = QHBoxLayout()
        for text in ("Март 2024", "1 248 файлов", "12.4 ГБ"):
            label = QLabel(text)
            label.setObjectName("badge")
            badges.addWidget(label)
        badges.addStretch()

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(badges)

        actions = QHBoxLayout()
        self.back_button = QPushButton("Назад")
        self.back_button.clicked.connect(self.back_requested.emit)
        set_variant(self.back_button, "ghost")

        self.open_button = QPushButton("Открыть файл")
        set_variant(self.open_button, "ghost")
        self.open_button.clicked.connect(self.show_open_hint)

        self.skip_button = QPushButton("Не удалять")
        set_variant(self.skip_button, "warning")
        self.skip_button.clicked.connect(self.mark_selected_as_skipped)

        self.delete_button = QPushButton("Удалить выбранные")
        set_variant(self.delete_button, "danger")
        self.delete_button.clicked.connect(self.confirm_delete)

        actions.addWidget(self.back_button)
        actions.addStretch()
        actions.addWidget(self.open_button)
        actions.addWidget(self.skip_button)
        actions.addWidget(self.delete_button)

        metrics_layout = QGridLayout()
        metrics_layout.setHorizontalSpacing(12)
        metrics_layout.setVerticalSpacing(12)
        for index, (value, label, badge_name) in enumerate(
            (
                ("4", "Готовы к удалению", "successBadge"),
                ("1", "Низкая уверенность", "warningBadge"),
                ("2.27 ГБ", "Выбрано сейчас", "badge"),
            )
        ):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            metric = QLabel(value)
            metric.setObjectName("metricValue")
            label_widget = QLabel(label)
            label_widget.setObjectName("metricLabel")
            pill = QLabel(label)
            pill.setObjectName(badge_name)
            card_layout.addWidget(metric)
            card_layout.addWidget(label_widget)
            card_layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignLeft)
            metrics_layout.addWidget(card, 0, index)

        table_card = QFrame()
        table_card.setObjectName("contentCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 20, 20, 20)
        table_layout.setSpacing(14)

        table_title = QLabel("Файлы внутри бандла")
        table_title.setObjectName("sectionTitle")

        self.table = QTableWidget(len(FILE_FIXTURES), 6)
        self.table.setHorizontalHeaderLabels(
            ["☑", "Имя файла", "Размер", "Категория", "Уверенность", "Причина"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(420)

        table_layout.addWidget(table_title)
        table_layout.addWidget(self.table)

        root.addWidget(hero)
        root.addLayout(actions)
        root.addLayout(metrics_layout)
        root.addWidget(table_card)

        self.populate_table()

    def populate_table(self):
        self.checkboxes.clear()
        for row, file_info in enumerate(FILE_FIXTURES):
            checkbox = QCheckBox()
            checkbox.setChecked(file_info["confidence"] >= 0.5)
            checkbox.stateChanged.connect(self.update_delete_summary)
            self.checkboxes.append((checkbox, file_info))
            self.table.setCellWidget(row, 0, checkbox)

            self.table.setItem(row, 1, QTableWidgetItem(file_info["filename"]))
            self.table.setItem(row, 2, QTableWidgetItem(file_info["size"]))

            category_item = QTableWidgetItem(file_info["category"])
            category_item.setForeground(self.category_color(file_info["category"]))
            self.table.setItem(row, 3, category_item)

            confidence_item = QTableWidgetItem(f"{int(file_info['confidence'] * 100)}%")
            confidence_item.setForeground(self.confidence_color(file_info["confidence"]))
            self.table.setItem(row, 4, confidence_item)

            self.table.setItem(row, 5, QTableWidgetItem(file_info["reason"]))

        self.table.selectRow(0)
        self.table.resizeRowsToContents()
        self.update_delete_summary()

    def category_color(self, category: str) -> QColor:
        mapping = {
            "Документы": QColor("#3a7cff"),
            "Изображения": QColor("#0ea5b7"),
            "Приложения": QColor("#8b5cf6"),
            "Видео": QColor("#f59e0b"),
        }
        return mapping.get(category, QColor("#9ca3af"))

    def confidence_color(self, confidence: float) -> QColor:
        if confidence >= 0.85:
            return QColor("#52d58a")
        if confidence >= 0.5:
            return QColor("#f4b74b")
        return QColor("#ff6c71")

    def selected_file(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return FILE_FIXTURES[row]

    def mark_selected_as_skipped(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Нет выбора", "Выберите строку в таблице.")
            return
        checkbox, file_info = self.checkboxes[row]
        checkbox.setChecked(False)
        QMessageBox.information(
            self,
            "Маркер сохранён",
            f"Файл `{file_info['filename']}` помечен как исключённый из удаления."
        )

    def show_open_hint(self):
        file_info = self.selected_file()
        if not file_info:
            QMessageBox.information(self, "Нет выбора", "Выберите файл в таблице.")
            return
        QMessageBox.information(
            self,
            "Открытие файла",
            f"Здесь будет вызов `open_file()` для `{file_info['filename']}` после подключения реальных путей."
        )

    def update_delete_summary(self):
        selected_count = sum(1 for checkbox, _ in self.checkboxes if checkbox.isChecked())
        self.delete_button.setText(f"Удалить выбранные ({selected_count})")

    def confirm_delete(self):
        selected_files = [file_info for checkbox, file_info in self.checkboxes if checkbox.isChecked()]
        if not selected_files:
            QMessageBox.information(self, "Нечего удалять", "Не выбрано ни одного файла.")
            return

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Подтверждение удаления")
        message.setText(
            "Вы уверены, что хотите удалить "
            f"{len(selected_files)} файлов общим размером 2.27 ГБ?\n\n"
            "Это действие необратимо!"
        )
        message.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message.button(QMessageBox.StandardButton.Yes).setText("Удалить")
        message.button(QMessageBox.StandardButton.No).setText("Отмена")
        message.setDefaultButton(QMessageBox.StandardButton.No)

        if message.exec() == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self,
                "Отчёт",
                f"Удалено: {len(selected_files)} файлов (2.27 ГБ)\n"
                "Ошибок: 0 (демонстрационный режим)"
            )
