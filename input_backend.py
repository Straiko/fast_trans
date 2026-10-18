"""
Keyboard input: global hotkeys and synthetic Ctrl+C / Ctrl+V.

On Linux, the `keyboard` package requires root. By default, pynput is used —
it works under X11 without sudo. On Windows, `keyboard` is preferred.
"""

from __future__ import annotations

import contextlib
import glob
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import pyperclip

logger = logging.getLogger(__name__)


_LATIN_TO_CYRILLIC: dict[str, str] = {
    'q': 'й',
    'w': 'ц',
    'e': 'у',
    'r': 'к',
    't': 'е',
    'y': 'н',
    'u': 'г',
    'i': 'ш',
    'o': 'щ',
    'p': 'з',
    'a': 'ф',
    's': 'ы',
    'd': 'в',
    'f': 'а',
    'g': 'п',
    'h': 'р',
    'j': 'о',
    'k': 'л',
    'l': 'д',
    'z': 'я',
    'x': 'ч',
    'c': 'с',
    'v': 'м',
    'b': 'и',
    'n': 'т',
    'm': 'ь',
    '[': 'х',
    ']': 'ъ',
    ';': 'ж',
    "'": 'э',
    ',': 'б',
    '.': 'ю',
}


def is_valid_hotkey(spec: str) -> bool:
    """Check if spec contains at least one non-modifier key."""
    if not spec or not spec.strip():
        return False
    parts = [p.strip().lower() for p in spec.split('+') if p.strip()]
    modifiers = {
        'ctrl',
        'control',
        'ctl',
        'shift',
        'alt',
        'meta',
        'option',
        'win',
        'super',
        'cmd',
        'command',
        'windows',
    }
    non_modifiers = [p for p in parts if p not in modifiers]
    return len(non_modifiers) >= 1


def ensure_wayland_env() -> None:
    """Ensure XDG_RUNTIME_DIR, WAYLAND_DISPLAY, and NIRI_SOCKET are set when running in Wayland (including under sudo)."""
    if not os.environ.get('XDG_RUNTIME_DIR'):
        uid = os.geteuid()
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            try:
                import pwd

                uid = pwd.getpwnam(sudo_user).pw_uid
            except Exception:
                uid = 1000
        elif uid == 0:
            uid = 1000
        candidate = f'/run/user/{uid}'
        if os.path.isdir(candidate):
            os.environ['XDG_RUNTIME_DIR'] = candidate

    rdir = os.environ.get('XDG_RUNTIME_DIR', '')
    if rdir and not os.environ.get('WAYLAND_DISPLAY'):
        socks = glob.glob(os.path.join(rdir, 'wayland-[0-9]*'))
        if socks:
            os.environ['WAYLAND_DISPLAY'] = os.path.basename(socks[0])

    if rdir and not os.environ.get('NIRI_SOCKET'):
        socks = glob.glob(os.path.join(rdir, 'niri.*.sock'))
        if socks:
            os.environ['NIRI_SOCKET'] = socks[0]


def is_wayland() -> bool:
    """True if running inside a Wayland desktop session."""
    ensure_wayland_env()
    return bool(
        os.environ.get('WAYLAND_DISPLAY') or os.environ.get('XDG_SESSION_TYPE') == 'wayland'
    )


def _send_wtype(combo: str) -> bool:
    """Send key combo via wtype (Wayland virtual keyboard). Returns True on success."""
    if not shutil.which('wtype'):
        return False

    ensure_wayland_env()
    parts = [p.strip().lower() for p in combo.split('+') if p.strip()]
    mod_map = {
        'ctrl': 'ctrl',
        'control': 'ctrl',
        'ctl': 'ctrl',
        'shift': 'shift',
        'alt': 'alt',
        'meta': 'alt',
        'win': 'win',
        'super': 'logo',
        'cmd': 'win',
    }
    modifiers = []
    keys = []
    for p in parts:
        if p in mod_map:
            modifiers.append(mod_map[p])
        elif p == 'insert':
            keys.append('Insert')
        else:
            keys.append(p)

    args = ['wtype', '-s', '25']
    for m in modifiers:
        args.extend(['-M', m, '-s', '15'])
    for k in keys:
        args.extend(['-k', k, '-s', '15'])
    for m in reversed(modifiers):
        args.extend(['-m', m, '-s', '15'])

    try:
        res = subprocess.run(args, env=os.environ, timeout=2, check=False, capture_output=True)
        return res.returncode == 0
    except Exception as e:
        logger.warning('wtype send failed: %s', e)
        return False


def is_terminal_window() -> bool:
    """Return True if the currently focused window is a terminal emulator."""
    system = platform.system()
    if system == 'Linux':
        ensure_wayland_env()
        # 1. Wayland / Niri
        if shutil.which('niri'):
            try:
                res = subprocess.run(
                    ['niri', 'msg', 'focused-window'],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if res.returncode == 0:
                    lower = res.stdout.lower()
                    terms = (
                        'ghostty',
                        'kitty',
                        'alacritty',
                        'foot',
                        'terminal',
                        'wezterm',
                        'xterm',
                        'konsole',
                        'terminator',
                        'tilix',
                        'rxvt',
                        'urxvt',
                        'tmux',
                    )
                    return any(t in lower for t in terms)
            except Exception:
                pass

        # 2. Wayland / Sway
        if shutil.which('swaymsg'):
            try:
                res = subprocess.run(
                    ['swaymsg', '-t', 'get_tree'],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if res.returncode == 0:

                    def check_sway(node: dict) -> bool | None:
                        if node.get('focused'):
                            app = (
                                node.get('app_id')
                                or node.get('window_properties', {}).get('class')
                                or ''
                            ).lower()
                            return any(
                                t in app
                                for t in ('term', 'kitty', 'alacritty', 'foot', 'ghostty', 'tmux')
                            )
                        for ch in node.get('nodes', []) + node.get('floating_nodes', []):
                            ret = check_sway(ch)
                            if ret is not None:
                                return ret
                        return None

                    val = check_sway(json.loads(res.stdout))
                    if val is not None:
                        return val
            except Exception:
                pass

        # 3. Wayland / Hyprland
        if shutil.which('hyprctl'):
            try:
                res = subprocess.run(
                    ['hyprctl', 'activewindow', '-j'],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if res.returncode == 0:
                    data = json.loads(res.stdout)
                    cls = (data.get('class') or data.get('initialClass') or '').lower()
                    return any(
                        t in cls for t in ('term', 'kitty', 'alacritty', 'foot', 'ghostty', 'tmux')
                    )
            except Exception:
                pass

        # 4. X11 via xdotool
        if shutil.which('xdotool'):
            try:
                res = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowclassname'],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if res.returncode == 0:
                    cls = res.stdout.strip().lower()
                    return any(
                        t in cls
                        for t in (
                            'term',
                            'kitty',
                            'alacritty',
                            'foot',
                            'ghostty',
                            'tmux',
                            'rxvt',
                            'console',
                        )
                    )
            except Exception:
                pass

    elif system == 'Windows':
        try:
            import psutil
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            name = proc.name().lower()
            return any(
                t in name
                for t in (
                    'cmd.exe',
                    'powershell.exe',
                    'windowsterminal.exe',
                    'conhost.exe',
                    'mintty.exe',
                    'bash.exe',
                )
            )
        except Exception:
            pass

    return False


def get_clipboard_text(pyperclip_module: Any = None) -> str:
    """Read regular clipboard text."""
    clip = pyperclip_module or pyperclip
    try:
        val = clip.paste()
        if val is not None:
            return val
    except Exception:
        pass

    if pyperclip_module is None and is_wayland() and shutil.which('wl-paste'):
        ensure_wayland_env()
        try:
            res = subprocess.run(
                ['wl-paste', '--no-newline'],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
    return ''


def get_primary_selection_text() -> str:
    """Read X11/Wayland primary selection (text selected by mouse/cursor)."""
    if is_wayland() and shutil.which('wl-paste'):
        ensure_wayland_env()
        try:
            res = subprocess.run(
                ['wl-paste', '--primary', '--no-newline'],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
    elif shutil.which('xclip'):
        try:
            res = subprocess.run(
                ['xclip', '-o', '-selection', 'primary'],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
    elif shutil.which('xsel'):
        try:
            res = subprocess.run(
                ['xsel', '-o', '-p'],
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
    return ''


def set_clipboard_and_primary(text: str, pyperclip_module: Any = None) -> None:
    """Copy text to both regular clipboard and PRIMARY selection buffer."""
    clip = pyperclip_module or pyperclip
    try:
        clip.copy(text)
    except Exception as e:
        logger.warning('pyperclip copy failed: %s', e)

    if is_wayland() and shutil.which('wl-copy'):
        ensure_wayland_env()
        with contextlib.suppress(Exception):
            subprocess.run(['wl-copy', text], env=os.environ, timeout=1, check=False)
        with contextlib.suppress(Exception):
            subprocess.run(['wl-copy', '--primary', text], env=os.environ, timeout=1, check=False)
    elif shutil.which('xclip'):
        with contextlib.suppress(Exception):
            p = subprocess.Popen(['xclip', '-selection', 'primary'], stdin=subprocess.PIPE)
            p.communicate(input=text.encode('utf-8'), timeout=1)


def capture_selected_text(
    pyperclip_module: Any = None,
    is_terminal: bool | None = None,
    backend: InputBackend | None = None,
    clipboard_before: str | None = None,
    primary_text: str | None = None,
) -> str:
    """
    Capture the currently selected text across terminals, GUI apps, Wayland, and X11.
    1. In terminals: reads PRIMARY selection directly (never sends Ctrl+C which cancels commands).
       Falls back to Ctrl+Shift+C.
    2. In GUI apps: sends Ctrl+C (Cmd+C on macOS), falls back to PRIMARY buffer.
    """
    ensure_wayland_env()
    b = backend or get_backend()
    is_term = is_terminal_window() if is_terminal is None else is_terminal

    def _get_primary() -> str:
        if primary_text is not None:
            return primary_text
        return get_primary_selection_text()

    # In terminal sessions:
    # Mouse selection directly populates PRIMARY selection buffer.
    # We must NEVER send Ctrl+C in a terminal, as it sends SIGINT.
    if is_term:
        primary = _get_primary()
        if primary and primary.strip():
            logger.info('Captured text from terminal primary selection.')
            return primary

        time.sleep(0.05)
        if clipboard_before is None:
            clipboard_before = get_clipboard_text(pyperclip_module)
        b.send('ctrl+shift+c')
        time.sleep(0.15)

        clipboard_after = get_clipboard_text(pyperclip_module)
        if clipboard_after and clipboard_after != clipboard_before and clipboard_after.strip():
            logger.info('Captured text from terminal via Ctrl+Shift+C.')
            return clipboard_after

        primary_after = _get_primary()
        if primary_after and primary_after.strip():
            return primary_after

        return clipboard_after if clipboard_after.strip() else ''

    # In GUI applications:
    primary_before = _get_primary()
    if clipboard_before is None:
        clipboard_before = get_clipboard_text(pyperclip_module)

    copy_combo = 'cmd+c' if platform.system() == 'Darwin' else 'ctrl+c'
    b.send(copy_combo)
    time.sleep(0.15)

    clipboard_after = get_clipboard_text(pyperclip_module)
    if clipboard_after and clipboard_after != clipboard_before and clipboard_after.strip():
        logger.info('Captured selection via %s.', copy_combo)
        return clipboard_after

    if primary_before and primary_before.strip():
        logger.info('Captured selection from primary buffer.')
        return primary_before

    primary_after = _get_primary()
    if primary_after and primary_after.strip():
        logger.info('Captured selection from updated primary buffer.')
        return primary_after

    # Retry once if clipboard unchanged (slow apps / Wayland lag)
    if clipboard_after == clipboard_before:
        time.sleep(0.1)
        b.send(copy_combo)
        time.sleep(0.15)
        clipboard_retry = get_clipboard_text(pyperclip_module)
        if clipboard_retry and clipboard_retry != clipboard_before and clipboard_retry.strip():
            return clipboard_retry

    if clipboard_after and clipboard_after.strip():
        logger.info('Using existing clipboard content as fallback.')
        return clipboard_after

    return ''


def paste_text(
    text: str,
    is_terminal: bool | None = None,
    pyperclip_module: Any = None,
    backend: InputBackend | None = None,
) -> None:
    """
    Set clipboard and primary selection, and paste into active window.
    Uses Ctrl+Shift+V in terminals, Ctrl+V in standard GUI applications.
    """
    b = backend or get_backend()
    set_clipboard_and_primary(text, pyperclip_module=pyperclip_module)
    time.sleep(0.1)

    is_term = is_terminal_window() if is_terminal is None else is_terminal

    paste_combo = 'ctrl+shift+v' if is_term else 'ctrl+v'
    b.send(paste_combo)


def _expand_cyrillic_hotkeys(mapping: list[tuple[str, Callable]]) -> list[tuple[str, Callable]]:
    """Return mapping expanded with Cyrillic layout variants so hotkeys work regardless of active language."""
    out: list[tuple[str, Callable]] = []
    seen = set()
    for spec, cb in mapping:
        if not is_valid_hotkey(spec):
            continue
        spec_clean = spec.strip().lower()
        if spec_clean not in seen:
            out.append((spec_clean, cb))
            seen.add(spec_clean)

        parts = [p.strip().lower() for p in spec_clean.split('+')]
        new_parts = []
        has_cyr = False
        for p in parts:
            if p in _LATIN_TO_CYRILLIC:
                new_parts.append(_LATIN_TO_CYRILLIC[p])
                has_cyr = True
            else:
                new_parts.append(p)
        if has_cyr:
            cyr_spec = '+'.join(new_parts)
            if cyr_spec not in seen:
                out.append((cyr_spec, cb))
                seen.add(cyr_spec)
    return out


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
        elif p == 'insert':
            keys.append(Key.insert)
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

        self.stop_hotkeys()
        expanded = _expand_cyrillic_hotkeys(mapping)
        for hotkey, cb in expanded:
            try:
                keyboard.add_hotkey(hotkey, cb, suppress=True)
            except Exception:
                with contextlib.suppress(Exception):
                    keyboard.add_hotkey(hotkey, cb, suppress=False)

    def stop_hotkeys(self) -> None:
        import keyboard

        with contextlib.suppress(Exception):
            keyboard.unhook_all()

    def send(self, combo: str) -> None:
        if is_wayland() and _send_wtype(combo):
            return
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
        self._listener: Any = None

        import shutil

        self._use_wtype = is_wayland() and shutil.which('wtype') is not None
        self._use_xdotool = is_wayland() and shutil.which('xdotool') is not None
        if self._use_wtype:
            logger.info('Wayland: will use wtype for virtual keyboard simulation.')
        elif self._use_xdotool:
            logger.info('Wayland: will use xdotool for Ctrl+C/V simulation.')

    def start_hotkeys(self, mapping: list[tuple[str, Callable]]) -> None:
        self.stop_hotkeys()
        expanded = _expand_cyrillic_hotkeys(mapping)
        hotkeys: dict[str, Callable] = {}
        for user_spec, cb in expanded:
            norm = _normalize_hotkey_for_pynput(user_spec)
            if norm:
                hotkeys[norm] = cb
        if not hotkeys:
            return
        self._listener = self._GlobalHotKeys(hotkeys)
        self._listener.start()

    def stop_hotkeys(self) -> None:
        if self._listener is not None:
            with contextlib.suppress(Exception):
                self._listener.stop()
            self._listener = None

    def send(self, combo: str) -> None:
        if self._use_wtype and _send_wtype(combo):
            return
        if self._use_xdotool:
            self._send_xdotool(combo)
        else:
            keys = _parse_send_parts(combo)
            c = self._controller
            for k in keys:
                c.press(k)
            for k in reversed(keys):
                c.release(k)

    @staticmethod
    def _send_xdotool(combo: str) -> None:
        """Use xdotool to simulate key combos (works on Wayland via XWayland)."""
        import subprocess

        try:
            subprocess.run(
                ['xdotool', 'key', '--clearmodifiers', combo],
                timeout=3,
                check=False,
                capture_output=True,
            )
        except Exception as e:
            logger.warning('xdotool send failed: %s', e)


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
        if is_wayland():
            logger.warning(
                'Wayland session detected: Linux Wayland security isolates applications.\n'
                '  Global hotkeys across other applications require root permissions on Wayland:\n'
                '    sudo ./run.sh\n'
                '  (or select an Xorg/X11 session on your Linux login screen).'
            )
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
        # Windows: try pynput first (works without admin), fallback to keyboard
        try:
            _backend = PynputBackend()
            logger.info('Windows: using pynput (no admin rights needed).')
        except Exception as e:
            logger.warning('pynput failed: %s, falling back to keyboard package.', e)
            _backend = KeyboardLibBackend()
            logger.info('Windows: using keyboard package (may need admin rights).')

    return _backend


def send_key_combo(combo: str) -> None:
    """Send Ctrl+C, Ctrl+V, etc. via the current backend."""
    get_backend().send(combo)
