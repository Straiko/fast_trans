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
from PyQt6.QtWidgets import QWidget

from input_backend import send_key_combo
from lang_registry import RECOGNITION_LANG_MAP
from mic_devices import SYSTEM_DEFAULT_INDEX, suppress_c_stderr

logger = logging.getLogger(__name__)

# How long (seconds) each audio chunk is when polling stop_recording.
_CHUNK_DURATION = 1.0
# Maximum total recording time in seconds.
_MAX_RECORD_SECONDS = 60


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
            mic_index = self.config.get('microphone_index', SYSTEM_DEFAULT_INDEX)
            with suppress_c_stderr():
                if mic_index == SYSTEM_DEFAULT_INDEX:
                    logger.info('Microphone: system default (no fixed device index)')
                    mic_ctx = sr.Microphone()
                else:
                    logger.info('Microphone device index %s', mic_index)
                    try:
                        mic_ctx = sr.Microphone(device_index=mic_index)
                    except OSError as e:
                        logger.error(
                            'Failed to open microphone %s: %s, falling back to default',
                            mic_index,
                            e,
                        )
                        mic_ctx = sr.Microphone()

            with mic_ctx as source:
                logger.info('Adjusting for ambient noise…')
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.recognizer.energy_threshold = 50
                self.recognizer.dynamic_energy_threshold = True

                logger.info('Speak now (press hotkey again to stop early)…')
                audio = self._listen_with_stop_check(source)

            if audio is None:
                logger.info('Recording stopped by user.')
                return

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

    def _listen_with_stop_check(self, source: sr.AudioSource) -> sr.AudioData | None:
        """Record audio in short chunks, checking stop_recording between each.

        Returns combined AudioData, or None if user pressed stop before any speech.
        Uses sr.Recognizer.record() with duration= so the loop can be interrupted
        without waiting for the full phrase_time_limit / timeout to expire.
        """
        frames: list[bytes] = []
        sample_rate: int | None = None
        sample_width: int | None = None
        elapsed = 0.0

        while elapsed < _MAX_RECORD_SECONDS:
            if self.stop_recording:
                break
            chunk: sr.AudioData = self.recognizer.record(source, duration=_CHUNK_DURATION)
            if sample_rate is None:
                sample_rate = chunk.sample_rate
                sample_width = chunk.sample_width
            frames.append(chunk.frame_data)
            elapsed += _CHUNK_DURATION

            # Stop automatically after silence: check energy on last chunk.
            # Silence heuristic: mean absolute amplitude < threshold.
            if self._is_silence(chunk) and frames and len(frames) > 2:
                logger.debug('Silence detected — stopping recording.')
                break

        if not frames or sample_rate is None or sample_width is None:
            return None

        combined = b''.join(frames)
        return sr.AudioData(combined, sample_rate, sample_width)

    @staticmethod
    def _is_silence(audio: sr.AudioData, threshold: int = 200) -> bool:
        """Return True if the chunk is below the amplitude threshold (silence)."""
        import audioop

        try:
            rms = audioop.rms(audio.frame_data, audio.sample_width)
            return rms < threshold
        except Exception:
            return False
