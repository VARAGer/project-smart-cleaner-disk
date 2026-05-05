from __future__ import annotations

THEMES = {
    "dark": {
        "background": "#0f0f12",
        "background_alt": "#17171b",
        "surface": "#121216",
        "surface_alt": "#19191f",
        "card": "rgba(255, 255, 255, 0.05)",
        "card_soft": "rgba(255, 255, 255, 0.08)",
        "border": "rgba(255, 255, 255, 0.08)",
        "border_strong": "rgba(255, 255, 255, 0.14)",
        "text": "#f4f2ee",
        "muted": "#aca7a1",
        "accent": "#6f6b74",
        "accent_soft": "rgba(255, 255, 255, 0.06)",
        "accent_alt": "#8a868f",
        "success": "#8ea88a",
        "warning": "#b69a76",
        "danger": "#b57b7b",
        "review": "#c6b08f",
        "selection": "rgba(255, 255, 255, 0.10)",
    },
    "light": {
        "background": "#f4f0e8",
        "background_alt": "#ebe5dc",
        "surface": "#f8f5ef",
        "surface_alt": "#f0ebe4",
        "card": "rgba(255, 255, 255, 0.58)",
        "card_soft": "rgba(255, 255, 255, 0.78)",
        "border": "rgba(92, 86, 82, 0.12)",
        "border_strong": "rgba(92, 86, 82, 0.18)",
        "text": "#161616",
        "muted": "#6f6963",
        "accent": "#5f5a57",
        "accent_soft": "rgba(95, 90, 87, 0.08)",
        "accent_alt": "#8c8680",
        "success": "#5f7f5d",
        "warning": "#a17f57",
        "danger": "#9d5c5c",
        "review": "#7e7469",
        "selection": "rgba(95, 90, 87, 0.12)",
    },
}


def refresh_style(widget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_variant(widget, variant: str) -> None:
    widget.setProperty("variant", variant)
    refresh_style(widget)


def build_stylesheet(theme_name: str) -> str:
    palette = THEMES.get(theme_name, THEMES["dark"])
    return f"""
    * {{
        color: {palette["text"]};
        font-family: "Segoe UI Variable", "Bahnschrift", "Segoe UI";
        font-size: 14px;
    }}

    QWidget#appRoot {{
        background-color: qradialgradient(
            cx: 0.15, cy: 0.1, radius: 1.25,
            fx: 0.15, fy: 0.1,
            stop: 0 {palette["background_alt"]},
            stop: 0.45 {palette["background"]},
            stop: 1 {palette["background"]}
        );
    }}

    QFrame#shell {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 {palette["surface"]},
            stop: 1 {palette["surface_alt"]}
        );
        border: 1px solid {palette["border"]};
        border-radius: 28px;
    }}

    QWidget#screen,
    QStackedWidget {{
        background: transparent;
    }}

    QFrame#heroCard,
    QFrame#contentCard,
    QFrame#sidePanel,
    QFrame#statCard,
    QFrame#bundleCard {{
        background-color: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 24px;
    }}

    QFrame#heroCard {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 {palette["card"]},
            stop: 1 {palette["card_soft"]}
        );
        border: 1px solid {palette["border_strong"]};
    }}

    QFrame#bundleCard[review="true"] {{
        border: 1px solid rgba(198, 176, 143, 0.55);
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 1,
            stop: 0 rgba(198, 176, 143, 0.14),
            stop: 1 {palette["card"]}
        );
    }}

    QFrame#bundleCard[selected="true"] {{
        border: 1px solid {palette["accent"]};
        background-color: {palette["accent_soft"]};
    }}

    QLabel#eyebrow {{
        color: {palette["accent_alt"]};
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
    }}

    QLabel#heroTitle,
    QLabel#pageTitle {{
        font-family: "Bahnschrift SemiBold", "Segoe UI Variable";
        font-size: 30px;
        font-weight: 700;
    }}

    QLabel#sectionTitle {{
        font-family: "Bahnschrift SemiBold", "Segoe UI Variable";
        font-size: 20px;
        font-weight: 700;
    }}

    QLabel#cardTitle {{
        font-size: 18px;
        font-weight: 700;
    }}

    QLabel#subtitle,
    QLabel#mutedText {{
        color: {palette["muted"]};
    }}

    QLabel#metricValue {{
        font-family: "Bahnschrift SemiBold", "Segoe UI Variable";
        font-size: 24px;
        font-weight: 700;
    }}

    QLabel#metricLabel {{
        color: {palette["muted"]};
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }}

    QLabel#badge {{
        background-color: rgba(255, 255, 255, 0.06);
        color: {palette["accent"]};
        border: 1px solid {palette["border"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 700;
    }}

    QLabel#warningBadge {{
        background-color: rgba(255, 255, 255, 0.06);
        color: {palette["review"]};
        border: 1px solid {palette["border"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 700;
    }}

    QLabel#successBadge {{
        background-color: rgba(255, 255, 255, 0.06);
        color: {palette["success"]};
        border: 1px solid {palette["border"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 700;
    }}

    QLabel#bulletText {{
        padding: 4px 0;
        color: {palette["muted"]};
    }}

    QLineEdit,
    QComboBox,
    QSpinBox,
    QListWidget,
    QTableWidget {{
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid {palette["border"]};
        border-radius: 16px;
        padding: 10px 12px;
        selection-background-color: {palette["selection"]};
        selection-color: {palette["text"]};
    }}

    QLineEdit:focus,
    QComboBox:focus,
    QSpinBox:focus,
    QListWidget:focus,
    QTableWidget:focus {{
        border: 1px solid {palette["accent"]};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 26px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {palette["muted"]};
        margin-right: 10px;
    }}

    QPushButton {{
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 18px;
        padding: 12px 18px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.14);
    }}

    QPushButton:pressed {{
        background-color: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }}

    QPushButton[variant="accent"] {{
        background-color: rgba(255, 255, 255, 0.08);
        color: {palette["text"]};
        border: 1px solid rgba(255, 255, 255, 0.14);
    }}

    QPushButton[variant="ghost"] {{
        background-color: transparent;
        border: 1px solid rgba(255, 255, 255, 0.10);
    }}

    QPushButton[variant="danger"] {{
        background-color: rgba(181, 123, 123, 0.08);
        color: {palette["danger"]};
        border: 1px solid rgba(181, 123, 123, 0.22);
    }}

    QPushButton[variant="warning"] {{
        background-color: rgba(198, 176, 143, 0.08);
        color: {palette["review"]};
        border: 1px solid rgba(198, 176, 143, 0.22);
    }}

    QPushButton[variant="theme"] {{
        text-align: left;
        padding: 16px;
        background-color: rgba(255, 255, 255, 0.04);
    }}

    QPushButton[variant="theme"]:checked {{
        background-color: rgba(255, 255, 255, 0.10);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }}

    QPushButton:disabled {{
        color: {palette["muted"]};
        background-color: rgba(255, 255, 255, 0.03);
        border-color: {palette["border"]};
    }}

    QProgressBar {{
        background-color: rgba(127, 127, 127, 0.10);
        border: 1px solid {palette["border"]};
        border-radius: 12px;
        text-align: center;
        min-height: 18px;
        font-weight: 700;
    }}

    QProgressBar::chunk {{
        border-radius: 10px;
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 {palette["accent"]},
            stop: 1 {palette["accent_alt"]}
        );
    }}

    QHeaderView::section {{
        background-color: transparent;
        color: {palette["muted"]};
        border: none;
        border-bottom: 1px solid {palette["border"]};
        padding: 10px 8px;
        font-weight: 700;
    }}

    QTableWidget {{
        gridline-color: {palette["border"]};
        outline: none;
    }}

    QTableCornerButton::section {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {palette["border"]};
    }}

    QCheckBox {{
        spacing: 10px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 6px;
        border: 1px solid {palette["border_strong"]};
        background-color: rgba(127, 127, 127, 0.10);
    }}

    QCheckBox::indicator:checked {{
        background-color: {palette["accent"]};
        border: 1px solid {palette["accent"]};
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: {palette["border_strong"]};
        border-radius: 6px;
        min-height: 36px;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical,
    QScrollBar::left-arrow:vertical,
    QScrollBar::right-arrow:vertical {{
        border: none;
        background: transparent;
        height: 0;
    }}
    """