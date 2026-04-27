# Olympus — Text & Voice Translator

A desktop app for instant text translation and voice input, with optional AI-powered text enhancement for better interaction with neural networks.

[Читать на русском](README.ru.md)

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)
![Tests](https://img.shields.io/badge/tests-105%20passed-success)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## Features

| Feature | Description |
|---------|-------------|
| **Text translation** | Select text → press hotkey → get translation |
| **Voice input** | Speak → speech is recognized, translated, and pasted |
| **AI text enhancement** | Optimizes text for better AI understanding (requires API key) |
| **Speech error correction** | AI fixes voice recognition mistakes before translation |
| **Auto-replace** | Automatically replaces selected text with the translation |
| **Clipboard recovery** | Original clipboard content is restored after auto-replace |
| **Tray notifications** | "Translation pasted" / "Translation copied" feedback |
| **Settings UI** | Hotkeys, languages, microphone, AI provider — all configurable |
| **System tray** | Runs in the background, accessible from the system tray |

## Quick Start

### Windows (1-click, no admin needed)

1. Download [`install_portable.bat`](https://github.com/Straiko/fast_trans/releases/latest/download/install_portable.bat) and run it

The script automatically:
- Downloads **portable Python** (no install, no admin, DLLs built-in)
- Sets up pip
- Clones the project to `C:\Olympus\fast_trans` (works without git — downloads zip instead)
- Installs dependencies
- Launches the app

**Re-launch after installation:**
```
C:\Olympus\python\python.exe C:\Olympus\fast_trans\main.py
```

### Linux / Manual

```bash
git clone https://github.com/Straiko/fast_trans.git
cd fast_trans
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

The app starts in the system tray and opens the Settings window.

## Usage

### Translate selected text

1. Select text in **any** application
2. Press **`Ctrl+Shift+T`** (default)
3. The text is translated and automatically replaced (if auto-replace is on)
4. Original clipboard content is restored after replacement

### Voice input

1. Press **`Ctrl+Shift+V`** (default)
2. Speak into your microphone — recording auto-stops after silence
3. A review dialog opens with the recognized text
4. Choose **"Fix & translate"** (AI-corrected) or **"Translate as-is"**
5. The translation is pasted into the active field

### Settings

- Right-click the tray icon → **Settings**
- Sidebar navigation: **Hotkeys**, **Translation**, **Microphone**, **AI / API**
- All changes apply instantly without restart
- **Cancel** reverts all changes made since opening the window

## Hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+T` | Translate selected text |
| `Ctrl+Shift+V` | Start/stop voice recording |

Both are configurable in Settings → Hotkeys.

## Supported Languages

| Code | Language | Code | Language |
|------|----------|------|----------|
| `auto` | Auto-detect | `de` | German |
| `ru` | Russian | `fr` | French |
| `en` | English | `es` | Spanish |
| `uk` | Ukrainian | `it` | Italian |
| `pl` | Polish | `pt` | Portuguese |
| `tr` | Turkish | `ko` | Korean |
| `ar` | Arabic | `ja` | Japanese |
| `zh-cn` | Chinese (Simplified) | | |

Voice recognition language is automatically matched to the source language setting.

## AI Providers

The AI text enhancement and speech correction features require an API key. Free providers are available:

| Provider | Cost | Model | Get a key |
|----------|------|-------|-----------|
| **Groq** | Free | Llama 3.3 | https://console.groq.com |
| **HuggingFace** | Free | Mixtral | https://huggingface.co/settings/tokens |
| OpenAI | Paid | GPT-4 | https://platform.openai.com/api-keys |
| Anthropic | Paid | Claude | https://console.anthropic.com |

> **Tip:** Groq is recommended — it's free and very fast.

## Linux Setup

### Voice input (microphone)

```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio

# Fedora
sudo dnf install portaudio-devel
pip install pyaudio
```

### Global hotkeys without root

The app uses `pynput` for global hotkeys on Linux without root access:

```bash
pip install six pynput
```

If `pynput` is unavailable, hotkeys and automatic paste (Ctrl+C/V) won't work. The app will show a tray warning.

### SSL issues with pip

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org six pynput
```

## Testing

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

105 tests covering: translation engine, API providers, keyboard listener, voice input, settings UI, config migration.

## Building Windows `.exe`

Run on Windows only (PyInstaller targets the current OS):

```powershell
.\build_windows.ps1
```

Output: `dist\Olympus.exe`

## Project Structure

```
fast_trans/
├── main.py              # App entry point, tray icon, config
├── translator.py        # Translation engine + AI enhancement
├── keyboard_listener.py # Hotkey handling, clipboard, auto-replace
├── voice_input.py       # Microphone recording, speech recognition
├── input_backend.py     # Keyboard abstraction (pynput / keyboard)
├── settings_window.py   # Settings UI with sidebar navigation
├── ui_theme.py          # Glassmorphism + Lavender theme
├── icon.png             # App icon
├── install_portable.bat  # Windows 1-click installer (no admin)
├── install.bat           # Windows installer (needs admin for VC++)
├── run.sh               # Linux launcher (auto-detects venv/sudo)
├── build_windows.ps1    # Windows build script
├── requirements.txt    # Python dependencies
├── LICENSE              # MIT
├── tests/               # 105 unit tests
└── tools/               # Utility scripts
```

## Config Location

| OS | Path |
|----|------|
| Linux | `~/.config/olympus/config.json` |
| Windows | `%APPDATA%\olympus\config.json` |

Legacy path (`~/.text_translator_config.json`) is automatically migrated on first run.

## License

[MIT](LICENSE)
