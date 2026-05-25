"""
Olympus UI theme — calm dark utility (Apple HIG–inspired: clarity, deference, depth).

Not a pixel-perfect Apple clone on Qt, but the same priorities:
  • High-contrast readable text
  • One clear accent, minimal decoration
  • Comfortable tap targets (controls ≥ 40px tall)
  • Visible keyboard focus
"""

from PyQt6.QtGui import QColor, QPalette

# --- Neutrals (depth) ---------------------------------------------------------
COLOR_BASE = '#0f0e14'
# Tray icon stroke (dark line on top of accent fill)
COLOR_ICON_STROKE = COLOR_BASE
COLOR_SURFACE = '#18161f'
COLOR_ELEVATED = '#1f1d28'
COLOR_BORDER = '#2e2c3d'
COLOR_BORDER_STRONG = '#3d3a4f'

# --- Text -------------------------------------------------------------------
COLOR_TEXT = '#f4f2f8'
COLOR_SECONDARY = '#c8c4d8'
COLOR_TERTIARY = '#9088a4'

# --- Accent (single hue — violet) ------------------------------------------
COLOR_ACCENT = '#7c6cf6'
COLOR_ACCENT_HOVER = '#9488ff'
COLOR_ACCENT_PRESSED = '#6558e6'
COLOR_FOCUS_RING = '#b8b0ff'

COLOR_ON_ACCENT = '#ffffff'

# --- Semantic ---------------------------------------------------------------
COLOR_DANGER = '#ef6a6a'
COLOR_DANGER_HOVER = '#e24f4f'
COLOR_SUCCESS = '#4ade80'
COLOR_WARNING = '#fbbf24'

# --- Glass panels (subtle — deference) --------------------------------------
GLASS_BG = 'rgba(28, 26, 36, 0.92)'
GLASS_BORDER = 'rgba(255, 255, 255, 0.06)'

# --- Typography (1.25-ish scale, base 13) -----------------------------------
FS_CAPTION = '11px'
FS_BODY = '13px'
FS_TITLE = '22px'

# --- Spacing (8-pt grid) ----------------------------------------------------
SPACE_2 = '8px'
SPACE_3 = '12px'
SPACE_4 = '16px'
SPACE_5 = '20px'
SPACE_6 = '24px'


def apply_app_palette(app) -> None:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(COLOR_BASE))
    p.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(COLOR_ELEVATED))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_SURFACE))
    p.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(COLOR_SURFACE))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_TEXT))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLOR_TERTIARY))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLOR_ELEVATED))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(COLOR_TEXT))
    p.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_ACCENT))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_ON_ACCENT))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(COLOR_TERTIARY))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(COLOR_TERTIARY))
    app.setPalette(p)
    app.setStyle('Fusion')


APP_STYLESHEET = f"""
QWidget {{
    font-family: 'Segoe UI', 'SF Pro Text', 'Inter', system-ui, sans-serif;
    font-size: {FS_BODY};
    color: {COLOR_TEXT};
    background: transparent;
}}

QLabel#appTitleLabel {{
    font-size: {FS_TITLE};
    font-weight: 700;
    letter-spacing: -0.4px;
    color: {COLOR_TEXT};
}}
QLabel#appSubtitleLabel {{
    font-size: {FS_CAPTION};
    color: {COLOR_TERTIARY};
}}
QLabel#autoHintLabel {{
    font-size: {FS_CAPTION};
    color: {COLOR_TERTIARY};
    line-height: 1.45;
}}
QLabel#providerInfoLabel {{
    font-size: {FS_CAPTION};
    color: {COLOR_SECONDARY};
    line-height: 1.5;
}}

QFrame#headerSeparator {{
    background: {COLOR_BORDER};
    max-height: 1px;
    min-height: 1px;
    margin: {SPACE_4} 0 {SPACE_3} 0;
}}

QListWidget {{
    background: {GLASS_BG};
    border: 1px solid {GLASS_BORDER};
    border-radius: 12px;
    padding: {SPACE_2};
    outline: none;
}}
QListWidget::item {{
    padding: 10px {SPACE_4};
    border-radius: 8px;
    color: {COLOR_SECONDARY};
    min-height: 22px;
}}
QListWidget::item:hover {{
    background: rgba(124, 108, 246, 0.08);
    color: {COLOR_TEXT};
}}
QListWidget::item:selected {{
    background: rgba(124, 108, 246, 0.16);
    color: {COLOR_TEXT};
    font-weight: 600;
}}

QGroupBox {{
    background: {GLASS_BG};
    border: 1px solid {GLASS_BORDER};
    border-radius: 12px;
    margin-top: {SPACE_5};
    padding: {SPACE_6} {SPACE_4} {SPACE_4} {SPACE_4};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {SPACE_4};
    padding: 0 {SPACE_2};
    color: {COLOR_TERTIARY};
    font-size: {FS_CAPTION};
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}}

QLineEdit, QComboBox {{
    background: {COLOR_BASE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 10px {SPACE_3};
    min-height: 20px;
    color: {COLOR_TEXT};
    font-size: {FS_BODY};
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: {COLOR_BORDER_STRONG};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 2px solid {COLOR_ACCENT};
    padding: 9px 11px;
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {COLOR_ACCENT};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {COLOR_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: rgba(124, 108, 246, 0.25);
}}

QCheckBox {{
    spacing: 10px;
    padding: 6px 0;
    font-size: {FS_BODY};
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 1px solid {COLOR_BORDER};
    background: {COLOR_BASE};
}}
QCheckBox::indicator:hover {{
    border-color: {COLOR_ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}

QPushButton {{
    background: {COLOR_ACCENT};
    color: {COLOR_ON_ACCENT};
    border: none;
    border-radius: 8px;
    padding: 11px {SPACE_5};
    min-height: 20px;
    font-weight: 600;
    font-size: {FS_BODY};
}}
QPushButton:hover {{ background: {COLOR_ACCENT_HOVER}; }}
QPushButton:pressed {{ background: {COLOR_ACCENT_PRESSED}; }}
QPushButton:focus {{
    border: 2px solid {COLOR_FOCUS_RING};
}}
QPushButton:disabled {{
    background: #2a2836;
    color: {COLOR_TERTIARY};
}}

QPushButton#cancelButton {{
    background: transparent;
    color: {COLOR_SECONDARY};
    border: 1px solid {COLOR_BORDER};
}}
QPushButton#cancelButton:hover {{
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
    background: rgba(124, 108, 246, 0.06);
}}

QPushButton#secondaryButton {{
    background: transparent;
    color: {COLOR_SECONDARY};
    border: 1px solid {COLOR_BORDER};
    padding: 9px {SPACE_4};
    font-size: {FS_CAPTION};
    font-weight: 600;
}}
QPushButton#secondaryButton:hover {{
    color: {COLOR_TEXT};
    border-color: {COLOR_BORDER_STRONG};
}}

QMenu {{
    background: {COLOR_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 4px;
}}
QMenu::item {{
    padding: 8px {SPACE_6};
    border-radius: 6px;
    color: {COLOR_SECONDARY};
}}
QMenu::item:selected {{
    background: rgba(124, 108, 246, 0.15);
    color: {COLOR_TEXT};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_STRONG};
    border-radius: 3px;
    min-height: 28px;
}}
"""
