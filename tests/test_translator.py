from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest

from translator import LANG_MAP, Translator, _split_by_words


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
        with patch('translator.DeepGoogleTranslator', side_effect=Exception('google error')):
            with patch.object(translator, '_translate_mymemory', side_effect=Exception('mymemory error')):
                result = translator.translate('Привет')
                assert result == 'Привет'

    def test_translate_fallback_to_llm(self, translator):
        translator.config['api_key'] = 'sk-fake'
        with patch('translator.DeepGoogleTranslator', side_effect=Exception('429 TooManyRequests')):
            with patch.object(translator, 'translate_with_llm', return_value='LLM translated') as mock_llm:
                result = translator.translate('Привет')
                assert result == 'LLM translated'
                mock_llm.assert_called_once()

    def test_translate_fallback_to_mymemory(self, translator):
        with patch('translator.DeepGoogleTranslator', side_effect=Exception('429 TooManyRequests')):
            with patch.object(translator, '_translate_mymemory', return_value='MyMemory translated') as mock_mm:
                result = translator.translate('Привет')
                assert result == 'MyMemory translated'
                mock_mm.assert_called_once()

    def test_translate_full_fallback_chain(self, translator):
        """Google fails → LLM fails → MyMemory succeeds."""
        translator.config['api_key'] = 'sk-fake'
        with patch('translator.DeepGoogleTranslator', side_effect=Exception('google error')):
            with patch.object(translator, 'translate_with_llm', side_effect=Exception('llm error')):
                with patch.object(translator, '_translate_mymemory', return_value='MM result') as mock_mm:
                    result = translator.translate('Привет')
                    assert result == 'MM result'
                    mock_mm.assert_called_once()

    def test_translate_all_fail_returns_original(self, translator):
        """All three providers fail — return original text."""
        translator.config['api_key'] = 'sk-fake'
        with patch('translator.DeepGoogleTranslator', side_effect=Exception('google')):
            with patch.object(translator, 'translate_with_llm', side_effect=Exception('llm')):
                with patch.object(translator, '_translate_mymemory', side_effect=Exception('mm')):
                    result = translator.translate('Привет')
                    assert result == 'Привет'

    @patch('translator.DeepGoogleTranslator')
    def test_translate_empty_string(self, mock_deep_cls, translator):
        mock_inst = MagicMock()
        mock_inst.translate.return_value = ''
        mock_deep_cls.return_value = mock_inst

        result = translator.translate('')
        assert result == ''


class TestTranslationCache:
    @patch('translator.DeepGoogleTranslator')
    def test_cache_hit_skips_api(self, mock_deep_cls, translator):
        """Second call with same input must not hit the API."""
        mock_inst = MagicMock()
        mock_inst.translate.return_value = 'Hello'
        mock_deep_cls.return_value = mock_inst

        translator.translate('Привет')
        translator.translate('Привет')

        assert mock_inst.translate.call_count == 1

    @patch('translator.DeepGoogleTranslator')
    def test_cache_hit_moves_to_end(self, mock_deep_cls, translator):
        """Cache hit must move the entry to MRU position (OrderedDict end)."""
        mock_inst = MagicMock()
        mock_inst.translate.side_effect = ['one', 'two']
        mock_deep_cls.return_value = mock_inst

        translator.translate('a')   # populates key_a
        translator.translate('b')   # populates key_b

        key_a = translator._get_cache_key('a', 'auto', 'en')
        key_b = translator._get_cache_key('b', 'auto', 'en')

        # Access key_a — should become MRU.
        translator.translate('a')

        keys = list(translator._translation_cache.keys())
        assert keys[-1] == key_a  # key_a is now most-recently used
        assert keys[-2] == key_b  # key_b is older

    @patch('translator.DeepGoogleTranslator')
    def test_lru_eviction_removes_oldest(self, mock_deep_cls, translator):
        """When cache is full, LRU (least-recently-used) entry is evicted."""
        from translator import _TRANSLATION_CACHE_SIZE

        mock_inst = MagicMock()
        mock_inst.translate.side_effect = [f'result_{i}' for i in range(_TRANSLATION_CACHE_SIZE + 2)]
        mock_deep_cls.return_value = mock_inst

        # Fill the cache.
        for i in range(_TRANSLATION_CACHE_SIZE):
            translator.config['target_lang'] = f'fake{i:03d}'
            translator.translate(f'text_{i}')

        # Access the very first entry to make it MRU.
        translator.config['target_lang'] = 'fake000'
        translator.translate('text_0')

        # Add one more entry — should evict text_1 (now LRU), not text_0.
        translator.config['target_lang'] = 'en'
        translator.translate('new_text')

        key_first = translator._get_cache_key('text_0', 'auto', 'fake000')
        key_second = translator._get_cache_key('text_1', 'auto', 'fake001')

        assert key_first in translator._translation_cache, 'text_0 should still be cached (MRU)'
        assert key_second not in translator._translation_cache, 'text_1 should have been evicted (LRU)'

    @patch('translator.DeepGoogleTranslator')
    def test_cache_uses_orderdict(self, mock_deep_cls, translator):
        assert isinstance(translator._translation_cache, OrderedDict)


class TestGoogleTranslatorCache:
    @patch('translator.DeepGoogleTranslator')
    def test_same_pair_reuses_instance(self, mock_deep_cls, translator):
        """Same (src, dest) pair must reuse the cached translator instance."""
        mock_inst = MagicMock()
        mock_inst.translate.side_effect = ['result1', 'result2']
        mock_deep_cls.return_value = mock_inst

        translator.translate('text one')
        translator.translate('text two')  # different text, same lang pair — hits cache

        # DeepGoogleTranslator constructor called only once.
        assert mock_deep_cls.call_count == 1

    @patch('translator.DeepGoogleTranslator')
    def test_failure_invalidates_cached_instance(self, mock_deep_cls, translator):
        """On Google failure, cached instance must be evicted so next call gets fresh one."""
        mock_fail = MagicMock()
        mock_fail.translate.side_effect = Exception('network error')
        mock_deep_cls.return_value = mock_fail

        with patch.object(translator, '_translate_mymemory', return_value='fallback'):
            translator.translate('test')

        assert ('auto', 'en') not in translator._google_translator_cache


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

    def test_ollama_no_key_needed(self, translator):
        """Ollama is local — llm_available() must return True without a key."""
        translator.config['api_key'] = ''
        translator.config['api_provider'] = 'ollama'
        assert translator.llm_available() is True


class TestSplitByWords:
    def test_short_text_not_split(self):
        text = 'Hello world'
        chunks = _split_by_words(text, max_chars=450)
        assert chunks == ['Hello world']

    def test_splits_on_word_boundary(self):
        # Create a text that exceeds max_chars only when joined.
        words = ['word'] * 100  # 100 × 5 = 500 chars + spaces
        text = ' '.join(words)
        chunks = _split_by_words(text, max_chars=50)
        for chunk in chunks:
            assert len(chunk) <= 55  # some tolerance for the last word
            assert not chunk.startswith(' ')
            assert not chunk.endswith(' ')

    def test_no_word_split_in_middle(self):
        text = 'short ' * 80  # repeated so it needs splitting
        chunks = _split_by_words(text.strip(), max_chars=50)
        for chunk in chunks:
            # No word should be split mid-character.
            for word in chunk.split(' '):
                assert word == 'short' or word == ''

    def test_single_long_word(self):
        word = 'a' * 600
        chunks = _split_by_words(word, max_chars=450)
        # A word longer than max_chars still becomes a single chunk.
        assert len(chunks) == 1
        assert chunks[0] == word

    def test_empty_string(self):
        assert _split_by_words('', max_chars=450) == ['']

    def test_rejoined_text_matches_original(self):
        text = 'The quick brown fox jumps over the lazy dog. ' * 20
        chunks = _split_by_words(text.strip(), max_chars=100)
        rejoined = ' '.join(chunks)
        assert rejoined == text.strip()


class TestOllamaProvider:
    @patch('translator.requests.post')
    def test_ollama_called_without_api_key(self, mock_post, translator):
        translator.config['api_provider'] = 'ollama'
        translator.config['api_key'] = ''

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'message': {'content': 'ollama result'}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = translator._run_llm_prompt('test prompt')
        assert result == 'ollama result'
        called_url = mock_post.call_args[0][0]
        assert 'localhost:11434' in called_url

    @patch('translator.requests.post')
    def test_ollama_custom_url_and_model(self, mock_post, translator):
        translator.config['api_provider'] = 'ollama'
        translator.config['api_key'] = ''
        translator.config['ollama_url'] = 'http://192.168.1.10:11434'
        translator.config['ollama_model'] = 'mistral'

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'message': {'content': 'custom result'}}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        translator._run_llm_prompt('hello')
        payload = mock_post.call_args[1]['json']
        assert payload['model'] == 'mistral'
        assert '192.168.1.10' in mock_post.call_args[0][0]


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
        assert (
            mock_post.call_args[1].get('timeout') == 30
            or mock_post.call_args.kwargs.get('timeout') == 30
        )

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
        with (
            pytest.raises(ValueError, match='Unknown extract mode'),
            patch('translator.requests.post') as mock_post,
        ):
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
