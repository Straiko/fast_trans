"""
Hotkey listener: intercepts shortcuts and triggers translation / voice input.
"""

import logging
import threading
import time

import pyperclip

from input_backend import degraded_input_mode, get_backend

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
        try:
            logger.info("  Translate hotkey: %s", self.config['hotkey'])
            logger.info("  Voice hotkey:     %s", self.config['voice_hotkey'])
            backend.start_hotkeys(
                [
                    (self.config['hotkey'], self.on_translate_hotkey),
                    (self.config['voice_hotkey'], self.on_voice_hotkey),
                ]
            )
            if degraded_input_mode():
                logger.warning("  Global hotkeys not available (pynput missing).")
            else:
                logger.info("  Hotkeys registered.")
        except Exception as e:
            logger.error("  Hotkey registration failed: %s", e)
            logger.info("  Falling back to defaults: ctrl+shift+t / ctrl+shift+v")
            self.config['hotkey'] = 'ctrl+shift+t'
            self.config['voice_hotkey'] = 'ctrl+shift+v'
            try:
                backend.stop_hotkeys()
                backend.start_hotkeys(
                    [
                        (self.config['hotkey'], self.on_translate_hotkey),
                        (self.config['voice_hotkey'], self.on_voice_hotkey),
                    ]
                )
                if degraded_input_mode():
                    logger.warning("  Retry failed — pynput unavailable (Linux without root).")
                else:
                    logger.info("  Default hotkeys registered.")
            except Exception as e2:
                logger.error("  Retry failed: %s", e2)

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

            clipboard_before = None
            if auto_replace:
                logger.info("  Capturing selection (Ctrl+C) and translating…")
                clipboard_before = pyperclip.paste()
                time.sleep(0.2)
                get_backend().send('ctrl+c')
                time.sleep(0.15)
                selected_text = pyperclip.paste()

                if not selected_text or not selected_text.strip():
                    logger.warning("  No text found — select text and try again.")
                    return

                if selected_text == clipboard_before:
                    time.sleep(0.12)
                    get_backend().send('ctrl+c')
                    time.sleep(0.12)
                    selected_text_retry = pyperclip.paste()
                    if selected_text_retry and selected_text_retry.strip():
                        selected_text = selected_text_retry
                    if selected_text == clipboard_before and clipboard_before and clipboard_before.strip():
                        logger.info("  Clipboard unchanged — using current clipboard as source.")
                    elif selected_text == clipboard_before:
                        logger.warning("  Clipboard unchanged — nothing selected? Select text and retry.")
                        return
            else:
                logger.info("  Translating from clipboard (copy text with Ctrl+C first)…")
                selected_text = pyperclip.paste()
                if not selected_text or not selected_text.strip():
                    logger.warning("  Clipboard is empty — copy text first, then press hotkey.")
                    return

            logger.info("  Source (%d chars): %.50s…", len(selected_text), selected_text)

            if self.config.get('ai_enhance', True) and self.translator.llm_available():
                enhanced = self.translator.enhance_text(selected_text)
                if enhanced != selected_text:
                    logger.info("  AI enhanced: %.50s…", enhanced)
                selected_text = enhanced

            translated = self.translator.translate(selected_text)
            logger.info("  Result: %.50s…", translated)

            pyperclip.copy(translated)

            if auto_replace:
                time.sleep(0.08)
                get_backend().send('ctrl+v')
                logger.info("  Selection replaced with translation.")
                if clipboard_before is not None:
                    try:
                        time.sleep(0.3)
                        pyperclip.copy(clipboard_before)
                    except Exception:
                        pass
            else:
                logger.info("  Translation copied to clipboard — press Ctrl+V to paste.")

            if self.translation_done is not None:
                self.translation_done(translated, auto_replace)

        except Exception as e:
            logger.error("  Translation error: %s", e, exc_info=True)

    def on_voice_hotkey(self) -> None:
        if self.voice_input is None:
            from voice_input import VoiceInput
            self.voice_input = VoiceInput(self.config, self.translator)

        if self.voice_input.is_recording:
            logger.info("  Voice hotkey pressed again — stopping recording.")
            self.voice_input.stop_recording = True
            if self.voice_input.recording_window:
                self.voice_input.recording_window.close()
        else:
            self.voice_input.start_recording()
