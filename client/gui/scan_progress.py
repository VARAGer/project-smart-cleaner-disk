from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client.gui.theme import set_variant
from client.utils.utils import format_duration


class ScanProgressScreen(QWidget):
    scan_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.elapsed_seconds = 0
        self.active_disks: list[str] = []

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        header = QFrame()
        header.setObjectName("heroCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)

        eyebrow = QLabel("Scan Pipeline")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Идёт сканирование")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Процент здесь не симулируется, потому что у текущей заглушки нет честного "
            "источника прогресса. Экран показывает только текущее состояние и длительность работы."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        header_layout.addWidget(eyebrow)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(18)

        progress_card = QFrame()
        progress_card.setObjectName("contentCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(24, 24, 24, 24)
        progress_layout.setSpacing(16)

        status_title = QLabel("Текущий статус")
        status_title.setObjectName("sectionTitle")

        self.status = QLabel("Сканер обходит выбранные диски и собирает метаданные файлов.")
        self.status.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)

        self.elapsed = QLabel("Прошло: 00:00")
        self.elapsed.setObjectName("badge")

        self.next_step = QLabel(
            "После завершения локального обхода будет выполнена фильтрация, а затем переход к списку бандлов."
        )
        self.next_step.setObjectName("mutedText")
        self.next_step.setWordWrap(True)

        self.fake_finish_button = QPushButton("Завершить демонстрацию")
        set_variant(self.fake_finish_button, "accent")
        self.fake_finish_button.clicked.connect(self.complete_demo)

        progress_layout.addWidget(status_title)
        progress_layout.addWidget(self.status)
        progress_layout.addWidget(self.elapsed, alignment=Qt.AlignmentFlag.AlignLeft)
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.next_step)
        progress_layout.addStretch()
        progress_layout.addWidget(self.fake_finish_button)

        side_card = QFrame()
        side_card.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side_card)
        side_layout.setContentsMargins(24, 24, 24, 24)
        side_layout.setSpacing(14)

        side_title = QLabel("Что важно")
        side_title.setObjectName("sectionTitle")
        side_layout.addWidget(side_title)
        for note in (
            "Системные папки (Windows, Program Files) пропускаются.",
            "Файлы меньше 1 КБ не попадают в кандидаты.",
            "Файлы моложе 6 месяцев исключаются автоматически.",
        ):
            lbl = QLabel(f"• {note}")
            lbl.setObjectName("mutedText")
            lbl.setWordWrap(True)
            side_layout.addWidget(lbl)

        side_layout.addStretch()

        body.addWidget(progress_card, 3)
        body.addWidget(side_card, 2)

        root.addWidget(header)
        root.addLayout(body)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start_scan(self, selected_disks: list[str] | None = None) -> None:
        self.active_disks = list(selected_disks or [])
        self.elapsed_seconds = 0
        self.timer.start()
        if self.active_disks:
            disks_text = ", ".join(self.active_disks)
            self.status.setText(f"Сканирование дисков: {disks_text}.")
        else:
            self.status.setText("Сканирование выбранных дисков.")
        self.elapsed.setText("Прошло: 00:00")

    # ── Slots ──────────────────────────────────────────────────────────────────

    def tick(self) -> None:
        self.elapsed_seconds += 1
        self.elapsed.setText(f"Прошло: {format_duration(self.elapsed_seconds)}")

    def complete_demo(self) -> None:
        self.timer.stop()
        self.elapsed_seconds = 0
        self.active_disks = []
        self.elapsed.setText("Прошло: 00:00")
        self.scan_finished.emit()
