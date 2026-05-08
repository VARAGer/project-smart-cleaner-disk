"""
Core backend module: forms AI prompt, calls provider (Gemini/Groq),
parses and validates classifications.
"""

import json
import logging
from datetime import datetime

import httpx

from config import (
    AI_PROVIDER,
    AI_TEMPERATURE,
    AI_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_API_URL,
    GROQ_API_KEY,
    GROQ_API_URL,
)

logger = logging.getLogger(__name__)


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
    current_date = datetime.now().strftime("%Y-%m-%d")
    user_prompt = (
        f"Текущая дата: {current_date}\n\n"
        f"Классифицируй следующие файлы:\n\n"
        f"{json.dumps(files, ensure_ascii=False, indent=2)}"
    )

    try:
        if AI_PROVIDER == "gemini":
            raw_response = await _call_gemini(user_prompt)
        elif AI_PROVIDER == "groq":
            raw_response = await _call_groq(user_prompt)
        else:
            raise ValueError(f"Unknown AI provider: {AI_PROVIDER}")

        classifications = _parse_response(raw_response)
        classifications = _validate_classifications(files, classifications)
        return classifications

    except Exception as e:
        # Log only the exception type — the message may contain the request
        # URL or response body, which we don't want in shared logs.
        logger.error(
            "AI classification failed: %s (provider=%s, n_files=%d)",
            type(e).__name__,
            AI_PROVIDER,
            len(files),
        )
        return _default_classifications(files)


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

    # API key goes in the header, NOT the query string — otherwise it can leak
    # through access logs, error messages, traceback URLs, and proxy logs.
    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await client.post(
            GEMINI_API_URL,
            json=payload,
            headers={"x-goog-api-key": GEMINI_API_KEY},
        )
        response.raise_for_status()
        data = response.json()

    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_groq(user_prompt: str) -> str:
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": AI_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await client.post(
            GROQ_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
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
