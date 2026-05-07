"""
Keyboard input: global hotkeys and synthetic Ctrl+C / Ctrl+V.

On Linux, the `keyboard` package requires root. By default, pynput is used —
it works under X11 without sudo. On Windows, `keyboard` is preferred.
"""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import re
from abc import ABC, abstractmethod
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _normalize_hotkey_for_pynput(spec: str) -> str:
    """ctrl+shift+l → <ctrl>+<shift>+l  (pynput GlobalHotKeys format)."""
    parts = [p.strip().lower() for p in spec.split('+')]
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        if p in ('ctrl', 'control', 'ctl'):
            out.append('<ctrl>')
        elif p == 'shift':
            out.append('<shift>')
        elif p in ('alt', 'meta', 'option'):
            out.append('<alt>')
        elif p in ('win', 'super', 'cmd', 'command', 'windows'):
            out.append('<cmd>')
        elif re.fullmatch(r'f(1[0-9]?|2[0-4]?|[1-9])', p):
            out.append(f'<{p}>')
        elif len(p) == 1:
            out.append(p)
        else:
            out.append(f'<{p}>')
    return '+'.join(out)


def _parse_send_parts(spec: str):
    """Parse ctrl+c into a sequence of keys for press/release."""
    from pynput.keyboard import Key

    parts = [p.strip().lower() for p in spec.split('+')]
    keys: list = []
    for p in parts:
        if p in ('ctrl', 'control', 'ctl'):
            keys.append(Key.ctrl)
        elif p == 'shift':
            keys.append(Key.shift)
        elif p in ('alt', 'meta', 'option'):
            keys.append(Key.alt)
        elif p in ('win', 'super', 'cmd', 'command', 'windows'):
            keys.append(Key.cmd)
        elif re.fullmatch(r'f(1[0-9]?|2[0-4]?|[1-9])', p):
            keys.append(getattr(Key, p))
        elif len(p) == 1:
            keys.append(p)
        else:
            keys.append(p)
    return keys


class InputBackend(ABC):
    @abstractmethod
    def start_hotkeys(self, mapping: list[tuple[str, Callable]]) -> None:
        pass

    @abstractmethod
    def stop_hotkeys(self) -> None:
        pass

    @abstractmethod
    def send(self, combo: str) -> None:
        pass


class KeyboardLibBackend(InputBackend):
    """Uses the `keyboard` package (Windows primary; Linux root-only)."""

    def start_hotkeys(self, mapping: list[tuple[str, Callable]]) -> None:
        import keyboard

        for hotkey, cb in mapping:
            keyboard.add_hotkey(hotkey, cb)

    def stop_hotkeys(self) -> None:
        import keyboard

        with contextlib.suppress(Exception):
            keyboard.unhook_all()

    def send(self, combo: str) -> None:
        import keyboard

        keyboard.send(combo)


class NoInputBackend(InputBackend):
    """Stub used when pynput is missing or keyboard is unavailable without root."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        self._warned = False

    def start_hotkeys(self, mapping: list[tuple[str, Callable]]) -> None:
        pass

    def stop_hotkeys(self) -> None:
        pass

    def send(self, combo: str) -> None:
        if not self._warned:
            logger.warning(
                'Keyboard simulation (Ctrl+C/V) unavailable — install pynput '
                '(pip install six pynput)'
            )
            self._warned = True


class PynputBackend(InputBackend):
    def __init__(self) -> None:
        from pynput.keyboard import Controller, GlobalHotKeys

        self._GlobalHotKeys = GlobalHotKeys
        self._controller = Controller()
        from typing import Any

        self._listener: Any = None

    def start_hotkeys(self, mapping: list[tuple[str, Callable]]) -> None:
        self.stop_hotkeys()
        hotkeys: dict[str, Callable] = {}
        for user_spec, cb in mapping:
            hotkeys[_normalize_hotkey_for_pynput(user_spec)] = cb
        self._listener = self._GlobalHotKeys(hotkeys)
        self._listener.start()

    def stop_hotkeys(self) -> None:
        if self._listener is not None:
            with contextlib.suppress(Exception):
                self._listener.stop()
            self._listener = None

    def send(self, combo: str) -> None:
        keys = _parse_send_parts(combo)
        c = self._controller
        for k in keys:
            c.press(k)
        for k in reversed(keys):
            c.release(k)


_backend: InputBackend | None = None


def degraded_input_mode() -> bool:
    """True when global hotkeys and synthetic keypresses are unavailable."""
    return isinstance(get_backend(), NoInputBackend)


def get_backend() -> InputBackend:
    global _backend
    if _backend is not None:
        return _backend

    system = platform.system()
    linux_non_root = system == 'Linux' and os.geteuid() != 0

    if linux_non_root:
        try:
            _backend = PynputBackend()
            logger.info('Linux: using pynput (hotkeys and paste without root).')
        except Exception as e:
            _backend = NoInputBackend(str(e))
            logger.warning(
                'Without pynput on Linux, global hotkeys are unavailable '
                '(keyboard requires root).\n'
                '  Reason: %s\n'
                '  Fix:  pip install six pynput\n'
                '  SSL workaround:\n'
                '  pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org six pynput',
                e,
            )
    elif system == 'Linux':
        _backend = KeyboardLibBackend()
        logger.info('Linux (root): using keyboard package.')
    elif system == 'Darwin':
        try:
            _backend = PynputBackend()
            logger.info('macOS: pynput (grant Accessibility if prompted).')
        except Exception as e:
            logger.warning('pynput failed: %s, falling back to keyboard.', e)
            _backend = KeyboardLibBackend()
    else:
        _backend = KeyboardLibBackend()

    return _backend


def send_key_combo(combo: str) -> None:
    """Send Ctrl+C, Ctrl+V, etc. via the current backend."""
    get_backend().send(combo)
