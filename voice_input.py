"""
Voice input: microphone capture and speech recognition.

Intentionally minimal UI — recording feedback is via tray / logs.
(Animated overlay windows are easy to get wrong across threads and platforms.)
"""

import logging
import threading
import time

import pyperclip
import speech_recognition as sr
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget

from input_backend import send_key_combo

logger = logging.getLogger(__name__)

RECOGNITION_LANG_MAP: dict[str, str] = {
    'auto': 'ru-RU',
    'ru': 'ru-RU',
    'en': 'en-US',
    'uk': 'uk-UA',
    'pl': 'pl-PL',
    'de': 'de-DE',
    'fr': 'fr-FR',
    'es': 'es-ES',
    'it': 'it-IT',
    'pt': 'pt-BR',
    'tr': 'tr-TR',
    'ar': 'ar-SA',
    'zh-cn': 'zh-CN',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
}


class VoiceTranslateThread(QThread):
    corrected_ready = pyqtSignal(str)
    translation_done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, translator, text: str, fix_first: bool) -> None:
        super().__init__()
        self._translator = translator
        self._text = text
        self._fix_first = fix_first

    def run(self) -> None:
        try:
            text = self._text
            if self._fix_first:
                fixed = self._translator.fix_speech_recognition_errors(text)
                self.corrected_ready.emit(fixed)
                text = fixed
            final = self._translator.translate(text)
            self.translation_done.emit(final)
        except Exception as e:
            self.failed.emit(str(e))


class RecordingWindow(QWidget):
    """Legacy placeholder — hotkey flow does not open a window."""

    def __init__(self, voice_input: 'VoiceInput') -> None:
        super().__init__()
        self.voice_input = voice_input


class VoiceInput:
    def __init__(self, config: dict, translator) -> None:
        self.config = config
        self.translator = translator
        self.recognizer = sr.Recognizer()
        self.is_recording = False
        self.stop_recording = False
        self.recording_window: RecordingWindow | None = None

    def start_recording(self) -> None:
        if self.is_recording:
            logger.info('Stopping recording…')
            self.stop_recording = True
            if self.recording_window:
                self.recording_window.close()
            return

        self.is_recording = True
        self.stop_recording = False
        threading.Thread(target=self._record_audio_simple, daemon=True).start()

    def _record_audio_simple(self) -> None:
        try:
            mic_index = self.config.get('microphone_index', -1)
            if mic_index == -1:
                logger.info('Microphone: system default (no fixed device index)')
                mic_ctx = sr.Microphone()
            else:
                logger.info('Microphone device index %s', mic_index)
                try:
                    mic_ctx = sr.Microphone(device_index=mic_index)
                except OSError as e:
                    logger.error(
                        'Failed to open microphone %s: %s, falling back to default', mic_index, e
                    )
                    mic_ctx = sr.Microphone()

            with mic_ctx as source:
                logger.info('Adjusting for ambient noise…')
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.recognizer.energy_threshold = 50
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.pause_threshold = 2.0

                logger.info('Speak now (auto-stops after silence)…')
                audio = self.recognizer.listen(source, timeout=30, phrase_time_limit=60)

                logger.info('Processing…')
                src_lang = (self.config.get('source_lang') or 'auto').strip().lower()
                recognition_lang = RECOGNITION_LANG_MAP.get(src_lang, 'ru-RU')
                text = self.recognizer.recognize_google(audio, language=recognition_lang)
                logger.info('Recognized: %s', text)

                if self.config.get('ai_enhance', True) and self.translator.llm_available():
                    text = self.translator.enhance_text(text)

                translated = self.translator.translate(text)
                logger.info('Translated: %s', translated)
                pyperclip.copy(translated)
                time.sleep(0.08)
                send_key_combo('ctrl+v')

        except sr.WaitTimeoutError:
            logger.warning('Timeout — no speech detected')
        except sr.UnknownValueError:
            logger.warning('Speech not recognized')
        except sr.RequestError as e:
            logger.error('Recognition service error: %s', e)
        except OSError as e:
            logger.error('Microphone error: %s', e, exc_info=True)
        except Exception as e:
            logger.error('Voice recording error: %s', e, exc_info=True)
        finally:
            self.is_recording = False
            self.stop_recording = False
