from unittest.mock import MagicMock, patch

import pytest

from keyboard_listener import KeyboardListener


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


@pytest.fixture
def listener(default_config, translator):
    return KeyboardListener(default_config, translator)


class TestDoTranslateAutoReplace:
    @patch('keyboard_listener.get_backend')
    @patch('keyboard_listener.pyperclip')
    def test_auto_replace_success(self, mock_clip, mock_backend_cls, listener, translator):
        mock_backend = MagicMock()
        mock_backend_cls.return_value = mock_backend

        mock_clip.paste.side_effect = ['old clipboard', 'Привет мир', 'old clipboard']
        mock_clip.copy.return_value = None

        with patch.object(translator, 'translate', return_value='Hello world'):
            listener._do_translate()

        assert mock_clip.copy.call_count >= 2
        copy_calls = [c.args[0] for c in mock_clip.copy.call_args_list]
        assert 'Hello world' in copy_calls
        assert 'old clipboard' in copy_calls
        mock_backend.send.assert_any_call('ctrl+v')

    @patch('keyboard_listener.get_backend')
    @patch('keyboard_listener.pyperclip')
    def test_empty_selection_returns(self, mock_clip, mock_backend_cls, listener):
        mock_backend = MagicMock()
        mock_backend_cls.return_value = mock_backend
        mock_backend.send = MagicMock()

        mock_clip.paste.side_effect = ['old', '']
        listener._do_translate()

        mock_backend.send.assert_called_once_with('ctrl+c')

    @patch('keyboard_listener.get_backend')
    @patch('keyboard_listener.pyperclip')
    def test_translation_done_callback(self, mock_clip, mock_backend_cls, listener, translator):
        mock_backend = MagicMock()
        mock_backend_cls.return_value = mock_backend

        callback = MagicMock()
        listener.translation_done = callback

        mock_clip.paste.side_effect = ['old', 'Привет', 'old']
        mock_clip.copy.return_value = None

        with patch.object(translator, 'translate', return_value='Hello'):
            listener._do_translate()

        callback.assert_called_once_with('Hello', True)


class TestDoTranslateNoAutoReplace:
    @patch('keyboard_listener.pyperclip')
    def test_translate_from_clipboard(self, mock_clip, listener, translator):
        listener.config['auto_replace'] = False

        mock_clip.paste.return_value = 'Привет мир'
        mock_clip.copy.return_value = None

        with patch.object(translator, 'translate', return_value='Hello world'), \
             patch('keyboard_listener.get_backend'):
            listener._do_translate()

        assert mock_clip.copy.call_args[0][0] == 'Hello world'

    @patch('keyboard_listener.pyperclip')
    def test_empty_clipboard_returns(self, mock_clip, listener):
        listener.config['auto_replace'] = False
        mock_clip.paste.return_value = ''

        listener._do_translate()

    @patch('keyboard_listener.pyperclip')
    def test_whitespace_clipboard_returns(self, mock_clip, listener):
        listener.config['auto_replace'] = False
        mock_clip.paste.return_value = '   '

        listener._do_translate()


class TestDoTranslateError:
    @patch('keyboard_listener.pyperclip')
    def test_exception_handled(self, mock_clip, listener, translator):
        listener.config['auto_replace'] = False
        mock_clip.paste.return_value = 'text'

        with patch.object(translator, 'translate', side_effect=RuntimeError('fail')):
            listener._do_translate()


class TestOnTranslateHotkey:
    def test_spawns_thread(self, listener):
        with patch('keyboard_listener.threading.Thread') as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            listener.on_translate_hotkey()

            mock_thread_cls.assert_called_once_with(target=listener._do_translate)
            mock_thread.start.assert_called_once()


class TestOnVoiceHotkey:
    def test_starts_recording(self, listener):
        mock_vi = MagicMock()
        mock_vi.is_recording = False
        listener.voice_input = mock_vi

        listener.on_voice_hotkey()

        mock_vi.start_recording.assert_called_once()

    def test_stops_recording(self, listener):
        mock_vi = MagicMock()
        mock_vi.is_recording = True
        listener.voice_input = mock_vi

        listener.on_voice_hotkey()

        assert mock_vi.stop_recording is True

    def test_creates_voice_input_if_none(self, listener):
        listener.voice_input = None

        with patch.dict('sys.modules', {'voice_input': MagicMock()}):
            mock_vi_mod = __import__('sys').modules['voice_input']
            mock_vi = MagicMock()
            mock_vi.is_recording = False
            mock_vi_mod.VoiceInput.return_value = mock_vi

            listener.on_voice_hotkey()

            mock_vi_mod.VoiceInput.assert_called_once()


class TestStop:
    def test_stop_calls_backend(self, listener):
        with patch('keyboard_listener.get_backend') as mock_backend_cls:
            mock_backend = MagicMock()
            mock_backend_cls.return_value = mock_backend

            listener.stop()

            mock_backend.stop_hotkeys.assert_called_once()
            assert listener.running is False
