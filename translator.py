"""
Translation engine and AI text improvement.
"""

import hashlib
import logging
import time

import requests
from deep_translator import GoogleTranslator as DeepGoogleTranslator

from performance import measure_time

logger = logging.getLogger(__name__)

LANG_MAP = {
    'zh-cn': 'zh-CN',
    'zh-tw': 'zh-TW',
    'pt-br': 'pt-BR',
    'auto': 'auto',
}

_REQUEST_TIMEOUT = 30
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0
_TRANSLATION_CACHE_SIZE = 500


class Translator:
    def __init__(self, config: dict) -> None:
        self.config = config
        self._translation_cache: dict[str, str] = {}

    def _get_cache_key(self, text: str, src: str, dest: str) -> str:
        """Generate cache key for translation."""
        content = f"{text}|{src}|{dest}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    @measure_time
    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text

        try:
            src = self._map_lang((self.config.get('source_lang') or 'auto').strip().lower())
            dest = self._map_lang((self.config.get('target_lang') or 'en').strip().lower())
            if dest == 'auto':
                dest = 'en'

            cache_key = self._get_cache_key(text, src, dest)
            if cache_key in self._translation_cache:
                logger.debug("Translation cache hit for: %.30s...", text)
                return self._translation_cache[cache_key]

            translator = DeepGoogleTranslator(source=src, target=dest)
            result = translator.translate(text)

            if len(self._translation_cache) >= _TRANSLATION_CACHE_SIZE:
                oldest_key = next(iter(self._translation_cache))
                del self._translation_cache[oldest_key]

            self._translation_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error("Translation error: %s", e, exc_info=True)
            return text

    def llm_available(self) -> bool:
        """True if an API key is configured for LLM calls."""
        return bool((self.config.get('api_key') or '').strip())

    def _run_llm_prompt(self, prompt: str) -> str:
        """Send *prompt* to the configured provider; raises on failure."""
        api_key = (self.config.get('api_key') or '').strip()
        if not api_key:
            raise ValueError('API key missing')

        api_provider = self.config.get('api_provider', 'groq')

        if api_provider == 'openai':
            return self._call_chat_api_with_retry(
                'https://api.openai.com/v1/chat/completions',
                {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                {'model': 'gpt-4o', 'messages': [{'role': 'user', 'content': prompt}],
                 'temperature': 0.3, 'max_tokens': 500},
                extract='openai',
            )
        if api_provider == 'anthropic':
            return self._call_chat_api_with_retry(
                'https://api.anthropic.com/v1/messages',
                {'x-api-key': api_key, 'anthropic-version': '2023-06-01',
                 'Content-Type': 'application/json'},
                {'model': 'claude-3-5-sonnet-20241022', 'max_tokens': 500,
                 'messages': [{'role': 'user', 'content': prompt}]},
                extract='anthropic',
            )
        if api_provider == 'groq':
            return self._call_chat_api_with_retry(
                'https://api.groq.com/openai/v1/chat/completions',
                {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                {'model': 'llama-3.3-70b-versatile',
                 'messages': [{'role': 'user', 'content': prompt}],
                 'temperature': 0.3, 'max_tokens': 500},
                extract='openai',
            )
        if api_provider == 'huggingface':
            return self._call_huggingface_with_retry(prompt, api_key)
        raise ValueError(f'Unknown API provider: {api_provider}')

    def _call_chat_api(self, url: str, headers: dict, payload: dict, extract: str) -> str:
        """Single HTTP call to an OpenAI-compatible or Anthropic API."""
        response = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if extract == 'openai':
            return data['choices'][0]['message']['content'].strip()
        if extract == 'anthropic':
            return data['content'][0]['text'].strip()
        raise ValueError(f'Unknown extract mode: {extract}')

    def _call_chat_api_with_retry(
        self, url: str, headers: dict, payload: dict, extract: str
    ) -> str:
        """Wrap `_call_chat_api` with exponential-backoff retry."""
        last_exc: Exception = RuntimeError('No attempts made')
        for attempt in range(_MAX_RETRIES):
            try:
                return self._call_chat_api(url, headers, payload, extract)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "API call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, wait, exc,
                    )
                    time.sleep(wait)
        raise last_exc

    def _call_huggingface(self, prompt: str, api_key: str) -> str:
        """Hugging Face Inference API (different request/response format)."""
        response = requests.post(
            'https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'inputs': prompt, 'parameters': {'max_new_tokens': 500, 'temperature': 0.3}},
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('generated_text', prompt).replace(prompt, '').strip()
        return prompt

    def _call_huggingface_with_retry(self, prompt: str, api_key: str) -> str:
        last_exc: Exception = RuntimeError('No attempts made')
        for attempt in range(_MAX_RETRIES):
            try:
                return self._call_huggingface(prompt, api_key)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "HuggingFace call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, wait, exc,
                    )
                    time.sleep(wait)
        raise last_exc

    def _map_lang(self, code: str) -> str:
        return LANG_MAP.get(code, code)

    @measure_time
    def enhance_text(self, text: str) -> str:
        if not self.llm_available():
            return text
        if not text or not text.strip():
            return text

        prompt = (
            "You are a text preprocessor for a translation pipeline. "
            "Fix any errors in the text below so the translator produces a better result. "
            "Fix: typos, grammar, punctuation, missing words, awkward phrasing, "
            "and unclear references. Keep the original language and meaning. "
            "Do NOT translate, summarize, or add commentary. "
            "Return ONLY the corrected text.\n\n"
            f"Text:\n{text}\n\nCorrected text:"
        )

        try:
            result = self._run_llm_prompt(prompt).strip()
            return result if result else text
        except Exception as e:
            logger.error("Text enhancement error: %s", e, exc_info=True)
            return text

    @measure_time
    def fix_speech_recognition_errors(self, text: str) -> str:
        if not self.llm_available():
            return text
        if not text or not text.strip():
            return text

        prompt = (
            "You are a speech recognition post-processor. "
            "The user spoke into a microphone and the speech-to-text engine produced the output below. "
            "Fix recognition errors: wrong homophones, misheard words, missing short words, "
            "cut-off endings, and any words that don't fit the context. "
            "Keep the original language. Keep the original meaning and tone. "
            "Do NOT translate, summarize, expand, or add commentary. "
            "Return ONLY the corrected text, nothing else.\n\n"
            f"Speech-to-text output:\n{text}\n\nCorrected text:"
        )

        try:
            result = self._run_llm_prompt(prompt).strip()
            return result if result else text
        except Exception as e:
            logger.error("Speech correction error: %s", e, exc_info=True)
            return text
