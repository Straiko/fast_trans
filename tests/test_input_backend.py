from input_backend import _normalize_hotkey_for_pynput, _parse_send_parts


class TestNormalizeHotkey:
    def test_ctrl_shift_letter(self):
        assert _normalize_hotkey_for_pynput('ctrl+shift+t') == '<ctrl>+<shift>+t'

    def test_ctrl_shift_v(self):
        assert _normalize_hotkey_for_pynput('ctrl+shift+v') == '<ctrl>+<shift>+v'

    def test_ctrl_c(self):
        assert _normalize_hotkey_for_pynput('ctrl+c') == '<ctrl>+c'

    def test_alt_letter(self):
        assert _normalize_hotkey_for_pynput('alt+f') == '<alt>+f'

    def test_win_key(self):
        assert _normalize_hotkey_for_pynput('win+r') == '<cmd>+r'

    def test_function_key(self):
        assert _normalize_hotkey_for_pynput('ctrl+f1') == '<ctrl>+<f1>'

    def test_single_letter(self):
        assert _normalize_hotkey_for_pynput('a') == 'a'

    def test_whitespace_handling(self):
        assert _normalize_hotkey_for_pynput(' ctrl + shift + t ') == '<ctrl>+<shift>+t'

    def test_control_alias(self):
        assert _normalize_hotkey_for_pynput('control+c') == '<ctrl>+c'

    def test_ctl_alias(self):
        assert _normalize_hotkey_for_pynput('ctl+c') == '<ctrl>+c'


class TestParseSendParts:
    def test_ctrl_c(self):
        keys = _parse_send_parts('ctrl+c')
        from pynput.keyboard import Key

        assert keys == [Key.ctrl, 'c']

    def test_ctrl_v(self):
        keys = _parse_send_parts('ctrl+v')
        from pynput.keyboard import Key

        assert keys == [Key.ctrl, 'v']

    def test_ctrl_shift_t(self):
        keys = _parse_send_parts('ctrl+shift+t')
        from pynput.keyboard import Key

        assert keys == [Key.ctrl, Key.shift, 't']

    def test_alt_tab(self):
        keys = _parse_send_parts('alt+tab')
        from pynput.keyboard import Key

        assert keys == [Key.alt, 'tab']


class TestNoInputBackend:
    def test_send_prints_warning_once(self, caplog):
        import logging

        from input_backend import NoInputBackend

        b = NoInputBackend('test reason')
        with caplog.at_level(logging.WARNING, logger='input_backend'):
            b.send('ctrl+c')
        assert 'pynput' in caplog.text.lower()

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger='input_backend'):
            b.send('ctrl+v')
        assert caplog.text == ''

    def test_start_stop_are_noop(self):
        from input_backend import NoInputBackend

        b = NoInputBackend('test')
        b.start_hotkeys([('ctrl+c', lambda: None)])
        b.stop_hotkeys()


class TestWtypeAndTerminal:
    def test_parse_send_parts_insert_key(self):
        from pynput.keyboard import Key

        from input_backend import _parse_send_parts

        keys = _parse_send_parts('shift+insert')
        assert keys == [Key.shift, Key.insert]

    def test_send_wtype_calls_subprocess(self):
        from unittest.mock import patch

        from input_backend import _send_wtype

        with (
            patch('shutil.which', return_value='/usr/bin/wtype'),
            patch('subprocess.run') as mock_run,
        ):
            mock_run.return_value.returncode = 0
            res = _send_wtype('ctrl+shift+v')
            assert res is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args == [
                'wtype',
                '-s',
                '25',
                '-M',
                'ctrl',
                '-s',
                '15',
                '-M',
                'shift',
                '-s',
                '15',
                '-k',
                'v',
                '-s',
                '15',
                '-m',
                'shift',
                '-s',
                '15',
                '-m',
                'ctrl',
                '-s',
                '15',
            ]

    def test_is_terminal_window_niri(self):
        from unittest.mock import patch

        from input_backend import is_terminal_window

        with (
            patch('platform.system', return_value='Linux'),
            patch(
                'shutil.which', side_effect=lambda cmd: '/usr/bin/niri' if cmd == 'niri' else None
            ),
            patch('subprocess.run') as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = 'Window ID 1:\n  App ID: "com.mitchellh.ghostty"'
            assert is_terminal_window() is True

    def test_is_terminal_window_false_for_browser(self):
        from unittest.mock import patch

        from input_backend import is_terminal_window

        with (
            patch('platform.system', return_value='Linux'),
            patch(
                'shutil.which', side_effect=lambda cmd: '/usr/bin/niri' if cmd == 'niri' else None
            ),
            patch('subprocess.run') as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = 'Window ID 2:\n  App ID: "firefox"'
            assert is_terminal_window() is False


class TestCaptureAndPaste:
    def test_paste_text_in_terminal(self):
        from unittest.mock import MagicMock

        from input_backend import paste_text

        mock_backend = MagicMock()
        mock_pyperclip = MagicMock()

        paste_text(
            'echo 123', is_terminal=True, pyperclip_module=mock_pyperclip, backend=mock_backend
        )
        mock_pyperclip.copy.assert_called_once_with('echo 123')
        mock_backend.send.assert_called_once_with('ctrl+shift+v')

    def test_paste_text_in_gui(self):
        from unittest.mock import MagicMock

        from input_backend import paste_text

        mock_backend = MagicMock()
        mock_pyperclip = MagicMock()

        paste_text(
            'Hello World', is_terminal=False, pyperclip_module=mock_pyperclip, backend=mock_backend
        )
        mock_pyperclip.copy.assert_called_once_with('Hello World')
        mock_backend.send.assert_called_once_with('ctrl+v')

    def test_capture_in_terminal_uses_primary_first(self):
        from unittest.mock import MagicMock

        from input_backend import capture_selected_text

        mock_backend = MagicMock()
        mock_pyperclip = MagicMock()

        text = capture_selected_text(
            pyperclip_module=mock_pyperclip,
            is_terminal=True,
            backend=mock_backend,
            primary_text='terminal text',
        )
        # Never send plain Ctrl+C in terminal
        assert text == 'terminal text'
        mock_backend.send.assert_not_called()

    def test_capture_in_terminal_falls_back_to_ctrl_shift_c(self):
        from unittest.mock import MagicMock, patch

        from input_backend import capture_selected_text

        mock_backend = MagicMock()
        mock_pyperclip = MagicMock()
        mock_pyperclip.paste.side_effect = ['old', 'copied in terminal']

        with patch('input_backend.get_primary_selection_text', return_value=''):
            text = capture_selected_text(
                pyperclip_module=mock_pyperclip,
                is_terminal=True,
                backend=mock_backend,
            )
            assert text == 'copied in terminal'
            mock_backend.send.assert_called_once_with('ctrl+shift+c')
