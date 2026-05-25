import logging

from PyQt6.QtCore import QRectF, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from client import load_user_settings
from client.api_client import SmartCleanerApiClient
from client.config import DEFAULT_MIN_AGE_MONTHS, DEFAULT_MIN_SIZE_BYTES
from client.gui.theme import set_variant
from client.pipeline.analysis_pipeline import run_scan_analysis_pipeline
from client.utils.formatters import format_duration


logger = logging.getLogger(__name__)


def load_scan_filter_settings() -> tuple[int, int]:
    settings = load_user_settings()
    return (
        _positive_int_setting(settings, "min_age_months", DEFAULT_MIN_AGE_MONTHS),
        _positive_int_setting(settings, "min_size_bytes", DEFAULT_MIN_SIZE_BYTES),
    )


def _positive_int_setting(settings: dict, key: str, default: int) -> int:
    try:
        value = int(settings.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


class RoundedIndeterminateProgressBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(24)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._phase = 0.0
        self.is_running = False
        self._timer = QTimer(self)
        self._timer.setInterval(24)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self.is_running = True
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self.is_running = False
        self._timer.stop()
        self._phase = 0.0
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 4.5, -0.5, -4.5)
        radius = rect.height() / 2

        border = QColor(self.palette().windowText().color())
        border.setAlpha(28)
        track = QColor(self.palette().windowText().color())
        track.setAlpha(18)
        painter.setPen(QPen(border, 1))
        painter.setBrush(track)
        painter.drawRoundedRect(rect, radius, radius)

        if not self.is_running or rect.width() <= 0:
            return

        chunk_width = max(rect.height() * 4.6, rect.width() * 0.17)
        chunk_width = min(chunk_width, rect.width())
        travel = max(0.0, rect.width() - chunk_width)
        x = rect.left() + travel * self._phase
        chunk = QRectF(x, rect.top(), chunk_width, rect.height())

        gradient = QLinearGradient(chunk.topLeft(), chunk.topRight())
        gradient.setColorAt(0.0, QColor("#47F5D4"))
        gradient.setColorAt(1.0, QColor("#78A9FF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(chunk, radius, radius)


class _ScanPipelineWorker(QThread):
    progress = pyqtSignal(str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        api_client: SmartCleanerApiClient,
        selected_disks: list[str],
    ):
        super().__init__()
        self._api_client = api_client
        self._selected_disks = selected_disks

    def run(self) -> None:
        try:
            min_age_months, min_size_bytes = load_scan_filter_settings()
            result = run_scan_analysis_pipeline(
                self._api_client,
                self._selected_disks,
                progress_callback=self.progress.emit,
                cancel_requested=self.isInterruptionRequested,
                min_age_months=min_age_months,
                min_size_bytes=min_size_bytes,
            )
        except Exception:
            logger.exception("Scan analysis pipeline failed")
            self.failed.emit("Не удалось завершить сканирование и анализ.")
            return
        if self.isInterruptionRequested():
            return
        self.succeeded.emit(result)


class ScanProgressScreen(QWidget):
    scan_finished = pyqtSignal(list)
    back_requested = pyqtSignal()

    def __init__(self, api_client: SmartCleanerApiClient):
        super().__init__()
        self.setObjectName("screen")
        self.api_client = api_client
        self.elapsed_seconds = 0
        self.active_disks: list[str] = []
        self._worker: _ScanPipelineWorker | None = None

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

        eyebrow = QLabel("Сканирование")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Идёт сканирование")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Приложение ищет старые и крупные файлы, затем аккуратно запрашивает "
            "анализ у сервера и показывает результат списком."
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

        self.progress = RoundedIndeterminateProgressBar()

        self.elapsed = QLabel("Прошло: 00:00")
        self.elapsed.setObjectName("badge")

        self.next_step = QLabel(
            "После завершения локального обхода будет выполнена фильтрация, а затем переход к списку бандлов."
        )
        self.next_step.setObjectName("mutedText")
        self.next_step.setWordWrap(True)

        self.back_button = QPushButton("Назад")
        set_variant(self.back_button, "ghost")
        self.back_button.clicked.connect(self._handle_back_requested)

        self.action_button = QPushButton("Ожидание запуска")
        set_variant(self.action_button, "ghost")
        self.action_button.setEnabled(False)

        progress_layout.addWidget(status_title)
        progress_layout.addWidget(self.status)
        progress_layout.addWidget(self.elapsed, alignment=Qt.AlignmentFlag.AlignLeft)
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.next_step)
        progress_layout.addStretch()
        progress_layout.addWidget(self.back_button)
        progress_layout.addWidget(self.action_button)

        side_card = QFrame()
        side_card.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side_card)
        side_layout.setContentsMargins(24, 24, 24, 24)
        side_layout.setSpacing(14)

        side_title = QLabel("Что происходит")
        side_title.setObjectName("sectionTitle")
        side_layout.addWidget(side_title)
        for note in (
            "Системные папки пропускаются.",
            "Файлы меньше 1 КБ не попадают в кандидаты.",
            "Файлы моложе 6 месяцев исключаются автоматически.",
            "На сервер уходит только краткое описание файла.",
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

    def start_scan(self, selected_disks: list[str] | None = None) -> bool:
        if self._worker is not None:
            self.status.setText("Предыдущее сканирование еще завершается.")
            return False
        if self.api_client.session is None:
            self.status.setText("Для анализа нужна активная backend-сессия.")
            return False

        self.active_disks = list(selected_disks or [])
        self.elapsed_seconds = 0
        self.progress.start()
        self.timer.start()
        self.action_button.setText("Сканирование выполняется")
        self.back_button.setText("Отменить и вернуться")
        if self.active_disks:
            disks_text = ", ".join(self.active_disks)
            self.status.setText(f"Сканирование дисков: {disks_text}.")
        else:
            self.status.setText("Сканирование выбранных дисков.")
        self._set_elapsed_label("Прошло")
        self._worker = _ScanPipelineWorker(self.api_client, self.active_disks)
        self._worker.progress.connect(self.status.setText)
        self._worker.succeeded.connect(self._handle_pipeline_success)
        self._worker.failed.connect(self._handle_pipeline_failure)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()
        return True

    # ── Slots ──────────────────────────────────────────────────────────────────

    def tick(self) -> None:
        self.elapsed_seconds += 1
        self._set_elapsed_label("Прошло")

    def _handle_pipeline_success(self, result) -> None:
        self.timer.stop()
        self.progress.stop()
        self._set_elapsed_label("Завершено за")
        self.status.setText(
            f"Готово: проанализировано {result.candidates_analyzed} файлов."
        )
        self.action_button.setText("Готово")
        self.back_button.setText("Назад")
        self.active_disks = []
        self.scan_finished.emit(result.bundles)

    def _handle_pipeline_failure(self, message: str) -> None:
        self.timer.stop()
        self.progress.stop()
        self._set_elapsed_label("Остановлено")
        self.status.setText(message)
        self.action_button.setText("Ошибка")
        self.back_button.setText("Назад")
        self.active_disks = []

    def _clear_worker(self) -> None:
        self._worker = None

    def _set_elapsed_label(self, prefix: str) -> None:
        self.elapsed.setText(f"{prefix}: {format_duration(self.elapsed_seconds)}")

    def _handle_back_requested(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self.timer.stop()
            self.progress.stop()
            self.status.setText("Сканирование остановлено пользователем.")
            self.action_button.setText("Остановлено")
            self.back_button.setText("Назад")
        self.back_requested.emit()
