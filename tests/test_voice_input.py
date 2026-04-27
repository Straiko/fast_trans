import pytest
from unittest.mock import patch, MagicMock
from voice_input import VoiceInput, VoiceTranslateThread, RECOGNITION_LANG_MAP


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

    def test_all_source_langs_covered(self):
        source_langs = ['auto', 'ru', 'en', 'uk', 'pl', 'de', 'fr', 'es', 'it', 'pt', 'tr', 'ar', 'zh-cn', 'ja', 'ko']
        for lang in source_langs:
            assert lang in RECOGNITION_LANG_MAP, f"Missing recognition mapping for source_lang: {lang}"


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


class TestRecordAudioSimple:
    @patch('voice_input.send_key_combo')
    @patch('voice_input.pyperclip')
    @patch('voice_input.sr')
    def test_recognize_with_source_lang(self, mock_sr, mock_clip, mock_send, default_config, translator):
        default_config['source_lang'] = 'de'
        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        mock_audio = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.listen.return_value = mock_audio
        mock_recognizer.recognize_google.return_value = 'Hallo Welt'
        vi.recognizer = mock_recognizer

        vi._record_audio_simple()

        mock_sr.Microphone.assert_called_once_with(device_index=0)
        mock_recognizer.recognize_google.assert_called_once()
        call_kwargs = mock_recognizer.recognize_google.call_args
        assert call_kwargs[1].get('language') == 'de-DE' or call_kwargs.kwargs.get('language') == 'de-DE'

    @patch('voice_input.sr')
    def test_timeout_error(self, mock_sr, default_config, translator):
        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        vi.recognizer = MagicMock()
        vi.recognizer.listen.side_effect = mock_sr.WaitTimeoutError()

        vi._record_audio_simple()

        assert vi.is_recording is False

    @patch('voice_input.sr')
    def test_unknown_value_error(self, mock_sr, default_config, translator):
        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        vi.recognizer = MagicMock()
        vi.recognizer.listen.side_effect = mock_sr.UnknownValueError()

        vi._record_audio_simple()

        assert vi.is_recording is False

    @patch('voice_input.send_key_combo')
    @patch('voice_input.pyperclip')
    @patch('voice_input.sr')
    def test_system_default_uses_microphone_without_index(
        self, mock_sr, mock_clip, mock_send, default_config, translator
    ):
        default_config['microphone_index'] = -1
        default_config['ai_enhance'] = False
        vi = VoiceInput(default_config, translator)

        mock_source = MagicMock()
        mock_sr.Microphone.return_value.__enter__ = MagicMock(return_value=mock_source)
        mock_sr.Microphone.return_value.__exit__ = MagicMock(return_value=False)

        mock_audio = MagicMock()
        mock_recognizer = MagicMock()
        mock_recognizer.listen.return_value = mock_audio
        mock_recognizer.recognize_google.return_value = 'hello'
        vi.recognizer = mock_recognizer

        vi._record_audio_simple()

        mock_sr.Microphone.assert_called_once_with()


class TestVoiceTranslateThread:
    def test_translate_without_fix(self):
        mock_translator = MagicMock()
        mock_translator.translate.return_value = 'Hello'

        thread = VoiceTranslateThread(mock_translator, 'Привет', fix_first=False)

        signals_emitted = []
        thread.translation_done.connect(lambda t: signals_emitted.append(('done', t)))

        thread.run()

        mock_translator.translate.assert_called_once_with('Привет')
        assert len(signals_emitted) == 1
        assert signals_emitted[0] == ('done', 'Hello')

    def test_translate_with_fix(self):
        mock_translator = MagicMock()
        mock_translator.fix_speech_recognition_errors.return_value = 'исправленный'
        mock_translator.translate.return_value = 'corrected'

        thread = VoiceTranslateThread(mock_translator, 'текст с ашыпками', fix_first=True)

        corrected = []
        done = []
        thread.corrected_ready.connect(lambda t: corrected.append(t))
        thread.translation_done.connect(lambda t: done.append(t))

        thread.run()

        mock_translator.fix_speech_recognition_errors.assert_called_once()
        assert corrected == ['исправленный']
        assert done == ['corrected']

    def test_error_emits_failed(self):
        mock_translator = MagicMock()
        mock_translator.translate.side_effect = RuntimeError('API down')

        thread = VoiceTranslateThread(mock_translator, 'text', fix_first=False)

        failed = []
        thread.failed.connect(lambda t: failed.append(t))

        thread.run()

        assert len(failed) == 1
