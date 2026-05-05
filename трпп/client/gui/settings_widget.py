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

import config
from gui.theme import set_variant


class SettingsScreen(QWidget):
    back_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")
        self.theme_buttons = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)

        eyebrow = QLabel("Settings")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Настройки")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Секция собрана как визуальный центр управления темой и базовыми UX-настройками. "
            "Логика подключения к локальной БД и реальным user settings может быть добавлена поверх этого интерфейса."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)

        content = QHBoxLayout()
        content.setSpacing(18)

        theme_card = QFrame()
        theme_card.setObjectName("contentCard")
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(24, 24, 24, 24)
        theme_layout.setSpacing(16)

        theme_title = QLabel("Темы интерфейса")
        theme_title.setObjectName("sectionTitle")
        theme_hint = QLabel("Приоритетные темы: тёмная и светлая, обе на чёрно-белой основе.")
        theme_hint.setObjectName("mutedText")
        theme_hint.setWordWrap(True)

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)

        theme_grid = QGridLayout()
        theme_grid.setHorizontalSpacing(12)
        theme_grid.setVerticalSpacing(12)

        for index, (theme_name, title_text, description) in enumerate(
            (
                ("dark", "Midnight", "Глубокая тёмная тема для основного рабочего режима."),
                ("light", "Paper", "Светлая тема с мягкими холодными акцентами."),
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

        preferences_card = QFrame()
        preferences_card.setObjectName("sidePanel")
        preferences_layout = QVBoxLayout(preferences_card)
        preferences_layout.setContentsMargins(24, 24, 24, 24)
        preferences_layout.setSpacing(16)

        preferences_title = QLabel("Поведение клиента")
        preferences_title.setObjectName("sectionTitle")

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        self.min_age = QSpinBox()
        self.min_age.setRange(1, 60)
        self.min_age.setValue(6)

        self.min_size = QSpinBox()
        self.min_size.setRange(1, 1024 * 1024)
        self.min_size.setValue(1024)
        self.min_size.setSuffix(" байт")

        self.skip_days = QSpinBox()
        self.skip_days.setRange(1, 365)
        self.skip_days.setValue(90)
        self.skip_days.setSuffix(" дней")

        form.addRow("Мин. возраст", self.min_age)
        form.addRow("Мин. размер", self.min_size)
        form.addRow("Срок skip", self.skip_days)

        backend_url = getattr(config, "BACKEND_URL", "не задан в текущем config.py")
        backend_label = QLabel(f"Backend: {backend_url}")
        backend_label.setObjectName("mutedText")
        backend_label.setWordWrap(True)

        self.save_button = QPushButton("Сохранить настройки")
        set_variant(self.save_button, "accent")
        self.save_button.clicked.connect(self.show_save_hint)

        self.back_button = QPushButton("Назад")
        self.back_button.clicked.connect(self.back_requested.emit)
        set_variant(self.back_button, "ghost")

        preferences_layout.addWidget(preferences_title)
        preferences_layout.addLayout(form)
        preferences_layout.addStretch()
        preferences_layout.addWidget(backend_label)
        preferences_layout.addWidget(self.save_button)
        preferences_layout.addWidget(self.back_button)

        content.addWidget(theme_card, 5)
        content.addWidget(preferences_card, 4)

        root.addWidget(hero)
        root.addLayout(content)

        self.set_current_theme("dark")

    def select_theme(self, theme_name: str):
        self.set_current_theme(theme_name)
        self.theme_changed.emit(theme_name)

    def set_current_theme(self, theme_name: str):
        for current_name, button in self.theme_buttons.items():
            button.setChecked(current_name == theme_name)

    def show_save_hint(self):
        QMessageBox.information(
            self,
            "Настройки",
            "Визуальная часть готова. Следующим шагом значения можно связать с `user_settings` в локальной SQLite."
        )
