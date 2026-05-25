from __future__ import annotations


THEMES = {
    "dark": {
        "background": "#090c12",
        "background_alt": "#111722",
        "surface": "#0f141d",
        "surface_alt": "#151b27",
        "card": "rgba(15, 18, 28, 0.82)",
        "card_soft": "rgba(21, 27, 38, 0.94)",
        "border": "rgba(255, 255, 255, 0.10)",
        "border_strong": "rgba(255, 255, 255, 0.18)",
        "text": "#f8fbff",
        "muted": "#9ca8ba",
        "accent": "#47F5D4",
        "accent_soft": "rgba(71, 245, 212, 0.22)",
        "accent_alt": "#78a9ff",
        "success": "#44dc8c",
        "warning": "#f0c56f",
        "danger": "#ef7e7e",
        "review": "#63f0b0",
        "selection": "rgba(71, 245, 212, 0.22)",
        "button_text_on_accent": "#061412",
        "dialog_bg": "#141922",
    },
    "light": {
        "background": "#edf4f8",
        "background_alt": "#d6e1e9",
        "surface": "#ffffff",
        "surface_alt": "#f3f8fb",
        "card": "rgba(255, 255, 255, 0.94)",
        "card_soft": "rgba(255, 255, 255, 0.98)",
        "border": "rgba(89, 104, 119, 0.18)",
        "border_strong": "rgba(89, 104, 119, 0.30)",
        "text": "#10202b",
        "muted": "#5f6d78",
        "accent": "#47F5D4",
        "accent_soft": "rgba(71, 245, 212, 0.18)",
        "accent_alt": "#7ea5ff",
        "success": "#148762",
        "warning": "#a56f1f",
        "danger": "#c05f67",
        "review": "#168967",
        "selection": "rgba(71, 245, 212, 0.18)",
        "button_text_on_accent": "#07221c",
        "dialog_bg": "#f8fbff",
    },
}


def get_palette(theme_name: str) -> dict[str, str]:
    return THEMES.get(theme_name, THEMES["light"]).copy()


def refresh_style(widget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_variant(widget, variant: str) -> None:
    widget.setProperty("variant", variant)
    refresh_style(widget)


def build_stylesheet(theme_name: str) -> str:
    palette = get_palette(theme_name)
    return f"""
    * {{
        color: {palette["text"]};
        font-family: "Segoe UI Variable", "Bahnschrift", "Segoe UI";
        font-size: 14px;
    }}

    QWidget#appRoot {{
        background-color: {palette["background"]};
    }}

    QFrame#shell {{
        background-color: {palette["background"]};
        border-radius: 18px;
    }}

    QFrame#heroCard {{
        background-color: {palette["surface"]};
        border: 1px solid {palette["border"]};
        border-radius: 18px;
    }}

    QFrame#contentCard {{
        background-color: {palette["surface_alt"]};
        border: 1px solid {palette["border"]};
        border-radius: 14px;
    }}

    QFrame#sidePanel {{
        background-color: {palette["background_alt"]};
        border: 1px solid {palette["border"]};
        border-radius: 14px;
    }}

    QFrame#statCard {{
        background-color: {palette["surface"]};
        border: 1px solid {palette["border"]};
        border-radius: 12px;
    }}

    QFrame#bundleCard {{
        background-color: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 14px;
    }}

    QFrame#bundleCard[review="true"] {{
        background-color: {palette["card_soft"]};
        border: 1px solid rgba(71, 245, 212, 0.28);
    }}

    QFrame#bundleCard[selected="true"] {{
        border: 2px solid {palette["accent"]};
        background-color: {palette["surface"]};
    }}

    QFrame#bundleCard[selected="true"][review="true"] {{
        background-color: {palette["surface"]};
        border: 2px solid {palette["accent"]};
    }}

    QFrame#bundleCard QLabel {{
        background: transparent;
        color: {palette["text"]};
    }}

    QWidget#loginScreen {{
        background-color: {palette["background"]};
    }}

    QFrame#loginCard {{
        background-color: {palette["card_soft"]};
        border: 1px solid {palette["border_strong"]};
        border-radius: 24px;
    }}

    QWidget#screen {{
        background-color: {palette["background"]};
    }}

    QLabel {{
        background: transparent;
    }}

    QLabel#pageTitle {{
        font-size: 26px;
        font-weight: 700;
        color: {palette["text"]};
    }}

    QLabel#sectionTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {palette["text"]};
    }}

    QLabel#cardTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {palette["text"]};
    }}

    QLabel#eyebrow {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.4px;
        color: {palette["accent"]};
        text-transform: uppercase;
    }}

    QLabel#subtitle {{
        font-size: 13px;
        color: {palette["muted"]};
    }}

    QLabel#mutedText {{
        font-size: 13px;
        color: {palette["muted"]};
    }}

    QLabel#metricValue {{
        font-size: 32px;
        font-weight: 700;
        color: {palette["text"]};
    }}

    QLabel#metricLabel {{
        font-size: 12px;
        color: {palette["muted"]};
    }}

    QLabel#badge {{
        font-size: 12px;
        font-weight: 600;
        color: {palette["accent_alt"]};
        background-color: rgba(120, 169, 255, 0.14);
        border: 1px solid rgba(120, 169, 255, 0.22);
        border-radius: 8px;
        padding: 3px 10px;
    }}

    QLabel#successBadge {{
        font-size: 12px;
        font-weight: 600;
        color: {palette["success"]};
        background-color: rgba(68, 220, 140, 0.12);
        border: 1px solid rgba(68, 220, 140, 0.24);
        border-radius: 8px;
        padding: 3px 10px;
    }}

    QLabel#warningBadge {{
        font-size: 12px;
        font-weight: 600;
        color: {palette["warning"]};
        background-color: rgba(240, 197, 111, 0.12);
        border: 1px solid rgba(240, 197, 111, 0.24);
        border-radius: 8px;
        padding: 3px 10px;
    }}

    QLabel#loginEyebrow {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.4px;
        color: {palette["accent"]};
    }}

    QLabel#loginTitle {{
        font-size: 22px;
        font-weight: 700;
        color: {palette["text"]};
    }}

    QLabel#loginSubtitle {{
        font-size: 13px;
        color: {palette["muted"]};
    }}

    QLabel#loginFooter {{
        font-size: 11px;
        color: {palette["muted"]};
    }}

    QPushButton {{
        background-color: {palette["card"]};
        border: 1px solid {palette["border_strong"]};
        border-radius: 12px;
        padding: 8px 18px;
        font-weight: 600;
        color: {palette["text"]};
    }}

    QPushButton:hover {{
        background-color: {palette["surface_alt"]};
        border-color: {palette["accent"]};
    }}

    QPushButton:pressed {{
        background-color: {palette["accent_soft"]};
    }}

    QPushButton[variant="accent"] {{
        background-color: {palette["accent"]};
        color: {palette["button_text_on_accent"]};
        border: none;
        border-radius: 12px;
        font-weight: 700;
    }}

    QPushButton[variant="accent"]:hover {{
        background-color: rgba(71, 245, 212, 0.88);
    }}

    QPushButton[variant="ghost"] {{
        background-color: transparent;
        border: 1px solid {palette["border_strong"]};
        color: {palette["muted"]};
    }}

    QPushButton[variant="ghost"]:hover {{
        background-color: {palette["surface_alt"]};
        color: {palette["text"]};
    }}

    QPushButton[variant="danger"] {{
        background-color: rgba(239, 126, 126, 0.12);
        color: {palette["danger"]};
        border: 1px solid rgba(239, 126, 126, 0.26);
    }}

    QPushButton[variant="warning"] {{
        background-color: rgba(240, 197, 111, 0.12);
        color: {palette["warning"]};
        border: 1px solid rgba(240, 197, 111, 0.26);
    }}

    QPushButton[variant="theme"] {{
        text-align: left;
        padding: 16px;
    }}

    QPushButton[variant="theme"]:checked {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 1, y2: 0,
            stop: 0 {palette["accent"]},
            stop: 1 rgba(150, 255, 234, 0.95)
        );
        color: {palette["button_text_on_accent"]};
        border: 1px solid rgba(255, 255, 255, 0.16);
    }}

    QPushButton#glassRegisterButton {{
        min-height: 56px;
        border-radius: 24px;
        padding: 14px 18px;
    }}

    QPushButton:disabled {{
        color: {palette["muted"]};
        background-color: rgba(255, 255, 255, 0.05);
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

    QCheckBox::indicator:hover {{
        border: 1px solid {palette["accent"]};
    }}

    QCheckBox::indicator:checked {{
        background-color: {palette["accent"]};
        border: 1px solid {palette["accent"]};
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollArea QWidget,
    QScrollArea > QWidget > QWidget {{
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

    QMessageBox {{
        background-color: {palette["dialog_bg"]};
    }}

    QMessageBox QLabel {{
        color: {palette["text"]};
        background: transparent;
        padding: 0;
    }}

    QMessageBox QLabel#qt_msgbox_label {{
        min-width: 0px;
    }}

    QMessageBox QPushButton {{
        min-width: 92px;
        min-height: 40px;
        border-radius: 18px;
        padding: 8px 18px;
        background-color: {palette["card"]};
        border: 1px solid {palette["border_strong"]};
        color: {palette["text"]};
    }}

    /* ── Tables ─────────────────────────────────────────────────────────── */

    QTableWidget, QTableView {{
        background-color: {palette["surface"]};
        alternate-background-color: {palette["surface_alt"]};
        color: {palette["text"]};
        border: 1px solid {palette["border"]};
        border-radius: 10px;
        gridline-color: {palette["border"]};
        selection-background-color: {palette["accent_soft"]};
        selection-color: {palette["text"]};
    }}

    QTableWidget::item, QTableView::item {{
        padding: 6px 10px;
        color: {palette["text"]};
        border: none;
    }}

    QTableWidget::item:selected, QTableView::item:selected {{
        background-color: {palette["accent_soft"]};
        color: {palette["text"]};
    }}

    QHeaderView {{
        background-color: {palette["background_alt"]};
        border: none;
    }}

    QHeaderView::section {{
        background-color: {palette["background_alt"]};
        color: {palette["muted"]};
        border: none;
        border-bottom: 1px solid {palette["border"]};
        border-right: 1px solid {palette["border"]};
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 600;
    }}

    QHeaderView::section:last {{
        border-right: none;
    }}

    /* ── SpinBox ─────────────────────────────────────────────────────────── */

    QSpinBox, QDoubleSpinBox {{
        background-color: {palette["surface"]};
        color: {palette["text"]};
        border: 1px solid {palette["border_strong"]};
        border-radius: 8px;
        padding: 6px 12px;
        min-height: 36px;
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {palette["accent"]};
    }}

    /* ── Login inputs ────────────────────────────────────────────────────── */

    QFrame#loginInputShell {{
        background-color: {palette["surface"]};
        border: 1.5px solid {palette["border_strong"]};
        border-radius: 14px;
    }}

    QFrame#loginInputShell[active="true"] {{
        border: 1.5px solid {palette["accent"]};
        background-color: {palette["surface_alt"]};
    }}

    QLineEdit#loginLineEdit {{
        background: transparent;
        border: none;
        color: {palette["text"]};
        font-size: 14px;
        padding: 0;
        selection-background-color: {palette["accent_soft"]};
    }}

    /* ── Floating arrow button (inside password field) ───────────────────── */

    QPushButton#floatingArrowButton {{
        background-color: {palette["accent"]};
        color: {palette["button_text_on_accent"]};
        border: none;
        border-radius: 19px;
        font-size: 16px;
        font-weight: 700;
        padding: 0;
    }}

    QPushButton#floatingArrowButton:hover {{
        background-color: rgba(71, 245, 212, 0.80);
    }}

    /* ── OrDivider ───────────────────────────────────────────────────────── */

    QFrame#orLine {{
        color: {palette["border_strong"]};
    }}

    QPushButton#orLabel {{
        color: {palette["muted"]};
        font-size: 12px;
        background: transparent;
        border: none;
        padding: 0 6px;
    }}
    """
