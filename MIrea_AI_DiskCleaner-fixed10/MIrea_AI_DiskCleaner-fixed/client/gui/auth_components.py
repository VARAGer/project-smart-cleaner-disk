from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from client.gui.theme import get_palette, refresh_style


class GlassPanel(QFrame):
    def __init__(self, object_name: str, blur_radius: int = 42, shadow_alpha: int = 80):
        super().__init__()
        self.setObjectName(object_name)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(0, 0, 0, shadow_alpha))
        self.setGraphicsEffect(shadow)


class GlowOrb(QWidget):
    def __init__(self, color: QColor, diameter: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._diameter = diameter
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(diameter, diameter)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QRadialGradient(QPointF(self.rect().center()), self.width() / 2)
        inner = QColor(self._color)
        inner.setAlpha(180)
        outer = QColor(self._color)
        outer.setAlpha(0)
        gradient.setColorAt(0.0, inner)
        gradient.setColorAt(1.0, outer)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(self.rect())


class GlassInputField(QFrame):
    def __init__(self, placeholder: str, *, password: bool = False):
        super().__init__()
        self.setObjectName("loginInputShell")
        self.setProperty("active", False)
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 12, 10)
        layout.setSpacing(10)

        self.line_edit = QLineEdit()
        self.line_edit.setObjectName("loginLineEdit")
        self.line_edit.setPlaceholderText(placeholder)
        if password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.line_edit.installEventFilter(self)
        layout.addWidget(self.line_edit, 1)

        self.trailing_widget: QWidget | None = None

    def apply_theme(self, theme_name: str) -> None:
        from PyQt6.QtGui import QPalette

        palette = get_palette(theme_name)
        line_palette = self.line_edit.palette()
        line_palette.setColor(QPalette.ColorRole.Text, QColor(palette["text"]))
        line_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(palette["muted"]))
        line_palette.setColor(QPalette.ColorRole.Highlight, QColor(palette["accent"]))
        line_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(palette["button_text_on_accent"]))
        self.line_edit.setPalette(line_palette)
        self.line_edit.update()


    def set_trailing_widget(self, widget: QWidget) -> None:
        if self.trailing_widget is not None:
            self.layout().removeWidget(self.trailing_widget)
        self.trailing_widget = widget
        self.layout().addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def eventFilter(self, watched, event):
        if watched is self.line_edit and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.setProperty("active", self.line_edit.hasFocus() or event.type() == QEvent.Type.FocusIn)
        refresh_style(self)
        return super().eventFilter(watched, event)


class FloatingArrowButton(QPushButton):
    """Round accent button with a '→' arrow, sits inside the password field."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("→", parent)
        self.setObjectName("floatingArrowButton")
        self.setFixedSize(38, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class OrDivider(QWidget):
    """Horizontal rule with centred '— or —' label."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        def _line() -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setObjectName("orLine")
            return line

        label = QPushButton("или")
        label.setFlat(True)
        label.setEnabled(False)
        label.setObjectName("orLabel")

        layout.addWidget(_line(), 1)
        layout.addWidget(label)
        layout.addWidget(_line(), 1)


class ThemeSwitch(QWidget):
    """Animated pill toggle that switches between light and dark themes."""

    theme_selected = pyqtSignal(str)

    _THEMES = ("light", "dark")

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current = "light"
        self._t: float = 0.0  # 0.0 = light, 1.0 = dark

        self.setFixedSize(64, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._anim = QPropertyAnimation(self, b"_anim_t", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── PyQt property for animation ──────────────────────────────────────────

    def _get_t(self) -> float:
        return self._t

    def _set_t(self, value: float) -> None:
        self._t = value
        self.update()

    _anim_t = pyqtProperty(float, _get_t, _set_t)

    # ── Public ───────────────────────────────────────────────────────────────

    def set_theme(self, theme_name: str) -> None:
        if theme_name not in self._THEMES or theme_name == self._current:
            return
        self._current = theme_name
        target = 1.0 if theme_name == "dark" else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(target)
        self._anim.start()

    # ── Events ───────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        next_theme = "dark" if self._current == "light" else "light"
        self.set_theme(next_theme)
        self.theme_selected.emit(next_theme)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track
        track_color = QColor(71, 245, 212, int(60 + 120 * self._t))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0, 4, 64, 24), 12, 12)

        # Icons: ☀ / ☽
        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(QPen(QColor(255, 255, 255, 180)))
        painter.drawText(QRectF(4, 4, 24, 24), Qt.AlignmentFlag.AlignCenter, "☀")
        painter.drawText(QRectF(36, 4, 24, 24), Qt.AlignmentFlag.AlignCenter, "☽")

        # Thumb
        thumb_x = 4 + self._t * 32
        thumb_color = QColor(255, 255, 255, 230)
        painter.setBrush(thumb_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(thumb_x, 6, 20, 20))
