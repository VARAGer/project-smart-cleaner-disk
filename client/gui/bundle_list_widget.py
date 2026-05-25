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

from client.files.deletion_service import DeletionStatus, delete_files_by_id
from client.database.local_db import MARKER_PROTECTED, MARKER_SKIP, mark_files
from client.gui.theme import refresh_style, set_variant
from client.review_policy import get_skip_expiration
from client.utils.formatters import format_size


class BundleCard(QFrame):
    selected = pyqtSignal(dict)
    open_requested = pyqtSignal(dict)
    skip_requested = pyqtSignal(dict)

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

        self.skip_button = QPushButton("Не удалять")
        self.skip_button.setFixedHeight(44)
        set_variant(self.skip_button, "warning" if bundle["review"] else "ghost")
        self.skip_button.clicked.connect(lambda: self.skip_requested.emit(self.bundle))

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


class BundleListScreen(QWidget):
    open_bundle = pyqtSignal(dict)
    open_settings = pyqtSignal()
    back_requested = pyqtSignal()
    all_bundles_resolved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.cards = []
        self.selected_bundle = None
        self.bundles: list[dict] = []
        self.allowed_roots: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(32, 28, 32, 28)
        header_layout.setSpacing(8)

        eyebrow = QLabel("Результаты")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Найденные группы файлов")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Выберите группу, посмотрите примеры справа и откройте детальный список "
            "для удаления или защиты отдельных файлов."
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
        left_title = QLabel("Группы")
        left_title.setObjectName("sectionTitle")
        left_hint = QLabel("Сначала — требующие проверки")
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

        self.container_layout = container_layout
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
            ["Файл", "Размер", "Категория", "Уверенность"]
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

        self.back_button = QPushButton("Новый скан")
        self.back_button.setFixedHeight(46)
        set_variant(self.back_button, "ghost")
        self.back_button.clicked.connect(self.back_requested.emit)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.setFixedHeight(46)
        set_variant(self.settings_button, "ghost")
        self.settings_button.clicked.connect(self.open_settings.emit)

        self.delete_button = QPushButton("Открыть для удаления")
        self.delete_button.setFixedHeight(50)
        set_variant(self.delete_button, "danger")
        self.delete_button.clicked.connect(self.emit_selected_bundle)

        self.delete_all_button = QPushButton("Удалить все рекомендации")
        self.delete_all_button.setFixedHeight(50)
        set_variant(self.delete_all_button, "danger")
        self.delete_all_button.clicked.connect(self.confirm_delete_all_recommendations)

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
        right_layout.addWidget(self.back_button)
        right_layout.addWidget(self.settings_button)
        right_layout.addWidget(self.delete_button)
        right_layout.addWidget(self.delete_all_button)
        right_layout.addStretch()

        content.addWidget(left_panel, 5)
        content.addWidget(right_panel, 4)

        root.addWidget(header)
        root.addLayout(content)

        self.set_bundles([])

    def set_allowed_roots(self, roots: list[str]) -> None:
        self.allowed_roots = list(roots)

    def set_bundles(self, bundles: list[dict]) -> None:
        self.bundles = list(bundles)
        self._rebuild_cards()
        self.update_summary()
        self._update_bulk_actions()
        if self.bundles:
            self.select_bundle(self.bundles[0])
        else:
            self.show_empty_state()

    def _rebuild_cards(self) -> None:
        for card in self.cards:
            self.container_layout.removeWidget(card)
            card.deleteLater()
        self.cards = []

        insert_index = max(0, self.container_layout.count() - 1)
        for bundle in self.bundles:
            bundle["total_size_bytes"] = sum(
                file["size_bytes"] for file in bundle["files"]
            )
            card = BundleCard(bundle)
            card.selected.connect(self.select_bundle)
            card.open_requested.connect(self.handle_open_bundle)
            card.skip_requested.connect(self.confirm_skip_bundle)
            self.cards.append(card)
            self.container_layout.insertWidget(insert_index, card)
            insert_index += 1

    def update_summary(self):
        total_files = sum(len(bundle["files"]) for bundle in self.bundles)
        total_size = sum(bundle.get("total_size_bytes", 0) for bundle in self.bundles)
        bundles_count = len(self.bundles)
        bundle_word = "бандл" if bundles_count == 1 else "бандлов"
        self.summary.setText(
            f"Всего: {bundles_count} {bundle_word}, {total_files} файлов, {format_size(total_size)}"
        )
        self._update_bulk_actions()

    def select_bundle(self, bundle: dict):
        self.selected_bundle = bundle
        self.open_button.setEnabled(True)
        self.delete_button.setEnabled(True)
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


    def show_empty_state(self):
        self.selected_bundle = None
        self.bundle_name.setText("Бандлы не найдены")
        self.bundle_subtitle.setText("После сканирования результаты появятся здесь.")
        self.bundle_stats.setText("0 файлов")
        self.preview_table.setRowCount(0)
        self.open_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        for card in self.cards:
            card.set_selected(False)

    def emit_selected_bundle(self):
        if not self.selected_bundle:
            QMessageBox.information(self, "Нет выбора", "Сначала выберите бандл.")
            return
        self.open_bundle.emit(self.selected_bundle)

    def handle_open_bundle(self, bundle: dict):
        self.select_bundle(bundle)
        self.open_bundle.emit(bundle)

    def confirm_skip_bundle(self, bundle: dict):
        files = [
            file_info
            for file_info in bundle.get("files", [])
            if str(file_info.get("file_id", ""))
        ]
        if not files:
            QMessageBox.information(
                self,
                "Нет файлов",
                "В этом бандле нет файлов для пометки.",
            )
            return

        marker_label = "защитить" if bundle.get("review") else "скрыть из рекомендаций"
        reply = QMessageBox.question(
            self,
            "Не удалять",
            (
                f"Пометить {len(files)} файл(ов) как «не удалять» и "
                f"{marker_label} весь бандл?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        file_ids = {file_info["file_id"] for file_info in files}
        if bundle.get("review"):
            mark_files(
                file_ids,
                MARKER_PROTECTED,
                reason="User permanently protected bundle from list",
            )
            message = f"{len(files)} файл(ов) больше не будут предлагаться к удалению."
        else:
            expires_at, interval_label = get_skip_expiration()
            mark_files(
                file_ids,
                MARKER_SKIP,
                expires_at=expires_at,
                reason="User deferred bundle deletion from list",
            )
            message = (
                f"{len(files)} файл(ов) скрыты из рекомендаций и вернутся "
                f"на пересмотр {interval_label}."
            )

        self._remove_bundle(bundle.get("bundle_id", ""))
        QMessageBox.information(self, "Не удалять", message)
        self._emit_resolved_if_empty()

    def confirm_delete_all_recommendations(self):
        candidates = self._deletable_recommendation_files()
        if not candidates:
            QMessageBox.information(
                self,
                "Нет файлов",
                "Нет обычных рекомендаций для массового удаления.",
            )
            return
        total_size = sum(file_info.get("size_bytes", 0) for file_info in candidates)
        reply = QMessageBox.question(
            self,
            "Подтвердить удаление",
            (
                f"Переместить в корзину {len(candidates)} файл(ов) "
                f"общим размером {format_size(total_size)}?\n"
                "Файлы из блока проверки не будут удалены этой кнопкой."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        delete_kwargs = (
            {"allowed_roots": self.allowed_roots}
            if self.allowed_roots
            else {}
        )
        result = delete_files_by_id(
            [file_info["file_id"] for file_info in candidates],
            **delete_kwargs,
        )
        deleted_ids = {
            item.file_id
            for item in result.results
            if item.status == DeletionStatus.DELETED
        }
        if deleted_ids:
            self._remove_files_from_bundles(deleted_ids)
        QMessageBox.information(
            self,
            "Готово",
            f"Удалено: {result.deleted_count}. Пропущено: {result.skipped_count}.",
        )
        self._emit_resolved_if_empty()

    def _deletable_recommendation_files(self) -> list[dict]:
        files: list[dict] = []
        seen: set[str] = set()
        for bundle in self.bundles:
            if bundle.get("review"):
                continue
            for file_info in bundle.get("files", []):
                file_id = str(file_info.get("file_id", ""))
                if file_id and file_id not in seen:
                    seen.add(file_id)
                    files.append(file_info)
        return files

    def _remove_files_from_bundles(self, deleted_ids: set[str]) -> None:
        updated_bundles = []
        for bundle in self.bundles:
            remaining_files = [
                file_info
                for file_info in bundle.get("files", [])
                if file_info.get("file_id") not in deleted_ids
            ]
            if remaining_files or bundle.get("review"):
                bundle["files"] = remaining_files
                bundle["total_size_bytes"] = sum(
                    file_info.get("size_bytes", 0)
                    for file_info in remaining_files
                )
                updated_bundles.append(bundle)
        self.set_bundles(updated_bundles)

    def _remove_bundle(self, bundle_id: str) -> None:
        self.set_bundles(
            [
                bundle
                for bundle in self.bundles
                if bundle.get("bundle_id") != bundle_id
            ]
        )

    def _emit_resolved_if_empty(self) -> None:
        if not self.bundles:
            self.all_bundles_resolved.emit()

    def _update_bulk_actions(self) -> None:
        has_recommendations = bool(self._deletable_recommendation_files())
        self.delete_all_button.setEnabled(has_recommendations)

