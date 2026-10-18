"""
Hotkey listener: intercepts shortcuts and triggers translation / voice input.
"""

import contextlib
import logging
import threading
import time

import pyperclip

from input_backend import (
    capture_selected_text,
    degraded_input_mode,
    get_backend,
    paste_text,
    set_clipboard_and_primary,
)

logger = logging.getLogger(__name__)


class KeyboardListener:
    def __init__(self, config: dict, translator, voice_input=None) -> None:
        self.config = config
        self.translator = translator
        self.running = False
        self.voice_input = voice_input
        from collections.abc import Callable

        self.translation_done: Callable[[str, bool], None] | None = None

    def start(self) -> None:
        self.running = True
        backend = get_backend()
        hotkey = self.config.get('hotkey', 'ctrl+shift+t')
        voice_hotkey = self.config.get('voice_hotkey', 'ctrl+shift+v')
        try:
            logger.info('  Translate hotkey: %s', hotkey)
            logger.info('  Voice hotkey:     %s', voice_hotkey)
            backend.start_hotkeys(
                [
                    (hotkey, self.on_translate_hotkey),
                    (voice_hotkey, self.on_voice_hotkey),
                ]
            )
            if degraded_input_mode():
                logger.warning('  Global hotkeys not available (pynput missing).')
            else:
                logger.info('  Hotkeys registered.')
        except Exception as e:
            logger.error('  Hotkey registration failed: %s', e)
            logger.info('  Falling back to defaults: ctrl+shift+t / ctrl+shift+v')
            fallback_hotkey = 'ctrl+shift+t'
            fallback_voice = 'ctrl+shift+v'
            try:
                backend.stop_hotkeys()
                backend.start_hotkeys(
                    [
                        (fallback_hotkey, self.on_translate_hotkey),
                        (fallback_voice, self.on_voice_hotkey),
                    ]
                )
                if degraded_input_mode():
                    logger.warning('  Retry failed — pynput unavailable (Linux without root).')
                else:
                    logger.info('  Default hotkeys registered.')
            except Exception as e2:
                logger.error('  Retry failed: %s', e2)

    def stop(self) -> None:
        self.running = False
        get_backend().stop_hotkeys()

    def on_translate_hotkey(self) -> None:
        thread = threading.Thread(target=self._do_translate)
        thread.daemon = True
        thread.start()

    def _do_translate(self) -> None:
        try:
            auto_replace = self.config.get('auto_replace', True)
            backend = get_backend()

            logger.info('  Capturing selection and translating…')
            clipboard_before = None
            with contextlib.suppress(Exception):
                clipboard_before = pyperclip.paste()

            selected_text = capture_selected_text(
                pyperclip_module=pyperclip,
                backend=backend,
                clipboard_before=clipboard_before,
            )

            if not selected_text or not selected_text.strip():
                logger.warning('  No text found — select text and try again.')
                return

            logger.info('  Source (%d chars): %.50s…', len(selected_text), selected_text)

            if self.config.get('ai_enhance', True) and self.translator.llm_available():
                enhanced = self.translator.enhance_text(selected_text)
                if enhanced != selected_text:
                    logger.info('  AI enhanced: %.50s…', enhanced)
                selected_text = enhanced

            translated = self.translator.translate(selected_text)
            logger.info('  Result: %.50s…', translated)

            if auto_replace:
                paste_text(
                    translated,
                    pyperclip_module=pyperclip,
                    backend=backend,
                )
                logger.info('  Selection replaced with translation.')
                if self.config.get('restore_clipboard', True) and clipboard_before is not None:
                    with contextlib.suppress(Exception):
                        time.sleep(0.4)
                        pyperclip.copy(clipboard_before)
            else:
                set_clipboard_and_primary(translated, pyperclip_module=pyperclip)
                logger.info('  Translation copied to clipboard — press paste to insert.')

            if self.translation_done is not None:
                self.translation_done(translated, auto_replace)

        except Exception as e:
            logger.error('  Translation error: %s', e, exc_info=True)

    def on_voice_hotkey(self) -> None:
        if self.voice_input is None:
            from voice_input import VoiceInput

            self.voice_input = VoiceInput(self.config, self.translator)

        if self.voice_input.is_recording:
            logger.info('  Voice hotkey pressed again — stopping recording.')
            self.voice_input.stop_recording = True
            if self.voice_input.recording_window:
                self.voice_input.recording_window.close()
        else:
            self.voice_input.start_recording()
