import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from main import _resolve_config_path


@pytest.fixture
def tmp_home(tmp_path):
    return tmp_path


class TestResolveConfigPath:
    def test_xdg_exists(self, tmp_path, monkeypatch):
        xdg_dir = tmp_path / '.config' / 'olympus'
        xdg_dir.mkdir(parents=True)
        config_file = xdg_dir / 'config.json'
        config_file.write_text('{"hotkey": "ctrl+alt+t"}')

        monkeypatch.setattr('main._XDG_CONFIG_PATH', config_file)
        monkeypatch.setattr('main._XDG_CONFIG_DIR', xdg_dir)
        monkeypatch.setattr('main._LEGACY_CONFIG_PATH', tmp_path / '.text_translator_config.json')

        result = _resolve_config_path()
        assert result == config_file

    def test_migrate_from_legacy(self, tmp_path, monkeypatch):
        xdg_dir = tmp_path / '.config' / 'olympus'
        xdg_config = xdg_dir / 'config.json'
        legacy_config = tmp_path / '.text_translator_config.json'
        legacy_config.write_text('{"hotkey": "ctrl+shift+x"}')

        monkeypatch.setattr('main._XDG_CONFIG_PATH', xdg_config)
        monkeypatch.setattr('main._XDG_CONFIG_DIR', xdg_dir)
        monkeypatch.setattr('main._LEGACY_CONFIG_PATH', legacy_config)

        result = _resolve_config_path()

        assert result == xdg_config
        assert xdg_config.exists()
        assert json.loads(xdg_config.read_text())['hotkey'] == 'ctrl+shift+x'

    def test_creates_xdg_dir_if_nothing_exists(self, tmp_path, monkeypatch):
        xdg_dir = tmp_path / '.config' / 'olympus'
        xdg_config = xdg_dir / 'config.json'
        legacy_config = tmp_path / '.text_translator_config.json'

        monkeypatch.setattr('main._XDG_CONFIG_PATH', xdg_config)
        monkeypatch.setattr('main._XDG_CONFIG_DIR', xdg_dir)
        monkeypatch.setattr('main._LEGACY_CONFIG_PATH', legacy_config)

        result = _resolve_config_path()

        assert result == xdg_config
        assert xdg_dir.exists()


class TestTranslatorAppLoadConfig:
    def test_load_config_defaults(self, tmp_path, monkeypatch):
        from main import TranslatorApp

        config_path = tmp_path / 'config.json'

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            app.config_path = config_path
            config = app.load_config()

        assert config['hotkey'] == 'ctrl+shift+t'
        assert config['target_lang'] == 'en'
        assert config['source_lang'] == 'auto'

    def test_load_config_from_file(self, tmp_path, monkeypatch):
        from main import TranslatorApp

        config_path = tmp_path / 'config.json'
        config_path.write_text(json.dumps({
            'hotkey': 'ctrl+alt+x',
            'target_lang': 'de',
            'api_key': 'test-key',
        }))

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            app.config_path = config_path
            config = app.load_config()

        assert config['hotkey'] == 'ctrl+alt+x'
        assert config['target_lang'] == 'de'
        assert config['api_key'] == 'test-key'
        assert config['source_lang'] == 'auto'

    def test_load_config_corrupt_file(self, tmp_path):
        from main import TranslatorApp

        config_path = tmp_path / 'config.json'
        config_path.write_text('{invalid json')

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            app.config_path = config_path
            config = app.load_config()

        assert config['hotkey'] == 'ctrl+shift+t'

    def test_sudo_user_path(self, monkeypatch):
        from main import TranslatorApp

        monkeypatch.setenv('SUDO_USER', 'testuser')

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            app.config_path = Path.home() / '.config' / 'olympus' / 'config.json'
            app.load_config()

        assert 'testuser' in str(app.config_path)


class TestTranslatorAppSaveConfig:
    def test_save_creates_file(self, tmp_path):
        from main import TranslatorApp

        config_path = tmp_path / 'config.json'

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            app.config_path = config_path
            app.config = {'hotkey': 'ctrl+shift+t', 'target_lang': 'en'}

            with patch.object(app, 'reload_settings'):
                app.save_config()

        assert config_path.exists()
        saved = json.loads(config_path.read_text())
        assert saved['hotkey'] == 'ctrl+shift+t'


class TestCreateIcon:
    @patch('main.QPainter')
    @patch('main.QPixmap')
    def test_create_icon_uses_painter(self, mock_pixmap_cls, mock_painter_cls):
        from main import TranslatorApp

        mock_pixmap = MagicMock()
        mock_pixmap_cls.return_value = mock_pixmap
        mock_icon_return = MagicMock()
        mock_icon_return.isNull.return_value = False

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            with patch('main.QIcon', return_value=mock_icon_return):
                icon = app.create_icon()
                assert icon is not None


class TestOnTranslationDone:
    def test_callback_stored(self):
        from main import TranslatorApp

        with patch.object(TranslatorApp, '__init__', lambda self: None):
            app = TranslatorApp.__new__(TranslatorApp)
            cb = MagicMock()
            app._on_translation_done = cb

            app._on_translation_done('text', True)
            cb.assert_called_once_with('text', True)
