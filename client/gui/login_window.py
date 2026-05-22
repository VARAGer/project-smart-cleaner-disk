from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client.gui.auth_components import (
    FloatingArrowButton,
    GlassInputField,
    GlassPanel,
    GlowOrb,
    OrDivider,
    ThemeSwitch,
)
from client.gui.theme import set_variant


class LoginScreen(QWidget):
    login_successful = pyqtSignal()
    theme_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("loginScreen")
        self._current_theme = "light"

        # Decorative background orbs
        self.left_orb = GlowOrb(QColor(71, 245, 212, 90), 260, self)
        self.right_orb = GlowOrb(QColor(126, 165, 255, 85), 340, self)
        self.bottom_orb = GlowOrb(QColor(71, 245, 212, 55), 220, self)

        root = QVBoxLayout(self)
        root.setContentsMargins(42, 30, 42, 30)
        root.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(14)

        self.brand_badge = QLabel("SmartCleaner")
        self.brand_badge.setObjectName("loginEyebrow")

        self.theme_switch = ThemeSwitch()
        self.theme_switch.theme_selected.connect(self.theme_requested.emit)

        top_bar.addWidget(
            self.brand_badge, 0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        top_bar.addStretch()
        top_bar.addWidget(
            self.theme_switch, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        root.addLayout(top_bar)
        root.addStretch()

        # ── Login card ────────────────────────────────────────────────────────
        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.addStretch()

        self.card = GlassPanel("loginCard", blur_radius=34, shadow_alpha=74)
        self.card.setMinimumWidth(420)
        self.card.setMaximumWidth(520)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(34, 34, 34, 30)
        card_layout.setSpacing(18)

        eyebrow = QLabel("Secure sign in")
        eyebrow.setObjectName("loginEyebrow")

        title = QLabel("Добро пожаловать в Smart Cleaner")
        title.setObjectName("loginTitle")

        subtitle = QLabel(
            "Войдите в локальный клиент и продолжите аккуратную очистку диска"
            " в выбранной теме."
        )
        subtitle.setObjectName("loginSubtitle")
        subtitle.setWordWrap(True)

        self.username_field = GlassInputField("Логин или email")
        self.password_field = GlassInputField("Пароль", password=True)

        self.username_input = self.username_field.line_edit
        self.password_input = self.password_field.line_edit

        # Enter on username → jump to password; Enter on password → submit
        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self._handle_login)

        self.submit_button = FloatingArrowButton()
        self.password_field.set_trailing_widget(self.submit_button)
        self.login_button = self.submit_button
        self.login_button.clicked.connect(self._handle_login)

        or_divider = OrDivider()

        self.register_button = QPushButton("Создать локальный профиль")
        self.register_button.setObjectName("glassRegisterButton")
        set_variant(self.register_button, "ghost")
        self.register_button.clicked.connect(self._handle_register)

        privacy = QLabel(
            "Файлы не покидают устройство: локально обрабатываются только"
            " метаданные, а критичные действия всегда подтверждаются отдельно."
        )
        privacy.setObjectName("loginFooter")
        privacy.setWordWrap(True)

        card_layout.addWidget(eyebrow)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.username_field)
        card_layout.addWidget(self.password_field)
        card_layout.addWidget(or_divider)
        card_layout.addWidget(self.register_button)
        card_layout.addSpacing(4)
        card_layout.addWidget(privacy)

        center_row.addWidget(self.card)
        center_row.addStretch()

        root.addLayout(center_row)
        root.addStretch()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_current_theme(self, theme_name: str) -> None:
        self._current_theme = theme_name
        self.theme_switch.set_theme(theme_name)
        for field in (self.username_field, self.password_field):
            field.apply_theme(theme_name)

    # ── Overrides ─────────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self.left_orb.move(-80, h // 2 - 130)
        self.right_orb.move(w - 200, -60)
        self.bottom_orb.move(w // 2 - 110, h - 140)

    # ── Private ────────────────────────────────────────────────────────────────

    def _handle_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Введите логин и пароль.")
            return
        # TODO: подключить реальную аутентификацию через backend
        self.login_successful.emit()

    def _handle_register(self) -> None:
        QMessageBox.information(
            self,
            "Регистрация",
            "Создание локального профиля будет доступно после подключения backend.",
        )
