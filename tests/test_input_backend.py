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
