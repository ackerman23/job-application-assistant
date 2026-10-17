import hashlib
import json
import threading
from collections import OrderedDict

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL

REQUEST_TIMEOUT_SECONDS = 60.0
TRANSPORT_RETRIES = 3
PARSE_ATTEMPTS = 2
CACHE_SIZE = 64

_client_lock = threading.Lock()
_client = None
_cache: OrderedDict[str, dict] = OrderedDict()
_cache_lock = threading.Lock()


def sampling_kwargs(model: str, temperature: float) -> dict:
    """GPT-5 and o-series reasoning models only accept the default temperature."""
    name = model.casefold()
    if name.startswith(("gpt-5", "o1", "o3", "o4")):
        return {}
    return {"temperature": temperature}


def _get_client():
    """Reuse one client; the SDK retries rate limits, timeouts and 5xx with backoff."""
    global _client
    with _client_lock:
        if _client is None:
            from openai import OpenAI
            _client = OpenAI(api_key=OPENAI_API_KEY, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=TRANSPORT_RETRIES)
        return _client


def _cache_key(system_prompt: str, payload: dict, model: str) -> str:
    raw = json.dumps([model, system_prompt, payload], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def complete_json(system_prompt: str, payload: dict, model: str | None = None) -> dict:
    """Request a JSON object from the configured model without logging candidate data.

    Identical requests are served from a small in-memory cache so re-submitting the
    same job description is instant. Malformed JSON triggers one corrective retry.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = model or OPENAI_MODEL
    key = _cache_key(system_prompt, payload, model)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return json.loads(json.dumps(_cache[key]))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    last_error: Exception | None = None
    for _ in range(PARSE_ATTEMPTS):
        response = _get_client().chat.completions.create(
            model=model,
            **sampling_kwargs(model, 0.1),
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = response.choices[0].message.content
        try:
            if not content:
                raise ValueError("The AI returned an empty response.")
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ValueError("The AI response was not a JSON object.")
        except ValueError as exc:
            last_error = exc
            messages = messages + [
                {"role": "assistant", "content": content or ""},
                {"role": "user", "content": "That was not a single valid JSON object. Return only the corrected JSON object."},
            ]
            continue
        with _cache_lock:
            _cache[key] = value
            while len(_cache) > CACHE_SIZE:
                _cache.popitem(last=False)
        return value
    raise ValueError(str(last_error))
