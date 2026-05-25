import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
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

from client.database.local_db import MARKER_PROTECTED, MARKER_SKIP, mark_files
from client.files.deletion_service import (
    DeletionStatus,
    delete_files_by_id,
)
from client.gui.theme import set_variant
from client.review_policy import get_skip_expiration
from client.utils.formatters import format_size


class BundleDetailScreen(QWidget):
    back_requested = pyqtSignal()
    bundle_resolved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.current_bundle = None
        self.checkboxes = []
        self.allowed_roots: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(10)

        eyebrow = QLabel("Детали")
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
        self.open_button.clicked.connect(self.open_selected_file)

        self.skip_button = QPushButton("Не удалять")
        self.skip_button.setFixedHeight(48)
        set_variant(self.skip_button, "warning")
        self.skip_button.clicked.connect(self.mark_selected_as_skipped)

        self.delete_button = QPushButton("Удалить отмеченные")
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
            ["", "Файл", "Размер", "Категория", "Уверенность"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_selected_file())
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(0, 32)

        # ── Assemble ──────────────────────────────────────────────────────────
        root.addWidget(hero)
        root.addLayout(actions)
        root.addLayout(metrics_layout)
        root.addWidget(self.table, 1)

        self._set_actions_enabled(False)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_allowed_roots(self, roots: list[str]) -> None:
        self.allowed_roots = list(roots)

    def set_bundle(self, bundle: dict) -> None:
        self.current_bundle = bundle
        self.checkboxes = []

        self.title.setText(bundle.get("name", "Группа файлов"))
        self.subtitle.setText(
            f"{len(bundle['files'])} файлов  •  "
            f"{format_size(bundle.get('total_size_bytes', 0))}"
        )

        # Clear old badges
        while self.badges.count():
            item = self.badges.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.badges.addStretch()

        if bundle.get("review"):
            review_badge = QLabel("Требует проверки")
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
            cb.stateChanged.connect(self._on_checkbox_state_changed)
            cb_cell = QWidget()
            cb_layout = QHBoxLayout(cb_cell)
            cb_layout.setContentsMargins(4, 0, 0, 0)
            cb_layout.addWidget(cb)
            self.table.setCellWidget(row, 0, cb_cell)
            self.checkboxes.append(cb)

            self.table.setItem(row, 1, QTableWidgetItem(f["filename"]))
            self.table.setItem(row, 2, QTableWidgetItem(format_size(f["size_bytes"])))
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
        if files:
            self.table.selectRow(0)

        self.ready_value.setText(str(ready))
        self.risk_value.setText(str(risk))
        self._update_selected_count()
        self._set_actions_enabled(bool(files))

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_checkbox_state_changed(self, *_args) -> None:
        self._update_selected_count()

    def _update_selected_count(self) -> None:
        count = sum(cb.isChecked() for cb in self.checkboxes)
        self.selected_value.setText(str(count))

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.open_button.setEnabled(enabled)
        self.skip_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def open_selected_file(self) -> None:
        if not self.current_bundle:
            QMessageBox.information(self, "Нет выбора", "Сначала выберите бандл.")
            return
        selected = self._selected_file()
        if not selected:
            QMessageBox.information(self, "Нет выбора", "Выберите строку с файлом.")
            return
        path = selected.get("path", "")
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Файл недоступен", "Локальный файл не найден.")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Файл недоступен",
                f"Не удалось открыть файл:\n{exc}",
            )

    def show_open_hint(self) -> None:
        self.open_selected_file()

    def mark_selected_as_skipped(self) -> None:
        if not self.current_bundle:
            QMessageBox.information(self, "Нет выбора", "Сначала выберите бандл.")
            return
        checked = self._checked_files()
        if not checked:
            QMessageBox.information(self, "Нет выбора", "Отметьте файлы для пропуска.")
            return

        checked_ids = {file_info["file_id"] for file_info in checked}
        if self.current_bundle.get("review"):
            mark_files(
                checked_ids,
                MARKER_PROTECTED,
                reason="User permanently protected file in review",
            )
            for file_info in checked:
                file_info["marker_type"] = MARKER_PROTECTED
            message = (
                f"{len(checked)} файл(ов) больше не будут предлагаться к удалению."
            )
        else:
            expires_at, interval_label = get_skip_expiration()
            mark_files(
                checked_ids,
                MARKER_SKIP,
                expires_at=expires_at,
                reason="User deferred deletion in client",
            )
            for file_info in checked:
                file_info["marker_type"] = MARKER_SKIP
                file_info["expires_at"] = expires_at
            message = (
                f"{len(checked)} файл(ов) скрыты из рекомендаций и вернутся "
                f"на пересмотр {interval_label}."
            )

        self.current_bundle["files"] = [
            file_info
            for file_info in self.current_bundle["files"]
            if file_info["file_id"] not in checked_ids
        ]
        self.current_bundle["total_size_bytes"] = sum(
            file_info["size_bytes"] for file_info in self.current_bundle["files"]
        )
        self.set_bundle(self.current_bundle)
        QMessageBox.information(
            self,
            "Не удалять",
            message,
        )
        if not self.current_bundle["files"]:
            self.bundle_resolved.emit()

    def confirm_delete(self) -> None:
        if not self.current_bundle:
            QMessageBox.information(self, "Нет выбора", "Сначала выберите бандл.")
            return
        checked = self._checked_files()
        if not checked:
            QMessageBox.information(self, "Нет выбора", "Отметьте файлы для удаления.")
            return
        reply = QMessageBox.question(
            self,
            "Подтвердить удаление",
            f"Переместить {len(checked)} файл(ов) в корзину?\n"
            "Файлы, помеченные как защищенные, будут пропущены.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_kwargs = (
                {"allowed_roots": self.allowed_roots}
                if self.allowed_roots
                else {}
            )
            deletion_result = delete_files_by_id(
                [file_info["file_id"] for file_info in checked],
                **delete_kwargs,
            )
            deleted_ids = {
                item.file_id
                for item in deletion_result.results
                if item.status == DeletionStatus.DELETED
            }
            self.current_bundle["files"] = [
                file_info
                for file_info in self.current_bundle["files"]
                if file_info["file_id"] not in deleted_ids
            ]
            self.set_bundle(self.current_bundle)
            QMessageBox.information(
                self,
                "Готово",
                (
                    f"Удалено: {deletion_result.deleted_count}. "
                    f"Пропущено: {deletion_result.skipped_count}."
                ),
            )
            if not self.current_bundle["files"]:
                self.bundle_resolved.emit()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _checked_files(self) -> list[dict]:
        if not self.current_bundle:
            return []
        return [
            self.current_bundle["files"][index]
            for index, cb in enumerate(self.checkboxes)
            if cb.isChecked()
        ]

    def _selected_file(self) -> dict | None:
        if not self.current_bundle:
            return None
        files = self.current_bundle.get("files", [])
        row = self.table.currentRow()
        if row < 0 or row >= len(files):
            return None
        return files[row]
