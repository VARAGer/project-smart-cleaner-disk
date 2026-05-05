# SmartCleaner — Бэкенд (backend.md)
# Полная техническая спецификация для разработки

> Этот файл — исчерпывающее ТЗ для серверной части SmartCleaner.
> Если ты нейросеть и тебя попросили написать код по этому файлу —
> следуй инструкциям дословно, не пропускай разделы, не упрощай архитектуру.
>
> Связанные документы:
> - app.md — спецификация клиента (PyQt6 + SQLite)
> - deployment.md — развёртывание, сетевое взаимодействие, Docker + ngrok

---

## 1. ОБЩЕЕ ОПИСАНИЕ

Бэкенд SmartCleaner — это тонкий сервис с двумя задачами:
1. Аутентификация пользователей (регистрация, логин, JWT)
2. Проксирование запросов к API нейросети (Gemini / Groq)

Бэкенд НЕ имеет доступа к файлам пользователя.
Бэкенд НЕ хранит файлы.
Бэкенд НЕ группирует и НЕ сортирует файлы.
Бэкенд получает метаданные файлов от клиента, формирует промпт,
отправляет в API нейросети, парсит ответ и возвращает клиенту.

Бэкенд запускается в Docker-контейнере.

---

## 2. СТЕК ТЕХНОЛОГИЙ И БИБЛИОТЕКИ

### Основные зависимости (requirements.txt):

```
# ===== Веб-фреймворк =====
fastapi>=0.110.0
# FastAPI — async-first, автогенерация OpenAPI-документации,
# встроенная валидация через Pydantic. Альтернатив НЕ рассматриваем.
# НЕ используй Flask, Django, Bottle — они синхронные или избыточные.

uvicorn[standard]>=0.29.0
# ASGI-сервер для запуска FastAPI.
# [standard] включает uvloop (Linux) и httptools для лучшей производительности.
# В Docker запускать как: uvicorn main:app --host 0.0.0.0 --port 8000

# ===== Валидация данных =====
pydantic>=2.6.0
# Pydantic v2 — валидация входящих запросов и формирование ответов.
# Используется внутри FastAPI автоматически.
# ВАЖНО: Pydantic v2, НЕ v1. Синтаксис отличается (model_validator вместо validator).

# ===== База данных =====
sqlalchemy>=2.0.0
# ORM для работы с БД. Используем async-режим.
# SQLAlchemy 2.0+, НЕ 1.x. Синтаксис отличается (select() вместо query()).

aiosqlite>=0.20.0
# Async-драйвер для SQLite. Для учебного проекта SQLite достаточно.
# В продакшене заменить на asyncpg + PostgreSQL.
# Строка подключения: sqlite+aiosqlite:///./data/app.db

# ===== Аутентификация =====
passlib[bcrypt]>=1.7.4
# Хеширование паролей через bcrypt.
# НИКОГДА не храни пароли в открытом виде.
# НИКОГДА не используй MD5/SHA256 для паролей — только bcrypt.

python-jose[cryptography]>=3.3.0
# Генерация и валидация JWT-токенов.
# Используем алгоритм HS256.
# Секретный ключ берём из переменной окружения JWT_SECRET.

# ===== HTTP-клиент =====
httpx>=0.27.0
# Async HTTP-клиент для запросов к API нейросети.
# НЕ используй requests — он синхронный, заблокирует event loop.

# ===== Конфигурация =====
python-dotenv>=1.0.0
# Загрузка переменных окружения из .env файла.
# В Docker переменные передаются через docker-compose.yml.
```

### Что НЕ нужно устанавливать:
- `cors` — CORS настраивается через встроенный CORSMiddleware FastAPI
- `json` — встроенная библиотека Python
- `uuid` — встроенная библиотека Python
- `datetime` — встроенная библиотека Python
- `logging` — встроенная библиотека Python

---

## 3. СТРУКТУРА ПРОЕКТА

```
server/
├── main.py                  # Точка входа FastAPI, CORS, подключение роутеров
├── config.py                # Конфигурация: env-переменные, константы
│
├── routers/                 # Эндпоинты API
│   ├── __init__.py
│   ├── auth.py              # POST /api/auth/register, POST /api/auth/login
│   └── analysis.py          # POST /api/analyze
│
├── services/                # Бизнес-логика
│   ├── __init__.py
│   ├── ai_service.py        # Формирование промпта, вызов API нейросети, парсинг ответа
│   └── auth_service.py      # Хеширование паролей, генерация JWT
│
├── models/                  # Модели данных
│   ├── __init__.py
│   ├── user.py              # SQLAlchemy-модель пользователя
│   └── schemas.py           # Pydantic-схемы запросов и ответов
│
├── database/                # Работа с БД
│   ├── __init__.py
│   └── db.py                # Подключение, создание таблиц, get_session
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env                     # НИКОГДА не коммитить в git!
```

---

## 4. КОНФИГУРАЦИЯ

```python
# server/config.py

import os
from dotenv import load_dotenv

load_dotenv()  # Загружаем .env файл (если есть)

# ===== API нейросети =====
# Gemini — основной провайдер (самый щедрый бесплатный тир)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-1.5-flash:generateContent"
)

# Groq — запасной провайдер (быстрый, но лимит меньше)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Активный провайдер: "gemini" или "groq"
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")

# ===== JWT =====
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE-ME-IN-PRODUCTION")
JWT_ALGORITHM = "HS256"
# Время жизни токена: 7 дней (в минутах)
JWT_EXPIRATION_MINUTES = 60 * 24 * 7

# ===== База данных =====
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/app.db"
)

# ===== CORS =====
# Разрешаем запросы от клиента.
# В учебном проекте разрешаем всё (*).
# В продакшене указать конкретные origins.
CORS_ORIGINS = ["*"]

# ===== Лимиты =====
MAX_FILES_PER_REQUEST = 200  # Максимум файлов в одном запросе
AI_TIMEOUT_SECONDS = 60      # Таймаут запроса к нейросети
AI_TEMPERATURE = 0.1          # Низкая температура = стабильный JSON
```

### Файл .env (пример):

```env
# НИКОГДА не коммитить в git!
# Добавь .env в .gitignore

GEMINI_API_KEY=AIzaSyВашКлючGemini
GROQ_API_KEY=gsk_ВашКлючGroq
AI_PROVIDER=gemini
JWT_SECRET=сгенерируй-случайную-строку-минимум-32-символа
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
```

### Как получить API-ключ Gemini:
1. Перейди на https://aistudio.google.com/apikey
2. Нажми «Create API key»
3. Скопируй ключ в .env
4. Бесплатный тир: 15 запросов/мин, 1M токенов/мин — хватит с запасом

### Как получить API-ключ Groq (запасной):
1. Перейди на https://console.groq.com/keys
2. Создай ключ
3. Бесплатный тир: 30 запросов/мин, 6K токенов/мин

---

## 5. БАЗА ДАННЫХ

### 5.1 Подключение и инициализация

```python
# server/database/db.py

"""
Используем SQLAlchemy 2.0 async API.
Для учебного проекта — SQLite через aiosqlite.
В продакшене — заменить на PostgreSQL + asyncpg.

ВАЖНО:
- create_async_engine() — НЕ create_engine()
- AsyncSession — НЕ Session
- async with session — НЕ session без контекстного менеджера
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL
import os

# Создаём директорию для БД
os.makedirs("data", exist_ok=True)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # True для дебага SQL-запросов
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


async def init_db():
    """Создаёт все таблицы. Вызывается при старте приложения."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """
    Dependency injection для FastAPI.
    Использование:

        @router.post("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session() as session:
        yield session
```

### 5.2 Модель пользователя

```python
# server/models/user.py

"""
Таблица users — единственная таблица на бэкенде.
Хранит логин, хеш пароля и UUID.

ВАЖНО:
- Пароль НИКОГДА не хранится в открытом виде
- Используем bcrypt через passlib
- UUID генерируется серверной стороной (uuid4)
- username уникальный (UNIQUE constraint)
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from database.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        # datetime.utcnow deprecated в Python 3.12+, используем timezone.utc
        default=lambda: datetime.now(timezone.utc),
    )
```

---

## 6. PYDANTIC-СХЕМЫ (валидация данных)

```python
# server/models/schemas.py

"""
Pydantic v2 схемы для валидации входящих запросов и формирования ответов.

ВАЖНО: Pydantic v2, НЕ v1.
- BaseModel без Config класса
- field_validator вместо validator
- model_config вместо class Config

Каждый эндпоинт имеет:
- Request-схему (что принимаем)
- Response-схему (что возвращаем)
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ===== Аутентификация =====

class AuthRequest(BaseModel):
    """Запрос на регистрацию / логин."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Логин пользователя (3-50 символов)"
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Пароль (минимум 6 символов)"
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Логин может содержать только буквы, цифры и подчёркивания."""
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "Логин может содержать только буквы, цифры и _"
            )
        return v


class AuthResponse(BaseModel):
    """Ответ на успешную регистрацию / логин."""
    user_id: str
    username: str
    access_token: str
    token_type: str = "bearer"


# ===== Анализ файлов =====

class FileMetadata(BaseModel):
    """Метаданные одного файла от клиента."""
    file_id: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Уникальный ID файла (MD5 хеш от пути)"
    )
    filename: str = Field(
        ...,
        max_length=500,
        description="Имя файла"
    )
    extension: str = Field(
        default="",
        max_length=20,
        description="Расширение файла (.docx, .exe и т.д.)"
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Размер файла в байтах"
    )
    modified_at: str = Field(
        ...,
        description="Дата последней модификации (ISO 8601)"
    )
    accessed_at: Optional[str] = Field(
        default=None,
        description="Дата последнего доступа (ISO 8601)"
    )
    parent_dir: str = Field(
        default="",
        max_length=1000,
        description="Родительская директория"
    )


class AnalysisRequest(BaseModel):
    """Запрос на анализ файлов."""
    scan_id: str = Field(
        ...,
        description="Идентификатор батча сканирования"
    )
    files: list[FileMetadata] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Список файлов для анализа (макс. 200)"
    )


class FileClassification(BaseModel):
    """Результат классификации одного файла."""
    file_id: str
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Уверенность в безопасности удаления (0.0-1.0)"
    )
    category: str = Field(
        ...,
        description="Категория файла"
    )
    reason: str = Field(
        ...,
        description="Причина рекомендации на русском языке"
    )


class AnalysisResponse(BaseModel):
    """Ответ с классификациями файлов."""
    scan_id: str
    classifications: list[FileClassification]
```

---

## 7. СЕРВИС АУТЕНТИФИКАЦИИ

```python
# server/services/auth_service.py

"""
Логика аутентификации:
1. Регистрация: username + password → bcrypt hash → сохраняем в БД → JWT
2. Логин: username + password → проверяем хеш → JWT
3. Валидация: JWT → декодируем → user_id

ВАЖНО:
- bcrypt rounds = 12 (по умолчанию в passlib) — достаточно безопасно
- JWT содержит: {"sub": user_id, "exp": timestamp}
- JWT подписывается секретным ключом из JWT_SECRET
- Время жизни токена: 7 дней
"""

from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Хеширует пароль через bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль против хеша."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    """
    Создаёт JWT-токен.

    Payload:
    {
        "sub": "uuid-пользователя",
        "exp": 1234567890  # Unix timestamp истечения
    }
    """
    # datetime.utcnow() deprecated в Python 3.12+
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> str | None:
    """
    Декодирует JWT-токен.
    Возвращает user_id или None, если токен невалидный/просрочен.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
```

---

## 8. СЕРВИС ИИ (ядро бэкенда)

```python
# server/services/ai_service.py

"""
ГЛАВНЫЙ МОДУЛЬ БЭКЕНДА.

Этот модуль:
1. Формирует системный промпт для нейросети
2. Формирует пользовательский промпт из метаданных файлов
3. Отправляет запрос к API нейросети (Gemini или Groq)
4. Парсит JSON-ответ
5. Валидирует: все file_id из запроса должны быть в ответе
6. Возвращает список классификаций

ПОДДЕРЖИВАЕМЫЕ ПРОВАЙДЕРЫ:
- Gemini 1.5 Flash (Google) — основной
- Groq (Llama 3.1 8B) — запасной

ФОРМАТ ОБЩЕНИЯ С ИИ:
- Системный промпт: инструкции по классификации (см. SYSTEM_PROMPT)
- Пользовательский промпт: JSON-массив файлов
- Ответ: JSON с массивом classifications
- Температура: 0.1 (минимум фантазий, максимум стабильности JSON)

ИИ НЕ ДЕЛАЕТ:
- Группировку по месяцам (делает клиент)
- Сортировку по размеру (делает клиент)
- Формирование бандлов (делает клиент)
- Получение или обработку содержимого файлов

ИИ ДЕЛАЕТ ТОЛЬКО:
- Получает метаданные → возвращает {file_id, confidence, category, reason}
"""

import json
import httpx
import logging
from datetime import datetime
from config import (
    GEMINI_API_KEY, GEMINI_API_URL,
    GROQ_API_KEY, GROQ_API_URL,
    AI_PROVIDER, AI_TIMEOUT_SECONDS, AI_TEMPERATURE,
)

logger = logging.getLogger(__name__)


# ============================================================
# СИСТЕМНЫЙ ПРОМПТ
# ============================================================
# Этот промпт отправляется нейросети ОДИН РАЗ при каждом запросе
# как system message. Он НЕ меняется между запросами.
# ============================================================

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


# ============================================================
# ВЫЗОВ API НЕЙРОСЕТИ
# ============================================================

async def classify_files(files: list[dict]) -> list[dict]:
    """
    Главная функция: классифицирует список файлов через нейросеть.

    Аргументы:
        files: список словарей с метаданными файлов
               [{file_id, filename, extension, size_bytes, modified_at,
                 accessed_at, parent_dir}, ...]

    Возвращает:
        список классификаций
        [{file_id, confidence, category, reason}, ...]

    При ошибке API возвращает дефолтные классификации
    (confidence=0.5, category="other").
    """
    # Формируем пользовательский промпт
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

        # Парсим JSON
        classifications = _parse_response(raw_response)

        # Валидируем: все file_id должны быть в ответе
        classifications = _validate_classifications(files, classifications)

        return classifications

    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        # При любой ошибке — дефолтные классификации
        return _default_classifications(files)


async def _call_gemini(user_prompt: str) -> str:
    """
    Вызов Gemini 1.5 Flash API.

    Документация:
    https://ai.google.dev/api/generate-content

    Особенности:
    - responseMimeType: "application/json" — ПРИНУЖДАЕТ модель отвечать JSON
    - temperature: 0.1 — минимум рандома для стабильного парсинга
    - API-ключ передаётся как query-параметр ?key=...
    """
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

    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    # Извлекаем текст ответа
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_groq(user_prompt: str) -> str:
    """
    Вызов Groq API (OpenAI-совместимый формат).

    Документация:
    https://console.groq.com/docs/api-reference

    Особенности:
    - Формат запроса совпадает с OpenAI Chat Completions API
    - Модель: llama-3.1-8b-instant (быстрая, бесплатная)
    - response_format: {"type": "json_object"} — принуждает JSON
    """
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


# ============================================================
# ПАРСИНГ И ВАЛИДАЦИЯ ОТВЕТА
# ============================================================

def _parse_response(raw_text: str) -> list[dict]:
    """
    Парсит JSON-ответ нейросети.

    Нейросеть ДОЛЖНА вернуть:
    {
        "classifications": [
            {"file_id": "...", "confidence": 0.9, "category": "...", "reason": "..."}
        ]
    }

    Но иногда модели оборачивают в markdown (```json ... ```),
    или возвращают массив напрямую без обёртки.
    Обрабатываем все варианты.
    """
    # Убираем markdown-обёртку, если есть
    text = raw_text.strip()
    if text.startswith("```"):
        # Убираем первую и последнюю строку (```json и ```)
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    parsed = json.loads(text)

    # Вариант 1: {"classifications": [...]}
    if isinstance(parsed, dict) and "classifications" in parsed:
        return parsed["classifications"]

    # Вариант 2: голый массив [...]
    if isinstance(parsed, list):
        return parsed

    # Вариант 3: другая структура с массивом внутри
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if isinstance(value, list) and len(value) > 0:
                return value

    raise ValueError(f"Cannot parse AI response: {text[:200]}")


def _validate_classifications(
    original_files: list[dict],
    classifications: list[dict],
) -> list[dict]:
    """
    Проверяет, что все file_id из запроса присутствуют в ответе.
    Файлы, отсутствующие в ответе ИИ, получают дефолтную классификацию.
    Файлы, которых не было в запросе, удаляются из ответа.
    """
    requested_ids = {f["file_id"] for f in original_files}
    response_map = {}

    for c in classifications:
        fid = c.get("file_id", "")
        if fid in requested_ids:
            # Валидируем поля
            response_map[fid] = {
                "file_id": fid,
                "confidence": max(0.0, min(1.0,
                    float(c.get("confidence", 0.5))
                )),
                "category": str(c.get("category", "other")),
                "reason": str(c.get("reason",
                    "Не удалось классифицировать"
                )),
            }

    # Добавляем дефолт для пропущенных файлов
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
    """Дефолтные классификации при ошибке API."""
    return [
        {
            "file_id": f["file_id"],
            "confidence": 0.5,
            "category": "other",
            "reason": "Сервис анализа временно недоступен",
        }
        for f in files
    ]
```

---

## 9. РОУТЕРЫ (эндпоинты API)

### 9.1 Аутентификация

```python
# server/routers/auth.py

"""
Два эндпоинта:
- POST /api/auth/register — регистрация нового пользователя
- POST /api/auth/login — вход существующего пользователя

Оба возвращают JWT-токен при успехе.

ВАЖНО:
- Проверка уникальности username при регистрации
- Ошибка 409 если username занят
- Ошибка 401 если неверный логин/пароль
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.db import get_session
from models.user import User
from models.schemas import AuthRequest, AuthResponse
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: AuthRequest,
    session: AsyncSession = Depends(get_session),
):
    """Регистрация нового пользователя."""
    # Проверяем уникальность username
    result = await session.execute(
        select(User).where(User.username == request.username)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Создаём пользователя
    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Генерируем токен
    token = create_access_token(user.id)

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        access_token=token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: AuthRequest,
    session: AsyncSession = Depends(get_session),
):
    """Вход существующего пользователя."""
    result = await session.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(
        request.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user.id)

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        access_token=token,
    )
```

### 9.2 Анализ файлов

```python
# server/routers/analysis.py

"""
POST /api/analyze — главный эндпоинт.

Принимает: список метаданных файлов (макс. 200).
Возвращает: список классификаций от нейросети.

Требует: JWT-токен в заголовке Authorization.

ВАЖНО:
- Валидация JWT через Depends(get_current_user)
- Лимит 200 файлов на запрос (валидация в Pydantic-схеме)
- При ошибке ИИ возвращаем дефолтные классификации, НЕ 500
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.schemas import AnalysisRequest, AnalysisResponse
from services.ai_service import classify_files
from services.auth_service import decode_token

router = APIRouter(prefix="/api", tags=["analysis"])
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Dependency: извлекает user_id из JWT.
    Возвращает user_id или бросает 401.
    """
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user_id


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_files(
    request: AnalysisRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Анализирует файлы через нейросеть.

    Поток:
    1. Клиент отправляет метаданные файлов
    2. Бэкенд формирует промпт и вызывает API нейросети
    3. Бэкенд парсит и валидирует JSON-ответ
    4. Бэкенд возвращает классификации клиенту
    """
    # Преобразуем Pydantic-модели в словари для промпта
    files_for_ai = [
        {
            "file_id": f.file_id,
            "filename": f.filename,
            "extension": f.extension,
            "size_bytes": f.size_bytes,
            "modified_at": f.modified_at,
            "accessed_at": f.accessed_at or "",
            "parent_dir": f.parent_dir,
        }
        for f in request.files
    ]

    # Классифицируем через ИИ
    classifications = await classify_files(files_for_ai)

    return AnalysisResponse(
        scan_id=request.scan_id,
        classifications=classifications,
    )
```

---

## 10. ТОЧКА ВХОДА (main.py)

```python
# server/main.py

"""
Точка входа FastAPI-приложения.

При старте:
1. Создаётся экземпляр FastAPI
2. Подключается CORS middleware
3. Подключаются роутеры (auth, analysis)
4. Создаются таблицы в БД (lifespan event)

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

В Docker:
    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db import init_db
from routers import auth, analysis
from config import CORS_ORIGINS
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event: выполняется при старте и остановке приложения.
    Создаём таблицы в БД при старте.
    """
    await init_db()
    logging.info("Database initialized")
    yield
    logging.info("Application shutting down")


app = FastAPI(
    title="SmartCleaner API",
    description="Backend for SmartCleaner file analysis service",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — разрешаем запросы от клиента
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router)
app.include_router(analysis.router)


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса. Используется Docker healthcheck."""
    return {"status": "ok"}
```

---

## 11. DOCKER

### 11.1 Dockerfile

```dockerfile
# server/Dockerfile

FROM python:3.12-slim

# Рабочая директория
WORKDIR /app

# Устанавливаем зависимости первыми (кешируется Docker layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Создаём директорию для БД
RUN mkdir -p /app/data

# Порт
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Запуск
# --workers 1 — для учебного проекта достаточно одного воркера
# В продакшене: --workers 4 (по количеству CPU)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.2 docker-compose.yml

```yaml
# server/docker-compose.yml

version: "3.9"

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      # API-ключи передаются через env_file или environment
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}
      - AI_PROVIDER=${AI_PROVIDER:-gemini}
      - JWT_SECRET=${JWT_SECRET}
      - DATABASE_URL=sqlite+aiosqlite:///./data/app.db
    volumes:
      # Персистентное хранение БД (выживает перезапуск контейнера)
      - smartcleaner-data:/app/data
    restart: unless-stopped

volumes:
  smartcleaner-data:
```

### 11.3 .dockerignore

```
__pycache__
*.pyc
.env
.git
.gitignore
*.md
data/
```

### 11.4 Запуск

```bash
# 1. Создать .env файл (см. раздел 4)

# 2. Собрать и запустить
docker-compose up --build -d

# 3. Проверить здоровье
curl http://localhost:8000/health
# {"status":"ok"}

# 4. Проверить документацию API
# Открыть в браузере: http://localhost:8000/docs

# 5. Остановить
docker-compose down

# 6. Посмотреть логи
docker-compose logs -f backend
```

---

## 12. API ДОКУМЕНТАЦИЯ

FastAPI автоматически генерирует OpenAPI (Swagger) документацию.
Доступна по адресу: http://localhost:8000/docs

### Эндпоинты:

```
GET  /health              — Проверка здоровья (без авторизации)
POST /api/auth/register   — Регистрация пользователя
POST /api/auth/login      — Вход пользователя
POST /api/analyze         — Анализ файлов (требует JWT)
```

### Формат ошибок:

```json
// 401 Unauthorized
{"detail": "Invalid or expired token"}

// 409 Conflict
{"detail": "Username already exists"}

// 422 Validation Error (Pydantic)
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "username"],
      "msg": "String should have at least 3 characters",
      "input": "ab"
    }
  ]
}
```

---

## 13. ОПТИМИЗАЦИИ И ЛУЧШИЕ ПРАКТИКИ

### Производительность:
1. async/await ВЕЗДЕ — FastAPI + httpx + SQLAlchemy async
2. Один воркер uvicorn для учебного проекта (4 для продакшена)
3. connection pooling SQLAlchemy (встроен)
4. Docker volume для персистентности БД

### Безопасность:
1. Пароли хешируются bcrypt (НИКОГДА не MD5/SHA)
2. JWT с ограниченным временем жизни (7 дней)
3. API-ключ нейросети ТОЛЬКО на сервере (в .env)
4. .env НИКОГДА не коммитить (добавить в .gitignore)
5. CORS настроен (в продакшене — конкретные origins)
6. Валидация входных данных через Pydantic

### Устойчивость к ошибкам:
1. При ошибке API нейросети — возвращаем дефолтные классификации
2. Парсинг ответа ИИ обрабатывает markdown-обёртку, голые массивы
3. Валидация: все file_id из запроса должны быть в ответе
4. Healthcheck в Docker для автоматического перезапуска

### Что НЕ нужно делать:
- НЕ использовать Flask/Django (избыточно, синхронно)
- НЕ использовать requests (синхронный, блокирует event loop)
- НЕ хранить пароли в открытом виде
- НЕ коммитить .env в git
- НЕ группировать/сортировать файлы на бэкенде (это задача клиента)
- НЕ возвращать 500 при ошибке ИИ (возвращать дефолтные классификации)
- НЕ доверять ответу ИИ без валидации (file_id может быть пропущен)
- НЕ отправлять полный путь к файлу на бэкенд (приватность)

---

## 14. РАСШИРЕНИЕ: ДОБАВЛЕНИЕ НОВОГО ПРОВАЙДЕРА ИИ

Если нужно добавить новый провайдер (например, OpenRouter, Together AI):

1. Добавь ключ в config.py:
   ```python
   OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
   OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
   ```

2. Добавь функцию в ai_service.py:
   ```python
   async def _call_openrouter(user_prompt: str) -> str:
       # OpenAI-совместимый формат (как Groq)
       ...
   ```

3. Добавь ветку в classify_files():
   ```python
   elif AI_PROVIDER == "openrouter":
       raw_response = await _call_openrouter(user_prompt)
   ```

4. Добавь ключ в .env и docker-compose.yml

Все провайдеры используют один и тот же SYSTEM_PROMPT.
Формат ответа одинаковый — JSON с classifications.
Отличается только формат HTTP-запроса к API.
