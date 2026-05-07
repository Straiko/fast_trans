#!/usr/bin/env python3
"""
Olympus — text & voice translator
  • Hotkey: translate selected text
  • Voice input: speech → text → translation
  • AI enhancement: optimise text for neural networks
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config_validator import validate_config
from input_backend import degraded_input_mode
from keyboard_listener import KeyboardListener
from settings_window import SettingsWindow
from translator import Translator
from ui_theme import (
    APP_STYLESHEET,
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ICON_STROKE,
    apply_app_palette,
)
from voice_input import VoiceInput

logger = logging.getLogger(__name__)

_XDG_CONFIG_DIR = Path.home() / '.config' / 'olympus'
_XDG_CONFIG_PATH = _XDG_CONFIG_DIR / 'config.json'
_LEGACY_CONFIG_PATH = Path.home() / '.text_translator_config.json'


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )


def _resolve_config_path() -> Path:
    """XDG path with automatic legacy-config migration."""
    if _XDG_CONFIG_PATH.exists():
        return _XDG_CONFIG_PATH

    if _LEGACY_CONFIG_PATH.exists():
        _XDG_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            _LEGACY_CONFIG_PATH.rename(_XDG_CONFIG_PATH)
            logger.info("Config migrated: %s → %s", _LEGACY_CONFIG_PATH, _XDG_CONFIG_PATH)
        except OSError:
            try:
                import shutil
                shutil.copy2(str(_LEGACY_CONFIG_PATH), str(_XDG_CONFIG_PATH))
                logger.info("Config copied: %s → %s", _LEGACY_CONFIG_PATH, _XDG_CONFIG_PATH)
            except Exception as e:
                logger.error("Config migration failed: %s", e)
        return _XDG_CONFIG_PATH

    _XDG_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return _XDG_CONFIG_PATH


class TranslatorApp:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        apply_app_palette(self.app)
        self.app.setStyleSheet(APP_STYLESHEET)
        self.config_path = _resolve_config_path()
        self.config = self.load_config()

        self.translator = Translator(self.config)
        self.voice_input = VoiceInput(self.config, self.translator)
        self.keyboard_listener = KeyboardListener(
            self.config, self.translator, voice_input=self.voice_input
        )
        self.keyboard_listener.translation_done = self._on_translation_done
        self.settings_window: SettingsWindow | None = None

        self.setup_tray()
        self.keyboard_listener.start()
        if degraded_input_mode():
            self.tray.showMessage(
                'Olympus',
                'Hotkeys and auto-paste are disabled — install pynput '
                '(pip install six pynput). See console output for details.',
                QSystemTrayIcon.MessageIcon.Warning,
                20000,
            )

    def load_config(self) -> dict:
        default_config: dict = {
            'hotkey': 'ctrl+shift+t',
            'voice_hotkey': 'ctrl+shift+v',
            'auto_replace': True,
            'ai_enhance': True,
            'source_lang': 'auto',
            'target_lang': 'en',
            'api_key': '',
            'api_provider': 'groq',
            'microphone_index': -1,
        }

        real_user = os.environ.get('SUDO_USER')
        if real_user:
            self.config_path = Path(f'/home/{real_user}/.config/olympus/config.json')

        if self.config_path.exists():
            try:
                with open(self.config_path, encoding='utf-8') as f:
                    config = json.load(f)
                    if not isinstance(config, dict):
                        logger.error("Config file is not a valid JSON object, using defaults")
                        return default_config
                    default_config.update(config)
                    logger.info("Config loaded from %s", self.config_path)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse config JSON: %s, using defaults", e)
            except Exception as e:
                logger.error("Failed to load config: %s, using defaults", e)

        return validate_config(default_config)

    def save_config(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info("Config saved to %s", self.config_path)
            self.reload_settings()
        except Exception as e:
            logger.error("Failed to save config: %s", e, exc_info=True)

    def reload_settings(self) -> None:
        logger.info("Applying settings…")
        self.keyboard_listener.stop()
        # Give pynput's listener thread time to fully unregister before starting a new one.
        time.sleep(0.2)

        self.translator.config = self.config
        self.keyboard_listener = KeyboardListener(
            self.config, self.translator, voice_input=self.voice_input
        )
        self.keyboard_listener.translation_done = self._on_translation_done
        self.keyboard_listener.start()
        logger.info("Settings applied — hotkeys active.")

    def create_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, 64, 64)
        gradient.setColorAt(0, QColor(COLOR_ACCENT))
        gradient.setColorAt(1, QColor(COLOR_ACCENT_HOVER))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(8, 8, 48, 48, 12, 12)

        painter.setPen(
            QPen(QColor(COLOR_ICON_STROKE), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawLine(20, 24, 36, 24)
        painter.drawLine(32, 20, 36, 24)
        painter.drawLine(32, 28, 36, 24)
        painter.drawLine(44, 40, 28, 40)
        painter.drawLine(32, 36, 28, 40)
        painter.drawLine(32, 44, 28, 40)

        painter.end()
        return QIcon(pixmap)

    def setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.app)
        self.tray.setIcon(self.create_icon())
        self.tray.setToolTip('Olympus')
        self.tray.activated.connect(self.on_tray_activated)

        menu = QMenu()

        settings_action = QAction('Settings', self.app)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        menu.addSeparator()

        quit_action = QAction('Quit', self.app)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()
        self.show_settings()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings()

    def show_settings(self) -> None:
        """Show the settings window; reuse the existing instance if already open."""
        if self.settings_window is not None:
            try:
                if not self.settings_window.isHidden():
                    self.settings_window.raise_()
                    self.settings_window.activateWindow()
                    return
            except RuntimeError:
                pass  # underlying C++ Qt object was already deleted
        self.settings_window = SettingsWindow(self.config, self.save_config)
        self.settings_window.show()

    def _on_translation_done(self, translated_text: str, auto_replace: bool) -> None:
        msg = 'Translation pasted' if auto_replace else 'Translation copied — press Ctrl+V to paste'
        self.tray.showMessage('Olympus', msg, QSystemTrayIcon.MessageIcon.Information, 3000)

    def quit(self) -> None:
        self.keyboard_listener.stop()
        self.app.quit()

    def run(self) -> int:
        return self.app.exec()


if __name__ == '__main__':
    _setup_logging()
    app = TranslatorApp()
    sys.exit(app.run())
