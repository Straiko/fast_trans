"""
Configuration validation and sanitization.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

VALID_API_PROVIDERS = {'groq', 'openai', 'anthropic', 'huggingface'}
VALID_LANGUAGES = {
    'auto',
    'ru',
    'en',
    'uk',
    'pl',
    'de',
    'fr',
    'es',
    'it',
    'pt',
    'tr',
    'ar',
    'zh-cn',
    'zh-tw',
    'pt-br',
    'ja',
    'ko',
}


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize configuration values."""
    validated = config.copy()

    if 'api_provider' in validated:
        provider = validated['api_provider']
        if provider not in VALID_API_PROVIDERS:
            logger.warning(
                "Invalid api_provider '%s', defaulting to 'groq'. Valid: %s",
                provider,
                VALID_API_PROVIDERS,
            )
            validated['api_provider'] = 'groq'

    if 'source_lang' in validated:
        lang = validated['source_lang']
        if lang not in VALID_LANGUAGES:
            logger.warning(
                "Invalid source_lang '%s', defaulting to 'auto'. Valid: %s", lang, VALID_LANGUAGES
            )
            validated['source_lang'] = 'auto'

    if 'target_lang' in validated:
        lang = validated['target_lang']
        if lang not in VALID_LANGUAGES:
            logger.warning(
                "Invalid target_lang '%s', defaulting to 'en'. Valid: %s", lang, VALID_LANGUAGES
            )
            validated['target_lang'] = 'en'

    if 'microphone_index' in validated:
        try:
            mic_idx = int(validated['microphone_index'])
            if mic_idx < -1:
                logger.warning('microphone_index must be >= -1, defaulting to -1')
                validated['microphone_index'] = -1
            else:
                validated['microphone_index'] = mic_idx
        except (ValueError, TypeError):
            logger.warning('Invalid microphone_index, defaulting to -1')
            validated['microphone_index'] = -1

    for bool_key in ('auto_replace', 'ai_enhance'):
        if bool_key in validated and not isinstance(validated[bool_key], bool):
            logger.warning("'%s' must be boolean, converting", bool_key)
            validated[bool_key] = bool(validated[bool_key])

    return validated
