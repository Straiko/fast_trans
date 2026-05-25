"""
Settings window for Olympus.

Design rationale (skills: apple-hig-expert, ui-design-system):
  • Clarity over decoration — no emoji-only navigation
  • Predictable forms — QFormLayout, plain helper copy
  • Thread-safe API test — QObject signal emitted from worker (queued to GUI thread)
  • No duplicate Qt signal connections (avoids double-save / flicker)
"""

from __future__ import annotations

import json
import logging
import threading

import requests
import speech_recognition as sr
from PyQt6.QtCore import QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mic_devices import SYSTEM_DEFAULT_INDEX, build_mic_entries
from ui_theme import APP_STYLESHEET

logger = logging.getLogger(__name__)

_NAV_LABELS = ['Hotkeys', 'Translation', 'Microphone', 'AI / API']

_PROVIDER_HELP: dict[str, str] = {
    'groq': (
        'Groq — free tier. Get a key: https://console.groq.com\nModel: llama-3.3-70b-versatile'
    ),
    'huggingface': (
        'Hugging Face — free inference token: https://huggingface.co/settings/tokens\n'
        'Model: Mixtral-8x7B (may be slow when busy)'
    ),
    'openai': (
        'OpenAI — paid usage: https://platform.openai.com/api-keys\n'
        'Model: gpt-4o-mini (connection test)'
    ),
    'anthropic': (
        'Anthropic — paid usage: https://console.anthropic.com\n'
        'Model: claude-3-5-haiku (connection test)'
    ),
}


class _ApiTestBridge(QObject):
    """Receives results from a background thread into the GUI thread."""

    finished = pyqtSignal(bool, str)


def _http_probe(provider: str, api_key: str) -> tuple[bool, str]:
    key = api_key.strip()
    if not key:
        return False, 'No API key entered'

    try:
        if provider == 'groq':
            r = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [{'role': 'user', 'content': 'ping'}],
                    'max_tokens': 1,
                },
                timeout=12,
            )
        elif provider == 'openai':
            r = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'gpt-4o-mini',
                    'messages': [{'role': 'user', 'content': 'ping'}],
                    'max_tokens': 1,
                },
                timeout=12,
            )
        elif provider == 'anthropic':
            r = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': 'claude-3-5-haiku-20241022',
                    'max_tokens': 1,
                    'messages': [{'role': 'user', 'content': 'ping'}],
                },
                timeout=12,
            )
        elif provider == 'huggingface':
            r = requests.post(
                'https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1',
                headers={'Authorization': f'Bearer {key}'},
                json={'inputs': 'ping', 'parameters': {'max_new_tokens': 1}},
                timeout=18,
            )
        else:
            return False, f'Unknown provider: {provider}'

        if r.status_code in (200, 201):
            return True, 'Connection OK'
        if r.status_code == 401:
            return False, 'Invalid API key (401)'
        if r.status_code == 429:
            return True, 'Key valid (rate limited 429)'
        return False, f'HTTP {r.status_code}'
    except requests.Timeout:
        return False, 'Request timed out'
    except Exception as exc:
        return False, str(exc)


class SettingsWindow(QWidget):
    def __init__(self, config: dict, save_callback) -> None:
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self._config_snapshot = json.loads(json.dumps(config))
        self._close_mode: str | None = None

        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.timeout.connect(self._flush_apply)

        self._api_test_bridge = _ApiTestBridge()
        self._api_test_bridge.finished.connect(self._on_test_result)

        self._mic_entries_all: list = []
        self._mic_filter_timer = QTimer(self)
        self._mic_filter_timer.setSingleShot(True)
        self._mic_filter_timer.timeout.connect(self._refill_mic_combo_after_filter)

        self._suspend_auto_apply = True
        self.init_ui()
        self._suspend_auto_apply = False
        self._wire_auto_apply()

    # ------------------------------------------------------------------
    def init_ui(self) -> None:
        self.setWindowTitle('Olympus — Settings')
        self.setMinimumSize(760, 640)
        self.resize(880, 700)
        self.setStyleSheet(APP_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        title = QLabel('Olympus')
        title.setObjectName('appTitleLabel')
        root.addWidget(title)

        subtitle = QLabel('Text and voice translation')
        subtitle.setObjectName('appSubtitleLabel')
        root.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName('headerSeparator')
        sep.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(sep)

        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        self.nav = QListWidget()
        self.nav.setFixedWidth(200)
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for label in _NAV_LABELS:
            it = QListWidgetItem(label)
            it.setSizeHint(QSize(0, 40))
            self.nav.addItem(it)
        body.addWidget(self.nav)

        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)

        self._build_pages()
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        sep2 = QFrame()
        sep2.setObjectName('headerSeparator')
        sep2.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(sep2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        hint = QLabel(
            'Changes save automatically. Cancel restores values from when this window opened.'
        )
        hint.setObjectName('autoHintLabel')
        hint.setWordWrap(True)
        btn_row.addWidget(hint, 1)

        cancel = QPushButton('Cancel')
        cancel.setObjectName('cancelButton')
        cancel.clicked.connect(self.cancel_settings)
        cancel.setMinimumWidth(100)
        btn_row.addWidget(cancel)

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.save_settings)
        close_btn.setMinimumWidth(100)
        btn_row.addWidget(close_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _build_pages(self) -> None:
        # --- Hotkeys ---
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        l0.setContentsMargins(0, 0, 0, 0)
        l0.setSpacing(12)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.hotkey_input = QLineEdit(self.config.get('hotkey', 'ctrl+shift+t'))
        self.voice_hotkey_input = QLineEdit(self.config.get('voice_hotkey', 'ctrl+shift+v'))

        form.addRow('Translate selection', self.hotkey_input)
        form.addRow('Voice input', self.voice_hotkey_input)

        g0 = QGroupBox('Hotkeys')
        g0.setLayout(form)
        l0.addWidget(g0)

        help_lbl = QLabel('Format: ctrl+shift+t — modifiers: ctrl, shift, alt, win')
        help_lbl.setObjectName('autoHintLabel')
        help_lbl.setWordWrap(True)
        l0.addWidget(help_lbl)
        l0.addStretch()
        self.pages.addWidget(p0)

        # --- Translation ---
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(12)

        tform = QFormLayout()
        tform.setHorizontalSpacing(14)
        tform.setVerticalSpacing(12)

        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(
            [
                'auto',
                'ru',
                'en',
                'uk',
                'pl',
                'de',
                'fr',
                'es',
                'it',
                'pt',
                'tr',
                'ar',
                'zh-cn',
                'ja',
                'ko',
            ]
        )
        self.source_lang_combo.setCurrentText(self.config.get('source_lang', 'auto'))

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(
            ['en', 'ru', 'uk', 'pl', 'de', 'fr', 'es', 'it', 'pt', 'tr', 'ar', 'zh-cn', 'ja', 'ko']
        )
        self.target_lang_combo.setCurrentText(self.config.get('target_lang', 'en'))

        tform.addRow('Source language', self.source_lang_combo)
        tform.addRow('Target language', self.target_lang_combo)

        g1 = QGroupBox('Translation')
        g1.setLayout(tform)
        l1.addWidget(g1)

        self.auto_replace_checkbox = QCheckBox('Replace selected text after translation')
        self.auto_replace_checkbox.setChecked(self.config.get('auto_replace', True))

        self.ai_enhance_checkbox = QCheckBox('Improve text with AI before translating')
        self.ai_enhance_checkbox.setChecked(self.config.get('ai_enhance', True))
        if not (self.config.get('api_key') or '').strip():
            self.ai_enhance_checkbox.setEnabled(False)

        l1.addWidget(self.auto_replace_checkbox)
        l1.addWidget(self.ai_enhance_checkbox)
        l1.addStretch()
        self.pages.addWidget(p1)

        # --- Microphone ---
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(12)

        mform = QFormLayout()
        mic_filter_row = QHBoxLayout()
        mic_filter_row.setSpacing(8)
        self.mic_filter = QLineEdit()
        self.mic_filter.setPlaceholderText('Filter by name…')
        self.mic_refresh_btn = QPushButton('Refresh')
        self.mic_refresh_btn.setObjectName('secondaryButton')
        self.mic_refresh_btn.clicked.connect(self._reload_mic_devices)
        mic_filter_row.addWidget(self.mic_filter, 1)
        mic_filter_row.addWidget(self.mic_refresh_btn)
        mic_filter_wrap = QWidget()
        mic_filter_wrap.setLayout(mic_filter_row)
        mform.addRow('Search', mic_filter_wrap)

        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumContentsLength(42)
        self._reload_mic_devices()
        mform.addRow('Input device', self.mic_combo)

        g2 = QGroupBox('Microphone')
        g2.setLayout(mform)
        l2.addWidget(g2)

        mic_help = QLabel(
            '“System default” follows the OS input (recommended). The list hides HDMI, monitors, '
            'loopbacks, and duplicate ALSA paths. Use search to find a device quickly.'
        )
        mic_help.setObjectName('autoHintLabel')
        mic_help.setWordWrap(True)
        l2.addWidget(mic_help)
        l2.addStretch()
        self.pages.addWidget(p2)

        # --- AI / API ---
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.setSpacing(12)

        aform = QFormLayout()
        aform.setHorizontalSpacing(14)
        aform.setVerticalSpacing(12)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(['groq', 'huggingface', 'openai', 'anthropic'])
        self.provider_combo.setCurrentText(self.config.get('api_provider', 'groq'))

        self.provider_info = QLabel()
        self.provider_info.setObjectName('providerInfoLabel')
        self.provider_info.setWordWrap(True)

        self.api_key_input = QLineEdit(self.config.get('api_key', ''))
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self.api_key_input, 1)
        self._reveal_btn = QPushButton('Show key')
        self._reveal_btn.setObjectName('secondaryButton')
        self._reveal_btn.setCheckable(True)
        self._reveal_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self._reveal_btn)

        aform.addRow('Provider', self.provider_combo)
        aform.addRow('', self.provider_info)
        aform.addRow('API key', key_row)

        g3 = QGroupBox('AI')
        g3.setLayout(aform)
        l3.addWidget(g3)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton('Test connection')
        self._test_btn.setObjectName('secondaryButton')
        self._test_btn.clicked.connect(self._test_api)
        self._test_btn.setEnabled(bool(self.api_key_input.text().strip()))
        test_row.addWidget(self._test_btn)

        self._test_status = QLabel('')
        self._test_status.setObjectName('autoHintLabel')
        test_row.addWidget(self._test_status, 1)

        l3.addLayout(test_row)
        l3.addStretch()
        self.pages.addWidget(p3)

        self.on_provider_changed(self.provider_combo.currentText())

    def _reload_mic_devices(self) -> None:
        """Re-query PortAudio and rebuild the curated list."""
        self._mic_entries_all = []
        try:
            raw = sr.Microphone.list_microphone_names()
        except Exception as exc:
            logger.error('Microphone load error: %s', exc)
            self.mic_combo.blockSignals(True)
            self.mic_combo.clear()
            self.mic_combo.addItem('Failed to load microphones', 0)
            self._select_mic_row_for_data(self.config.get('microphone_index', 0))
            self.mic_combo.blockSignals(False)
            return
        if not isinstance(raw, (list, tuple)):
            logger.warning('Unexpected microphone list type: %s', type(raw).__name__)
            raw = []
        device_names = [str(n) for n in raw]
        self._mic_entries_all = build_mic_entries(device_names)
        self._refill_mic_combo_after_filter(select_data=self.config.get('microphone_index', 0))

    def _refill_mic_combo_after_filter(self, select_data: int | None = None) -> None:
        """Apply search filter; keep selection when the device is still visible."""
        needle = self.mic_filter.text().strip().lower()
        prev = self.mic_combo.currentData() if self.mic_combo.count() else None
        pick = select_data if select_data is not None else prev
        if pick is None:
            pick = self.config.get('microphone_index', 0)

        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.addItem('System default (follow OS input)', SYSTEM_DEFAULT_INDEX)

        for e in self._mic_entries_all:
            if needle:
                hay = (e.label + '\n' + e.tooltip).lower()
                if needle not in hay:
                    continue
            self.mic_combo.addItem(e.label, e.index)
            row = self.mic_combo.count() - 1
            self.mic_combo.setItemData(row, e.tooltip, Qt.ItemDataRole.ToolTipRole)

        self._select_mic_row_for_data(pick)
        self.mic_combo.blockSignals(False)

    def _select_mic_row_for_data(self, data: object) -> None:
        if data is None:
            data = SYSTEM_DEFAULT_INDEX
        for i in range(self.mic_combo.count()):
            if self.mic_combo.itemData(i) == data:
                self.mic_combo.setCurrentIndex(i)
                return
        self.mic_combo.setCurrentIndex(0)

    def _schedule_mic_filter(self) -> None:
        self._mic_filter_timer.start(200)

    # ------------------------------------------------------------------
    def on_provider_changed(self, provider: str) -> None:
        self.provider_info.setText(_PROVIDER_HELP.get(provider, ''))

    def _toggle_key_visibility(self, visible: bool) -> None:
        self.api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self._reveal_btn.setText('Hide key' if visible else 'Show key')

    def _test_api(self) -> None:
        key = self.api_key_input.text()
        provider = self.provider_combo.currentText()
        self._test_btn.setEnabled(False)
        self._test_status.setText('Testing…')

        def _run() -> None:
            ok, msg = _http_probe(provider, key)
            self._api_test_bridge.finished.emit(ok, msg)

        threading.Thread(target=_run, daemon=True).start()

    def _on_test_result(self, ok: bool, msg: str) -> None:
        self._test_status.setText(('OK — ' if ok else 'Error — ') + msg)
        self._test_btn.setEnabled(True)
        QTimer.singleShot(8000, lambda: self._test_status.setText(''))

    # ------------------------------------------------------------------
    def _sync_ui_to_config(self) -> None:
        self.config['hotkey'] = self.hotkey_input.text().strip()
        self.config['voice_hotkey'] = self.voice_hotkey_input.text().strip()
        self.config['auto_replace'] = self.auto_replace_checkbox.isChecked()
        self.config['ai_enhance'] = self.ai_enhance_checkbox.isChecked()
        self.config['source_lang'] = self.source_lang_combo.currentText()
        self.config['target_lang'] = self.target_lang_combo.currentText()
        self.config['api_provider'] = self.provider_combo.currentText()
        self.config['api_key'] = self.api_key_input.text()
        mic_data = self.mic_combo.currentData()
        self.config['microphone_index'] = mic_data if mic_data is not None else 0

    def _flush_apply(self) -> None:
        self._sync_ui_to_config()
        self.save_callback()

    def _schedule_apply(self) -> None:
        if self._suspend_auto_apply:
            return
        self._apply_timer.start(280)

    def _apply_now(self) -> None:
        if self._suspend_auto_apply:
            return
        self._apply_timer.stop()
        self._flush_apply()

    def _wire_auto_apply(self) -> None:
        self.auto_replace_checkbox.stateChanged.connect(lambda *_: self._schedule_apply())
        self.ai_enhance_checkbox.stateChanged.connect(lambda *_: self._schedule_apply())
        self.mic_combo.currentIndexChanged.connect(lambda *_: self._schedule_apply())
        self.mic_filter.textChanged.connect(self._schedule_mic_filter)
        self.source_lang_combo.currentTextChanged.connect(lambda *_: self._schedule_apply())
        self.target_lang_combo.currentTextChanged.connect(lambda *_: self._schedule_apply())

        self.provider_combo.currentTextChanged.connect(self._on_provider_combo_changed)

        self.hotkey_input.editingFinished.connect(self._apply_now)
        self.voice_hotkey_input.editingFinished.connect(self._apply_now)
        self.api_key_input.editingFinished.connect(self._on_api_key_edited)
        self.api_key_input.editingFinished.connect(self._apply_now)

    def _on_provider_combo_changed(self, text: str) -> None:
        """Single entry point: update help + persist (once)."""
        self.on_provider_changed(text)
        self._schedule_apply()

    def _on_api_key_edited(self) -> None:
        has = bool(self.api_key_input.text().strip())
        self.ai_enhance_checkbox.setEnabled(has)
        self._test_btn.setEnabled(has)
        if not has:
            self.ai_enhance_checkbox.setChecked(False)

    # ------------------------------------------------------------------
    def cancel_settings(self) -> None:
        self._apply_timer.stop()
        self.config.clear()
        self.config.update(json.loads(json.dumps(self._config_snapshot)))
        self.save_callback()
        self._close_mode = 'cancel'
        self.close()

    def save_settings(self) -> None:
        self._apply_timer.stop()
        self._sync_ui_to_config()
        self.save_callback()
        self._close_mode = 'save'
        self.close()

    def closeEvent(self, event) -> None:
        self._apply_timer.stop()
        mode = self._close_mode
        self._close_mode = None
        if mode in ('cancel', 'save'):
            event.accept()
            return
        self._sync_ui_to_config()
        self.save_callback()
        event.accept()
