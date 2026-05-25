"""
Core backend module: forms AI prompt, calls Gemini,
parses and validates classifications.
"""

import json
import logging
import asyncio
import random
from datetime import datetime

import httpx

from config import (
    AI_MAX_RETRIES,
    AI_RETRY_BASE_SECONDS,
    AI_RETRY_MAX_SECONDS,
    AI_TEMPERATURE,
    AI_TOTAL_TIMEOUT_SECONDS,
    AI_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_API_BASE_URL,
    GEMINI_FALLBACK_MODELS,
    GEMINI_MODEL,
    GROQ_API_BASE_URL,
    GROQ_API_KEY,
    GROQ_MODEL,
    XAI_API_BASE_URL,
    XAI_API_KEY,
    XAI_MODEL,
)

logger = logging.getLogger(__name__)

_AI_FILE_FIELDS = (
    "file_id",
    "filename",
    "extension",
    "size_bytes",
    "modified_at",
    "accessed_at",
    "parent_dir",
)


SYSTEM_PROMPT = """Ты — классификатор файлов. Тебе предоставляется список файлов с метаданными.
Файлы уже отфильтрованы и сгруппированы клиентским приложением.

Твоя ЕДИНСТВЕННАЯ задача — для каждого файла определить:
1. Безопасно ли его удалять (confidence: 0.0–1.0)
2. К какой категории он относится
3. Краткую причину рекомендации на русском языке

КАТЕГОРИИ:
- document    — документы (docx, pdf, txt, xlsx, pptx)
- media       — фото, видео, аудио
- installer   — установщики программ (exe, msi, dmg)
- cache       — кеши приложений и браузеров
- temp        — временные файлы
- archive     — архивы (zip, rar, 7z, tar)
- backup      — резервные копии
- database    — базы данных (db, sql, sqlite)
- code        — исходный код и проекты
- config      — конфигурационные файлы
- log         — файлы логов
- other       — прочее

ПРАВИЛА ОЦЕНКИ CONFIDENCE:

Высокая безопасность (0.85–1.0):
- Установщики программ в папке Downloads
- Временные файлы (.tmp, ~$, .bak)
- Кеши браузеров и приложений
- Файлы логов (.log)
- Дубликаты (copy, (1), (2) в имени файла)
- Архивы установщиков (setup, install в имени)

Средняя безопасность (0.5–0.84):
- Документы в папке Downloads старше года
- Старые архивы без явного назначения
- Медиафайлы в временных папках

Низкая безопасность (0.0–0.49):
- Файлы с ключевыми словами: family, photo, wedding, birthday, project, work, report, thesis, diploma, contract, диплом, курсовая, семья, свадьба, проект, работа, договор
- Файлы в папках Documents, Desktop, Projects
- Исходный код (.py, .js, .java, .cpp) и папки .git
- Базы данных (.db, .sql, .sqlite)
- Конфигурации (.env, .config, settings)
- Уникальные медиафайлы (не скриншоты, не кеш)

ФОРМАТ ОТВЕТА — строго JSON, без markdown, без пояснений:
{
  "classifications": [
    {
      "file_id": "<точно скопируй file_id из входных данных>",
      "confidence": 0.92,
      "category": "installer",
      "reason": "Установщик устаревшей версии программы, можно безопасно удалить"
    }
  ]
}

КРИТИЧЕСКИ ВАЖНО:
- Поле file_id ДОЛЖНО точно совпадать с входными данными
- Каждый файл из входных данных ДОЛЖЕН присутствовать в ответе
- Не добавляй файлы, которых нет во входных данных
- Не группируй и не сортируй — просто классифицируй каждый файл
- Отвечай ТОЛЬКО JSON, никакого текста до или после"""


async def classify_files(files: list[dict]) -> list[dict]:
    safe_files = _sanitize_files_for_ai(files)
    current_date = datetime.now().strftime("%Y-%m-%d")
    user_prompt = (
        f"Текущая дата: {current_date}\n\n"
        f"Классифицируй следующие файлы:\n\n"
        f"{json.dumps(safe_files, ensure_ascii=False, indent=2)}"
    )

    try:
        raw_response = await asyncio.wait_for(
            _call_ai_provider(user_prompt),
            timeout=AI_TOTAL_TIMEOUT_SECONDS,
        )
        classifications = _parse_response(raw_response)
        classifications = _validate_classifications(safe_files, classifications)
        return classifications

    except Exception as e:
        # Log only the exception type — the message may contain the request
        # URL or response body, which we don't want in shared logs.
        logger.error(
            "AI classification failed: %s (n_files=%d)",
            type(e).__name__,
            len(safe_files),
        )
        return _default_classifications(safe_files)


def _sanitize_files_for_ai(files: list[dict]) -> list[dict]:
    """Keep only metadata fields allowed to leave the client."""
    return [
        {
            field: file_info.get(field, "")
            for field in _AI_FILE_FIELDS
        }
        for file_info in files
    ]


def _gemini_api_url_for_model(model: str) -> str:
    base = GEMINI_API_BASE_URL.rstrip("/")
    return f"{base}/models/{model}:generateContent"


def _xai_chat_completions_url() -> str:
    base = XAI_API_BASE_URL.rstrip("/")
    return f"{base}/chat/completions"


def _groq_chat_completions_url() -> str:
    base = GROQ_API_BASE_URL.rstrip("/")
    return f"{base}/chat/completions"


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {429, 500, 502, 503, 504}


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _retry_delay_seconds(attempt: int) -> float:
    base = AI_RETRY_BASE_SECONDS * (2 ** attempt)
    capped = min(base, AI_RETRY_MAX_SECONDS)
    jitter = random.uniform(0, AI_RETRY_BASE_SECONDS)
    return capped + jitter


async def _post_json_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    json_payload: dict,
    headers: dict,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(AI_MAX_RETRIES + 1):
        try:
            response = await client.post(url, json=json_payload, headers=headers)
            if response.status_code < 400:
                return response
            if not _is_retryable_status(response.status_code):
                response.raise_for_status()
            if response.status_code == 429:
                last_error = httpx.HTTPStatusError(
                    "AI HTTP 429 rate limited",
                    request=getattr(response, "request", None),
                    response=response,
                )
                retry_after = _retry_after_seconds(response)
                if retry_after is None:
                    break
                if attempt >= AI_MAX_RETRIES:
                    break
                await asyncio.sleep(min(retry_after, AI_RETRY_MAX_SECONDS))
                continue
            last_error = httpx.HTTPStatusError(
                f"retryable AI HTTP {response.status_code}",
                request=getattr(response, "request", None),
                response=response,
            )
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_error = e

        if attempt >= AI_MAX_RETRIES:
            break
        await asyncio.sleep(_retry_delay_seconds(attempt))

    if last_error is not None:
        raise last_error
    raise RuntimeError("AI request failed without an error")


async def _call_ai_provider(user_prompt: str) -> str:
    try:
        return await _call_gemini(user_prompt)
    except Exception as gemini_error:
        fallback_providers = []
        if XAI_API_KEY:
            fallback_providers.append(("xAI", _call_xai))
        if GROQ_API_KEY:
            fallback_providers.append(("Groq", _call_groq))
        if not fallback_providers:
            raise

        logger.warning(
            "Gemini provider failed; trying configured fallback AI providers "
            "(error=%s)",
            type(gemini_error).__name__,
        )
        last_error: Exception = gemini_error
        for provider_name, call_provider in fallback_providers:
            try:
                return await call_provider(user_prompt)
            except Exception as provider_error:
                last_error = provider_error
                logger.warning(
                    "%s fallback provider failed (error=%s)",
                    provider_name,
                    type(provider_error).__name__,
                )
        raise RuntimeError("All AI providers failed") from last_error


async def _call_gemini(user_prompt: str) -> str:
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}],
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": AI_TEMPERATURE,
        },
    }

    models = [GEMINI_MODEL] + [
        model for model in GEMINI_FALLBACK_MODELS if model != GEMINI_MODEL
    ]
    last_error: Exception | None = None
    for index, model in enumerate(models):
        try:
            # API key goes in the header, NOT the query string — otherwise it can leak
            # through access logs, error messages, traceback URLs, and proxy logs.
            async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
                response = await _post_json_with_retries(
                    client,
                    _gemini_api_url_for_model(model),
                    json_payload=payload,
                    headers={"x-goog-api-key": GEMINI_API_KEY},
                )
                data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as e:
            last_error = e
            status_code = e.response.status_code if e.response else 0
            if status_code == 429 and index >= len(models) - 1:
                raise
            if not _is_retryable_status(status_code):
                raise
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_error = e
        logger.warning(
            "Gemini model failed after retries; trying fallback if configured "
            "(model=%s, error=%s)",
            model,
            type(last_error).__name__,
        )

    if last_error is not None:
        raise last_error
    raise RuntimeError("Gemini request failed without an error")


async def _call_xai(user_prompt: str) -> str:
    payload = {
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": AI_TEMPERATURE,
        "response_format": {"type": "json_object"},
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await _post_json_with_retries(
            client,
            _xai_chat_completions_url(),
            json_payload=payload,
            headers={
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        data = response.json()
    return data["choices"][0]["message"]["content"]


async def _call_groq(user_prompt: str) -> str:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": AI_TEMPERATURE,
        "response_format": {"type": "json_object"},
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await _post_json_with_retries(
            client,
            _groq_chat_completions_url(),
            json_payload=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_response(raw_text: str) -> list[dict]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    parsed = json.loads(text)

    if isinstance(parsed, dict) and "classifications" in parsed:
        return parsed["classifications"]

    if isinstance(parsed, list):
        return parsed

    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list) and len(value) > 0:
                return value

    raise ValueError(f"Cannot parse AI response: {text[:200]}")


def _validate_classifications(
    original_files: list[dict],
    classifications: list[dict],
) -> list[dict]:
    requested_ids = {f["file_id"] for f in original_files}
    response_map: dict[str, dict] = {}

    for c in classifications:
        fid = c.get("file_id", "")
        if fid in requested_ids:
            response_map[fid] = {
                "file_id": fid,
                "confidence": max(
                    0.0,
                    min(1.0, float(c.get("confidence", 0.5))),
                ),
                "category": str(c.get("category", "other")),
                "reason": str(
                    c.get("reason", "Не удалось классифицировать")
                ),
            }

    for fid in requested_ids:
        if fid not in response_map:
            response_map[fid] = {
                "file_id": fid,
                "confidence": 0.5,
                "category": "other",
                "reason": "Не удалось классифицировать",
            }

    return list(response_map.values())


def _default_classifications(files: list[dict]) -> list[dict]:
    return [
        {
            "file_id": f["file_id"],
            "confidence": 0.5,
            "category": "other",
            "reason": "Сервис анализа временно недоступен",
        }
        for f in files
    ]
