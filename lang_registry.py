"""
Single source of truth for supported languages.

Both config_validator and voice_input import from here to avoid drift.
"""

# Maps language code → Google Speech-to-Text locale tag.
# Keys are the canonical codes used throughout the config.
LANG_REGISTRY: dict[str, str] = {
    'auto':  'ru-RU',   # default fallback for speech recognition
    'ru':    'ru-RU',
    'en':    'en-US',
    'uk':    'uk-UA',
    'pl':    'pl-PL',
    'de':    'de-DE',
    'fr':    'fr-FR',
    'es':    'es-ES',
    'it':    'it-IT',
    'pt':    'pt-BR',
    'pt-br': 'pt-BR',
    'tr':    'tr-TR',
    'ar':    'ar-SA',
    'zh-cn': 'zh-CN',
    'zh-tw': 'zh-TW',
    'ja':    'ja-JP',
    'ko':    'ko-KR',
}

# Set of valid language codes for config validation.
VALID_LANGUAGES: frozenset[str] = frozenset(LANG_REGISTRY.keys())

# Map used by voice_input to pick the recognition locale.
RECOGNITION_LANG_MAP: dict[str, str] = dict(LANG_REGISTRY)
