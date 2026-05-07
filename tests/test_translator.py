from unittest.mock import MagicMock, patch

import pytest

from translator import LANG_MAP, Translator


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
    return Translator(default_config)


class TestLangMap:
    def test_zh_cn(self):
        assert LANG_MAP['zh-cn'] == 'zh-CN'

    def test_zh_tw(self):
        assert LANG_MAP['zh-tw'] == 'zh-TW'

    def test_pt_br(self):
        assert LANG_MAP['pt-br'] == 'pt-BR'

    def test_auto(self):
        assert LANG_MAP['auto'] == 'auto'

    def test_passthrough(self, translator):
        assert translator._map_lang('en') == 'en'
        assert translator._map_lang('ru') == 'ru'
        assert translator._map_lang('de') == 'de'


class TestTranslate:
    @patch('translator.DeepGoogleTranslator')
    def test_translate_auto_to_en(self, mock_deep_cls, translator):
        mock_inst = MagicMock()
        mock_inst.translate.return_value = 'Hello world'
        mock_deep_cls.return_value = mock_inst

        result = translator.translate('Привет мир')

        mock_deep_cls.assert_called_once_with(source='auto', target='en')
        mock_inst.translate.assert_called_once_with('Привет мир')
        assert result == 'Hello world'

    @patch('translator.DeepGoogleTranslator')
    def test_translate_ru_to_en(self, mock_deep_cls, translator):
        translator.config['source_lang'] = 'ru'
        mock_inst = MagicMock()
        mock_inst.translate.return_value = 'Hello'
        mock_deep_cls.return_value = mock_inst

        result = translator.translate('Привет')

        mock_deep_cls.assert_called_once_with(source='ru', target='en')
        assert result == 'Hello'

    @patch('translator.DeepGoogleTranslator')
    def test_translate_auto_target_defaults_to_en(self, mock_deep_cls, translator):
        translator.config['target_lang'] = 'auto'
        mock_inst = MagicMock()
        mock_inst.translate.return_value = 'result'
        mock_deep_cls.return_value = mock_inst

        translator.translate('text')

        assert mock_deep_cls.call_args[1]['target'] == 'en'

    @patch('translator.DeepGoogleTranslator')
    def test_translate_zh_cn_mapped(self, mock_deep_cls, translator):
        translator.config['source_lang'] = 'zh-cn'
        translator.config['target_lang'] = 'en'
        mock_inst = MagicMock()
        mock_inst.translate.return_value = 'hello'
        mock_deep_cls.return_value = mock_inst

        translator.translate('你好')

        mock_deep_cls.assert_called_once_with(source='zh-CN', target='en')

    def test_translate_exception_returns_original(self, translator):
        with patch('translator.DeepGoogleTranslator', side_effect=Exception('network error')):
            result = translator.translate('Привет')
            assert result == 'Привет'

    @patch('translator.DeepGoogleTranslator')
    def test_translate_empty_string(self, mock_deep_cls, translator):
        mock_inst = MagicMock()
        mock_inst.translate.return_value = ''
        mock_deep_cls.return_value = mock_inst

        result = translator.translate('')
        assert result == ''


class TestLlmAvailable:
    def test_no_key(self, translator):
        translator.config['api_key'] = ''
        assert translator.llm_available() is False

    def test_with_key(self, translator):
        translator.config['api_key'] = 'sk-123'
        assert translator.llm_available() is True

    def test_whitespace_only(self, translator):
        translator.config['api_key'] = '   '
        assert translator.llm_available() is False


class TestFixSpeechRecognitionErrors:
    def test_no_api_key_returns_original(self, translator):
        translator.config['api_key'] = ''
        result = translator.fix_speech_recognition_errors('текст')
        assert result == 'текст'

    @patch('translator.requests.post')
    def test_with_api_key(self, mock_post, translator):
        translator.config['api_key'] = 'gsk-abc'
        translator.config['api_provider'] = 'groq'

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'choices': [{'message': {'content': 'исправленный текст'}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator.fix_speech_recognition_errors('текст с ашыпками')
        assert result == 'исправленный текст'

    @patch('translator.requests.post', side_effect=Exception('fail'))
    def test_error_returns_original(self, mock_post, translator):
        translator.config['api_key'] = 'gsk-abc'
        result = translator.fix_speech_recognition_errors('текст')
        assert result == 'текст'


class TestCallChatApi:
    @patch('translator.requests.post')
    def test_openai_extract(self, mock_post, translator):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'choices': [{'message': {'content': 'hello'}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._call_chat_api(
            'https://api.openai.com/v1/chat/completions',
            {'Authorization': 'Bearer test'},
            {'model': 'gpt-4', 'messages': [{'role': 'user', 'content': 'hi'}]},
            extract='openai',
        )
        assert result == 'hello'
        mock_post.assert_called_once()
        assert mock_post.call_args[1].get('timeout') == 30 or mock_post.call_args.kwargs.get('timeout') == 30

    @patch('translator.requests.post')
    def test_anthropic_extract(self, mock_post, translator):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'content': [{'text': 'bonjour'}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._call_chat_api(
            'https://api.anthropic.com/v1/messages',
            {'x-api-key': 'test'},
            {'model': 'claude', 'messages': [{'role': 'user', 'content': 'hi'}]},
            extract='anthropic',
        )
        assert result == 'bonjour'

    def test_unknown_extract_raises(self, translator):
        with pytest.raises(ValueError, match='Unknown extract mode'), \
             patch('translator.requests.post') as mock_post:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {}
                mock_resp.raise_for_status = MagicMock()
                mock_post.return_value = mock_resp
                translator._call_chat_api('https://api.example.com', {}, {}, extract='invalid')


class TestRunLlmPrompt:
    def test_missing_api_key(self, translator):
        translator.config['api_key'] = ''
        with pytest.raises(ValueError, match='API key missing'):
            translator._run_llm_prompt('test')

    def test_unknown_provider(self, translator):
        translator.config['api_key'] = 'sk-abc'
        translator.config['api_provider'] = 'unknown'
        with pytest.raises(ValueError, match='Unknown API provider'):
            translator._run_llm_prompt('test')

    @patch('translator.requests.post')
    def test_groq_provider(self, mock_post, translator):
        translator.config['api_provider'] = 'groq'
        translator.config['api_key'] = 'gsk-abc'

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'choices': [{'message': {'content': 'result'}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._run_llm_prompt('test prompt')
        assert result == 'result'

    @patch('translator.requests.post')
    def test_openai_provider(self, mock_post, translator):
        translator.config['api_provider'] = 'openai'
        translator.config['api_key'] = 'sk-abc'

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'choices': [{'message': {'content': 'openai result'}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._run_llm_prompt('test prompt')
        assert result == 'openai result'

    @patch('translator.requests.post')
    def test_anthropic_provider(self, mock_post, translator):
        translator.config['api_provider'] = 'anthropic'
        translator.config['api_key'] = 'sk-ant-abc'

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'content': [{'text': 'claude result'}]}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._run_llm_prompt('test prompt')
        assert result == 'claude result'

    @patch('translator.requests.post')
    def test_huggingface_provider(self, mock_post, translator):
        translator.config['api_provider'] = 'huggingface'
        translator.config['api_key'] = 'hf_abc'

        mock_resp = MagicMock()
        mock_resp.json.return_value = [{'generated_text': 'test prompthf result'}]
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._run_llm_prompt('test prompt')
        assert result != 'test prompt'
