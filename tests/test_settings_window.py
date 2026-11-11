from unittest.mock import MagicMock, patch

import pytest

from settings_window import SettingsWindow


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
def save_callback():
    return MagicMock()


@pytest.fixture
def settings_window(default_config, save_callback, qapp):
    with patch('settings_window.sr'):
        win = SettingsWindow(default_config, save_callback)
    return win


class TestSyncUiToConfig:
    def test_sync_hotkey(self, settings_window, default_config):
        settings_window.hotkey_input.setText('ctrl+alt+x')
        settings_window._sync_ui_to_config()
        assert default_config['hotkey'] == 'ctrl+alt+x'

    def test_sync_voice_hotkey(self, settings_window, default_config):
        settings_window.voice_hotkey_input.setText('ctrl+alt+v')
        settings_window._sync_ui_to_config()
        assert default_config['voice_hotkey'] == 'ctrl+alt+v'

    def test_sync_auto_replace(self, settings_window, default_config):
        settings_window.auto_replace_checkbox.setChecked(False)
        settings_window._sync_ui_to_config()
        assert default_config['auto_replace'] is False

    def test_sync_source_lang(self, settings_window, default_config):
        settings_window.source_lang_combo.setCurrentText('ru')
        settings_window._sync_ui_to_config()
        assert default_config['source_lang'] == 'ru'

    def test_sync_target_lang(self, settings_window, default_config):
        settings_window.target_lang_combo.setCurrentText('de')
        settings_window._sync_ui_to_config()
        assert default_config['target_lang'] == 'de'

    def test_sync_api_provider(self, settings_window, default_config):
        settings_window.provider_combo.setCurrentText('openai')
        settings_window._sync_ui_to_config()
        assert default_config['api_provider'] == 'openai'

    def test_sync_api_key(self, settings_window, default_config):
        settings_window.api_key_input.setText('sk-test-key')
        settings_window._sync_ui_to_config()
        assert default_config['api_key'] == 'sk-test-key'

    def test_sync_prefer_llm(self, settings_window, default_config):
        settings_window.prefer_llm_checkbox.setChecked(True)
        settings_window._sync_ui_to_config()
        assert default_config['prefer_llm_translation'] is True


class TestCancelSettings:
    def test_cancel_restores_snapshot(self, settings_window, default_config):
        original_hotkey = default_config['hotkey']
        settings_window.hotkey_input.setText('ctrl+alt+z')

        settings_window._apply_timer.stop()
        with patch.object(settings_window, 'close'):
            settings_window.cancel_settings()

        assert default_config['hotkey'] == original_hotkey

    def test_cancel_calls_save(self, settings_window, save_callback):
        settings_window._apply_timer.stop()
        with patch.object(settings_window, 'close'):
            settings_window.cancel_settings()

        save_callback.assert_called_once()


class TestSaveSettings:
    def test_save_syncs_and_closes(self, settings_window, default_config, save_callback):
        settings_window.hotkey_input.setText('ctrl+alt+y')

        settings_window._apply_timer.stop()
        with patch.object(settings_window, 'close'):
            settings_window.save_settings()

        assert default_config['hotkey'] == 'ctrl+alt+y'
        save_callback.assert_called_once()


class TestAutoApply:
    def test_schedule_apply_respects_suspend(self, settings_window):
        settings_window._suspend_auto_apply = True
        settings_window._schedule_apply()
        assert not settings_window._apply_timer.isActive()

    def test_apply_now_respects_suspend(self, settings_window):
        settings_window._suspend_auto_apply = True
        settings_window._apply_now()
        assert not settings_window._apply_timer.isActive()


class TestProviderInfo:
    def test_groq_info(self, settings_window):
        settings_window.on_provider_changed('groq')
        assert 'groq.com' in settings_window.provider_info.text()

    def test_huggingface_info(self, settings_window):
        settings_window.on_provider_changed('huggingface')
        assert 'huggingface' in settings_window.provider_info.text()

    def test_openai_info(self, settings_window):
        settings_window.on_provider_changed('openai')
        assert 'openai.com' in settings_window.provider_info.text()

    def test_anthropic_info(self, settings_window):
        settings_window.on_provider_changed('anthropic')
        assert 'anthropic.com' in settings_window.provider_info.text()

    def test_deepseek_info(self, settings_window):
        settings_window.on_provider_changed('deepseek')
        assert 'deepseek.com' in settings_window.provider_info.text()

    def test_gemini_info(self, settings_window):
        settings_window.on_provider_changed('gemini')
        assert 'aistudio.google.com' in settings_window.provider_info.text()

    def test_ollama_enables_ai_enhance_without_key(self, settings_window):
        settings_window.api_key_input.setText('')
        settings_window.on_provider_changed('ollama')
        assert settings_window.ai_enhance_checkbox.isEnabled() is True
        assert settings_window.prefer_llm_checkbox.isEnabled() is True

    def test_switch_to_groq_without_key_disables_ai_enhance(self, settings_window):
        settings_window.api_key_input.setText('')
        settings_window.on_provider_changed('groq')
        assert settings_window.ai_enhance_checkbox.isEnabled() is False
        assert settings_window.ai_enhance_checkbox.isChecked() is False
        assert settings_window.prefer_llm_checkbox.isEnabled() is False
        assert settings_window.prefer_llm_checkbox.isChecked() is False


class TestHttpProbe:
    @patch('settings_window.requests.post')
    def test_probe_deepseek_ok(self, mock_post):
        from settings_window import _http_probe

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, msg = _http_probe('deepseek', 'sk-dsk-test')
        assert ok is True
        assert 'OK' in msg
        assert 'api.deepseek.com' in mock_post.call_args[0][0]

    @patch('settings_window.requests.post')
    def test_probe_gemini_ok(self, mock_post):
        from settings_window import _http_probe

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, msg = _http_probe('gemini', 'gemini-key')
        assert ok is True
        assert 'OK' in msg
        assert 'generativelanguage.googleapis.com' in mock_post.call_args[0][0]


class TestConfigSnapshot:
    def test_snapshot_on_open(self, settings_window, default_config):
        assert settings_window._config_snapshot['hotkey'] == default_config['hotkey']

    def test_snapshot_independent(self, settings_window, default_config):
        default_config['hotkey'] = 'changed'
        assert settings_window._config_snapshot['hotkey'] == 'ctrl+shift+t'
