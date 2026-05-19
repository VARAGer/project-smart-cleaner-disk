from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import client.config as config
from client import load_user_settings, save_user_settings
from client.gui.theme import set_variant


class SettingsScreen(QWidget):
    back_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.theme_buttons = {}
        self.settings_error = ""
        self.settings = self.load_settings_safe()

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        # ── Hero ──────────────────────────────────────────────────────────────
        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)

        eyebrow = QLabel("Settings")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Настройки")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Светлая и тёмная темы переключаются сразу, а пользовательские "
            "настройки сохраняются без изменения общей логики приложения."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)

        # ── Content area ──────────────────────────────────────────────────────
        content = QHBoxLayout()
        content.setSpacing(18)

        # Theme card
        theme_card = QFrame()
        theme_card.setObjectName("contentCard")
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(24, 24, 24, 24)
        theme_layout.setSpacing(16)

        theme_title = QLabel("Темы интерфейса")
        theme_title.setObjectName("sectionTitle")
        theme_hint = QLabel(
            "Светлая тема доступна уже на первом запуске, а выбранная тема "
            "подсвечивается заметнее."
        )
        theme_hint.setObjectName("mutedText")
        theme_hint.setWordWrap(True)

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)

        theme_grid = QGridLayout()
        theme_grid.setHorizontalSpacing(12)
        theme_grid.setVerticalSpacing(12)

        for index, (theme_name, title_text, description) in enumerate(
            (
                ("light", "Paper", "Светлая тема с мягкими кремовыми поверхностями."),
                ("dark", "Midnight", "Тёмная тема с глубокими графитовыми карточками."),
            )
        ):
            button = QPushButton(f"{title_text}\n{description}")
            button.setCheckable(True)
            set_variant(button, "theme")
            button.clicked.connect(lambda checked, name=theme_name: self.select_theme(name))
            button_group.addButton(button)
            self.theme_buttons[theme_name] = button
            theme_grid.addWidget(button, 0, index)

        theme_layout.addWidget(theme_title)
        theme_layout.addWidget(theme_hint)
        theme_layout.addLayout(theme_grid)
        theme_layout.addStretch()

        # Settings form card
        form_card = QFrame()
        form_card.setObjectName("contentCard")
        form_layout_outer = QVBoxLayout(form_card)
        form_layout_outer.setContentsMargins(24, 24, 24, 24)
        form_layout_outer.setSpacing(16)

        form_title = QLabel("Параметры сканирования")
        form_title.setObjectName("sectionTitle")

        form = QFormLayout()
        form.setSpacing(12)

        self.age_spin = QSpinBox()
        self.age_spin.setRange(1, 120)
        self.age_spin.setSuffix(" мес.")
        self.age_spin.setSingleStep(1)
        self.age_spin.setValue(self.settings.get("min_age_months", config.DEFAULT_MIN_AGE_MONTHS))

        self.skip_spin = QSpinBox()
        self.skip_spin.setRange(1, 365)
        self.skip_spin.setSuffix(" дн.")
        self.skip_spin.setSingleStep(1)
        self.skip_spin.setValue(
            self.settings.get("skip_duration_days", config.DEFAULT_SKIP_DURATION_DAYS)
        )

        form.addRow("Мин. возраст файла:", self.age_spin)
        form.addRow("Период пропуска:", self.skip_spin)

        if self.settings_error:
            error_label = QLabel(f"Настройки не загружены: {self.settings_error}")
            error_label.setObjectName("warningBadge")
            error_label.setWordWrap(True)
            form_layout_outer.addWidget(error_label)

        self.save_button = QPushButton("Сохранить настройки")
        self.save_button.setFixedHeight(46)
        set_variant(self.save_button, "accent")
        self.save_button.clicked.connect(self.save_settings)

        form_layout_outer.addWidget(form_title)
        form_layout_outer.addLayout(form)
        form_layout_outer.addStretch()
        form_layout_outer.addWidget(self.save_button)

        content.addWidget(theme_card, 1)
        content.addWidget(form_card, 1)

        # ── Back button ───────────────────────────────────────────────────────
        back_button = QPushButton("← Назад")
        back_button.setFixedHeight(46)
        set_variant(back_button, "ghost")
        back_button.clicked.connect(self.back_requested.emit)

        # ── Assemble root ─────────────────────────────────────────────────────
        root.addWidget(hero)
        root.addLayout(content)
        root.addWidget(back_button)

        # Reflect saved theme in button state
        saved_theme = self.settings.get("theme", "light")
        if saved_theme in self.theme_buttons:
            self.theme_buttons[saved_theme].setChecked(True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_selected_theme(self) -> str:
        """Return the currently active theme name."""
        return self.settings.get("theme", "light")

    def set_current_theme(self, theme_name: str) -> None:
        """Update button highlight to reflect the active theme (called by ThemeManager)."""
        if theme_name in self.theme_buttons:
            self.theme_buttons[theme_name].setChecked(True)
        self.settings["theme"] = theme_name

    # ── Private helpers ────────────────────────────────────────────────────────

    def load_settings_safe(self) -> dict:
        try:
            return load_user_settings()
        except Exception as exc:
            self.settings_error = str(exc)
            return {}

    def select_theme(self, theme_name: str) -> None:
        """Called when user clicks a theme button."""
        self.settings["theme"] = theme_name
        self.theme_changed.emit(theme_name)

    def save_settings(self) -> None:
        """Persist current settings to disk."""
        self.settings["min_age_months"] = self.age_spin.value()
        self.settings["skip_duration_days"] = self.skip_spin.value()
        try:
            save_user_settings(self.settings)
            QMessageBox.information(self, "Сохранено", "Настройки успешно сохранены.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки:\n{exc}")
