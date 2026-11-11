from config_validator import VALID_API_PROVIDERS, validate_config


class TestConfigValidator:
    def test_valid_providers_contain_expected(self):
        assert 'groq' in VALID_API_PROVIDERS
        assert 'openai' in VALID_API_PROVIDERS
        assert 'anthropic' in VALID_API_PROVIDERS
        assert 'huggingface' in VALID_API_PROVIDERS
        assert 'ollama' in VALID_API_PROVIDERS
        assert 'deepseek' in VALID_API_PROVIDERS
        assert 'gemini' in VALID_API_PROVIDERS

    def test_valid_config_unchanged(self):
        config = {
            'api_provider': 'deepseek',
            'source_lang': 'en',
            'target_lang': 'ru',
            'microphone_index': 2,
            'auto_replace': False,
            'ai_enhance': True,
            'prefer_llm_translation': True,
        }
        validated = validate_config(config)
        assert validated == config

    def test_invalid_api_provider_defaults_to_groq(self):
        config = {'api_provider': 'nonexistent_provider'}
        validated = validate_config(config)
        assert validated['api_provider'] == 'groq'

    def test_invalid_source_lang_defaults_to_auto(self):
        config = {'source_lang': 'invalid_lang'}
        validated = validate_config(config)
        assert validated['source_lang'] == 'auto'

    def test_invalid_target_lang_defaults_to_en(self):
        config = {'target_lang': 'invalid_lang'}
        validated = validate_config(config)
        assert validated['target_lang'] == 'en'

    def test_microphone_index_sanitization(self):
        # Index < -1 should reset to -1
        assert validate_config({'microphone_index': -5})['microphone_index'] == -1
        # Valid -1 stays -1
        assert validate_config({'microphone_index': -1})['microphone_index'] == -1
        # String number converted to int
        assert validate_config({'microphone_index': '3'})['microphone_index'] == 3
        # Non-numeric string reset to -1
        assert validate_config({'microphone_index': 'abc'})['microphone_index'] == -1

    def test_boolean_coercion(self):
        config = {
            'auto_replace': 'yes',
            'ai_enhance': 0,
            'prefer_llm_translation': 1,
        }
        validated = validate_config(config)
        assert validated['auto_replace'] is True
        assert validated['ai_enhance'] is False
        assert validated['prefer_llm_translation'] is True
