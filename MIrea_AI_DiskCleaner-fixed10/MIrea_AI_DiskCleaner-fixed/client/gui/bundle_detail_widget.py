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

from client.gui.theme import set_variant
from client.utils.utils import format_size


class BundleDetailScreen(QWidget):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.current_bundle = None
        self.checkboxes = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(10)

        eyebrow = QLabel("BUNDLE DETAIL")
        eyebrow.setObjectName("eyebrow")
        self.title = QLabel("Содержимое бандла")
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel("Выберите бандл на предыдущем экране.")
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setWordWrap(True)

        self.badges = QHBoxLayout()
        self.badges.addStretch()

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(self.title)
        hero_layout.addWidget(self.subtitle)
        hero_layout.addLayout(self.badges)

        actions = QHBoxLayout()
        self.back_button = QPushButton("Назад")
        self.back_button.setFixedHeight(46)
        self.back_button.clicked.connect(self.back_requested.emit)
        set_variant(self.back_button, "ghost")

        self.open_button = QPushButton("Открыть файл")
        self.open_button.setFixedHeight(48)
        set_variant(self.open_button, "ghost")
        self.open_button.clicked.connect(self.show_open_hint)

        self.skip_button = QPushButton("Не удалять")
        self.skip_button.setFixedHeight(48)
        set_variant(self.skip_button, "warning")
        self.skip_button.clicked.connect(self.mark_selected_as_skipped)

        self.delete_button = QPushButton("Удалить выбранные")
        self.delete_button.setFixedHeight(48)
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

        self.ready_value = QLabel()
        self.ready_value.setObjectName("metricValue")
        self.risk_value = QLabel()
        self.risk_value.setObjectName("metricValue")
        self.selected_value = QLabel()
        self.selected_value.setObjectName("metricValue")

        cards = [
            (self.ready_value, "Готовы к удалению", "successBadge"),
            (self.risk_value, "Низкая уверенность", "warningBadge"),
            (self.selected_value, "Выбрано сейчас", "badge"),
        ]
        for index, (value_label, text, badge_name) in enumerate(cards):
            badge = QLabel()
            badge.setObjectName(badge_name)
            badge.setFixedWidth(20)
            badge.setFixedHeight(20)

            label = QLabel(text)
            label.setObjectName("metricLabel")

            layout = QHBoxLayout()
            layout.setSpacing(8)
            layout.addWidget(badge)
            layout.addWidget(value_label)

            card = QFrame()
            card.setObjectName("contentCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.addLayout(layout)

            metrics_layout.addWidget(card, 0, index)
        # ── File table ────────────────────────────────────────────────────────
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["", "Файл", "Размер", "Категория", "Confidence"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 32)
        self.table.itemChanged.connect(self._on_item_changed)

        # ── Assemble ──────────────────────────────────────────────────────────
        root.addWidget(hero)
        root.addLayout(actions)
        root.addLayout(metrics_layout)
        root.addWidget(self.table, 1)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_bundle(self, bundle: dict) -> None:
        self.current_bundle = bundle
        self.checkboxes = []

        self.title.setText(bundle.get("name", "Bundle"))
        self.subtitle.setText(
            f"{len(bundle['files'])} файлов  •  "
            f"{self._fmt_size(bundle.get('total_size_bytes', 0))}"
        )

        # Clear old badges
        while self.badges.count():
            item = self.badges.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.badges.addStretch()

        if bundle.get("review"):
            review_badge = QLabel("Review Bundle")
            review_badge.setObjectName("warningBadge")
            self.badges.addWidget(review_badge)

        # Populate table
        files = bundle.get("files", [])
        self.table.blockSignals(True)
        self.table.setRowCount(len(files))
        self.checkboxes = []

        ready = risk = 0
        for row, f in enumerate(files):
            cb = QCheckBox()
            cb.setChecked(True)
            cb_cell = QWidget()
            cb_layout = QHBoxLayout(cb_cell)
            cb_layout.setContentsMargins(4, 0, 0, 0)
            cb_layout.addWidget(cb)
            self.table.setCellWidget(row, 0, cb_cell)
            self.checkboxes.append(cb)

            self.table.setItem(row, 1, QTableWidgetItem(f["filename"]))
            self.table.setItem(row, 2, QTableWidgetItem(self._fmt_size(f["size_bytes"])))
            self.table.setItem(row, 3, QTableWidgetItem(f["category"]))

            pct = int(f["confidence"] * 100)
            conf_item = QTableWidgetItem(f"{pct}%")
            conf_item.setForeground(
                QColor("#44dc8c") if f["confidence"] >= 0.9 else QColor("#f0c56f")
            )
            self.table.setItem(row, 4, conf_item)

            if f["confidence"] >= 0.9:
                ready += 1
            else:
                risk += 1

        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 32)

        self.ready_value.setText(str(ready))
        self.risk_value.setText(str(risk))
        self._update_selected_count()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_item_changed(self) -> None:
        self._update_selected_count()

    def _update_selected_count(self) -> None:
        count = sum(cb.isChecked() for cb in self.checkboxes)
        self.selected_value.setText(str(count))

    def show_open_hint(self) -> None:
        QMessageBox.information(
            self, "Открыть файл",
            "Открытие файла будет доступно после подключения реальных данных.",
        )

    def mark_selected_as_skipped(self) -> None:
        count = sum(cb.isChecked() for cb in self.checkboxes)
        if count == 0:
            QMessageBox.information(self, "Нет выбора", "Отметьте файлы для пропуска.")
            return
        QMessageBox.information(
            self, "Пропуск",
            f"{count} файл(ов) помечены как «не удалять».\n"
            "Маркер будет сохранён после подключения реального хранилища.",
        )

    def confirm_delete(self) -> None:
        checked = [
            self.current_bundle["files"][i]
            for i, cb in enumerate(self.checkboxes)
            if cb.isChecked()
        ]
        if not checked:
            QMessageBox.information(self, "Нет выбора", "Отметьте файлы для удаления.")
            return
        reply = QMessageBox.question(
            self,
            "Подтвердить удаление",
            f"Удалить {len(checked)} файл(ов)?\nДействие необратимо.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self, "Готово",
                "Удаление будет выполнено после подключения реального сканера.",
            )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} Б"
        for unit in ("КБ", "МБ", "ГБ", "ТБ"):
            size_bytes /= 1024
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
        return f"{size_bytes:.1f} ТБ"
