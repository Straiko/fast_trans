# Changelog

All notable changes to Olympus are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Anthropic provider**: corrected model identifier to `claude-3-5-sonnet-20241022`
  (the previous `claude-sonnet-4-6` was not a valid API model ID)
- **OpenAI provider**: updated default model from `gpt-4` to `gpt-4o`
- **Groq provider**: updated model from `llama-3.1-8b-instant` to `llama-3.3-70b-versatile`
  for significantly better translation quality at the same free tier
- `SettingsWindow` is no longer recreated on every open — raises the existing
  window if it is already visible, preventing widget accumulation
- `NoInputBackend.send()` now emits a warning log only once instead of every call

### Added
- **Structured logging** across all modules (`logging` module, replaces bare `print`)
  — log level and format configurable; defaults to `INFO` with timestamps
- **Retry with exponential backoff** (3 attempts, 1 s / 2 s / 4 s) for all LLM
  provider HTTP calls (`_call_chat_api_with_retry`, `_call_huggingface_with_retry`)
- Full **type annotations** on all public methods in `translator.py`,
  `main.py`, `keyboard_listener.py`, `voice_input.py`, and `input_backend.py`
- `pyproject.toml` — project metadata, Ruff linter/formatter config,
  mypy config, and pytest config in one place
- `.pre-commit-config.yaml` — Ruff check+format and common pre-commit hooks
- **GitHub Actions CI** (`.github/workflows/ci.yml`):
  - Test matrix: Python 3.10, 3.11, 3.12 × Linux + Windows
  - Separate lint (Ruff) and type-check (mypy) jobs
- GitHub issue templates (bug report, feature request)
- GitHub pull-request template

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
