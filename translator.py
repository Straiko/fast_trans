"""
Translation engine and AI text improvement.
"""

import hashlib
import html
import logging
import time
from collections import OrderedDict

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

# Model names — change here only, not buried in provider branches.
_GROQ_MODEL = 'llama-3.3-70b-versatile'
_OPENAI_MODEL = 'gpt-4o'
_ANTHROPIC_MODEL = 'claude-3-5-sonnet-20241022'
_HUGGINGFACE_MODEL = 'mistralai/Mixtral-8x7B-Instruct-v0.1'
_OLLAMA_MODEL = 'llama3'  # default; user can override via config key 'ollama_model'


class Translator:
    def __init__(self, config: dict) -> None:
        self.config = config
        # OrderedDict used as LRU cache: on hit, entry is moved to the end (most-recent).
        # On eviction, the leftmost (least-recently-used) entry is removed.
        self._translation_cache: OrderedDict[str, str] = OrderedDict()
        # Cache DeepGoogleTranslator instances keyed by (src, dest) to avoid re-creation.
        self._google_translator_cache: dict[tuple[str, str], DeepGoogleTranslator] = {}

    def _get_cache_key(self, text: str, src: str, dest: str) -> str:
        """Generate cache key for translation."""
        content = f'{text}|{src}|{dest}'
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _get_google_translator(self, src: str, dest: str) -> DeepGoogleTranslator:
        """Return a cached DeepGoogleTranslator for the given language pair."""
        key = (src, dest)
        if key not in self._google_translator_cache:
            self._google_translator_cache[key] = DeepGoogleTranslator(source=src, target=dest)
        return self._google_translator_cache[key]

    @measure_time
    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text

        src = self._map_lang((self.config.get('source_lang') or 'auto').strip().lower())
        dest = self._map_lang((self.config.get('target_lang') or 'en').strip().lower())
        if dest == 'auto':
            dest = 'en'

        cache_key = self._get_cache_key(text, src, dest)
        if cache_key in self._translation_cache:
            logger.debug('Translation cache hit for: %.30s...', text)
            # Move to end = mark as most-recently used.
            self._translation_cache.move_to_end(cache_key)
            return self._translation_cache[cache_key]

        result: str | None = None

        # 1. Primary: Google Translator
        try:
            translator = self._get_google_translator(src, dest)
            result = translator.translate(text)
        except Exception as e:
            logger.warning('Google translation failed (%s). Attempting fallback...', e)
            # Invalidate cached instance on failure — it may have a stale session.
            self._google_translator_cache.pop((src, dest), None)

        # 2. Fallback: Configured LLM (Groq, OpenAI, Anthropic, HuggingFace, Ollama)
        if not result and self.llm_available():
            try:
                logger.info(
                    'Using LLM fallback (%s) for translation...',
                    self.config.get('api_provider', 'llm'),
                )
                result = self.translate_with_llm(text, src, dest)
            except Exception as llm_err:
                logger.warning('LLM translation fallback failed: %s', llm_err)

        # 3. Fallback: MyMemory free translation API
        if not result:
            try:
                logger.info('Using MyMemory fallback for translation...')
                result = self._translate_mymemory(text, src, dest)
            except Exception as mm_err:
                logger.warning('MyMemory translation fallback failed: %s', mm_err)

        if not result:
            logger.error('All translation providers failed for: %.30s...', text)
            return text

        # LRU eviction: remove least-recently-used entry when at capacity.
        if len(self._translation_cache) >= _TRANSLATION_CACHE_SIZE:
            self._translation_cache.popitem(last=False)

        self._translation_cache[cache_key] = result
        return result

    def translate_with_llm(self, text: str, src: str, dest: str) -> str:
        """Translate text using configured LLM provider."""
        if not self.llm_available():
            raise ValueError('LLM API key not configured')

        prompt = (
            f'Translate the following text to language "{dest}". '
            'Preserve original formatting, capitalization, and tone. '
            'Do NOT add explanations, notes, intros, or quotation marks. '
            'Return ONLY the translated text.\n\n'
            f'Text:\n{text}\n\nTranslation:'
        )
        result = self._run_llm_prompt(prompt).strip()
        if not result:
            raise ValueError('LLM returned empty translation')
        return result

    def _translate_mymemory(self, text: str, src: str, dest: str) -> str:
        """Fallback translation using MyMemory free API."""
        src_code = src.split('-')[0].lower()
        if src_code == 'auto':
            has_cyrillic = any('\u0400' <= ch <= '\u04ff' for ch in text)
            src_code = 'ru' if has_cyrillic else 'en'

        dest_code = dest.split('-')[0].lower()
        if dest_code == 'auto':
            dest_code = 'en' if src_code != 'en' else 'ru'

        if src_code == dest_code:
            dest_code = 'ru' if src_code == 'en' else 'en'

        langpair = f'{src_code}|{dest_code}'

        if len(text) > 500:
            chunks = _split_by_words(text, max_chars=450)
            translated_chunks = []
            for chunk in chunks:
                resp = requests.get(
                    'https://api.mymemory.translated.net/get',
                    params={'q': chunk, 'langpair': langpair},
                    timeout=_REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
                t_text = (data.get('responseData') or {}).get('translatedText')
                if t_text:
                    translated_chunks.append(html.unescape(t_text))
                else:
                    translated_chunks.append(chunk)
            return ' '.join(translated_chunks)

        resp = requests.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text, 'langpair': langpair},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        t_text = (data.get('responseData') or {}).get('translatedText')
        if t_text:
            return html.unescape(t_text).strip()
        raise ValueError('MyMemory returned no translated text')

    def llm_available(self) -> bool:
        """True if an API key is configured for LLM calls (or Ollama local mode)."""
        if self.config.get('api_provider') == 'ollama':
            return True
        return bool((self.config.get('api_key') or '').strip())

    def _run_llm_prompt(self, prompt: str) -> str:
        """Send *prompt* to the configured provider; raises on failure."""
        api_provider = self.config.get('api_provider', 'groq')

        if api_provider == 'ollama':
            return self._call_ollama_with_retry(prompt)

        api_key = (self.config.get('api_key') or '').strip()
        if not api_key:
            raise ValueError('API key missing')

        if api_provider == 'openai':
            return self._call_chat_api_with_retry(
                'https://api.openai.com/v1/chat/completions',
                {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                {
                    'model': _OPENAI_MODEL,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.3,
                    'max_tokens': 500,
                },
                extract='openai',
            )
        if api_provider == 'anthropic':
            return self._call_chat_api_with_retry(
                'https://api.anthropic.com/v1/messages',
                {
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'Content-Type': 'application/json',
                },
                {
                    'model': _ANTHROPIC_MODEL,
                    'max_tokens': 500,
                    'messages': [{'role': 'user', 'content': prompt}],
                },
                extract='anthropic',
            )
        if api_provider == 'groq':
            return self._call_chat_api_with_retry(
                'https://api.groq.com/openai/v1/chat/completions',
                {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                {
                    'model': _GROQ_MODEL,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.3,
                    'max_tokens': 500,
                },
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
                    wait = _RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        'API call failed (attempt %d/%d), retrying in %.1fs: %s',
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
        raise last_exc

    def _call_ollama(self, prompt: str) -> str:
        """Send prompt to a local Ollama instance (OpenAI-compatible endpoint)."""
        base_url = (self.config.get('ollama_url') or 'http://localhost:11434').rstrip('/')
        model = (self.config.get('ollama_model') or _OLLAMA_MODEL).strip()
        response = requests.post(
            f'{base_url}/api/chat',
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'stream': False,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data['message']['content'].strip()

    def _call_ollama_with_retry(self, prompt: str) -> str:
        last_exc: Exception = RuntimeError('No attempts made')
        for attempt in range(_MAX_RETRIES):
            try:
                return self._call_ollama(prompt)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        'Ollama call failed (attempt %d/%d), retrying in %.1fs: %s',
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
        raise last_exc

    def _call_huggingface(self, prompt: str, api_key: str) -> str:
        """Hugging Face Inference API (different request/response format)."""
        response = requests.post(
            f'https://api-inference.huggingface.co/models/{_HUGGINGFACE_MODEL}',
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
                    wait = _RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        'HuggingFace call failed (attempt %d/%d), retrying in %.1fs: %s',
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        exc,
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
            'You are a text preprocessor for a translation pipeline. '
            'Fix any errors in the text below so the translator produces a better result. '
            'Fix: typos, grammar, punctuation, missing words, awkward phrasing, '
            'and unclear references. Keep the original language and meaning. '
            'Do NOT translate, summarize, or add commentary. '
            'Return ONLY the corrected text.\n\n'
            f'Text:\n{text}\n\nCorrected text:'
        )

        try:
            result = self._run_llm_prompt(prompt).strip()
            return result if result else text
        except Exception as e:
            logger.error('Text enhancement error: %s', e, exc_info=True)
            return text

    @measure_time
    def fix_speech_recognition_errors(self, text: str) -> str:
        if not self.llm_available():
            return text
        if not text or not text.strip():
            return text

        prompt = (
            'You are a speech recognition post-processor. '
            'The user spoke into a microphone and the speech-to-text engine produced the output below. '
            'Fix recognition errors: wrong homophones, misheard words, missing short words, '
            "cut-off endings, and any words that don't fit the context. "
            'Keep the original language. Keep the original meaning and tone. '
            'Do NOT translate, summarize, expand, or add commentary. '
            'Return ONLY the corrected text, nothing else.\n\n'
            f'Speech-to-text output:\n{text}\n\nCorrected text:'
        )

        try:
            result = self._run_llm_prompt(prompt).strip()
            return result if result else text
        except Exception as e:
            logger.error('Speech correction error: %s', e, exc_info=True)
            return text


def _split_by_words(text: str, max_chars: int = 450) -> list[str]:
    """Split *text* into chunks of at most *max_chars* characters, breaking on word boundaries.

    Avoids cutting words in half (unlike plain byte-slicing).
    """
    words = text.split(' ')
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        # +1 for the space that will join preceding words
        needed = len(word) + (1 if current else 0)
        if current and current_len + needed > max_chars:
            chunks.append(' '.join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += needed

    if current:
        chunks.append(' '.join(current))

    return chunks
