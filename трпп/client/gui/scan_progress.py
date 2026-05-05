from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.theme import set_variant


class ScanProgressScreen(QWidget):
    scan_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)

        eyebrow = QLabel("Scan Pipeline")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Сканирование и подготовка батчей")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "По app.md тяжёлые операции должны работать в отдельном `QThread`. "
            "Этот экран уже собран как progress-dashboard для локального обхода, "
            "фильтрации и последующей отправки батчей на backend."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        header_layout.addWidget(eyebrow)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        content = QHBoxLayout()
        content.setSpacing(18)

        progress_card = QFrame()
        progress_card.setObjectName("contentCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(24, 24, 24, 24)
        progress_layout.setSpacing(16)

        status_title = QLabel("Текущий статус")
        status_title.setObjectName("sectionTitle")

        self.status = QLabel("Собираем индекс файлов и подготавливаем кандидатов для анализа.")
        self.status.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setValue(64)
        self.progress.setFormat("%p% готово")

        self.phase = QLabel("Этап 2 из 3 • локальная фильтрация")
        self.phase.setObjectName("badge")

        self.detail = QLabel(
            "Следом экран переключится к итоговым бандлам. Симуляция оставлена, "
            "потому что реальный worker ещё не подключён."
        )
        self.detail.setObjectName("mutedText")
        self.detail.setWordWrap(True)

        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(12)
        metrics_grid.setVerticalSpacing(12)
        metrics = [
            ("47 218", "Файлов найдено"),
            ("3 184", "После фильтров"),
            ("16", "Батчей к AI"),
            ("12.4 ГБ", "Потенциал очистки"),
        ]
        for index, (value, label) in enumerate(metrics):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(4)
            value_label = QLabel(value)
            value_label.setObjectName("metricValue")
            text_label = QLabel(label)
            text_label.setObjectName("metricLabel")
            card_layout.addWidget(value_label)
            card_layout.addWidget(text_label)
            metrics_grid.addWidget(card, index // 2, index % 2)

        self.fake_finish_button = QPushButton("Завершить демонстрацию")
        set_variant(self.fake_finish_button, "accent")
        self.fake_finish_button.clicked.connect(self.complete_demo)

        progress_layout.addWidget(status_title)
        progress_layout.addWidget(self.status)
        progress_layout.addWidget(self.phase, alignment=Qt.AlignmentFlag.AlignLeft)
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.detail)
        progress_layout.addLayout(metrics_grid)
        progress_layout.addStretch()
        progress_layout.addWidget(self.fake_finish_button)

        stage_card = QFrame()
        stage_card.setObjectName("sidePanel")
        stage_layout = QVBoxLayout(stage_card)
        stage_layout.setContentsMargins(24, 24, 24, 24)
        stage_layout.setSpacing(14)

        stage_title = QLabel("Этапы процесса")
        stage_title.setObjectName("sectionTitle")
        stage_layout.addWidget(stage_title)

        for text, style in (
            ("1. Обход дисков и индексация метаданных", "successBadge"),
            ("2. Локальные фильтры по возрасту, размеру и системным файлам", "badge"),
            ("3. Батчинг и классификация через backend", "warningBadge"),
        ):
            label = QLabel(text)
            label.setObjectName(style)
            label.setWordWrap(True)
            stage_layout.addWidget(label)

        stage_note = QLabel(
            "Кодовая логика не менялась: дизайн только визуализирует pipeline, "
            "который уже описан в `scanner/*`, `heuristics/*` и `api_client/analysis.py`."
        )
        stage_note.setObjectName("mutedText")
        stage_note.setWordWrap(True)
        stage_layout.addStretch()
        stage_layout.addWidget(stage_note)

        content.addWidget(progress_card, 5)
        content.addWidget(stage_card, 3)

        root.addWidget(header)
        root.addLayout(content)

    def complete_demo(self):
        self.progress.setValue(100)
        self.status.setText("Индекс собран, батчи отправлены, бандлы готовы к просмотру.")
        self.phase.setText("Этап 3 из 3 • завершено")
        self.detail.setText("Переходим к экрану `BundleListScreen` с итоговыми группами файлов.")
        self.scan_finished.emit()
