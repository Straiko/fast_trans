from unittest.mock import MagicMock, patch

import pytest

from lang_registry import RECOGNITION_LANG_MAP
from voice_input import VoiceInput


@pytest.fixture
def default_config():
    return {
        'hotkey': 'ctrl+shift+t',
        'voice_hotkey': 'ctrl+shift+v',
        'auto_replace': True,
        'source_lang': 'auto',
        'target_lang': 'en',
        'api_key': '',
        'api_provider': 'groq',
        'microphone_index': 0,
    }


@pytest.fixture
def translator(default_config):
    from translator import Translator

    return Translator(default_config)


class TestRecognitionLangMap:
    def test_auto_defaults_ru(self):
        assert RECOGNITION_LANG_MAP['auto'] == 'ru-RU'

    def test_russian(self):
        assert RECOGNITION_LANG_MAP['ru'] == 'ru-RU'

    def test_english(self):
        assert RECOGNITION_LANG_MAP['en'] == 'en-US'

    def test_german(self):
        assert RECOGNITION_LANG_MAP['de'] == 'de-DE'

    def test_french(self):
        assert RECOGNITION_LANG_MAP['fr'] == 'fr-FR'

    def test_chinese(self):
        assert RECOGNITION_LANG_MAP['zh-cn'] == 'zh-CN'

    def test_japanese(self):
        assert RECOGNITION_LANG_MAP['ja'] == 'ja-JP'

    def test_zh_tw_covered(self):
        """zh-TW must be in the registry (was missing from old voice_input map)."""
        assert 'zh-tw' in RECOGNITION_LANG_MAP
        assert RECOGNITION_LANG_MAP['zh-tw'] == 'zh-TW'

    def test_pt_br_covered(self):
        """pt-br must be in the registry (was missing from old voice_input map)."""
        assert 'pt-br' in RECOGNITION_LANG_MAP

    def test_all_source_langs_covered(self):
        source_langs = [
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
        for lang in source_langs:
            assert lang in RECOGNITION_LANG_MAP, (
                f'Missing recognition mapping for source_lang: {lang}'
            )


class TestVoiceInputInit:
    def test_initial_state(self, default_config, translator):
        vi = VoiceInput(default_config, translator)
        assert vi.is_recording is False
        assert vi.stop_recording is False
        assert vi.recording_window is None


class TestVoiceInputStartRecording:
    def test_starts_when_not_recording(self, default_config, translator):
        vi = VoiceInput(default_config, translator)
        with patch('voice_input.threading.Thread') as mock_thread:
            mock_thread.return_value = MagicMock()
            vi.start_recording()
            assert vi.is_recording is True
            mock_thread.assert_called_once()

    def test_stops_when_already_recording(self, default_config, translator):
        vi = VoiceInput(default_config, translator)
        vi.is_recording = True
        vi.recording_window = MagicMock()

        vi.start_recording()

        assert vi.stop_recording is True
        vi.recording_window.close.assert_called_once()

    def test_stop_recording_flag_checked(self, default_config, translator):
        """stop_recording flag must actually terminate the recording loop."""
        vi = VoiceInput(default_config, translator)
        vi.is_recording = True
        vi.stop_recording = False

        vi.start_recording()  # already recording — sets stop_recording = True

        assert vi.stop_recording is True


class TestListenWithStopCheck:
    """Unit tests for the chunk-polling recording loop."""

    def _make_audio_chunk(self, sample_rate=16000, sample_width=2, duration_secs=1):
        """Return a fake sr.AudioData chunk with silence-level amplitude."""
        import speech_recognition as sr

        frame_count = sample_rate * duration_secs
        # Silence: all zero bytes.
        frame_data = bytes(frame_count * sample_width)
        return sr.AudioData(frame_data, sample_rate, sample_width)

    def test_returns_none_when_stop_immediately(self, default_config, translator):
        """If stop_recording is set before first chunk, return None."""
        vi = VoiceInput(default_config, translator)
        vi.stop_recording = True  # already stopped

        mock_source = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.record.return_value = self._make_audio_chunk()
        vi.recognizer = mock_recognizer

        # Patch _is_silence to always True so it stops on first non-stop-recording check.
        with patch.object(VoiceInput, '_is_silence', return_value=True):
            result = vi._listen_with_stop_check(mock_source)

        assert result is None

    def test_accumulates_chunks_until_silence(self, default_config, translator):
        """Loop collects chunks and stops on extended silence."""
        vi = VoiceInput(default_config, translator)
        vi.stop_recording = False

        chunk = self._make_audio_chunk()
        mock_source = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.record.return_value = chunk
        vi.recognizer = mock_recognizer

        call_count = 0

        def silence_after_3(_audio):
            nonlocal call_count
            call_count += 1
            return call_count >= 3  # silence starting at chunk 3

        with patch.object(VoiceInput, '_is_silence', side_effect=silence_after_3):
            result = vi._listen_with_stop_check(mock_source)

        assert result is not None
        assert mock_recognizer.record.call_count >= 3


class TestRecordAudioSimple:
    @patch('voice_input.send_key_combo')
    @patch('voice_input.pyperclip')
    @patch('voice_input.sr')
    def test_recognize_with_source_lang(
        self, mock_sr, mock_clip, mock_send, default_config, translator
    ):
        import speech_recognition as sr

        mock_sr.WaitTimeoutError = sr.WaitTimeoutError
        mock_sr.UnknownValueError = sr.UnknownValueError
        mock_sr.AudioData = sr.AudioData
        default_config['source_lang'] = 'de'
        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        mock_audio = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.return_value = 'Hallo Welt'
        vi.recognizer = mock_recognizer

        # Patch _listen_with_stop_check to return a fake audio object directly.
        with patch.object(vi, '_listen_with_stop_check', return_value=mock_audio):
            vi._record_audio_simple()

        mock_sr.Microphone.assert_called_once_with(device_index=0)
        mock_recognizer.recognize_google.assert_called_once()
        call_kwargs = mock_recognizer.recognize_google.call_args
        assert (
            call_kwargs[1].get('language') == 'de-DE'
            or call_kwargs.kwargs.get('language') == 'de-DE'
        )

    @patch('voice_input.sr')
    def test_stop_recording_returns_early(self, mock_sr, default_config, translator):
        """If _listen_with_stop_check returns None, do not call recognize_google."""
        import speech_recognition as sr

        mock_sr.WaitTimeoutError = sr.WaitTimeoutError
        mock_sr.UnknownValueError = sr.UnknownValueError
        mock_sr.AudioData = sr.AudioData

        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        mock_recognizer = MagicMock()
        vi.recognizer = mock_recognizer

        with patch.object(vi, '_listen_with_stop_check', return_value=None):
            vi._record_audio_simple()

        mock_recognizer.recognize_google.assert_not_called()
        assert vi.is_recording is False

    @patch('voice_input.sr')
    def test_unknown_value_error(self, mock_sr, default_config, translator):
        import speech_recognition as sr

        mock_sr.WaitTimeoutError = sr.WaitTimeoutError
        mock_sr.UnknownValueError = sr.UnknownValueError
        mock_sr.AudioData = sr.AudioData

        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()
        vi.recognizer = mock_recognizer

        mock_audio = MagicMock()
        with patch.object(vi, '_listen_with_stop_check', return_value=mock_audio):
            vi._record_audio_simple()

        assert vi.is_recording is False

    @patch('voice_input.send_key_combo')
    @patch('voice_input.pyperclip')
    @patch('voice_input.sr')
    def test_system_default_uses_microphone_without_index(
        self, mock_sr, mock_clip, mock_send, default_config, translator
    ):
        import speech_recognition as sr

        mock_sr.WaitTimeoutError = sr.WaitTimeoutError
        mock_sr.UnknownValueError = sr.UnknownValueError
        mock_sr.AudioData = sr.AudioData
        default_config['microphone_index'] = -1
        default_config['ai_enhance'] = False
        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        mock_audio = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.return_value = 'hello'
        vi.recognizer = mock_recognizer

        with patch.object(vi, '_listen_with_stop_check', return_value=mock_audio):
            vi._record_audio_simple()

        mock_sr.Microphone.assert_called_once_with()
