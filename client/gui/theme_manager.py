from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, pyqtSignal
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QWidget

from client.gui.theme import THEMES, build_stylesheet


class ThemeManager(QObject):
    theme_applied = pyqtSignal(str)

    def __init__(self, target: QWidget, initial_theme: str):
        super().__init__(target)
        self._target = target
        self._theme = initial_theme if initial_theme in THEMES else "light"
        self._animations: list[QPropertyAnimation] = []
        self._overlays: list[QLabel] = []

    def current_theme(self) -> str:
        return self._theme

    def set_theme(self, theme_name: str, *, animate: bool = True) -> None:
        theme_name = theme_name if theme_name in THEMES else "light"
        overlay = None

        if animate and self._target.isVisible():
            overlay = QLabel(self._target)
            overlay.setPixmap(self._target.grab())
            overlay.setScaledContents(True)
            overlay.setGeometry(self._target.rect())
            overlay.show()
            overlay.raise_()
            self._overlays.append(overlay)

        QApplication.instance().setStyleSheet(build_stylesheet(theme_name))
        self._theme = theme_name
        self.theme_applied.emit(theme_name)

        if overlay is None:
            return

        effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", overlay)
        animation.setDuration(280)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def cleanup() -> None:
            if overlay in self._overlays:
                self._overlays.remove(overlay)
            if animation in self._animations:
                self._animations.remove(animation)
            overlay.deleteLater()

        animation.finished.connect(cleanup)
        self._animations.append(animation)
        animation.start()