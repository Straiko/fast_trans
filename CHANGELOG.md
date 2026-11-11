# Changelog

All notable changes to Olympus are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] — 2026-11-11

### Added
- **DeepSeek provider**: integrated DeepSeek API (`deepseek-chat`) for high-speed, cost-effective translation and text enhancement
- **Google Gemini provider**: integrated Gemini API (`gemini-2.0-flash`) via OpenAI-compatible endpoint with generous free tier
- **Direct AI Translation mode** (`prefer_llm_translation`): option to translate directly with the configured AI provider for nuanced, idiomatic output, with automatic fallbacks to Google and MyMemory
- **Custom model overrides**: users can specify custom models via config (`deepseek_model`, `gemini_model`, `openai_model`, `anthropic_model`, `groq_model`, `ollama_model`)
- **Python 3.13+ compatibility**: safe pure-Python RMS audio silence calculation fallback in `voice_input.py` when `audioop` is absent (PEP 594 compliance), and added `audioop-lts` to dependencies
- **Settings UI upgrades**: DeepSeek and Gemini in provider dropdown, connection probe support, and Direct AI translation toggle in Translation tab
- **Comprehensive test suite**: added `tests/test_config_validator.py`, expanded provider and silence tests to 159 passing unit tests
- **CI/CD matrix upgrade**: added Python 3.13 to GitHub Actions test matrix, upgraded mypy step to full-project analysis, and dynamic release versioning in `build.yml`

### Fixed
- **Anthropic provider**: corrected model identifier to `claude-3-5-sonnet-20241022`
- **OpenAI provider**: updated default model to `gpt-4o`
- **Groq provider**: updated model to `llama-3.3-70b-versatile`
- `SettingsWindow` is no longer recreated on every open — raises the existing window if already visible
- `NoInputBackend.send()` warning log emitted once instead of on every key event

---

## [1.2.0] — 2026-04-27

### Added
- **Structured logging** across all modules (`logging` module, replaces bare `print`)
- **Retry with exponential backoff** (3 attempts) for all LLM provider HTTP calls
- Full **type annotations** across public APIs
- Configuration validation and sanitization (`config_validator.py`)
- Performance monitoring decorator (`performance.py`)
- LRU caching for translations in `translator.py`
- Wayland / Niri / Hyprland / Sway desktop environment detection and primary clipboard support in `input_backend.py`

---

## [1.1.0] — 2025-04-17

### Added
- HuggingFace Inference API provider (Mixtral-8x7B)
- Clipboard recovery after auto-replace
- Tray balloon notification after translation
- Legacy config auto-migration from `~/.text_translator_config.json` to XDG path
  (`~/.config/olympus/config.json`)

### Fixed
- pynput fallback on Linux without root access
- macOS: Accessibility permission prompt for pynput

---

## [1.0.0] — 2025-03-01

### Added
- Initial release
- Global hotkey for translating selected text (`Ctrl+Shift+T`)
- Voice input with Google Speech Recognition (`Ctrl+Shift+V`)
- AI text enhancement and speech error correction via Groq / OpenAI / Anthropic
- PyQt6 Settings UI with glassmorphism / lavender theme
- System tray icon with balloon notifications
- Auto-replace selected text + clipboard restore
- Windows one-click portable installer (`install_portable.bat`)
- 105 unit tests across translator, keyboard, voice, UI, and config migration
