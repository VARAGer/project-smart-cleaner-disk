from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.theme import set_variant


class LoginScreen(QWidget):
    login_successful = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")

        root = QHBoxLayout(self)
        root.setContentsMargins(56, 48, 56, 48)
        root.setSpacing(24)

        brand_card = QFrame()
        brand_card.setObjectName("heroCard")
        brand_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        brand_layout = QVBoxLayout(brand_card)
        brand_layout.setContentsMargins(36, 36, 36, 36)
        brand_layout.setSpacing(18)

        eyebrow = QLabel("Smart File Intelligence")
        eyebrow.setObjectName("eyebrow")

        title = QLabel("SmartCleaner")
        title.setObjectName("heroTitle")

        subtitle = QLabel(
            "Минималистичный клиент для аккуратной очистки дисков: "
            "локальное сканирование, безопасная классификация и понятные бандлы."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        feature_labels = [
            "Метаданные анализируются пакетно, без отправки содержимого файлов.",
            "Критичные действия подтверждаются отдельно, а low-confidence файлы не удаляются по умолчанию.",
            "Архитектура экранов, потоки QThread и сценарии строго оставлены в рамках app.md.",
        ]

        brand_layout.addWidget(eyebrow)
        brand_layout.addWidget(title)
        brand_layout.addWidget(subtitle)
        brand_layout.addSpacing(10)
        for text in feature_labels:
            bullet = QLabel(f"• {text}")
            bullet.setObjectName("bulletText")
            bullet.setWordWrap(True)
            brand_layout.addWidget(bullet)
        brand_layout.addStretch()

        footer_badges = QHBoxLayout()
        for text in ("Локальная БД", "JWT авторизация", "AI batch-ready"):
            badge = QLabel(text)
            badge.setObjectName("badge")
            footer_badges.addWidget(badge)
        footer_badges.addStretch()
        brand_layout.addLayout(footer_badges)

        auth_card = QFrame()
        auth_card.setObjectName("contentCard")
        auth_card.setMaximumWidth(430)
        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setContentsMargins(32, 32, 32, 32)
        auth_layout.setSpacing(16)

        auth_label = QLabel("Вход в систему")
        auth_label.setObjectName("sectionTitle")

        auth_note = QLabel(
            "Используйте логин и пароль. Регистрация и вход будут подключены "
            "к backend `/api/auth/*` без изменения визуального слоя."
        )
        auth_note.setObjectName("mutedText")
        auth_note.setWordWrap(True)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        form.addRow("Логин", self.username_input)
        form.addRow("Пароль", self.password_input)

        self.login_button = QPushButton("Войти")
        self.register_button = QPushButton("Регистрация")
        set_variant(self.login_button, "accent")
        set_variant(self.register_button, "ghost")

        self.username_input.returnPressed.connect(self.focus_password_input)
        self.password_input.returnPressed.connect(self.handle_login)
        self.login_button.clicked.connect(self.handle_login)
        self.register_button.clicked.connect(self.handle_register)

        self.setTabOrder(self.username_input, self.password_input)
        self.setTabOrder(self.password_input, self.login_button)
        self.username_input.setFocus()

        privacy_note = QLabel(
            "Содержимое файлов не покидает устройство. На сервер отправляются "
            "только имя файла, расширение, размер и `parent_dir`."
        )
        privacy_note.setObjectName("mutedText")
        privacy_note.setWordWrap(True)

        auth_layout.addWidget(auth_label)
        auth_layout.addWidget(auth_note)
        auth_layout.addSpacing(4)
        auth_layout.addLayout(form)
        auth_layout.addSpacing(6)
        auth_layout.addWidget(self.login_button)
        auth_layout.addWidget(self.register_button)
        auth_layout.addStretch()
        auth_layout.addWidget(privacy_note)

        root.addWidget(brand_card, 3)
        root.addWidget(auth_card, 2)

    def focus_password_input(self):
        self.password_input.setFocus(Qt.FocusReason.TabFocusReason)

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Введите логин и пароль.")
            return

        self.login_successful.emit()

    def handle_register(self):
        QMessageBox.information(
            self,
            "Регистрация",
            "На следующем этапе сюда подключится реальный запрос к backend `/api/auth/register`."
        )
