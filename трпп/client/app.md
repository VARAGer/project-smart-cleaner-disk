# SmartCleaner — Клиентское приложение (app.md)
# Полная техническая спецификация для разработки

> Этот файл — исчерпывающее ТЗ для десктопного клиента SmartCleaner.
> Если ты нейросеть и тебя попросили написать код по этому файлу —
> следуй инструкциям дословно, не пропускай разделы, не упрощай архитектуру.
>
> Связанные документы:
> - backend.md — спецификация бэкенда (FastAPI + Docker)
> - deployment.md — развёртывание, сетевое взаимодействие, упаковка в .exe

---

## 1. ОБЩЕЕ ОПИСАНИЕ ПРОЕКТА

SmartCleaner — десктопное приложение для интеллектуальной очистки файловой
системы. Приложение сканирует диски пользователя, собирает метаданные файлов,
отправляет их на бэкенд для классификации нейросетью, формирует «бандлы»
(группы файлов для удаления) и предлагает пользователю удалить ненужные файлы.

Клиент — это PyQt6-приложение, которое устанавливается на машину пользователя.
Бэкенд — это отдельный сервис в Docker-контейнере (описан в backend.md).

### Ключевые принципы:
- Клиент делает ВСЮ тяжёлую работу: сканирование, фильтрация, группировка, сортировка, удаление
- Бэкенд — тонкий прокси между клиентом и API нейросети + аутентификация
- Нейросеть только классифицирует файлы (confidence + category + reason)
- Никакое содержимое файлов НИКОГДА не покидает машину пользователя — только метаданные
- Полный путь к файлу НЕ отправляется на бэкенд — только parent_dir и filename

---

## 2. СТЕК ТЕХНОЛОГИЙ И БИБЛИОТЕКИ

### Основные зависимости (requirements.txt):

```
# ===== GUI =====
PyQt6>=6.6.0
# Используем PyQt6, НЕ PyQt5, НЕ PySide6, НЕ tkinter, НЕ customtkinter.
# PyQt6 обеспечивает нативный внешний вид на Windows, macOS, Linux.

# ===== HTTP-клиент =====
httpx>=0.27.0
# Используем httpx, НЕ requests.
# httpx поддерживает async из коробки, что критично для неблокирующего GUI.
# НИКОГДА не используй requests — он синхронный и заморозит интерфейс.

# ===== Определение типов файлов =====
# Тип файла определяется по расширению (.docx, .exe и т.д.).
# Этого достаточно для классификации — нейросеть анализирует
# расширение, имя файла и parent_dir для определения категории.
#
# Если нужна более точная классификация по содержимому (magic bytes):
# pip install python-magic-bin  (Windows) / python-magic (Linux/macOS)
# Но для учебного проекта это избыточно и усложняет установку на Windows.

# ===== Информация о дисках =====
psutil>=5.9.0
# Получение списка дисков, их размеров, файловых систем.
# Кроссплатформенный. Работает на Windows, macOS, Linux.

# ===== Сборка =====
PyInstaller>=6.0.0
# Упаковка в .exe / .app. Только для dev-окружения.
# Альтернатива: Nuitka (компилирует в C, быстрее, но сложнее в настройке).
```

### Встроенные библиотеки Python (НЕ нужно устанавливать):
- `os` — работа с файловой системой (scandir, remove, path)
- `sqlite3` — локальная база данных
- `hashlib` — генерация file_id (MD5-хеш от пути)
- `json` — сериализация данных
- `datetime` — работа с датами
- `collections.defaultdict` — группировка файлов
- `asyncio` — асинхронные операции (используется внутри QThread для httpx)
- `platform` — определение ОС (Windows/macOS/Linux)
- `subprocess` — открытие файлов на macOS/Linux

НЕ используем напрямую:
- `threading` — НЕ использовать, вместо него QThread из PyQt6
- `pathlib` — НЕ использовать, весь код работает через os.path и os.scandir

### Опциональные зависимости (расширенная функциональность):
```
# Метаданные медиафайлов (для более точной классификации)
Pillow>=10.0.0          # EXIF из изображений
mutagen>=1.47.0         # Метаданные аудио

# Мониторинг изменений в реальном времени (для будущих версий)
watchdog>=4.0.0
```

### Установка зависимостей на Windows:
```bash
pip install PyQt6 httpx psutil
```

---

## 3. СТРУКТУРА ПРОЕКТА

```
client/
├── main.py                          # Точка входа приложения
├── config.py                        # Конфигурация (URL бэкенда, константы)
│
├── scanner/                         # Модуль сканирования файловой системы
│   ├── __init__.py
│   ├── disk_detector.py             # Обнаружение подключённых дисков
│   ├── file_scanner.py              # Рекурсивный обход + сбор метаданных
│   └── incremental.py               # Инкрементальное сканирование
│
├── heuristics/                      # Логика фильтрации и группировки
│   ├── __init__.py
│   ├── filters.py                   # Фильтры: системные, по возрасту, по размеру
│   ├── bundler.py                   # Группировка по месяцам + сортировка по размеру
│   └── marker_manager.py            # Управление маркерами skip/protected
│
├── api_client/                      # Коммуникация с бэкендом
│   ├── __init__.py
│   ├── auth.py                      # Регистрация, логин, хранение JWT
│   └── analysis.py                  # Отправка файлов на анализ, получение классификаций
│
├── database/                        # Локальная база данных
│   ├── __init__.py
│   └── local_db.py                  # Инициализация SQLite, миграции
│
├── gui/                             # Графический интерфейс (PyQt6)
│   ├── __init__.py
│   ├── main_window.py               # Главное окно приложения
│   ├── login_window.py              # Окно входа / регистрации
│   ├── disk_selector.py             # Выбор дисков для сканирования
│   ├── scan_progress.py             # Прогресс-бар сканирования
│   ├── bundle_list_widget.py        # Список бандлов (название + размер)
│   ├── bundle_detail_widget.py      # Содержимое бандла (таблица файлов)
│   ├── review_bundle_widget.py      # Бандл пересмотра исключённых файлов
│   ├── settings_widget.py           # Настройки пользователя
│   └── confirmation_dialog.py       # Диалог подтверждения удаления
│
├── utils/                           # Вспомогательные функции
│   ├── __init__.py
│   ├── file_operations.py           # Удаление файлов, перемещение в корзину
│   └── formatters.py                # Форматирование размеров, дат
│
└── requirements.txt
```

### Правила именования:
- Файлы: snake_case (bundle_list_widget.py)
- Классы: PascalCase (BundleListWidget)
- Функции и переменные: snake_case (get_available_disks)
- Константы: UPPER_SNAKE_CASE (SKIP_DIRS, MAX_BATCH_SIZE)

---

## 4. КОНФИГУРАЦИЯ

```python
# client/config.py

import os
import platform

# ===== Бэкенд =====
# URL бэкенда определяется ДИНАМИЧЕСКИ.
# Бэкенд работает на машине разработчика за ngrok-туннелем,
# поэтому URL меняется при каждом перезапуске ngrok.
# Актуальный URL хранится в GitHub Gist (см. deployment.md).
#
# Приоритет:
# 1. Переменная окружения SMARTCLEANER_BACKEND (для разработки)
# 2. URL из GitHub Gist (для продакшена)
# 3. Fallback: http://localhost:8000

CONFIG_GIST_URL = (
    "https://gist.githubusercontent.com/"
    "ТВОЙ_GITHUB_USERNAME/ID_GIST/raw/config.json"
)
# ^^^ ЗАМЕНИТЬ на реальный URL гиста при развёртывании!

def get_backend_url() -> str:
    """Получает актуальный URL бэкенда."""
    # 1. Переменная окружения (для локальной разработки)
    env_url = os.getenv("SMARTCLEANER_BACKEND")
    if env_url:
        return env_url

    # 2. GitHub Gist (для продакшена — ngrok URL)
    try:
        import httpx
        response = httpx.get(CONFIG_GIST_URL, timeout=5.0)
        if response.status_code == 200:
            return response.json()["backend_url"]
    except Exception:
        pass

    # 3. Fallback для локальной разработки
    return "http://localhost:8000"

BACKEND_URL = get_backend_url()
API_PREFIX = "/api"
AUTH_ENDPOINT = f"{API_PREFIX}/auth"
ANALYSIS_ENDPOINT = f"{API_PREFIX}/analyze"

# ===== Локальная БД =====
# На Windows: %APPDATA%/SmartCleaner/
# На macOS: ~/Library/Application Support/SmartCleaner/
# На Linux: ~/.local/share/SmartCleaner/
def get_data_dir() -> str:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "SmartCleaner")
    elif system == "Darwin":
        return os.path.expanduser("~/Library/Application Support/SmartCleaner")
    else:
        return os.path.expanduser("~/.local/share/SmartCleaner")

DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "smartcleaner.db")
TOKEN_PATH = os.path.join(DATA_DIR, "auth_token.json")

# ===== Сканирование =====
# Директории, которые ВСЕГДА пропускаются при сканировании.
# Это системные и служебные папки, удаление файлов из которых опасно.
SKIP_DIRS = {
    # Windows системные
    "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information",
    "ProgramData", "Recovery", "PerfLogs",
    # Разработка (внутри много мелких файлов, не мусор)
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".pytest_cache", ".mypy_cache",
    # macOS
    ".Spotlight-V100", ".fseventsd", ".Trashes",
}

# Расширения системных файлов — никогда не предлагать к удалению
SYSTEM_EXTENSIONS = {
    ".sys", ".dll", ".drv", ".inf", ".cat", ".mui",
    ".manifest", ".mof", ".msc",
}

# ===== Батчинг =====
# Максимум файлов в одном запросе к бэкенду.
# Gemini 1.5 Flash имеет контекст ~1M токенов, но лучше не рисковать.
# 200 файлов ≈ 20-30K токенов — комфортно.
MAX_BATCH_SIZE = 200

# ===== Значения по умолчанию =====
DEFAULT_MIN_AGE_MONTHS = 6       # Минимальный возраст файлов (месяцы)
DEFAULT_MIN_SIZE_BYTES = 1024    # Минимальный размер (1 КБ)
DEFAULT_SKIP_DURATION_DAYS = 90  # Срок действия skip-маркера (дни)
```

---

## 5. ЛОКАЛЬНАЯ БАЗА ДАННЫХ (SQLite)

### 5.1 Инициализация

```python
# client/database/local_db.py

import sqlite3
import os
from config import DB_PATH, DATA_DIR

def init_database():
    """
    Создаёт базу данных и все таблицы.
    Вызывается при первом запуске приложения.
    Безопасно вызывать повторно — CREATE TABLE IF NOT EXISTS.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    conn.executescript("""
        -- Основная таблица: индекс всех просканированных файлов
        CREATE TABLE IF NOT EXISTS scanned_files (
            file_id       TEXT PRIMARY KEY,
            path          TEXT UNIQUE NOT NULL,
            filename      TEXT NOT NULL,
            extension     TEXT,
            size_bytes    INTEGER NOT NULL,
            created_at    TIMESTAMP,
            modified_at   TIMESTAMP,
            accessed_at   TIMESTAMP,
            parent_dir    TEXT,
            disk_label    TEXT,
            scan_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Индексы для быстрых выборок
        CREATE INDEX IF NOT EXISTS idx_modified
            ON scanned_files(modified_at);
        CREATE INDEX IF NOT EXISTS idx_size
            ON scanned_files(size_bytes DESC);
        CREATE INDEX IF NOT EXISTS idx_disk
            ON scanned_files(disk_label);
        CREATE INDEX IF NOT EXISTS idx_extension
            ON scanned_files(extension);

        -- Маркеры исключения файлов
        CREATE TABLE IF NOT EXISTS file_markers (
            file_id       TEXT PRIMARY KEY
                          REFERENCES scanned_files(file_id) ON DELETE CASCADE,
            marker_type   TEXT NOT NULL
                          CHECK(marker_type IN ('skip', 'protected')),
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at    TIMESTAMP,
            skip_count    INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_marker_type
            ON file_markers(marker_type);
        CREATE INDEX IF NOT EXISTS idx_expires
            ON file_markers(expires_at);

        -- Кеш результатов классификации ИИ
        -- Позволяет не отправлять файлы повторно при следующем запуске
        CREATE TABLE IF NOT EXISTS analysis_cache (
            file_id       TEXT PRIMARY KEY
                          REFERENCES scanned_files(file_id) ON DELETE CASCADE,
            confidence    REAL,
            category      TEXT,
            reason        TEXT,
            analyzed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Пользовательские настройки (key-value)
        CREATE TABLE IF NOT EXISTS user_settings (
            key           TEXT PRIMARY KEY,
            value         TEXT NOT NULL
        );

        -- Значения по умолчанию (только при первой инициализации)
        INSERT OR IGNORE INTO user_settings (key, value) VALUES
            ('min_age_months', '6'),
            ('min_size_bytes', '1024'),
            ('skip_duration_days', '90'),
            ('last_scan_date', ''),
            ('selected_disks', '[]');

        -- Включаем WAL-режим для лучшей производительности
        -- при одновременном чтении и записи
        PRAGMA journal_mode=WAL;

        -- Включаем каскадное удаление
        PRAGMA foreign_keys=ON;
    """)

    conn.close()
```

### 5.2 Важные замечания по SQLite:

- **journal_mode=WAL** — обязательно. Позволяет читать данные из БД
  пока фоновый поток записывает (сканирование). Без WAL GUI будет
  блокироваться при каждой вставке.
- **foreign_keys=ON** — нужно включать при КАЖДОМ подключении
  (SQLite по умолчанию не включает FK).
- **ON DELETE CASCADE** — при удалении файла из scanned_files
  автоматически удаляются его маркеры и кеш классификации.
- Все даты хранятся как ISO 8601 строки (YYYY-MM-DDTHH:MM:SS).
- file_id — строка из 12 символов, MD5-хеш от полного пути файла.

---

## 6. МОДУЛЬ СКАНИРОВАНИЯ

### 6.1 Обнаружение дисков

```python
# client/scanner/disk_detector.py

import psutil

def get_available_disks() -> list[dict]:
    """
    Возвращает список всех доступных дисков с информацией.

    Каждый элемент:
    {
        "device": "C:\\",         # Идентификатор устройства
        "mountpoint": "C:\\",     # Точка монтирования
        "fstype": "NTFS",        # Файловая система
        "total_bytes": ...,      # Общий размер в байтах
        "used_bytes": ...,       # Использовано
        "free_bytes": ...,       # Свободно
        "percent_used": 75.3,    # Процент использования
    }

    Пропускает:
    - CD/DVD приводы (opts содержит "cdrom")
    - Сетевые диски (fstype пустой)
    - Диски без доступа (PermissionError)
    """
    disks = []
    for partition in psutil.disk_partitions(all=False):
        if "cdrom" in partition.opts or partition.fstype == "":
            continue
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except PermissionError:
            continue

        disks.append({
            "device": partition.device,
            "mountpoint": partition.mountpoint,
            "fstype": partition.fstype,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "percent_used": usage.percent,
        })

    return disks
```

### 6.2 Сканирование файловой системы

```python
# client/scanner/file_scanner.py

import os
import hashlib
from datetime import datetime
from config import SKIP_DIRS, SYSTEM_EXTENSIONS

def generate_file_id(file_path: str) -> str:
    """
    Генерирует уникальный ID файла — MD5-хеш от полного пути.
    Обрезаем до 12 символов — вероятность коллизии пренебрежимо мала
    при масштабе домашнего ПК (< 1M файлов).
    """
    return hashlib.md5(file_path.encode("utf-8")).hexdigest()[:12]


def scan_directory(root_path: str, disk_label: str,
                   progress_callback=None, _counter=None):
    """
    Рекурсивный генератор метаданных файлов.

    Использует os.scandir() — это КРИТИЧЕСКИ ВАЖНО.
    os.scandir() возвращает DirEntry, который содержит метаданные
    (размер, даты) без дополнительных системных вызовов.
    os.walk() + os.stat() делает 2 системных вызова на файл — вдвое медленнее.

    НЕ ИСПОЛЬЗОВАТЬ: os.walk(), pathlib.Path.rglob(), glob.glob().
    Все они медленнее os.scandir() для нашей задачи.

    Аргументы:
        root_path: корневая директория для сканирования (например, "C:\\")
        disk_label: метка диска (например, "C:\\")
        progress_callback: callable(count: int) — вызывается каждые N файлов
        _counter: внутренний счётчик (не передавать вручную)

    Yields:
        dict с метаданными файла (см. структуру ниже)
    """
    # Используем изменяемый список как счётчик,
    # чтобы он сохранялся между рекурсивными вызовами
    if _counter is None:
        _counter = [0]

    try:
        for entry in os.scandir(root_path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    # Пропускаем системные и служебные директории
                    if entry.name in SKIP_DIRS:
                        continue
                    # Пропускаем скрытые директории на Windows
                    if entry.name.startswith(".") or entry.name.startswith("$"):
                        continue
                    # Рекурсия — передаём тот же _counter
                    yield from scan_directory(
                        entry.path, disk_label, progress_callback, _counter
                    )

                elif entry.is_file(follow_symlinks=False):
                    stat = entry.stat()
                    extension = os.path.splitext(entry.name)[1].lower()

                    # Пропускаем системные расширения сразу при сканировании
                    if extension in SYSTEM_EXTENSIONS:
                        continue

                    _counter[0] += 1
                    if progress_callback and _counter[0] % 1000 == 0:
                        progress_callback(_counter[0])

                    yield {
                        "file_id": generate_file_id(entry.path),
                        "path": entry.path,
                        "filename": entry.name,
                        "extension": extension,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(
                            stat.st_ctime
                        ).isoformat(),
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "accessed_at": datetime.fromtimestamp(
                            stat.st_atime
                        ).isoformat(),
                        "parent_dir": os.path.dirname(entry.path),
                        "disk_label": disk_label,
                    }

            except (PermissionError, OSError):
                # Файл заблокирован или недоступен — пропускаем молча
                continue

    except (PermissionError, OSError):
        # Директория недоступна — пропускаем молча
        pass
```

### 6.3 Инкрементальное сканирование

```python
# client/scanner/incremental.py

"""
ПРИНЦИП РАБОТЫ:

Первый запуск:
  - Полный обход всей файловой системы через scan_directory()
  - Все файлы записываются в таблицу scanned_files

Повторные запуски:
  1. Загружаем из БД существующий индекс для диска (path → modified_at)
  2. Обходим файловую систему через os.scandir()
  3. Для каждого файла сравниваем modified_at (mtime) из БД с реальным
  4. Если mtime совпадает → файл не изменился, ПРОПУСКАЕМ
  5. Если mtime изменился → обновляем запись в БД
  6. Если файл новый (нет в БД) → вставляем
  7. Если файл из БД не найден на диске → удаляем из БД
  8. Записываем результат батчами по 500 (для скорости)

ПОЧЕМУ ЭТО БЫСТРО:
  - os.scandir() получает mtime без дополнительного syscall
  - Сравнение строк (ISO дат) быстрее, чем полный сбор метаданных
  - При повторном запуске ~95% файлов не изменились → пропускаются
  - Первое сканирование: 1-3 мин. Повторное: 10-30 сек.

ВАЖНО:
  - Батчевая вставка через executemany() или ручной flush каждые 500 записей
  - conn.commit() вызывать НЕ после каждой записи, а после каждого батча
  - Иначе SQLite будет делать fsync на каждый INSERT — катастрофически медленно
"""

import os
import sqlite3
from datetime import datetime
import hashlib
from config import DB_PATH, SKIP_DIRS, SYSTEM_EXTENSIONS

class IncrementalScanner:
    BATCH_SIZE = 500

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def scan(self, root_path: str, disk_label: str,
             progress_callback=None) -> dict:
        """
        Инкрементальное сканирование.

        Возвращает:
        {
            "new": 1234,        # Новых файлов найдено
            "updated": 56,      # Файлов обновлено (mtime изменился)
            "deleted": 78,      # Файлов удалено из индекса (нет на диске)
            "unchanged": 45678, # Файлов без изменений (пропущены)
            "total": 47046,     # Всего обработано
        }
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Шаг 1: загружаем существующий индекс
        existing = {}
        rows = conn.execute(
            "SELECT file_id, path, modified_at FROM scanned_files "
            "WHERE disk_label = ?",
            (disk_label,)
        ).fetchall()
        for row in rows:
            existing[row[1]] = {
                "file_id": row[0],
                "modified_at": row[2]
            }

        stats = {"new": 0, "updated": 0, "deleted": 0, "unchanged": 0}
        seen_paths = set()
        batch = []

        # Шаг 2: обходим файловую систему
        for file_info in self._walk(root_path, disk_label):
            path = file_info["path"]
            seen_paths.add(path)

            if path in existing:
                if existing[path]["modified_at"] == file_info["modified_at"]:
                    stats["unchanged"] += 1
                    continue
                else:
                    file_info["file_id"] = existing[path]["file_id"]
                    batch.append(("update", file_info))
                    stats["updated"] += 1
            else:
                batch.append(("insert", file_info))
                stats["new"] += 1

            if len(batch) >= self.BATCH_SIZE:
                self._flush_batch(conn, batch)
                batch.clear()

            if progress_callback:
                total = stats["new"] + stats["updated"] + stats["unchanged"]
                progress_callback(total)

        # Финальный flush
        if batch:
            self._flush_batch(conn, batch)

        # Шаг 3: удаляем из БД файлы, которых больше нет на диске
        deleted_paths = set(existing.keys()) - seen_paths
        if deleted_paths:
            # SQLite имеет лимит на количество параметров (~999).
            # Если удалённых файлов много, разбиваем на чанки.
            for chunk in self._chunks(list(deleted_paths), 900):
                placeholders = ",".join("?" * len(chunk))
                conn.execute(
                    f"DELETE FROM scanned_files "
                    f"WHERE path IN ({placeholders})",
                    chunk
                )
            conn.commit()
            stats["deleted"] = len(deleted_paths)

        # Шаг 4: обновляем дату последнего сканирования
        conn.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) "
            "VALUES (?, ?)",
            ("last_scan_date", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        stats["total"] = sum(stats.values())
        return stats

    def _walk(self, root_path: str, disk_label: str):
        """Генератор файлов. Аналогичен file_scanner.scan_directory()."""
        try:
            for entry in os.scandir(root_path):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in SKIP_DIRS:
                            continue
                        if entry.name.startswith((".", "$")):
                            continue
                        yield from self._walk(entry.path, disk_label)
                    elif entry.is_file(follow_symlinks=False):
                        stat = entry.stat()
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in SYSTEM_EXTENSIONS:
                            continue
                        yield {
                            "file_id": hashlib.md5(
                                entry.path.encode("utf-8")
                            ).hexdigest()[:12],
                            "path": entry.path,
                            "filename": entry.name,
                            "extension": ext,
                            "size_bytes": stat.st_size,
                            "created_at": datetime.fromtimestamp(
                                stat.st_ctime
                            ).isoformat(),
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                            "accessed_at": datetime.fromtimestamp(
                                stat.st_atime
                            ).isoformat(),
                            "parent_dir": os.path.dirname(entry.path),
                            "disk_label": disk_label,
                        }
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass

    def _flush_batch(self, conn, batch):
        """Записывает батч в БД и делает commit."""
        for action, f in batch:
            if action == "insert":
                conn.execute(
                    "INSERT OR IGNORE INTO scanned_files "
                    "(file_id, path, filename, extension, size_bytes, "
                    "created_at, modified_at, accessed_at, parent_dir, "
                    "disk_label) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (f["file_id"], f["path"], f["filename"],
                     f["extension"], f["size_bytes"], f["created_at"],
                     f["modified_at"], f["accessed_at"],
                     f["parent_dir"], f["disk_label"])
                )
            elif action == "update":
                conn.execute(
                    "UPDATE scanned_files SET size_bytes=?, "
                    "modified_at=?, accessed_at=?, "
                    "scan_date=CURRENT_TIMESTAMP WHERE file_id=?",
                    (f["size_bytes"], f["modified_at"],
                     f["accessed_at"], f["file_id"])
                )
        conn.commit()

    @staticmethod
    def _chunks(lst, n):
        """Разбивает список на чанки размером n."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
```

---

## 7. МОДУЛЬ ФИЛЬТРАЦИИ

```python
# client/heuristics/filters.py

"""
Фильтрация происходит ПЕРЕД отправкой на бэкенд.
Цель — отсечь файлы, которые точно не нужно анализировать,
чтобы сэкономить токены ИИ.

ПОРЯДОК ФИЛЬТРАЦИИ (каждый шаг уменьшает выборку):
1. Удаляем файлы младше min_age_months (по modified_at)
2. Удаляем файлы меньше min_size_bytes
3. Удаляем файлы с маркерами skip/protected
4. Удаляем файлы с системными расширениями (уже отфильтрованы при скане,
   но на случай если в БД остались старые записи)
5. Удаляем файлы из системных директорий

После фильтрации: сортируем по size_bytes DESC.
"""

from datetime import datetime, timedelta
from config import SYSTEM_EXTENSIONS

def filter_files(
    files: list[dict],
    excluded_ids: set,
    min_age_months: int = 6,
    min_size_bytes: int = 1024,
) -> list[dict]:
    """
    Фильтрует файлы перед отправкой на анализ.

    Аргументы:
        files: список файлов из БД
        excluded_ids: set файлов с маркерами skip/protected
        min_age_months: минимальный возраст в месяцах
        min_size_bytes: минимальный размер в байтах

    Возвращает:
        отфильтрованный и отсортированный список
    """
    cutoff_date = datetime.now() - timedelta(days=min_age_months * 30)
    filtered = []

    for f in files:
        # Пропускаем исключённые файлы
        if f["file_id"] in excluded_ids:
            continue

        # Пропускаем свежие файлы
        try:
            modified = datetime.fromisoformat(f["modified_at"])
            if modified > cutoff_date:
                continue
        except (ValueError, TypeError):
            continue

        # Пропускаем мелкие файлы
        if f["size_bytes"] < min_size_bytes:
            continue

        # Пропускаем системные расширения
        if f.get("extension", "") in SYSTEM_EXTENSIONS:
            continue

        filtered.append(f)

    # Сортируем по размеру — большие файлы первыми
    filtered.sort(key=lambda x: x["size_bytes"], reverse=True)

    return filtered
```

---

## 8. МОДУЛЬ ГРУППИРОВКИ В БАНДЛЫ

```python
# client/heuristics/bundler.py

"""
Группировка файлов в бандлы — ПОЛНОСТЬЮ на клиенте.
ИИ НЕ группирует. ИИ только классифицирует.

Алгоритм:
1. Получаем отфильтрованные файлы
2. Для каждого файла берём классификацию из кеша ИИ
3. Группируем по месяцу modified_at (ключ: "YYYY-MM")
4. Внутри каждой группы сортируем по size_bytes DESC
5. Формируем бандл с названием, описанием, размером
6. Сортируем бандлы по дате (старые первыми)
7. Отдельно формируем review_bundle из файлов с истёкшими skip-маркерами

ВАЖНО:
- Файлы без классификации (не были отправлены на ИИ или кеш устарел)
  получают confidence=0.5, category="other", reason="Не классифицирован"
- Бандлы с 0 файлов не создаются
- Каждый бандл содержит поле total_size_bytes — сумма размеров ВСЕХ
  файлов в бандле (нужно для отображения в GUI)
"""

from datetime import datetime
from collections import defaultdict
from typing import Optional

class BundleBuilder:
    def __init__(self, marker_manager, classification_cache: dict = None):
        """
        Аргументы:
            marker_manager: экземпляр MarkerManager
            classification_cache: dict {file_id: {confidence, category, reason}}
                                  Загружается из таблицы analysis_cache
        """
        self.marker_manager = marker_manager
        self.cache = classification_cache or {}

    def build_bundles(self, files: list[dict]) -> list[dict]:
        """
        Группирует файлы в бандлы по месяцам.

        Аргументы:
            files: отфильтрованный список файлов

        Возвращает:
            список бандлов, отсортированных по дате (старые первыми)
        """
        month_groups = defaultdict(list)

        for f in files:
            try:
                modified = datetime.fromisoformat(f["modified_at"])
            except (ValueError, TypeError):
                continue

            month_key = modified.strftime("%Y-%m")

            # Добавляем классификацию из кеша
            cls = self.cache.get(f["file_id"], {})
            f["confidence"] = cls.get("confidence", 0.5)
            f["category"] = cls.get("category", "other")
            f["reason"] = cls.get("reason", "Не классифицирован")

            month_groups[month_key].append(f)

        bundles = []
        now = datetime.now()

        for month_key in sorted(month_groups.keys()):
            files_in_month = month_groups[month_key]

            # Сортировка по размеру ВНУТРИ бандла
            files_in_month.sort(
                key=lambda x: x["size_bytes"], reverse=True
            )

            total_size = sum(f["size_bytes"] for f in files_in_month)

            # Возраст бандла в месяцах
            year, month = map(int, month_key.split("-"))
            age_months = (now.year - year) * 12 + (now.month - month)

            # Человекочитаемое название
            month_names_ru = {
                1: "Январь", 2: "Февраль", 3: "Март",
                4: "Апрель", 5: "Май", 6: "Июнь",
                7: "Июль", 8: "Август", 9: "Сентябрь",
                10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
            }
            name = f"{month_names_ru[month]} {year}"

            bundles.append({
                "bundle_id": f"b_{month_key}",
                "name": name,
                "description": f"Файлы старше {age_months} мес.",
                "period": month_key,
                "age_months": age_months,
                "total_size_bytes": total_size,
                "files_count": len(files_in_month),
                "files": files_in_month,
                "is_review": False,
            })

        return bundles

    def build_review_bundle(self) -> Optional[dict]:
        """
        Формирует специальный бандл из файлов с истёкшими
        skip-маркерами.

        Этот бандл показывается ПЕРВЫМ в списке, выделяется
        визуально, и имеет особую логику:
        - Нажатие «Не удалять» в этом бандле → marker = protected
        - Нажатие «Удалить» → обычное удаление

        Возвращает None, если нет файлов для пересмотра.
        """
        review_files = self.marker_manager.get_review_files()
        if not review_files:
            return None

        review_files.sort(
            key=lambda x: x["size_bytes"], reverse=True
        )
        total_size = sum(f["size_bytes"] for f in review_files)

        return {
            "bundle_id": "review_bundle",
            "name": "Пересмотр исключённых файлов",
            "description": (
                "Ранее вы исключили эти файлы из удаления. "
                "Пожалуйста, просмотрите их ещё раз."
            ),
            "period": "review",
            "age_months": None,
            "total_size_bytes": total_size,
            "files_count": len(review_files),
            "files": review_files,
            "is_review": True,
        }
```

---

## 9. СИСТЕМА МАРКЕРОВ ИСКЛЮЧЕНИЯ

```python
# client/heuristics/marker_manager.py

"""
ЖИЗНЕННЫЙ ЦИКЛ МАРКЕРА:

1. Файл попадает в бандл → пользователь нажимает «Не удалять»
2. Создаётся маркер типа 'skip' со сроком действия (по умолчанию 90 дней)
3. Файл НЕ ПОЯВЛЯЕТСЯ в обычных бандлах, пока маркер активен
4. Через 90 дней маркер «истекает»
5. Файл попадает в специальный review_bundle
6. Если пользователь СНОВА нажимает «Не удалять» → маркер типа 'protected'
7. Файл НАВСЕГДА исключён из бандлов

Два типа маркеров:
- skip:      временный, expires_at != NULL, skip_count = 1
- protected: перманентный, expires_at = NULL, skip_count >= 2

Пользователь может:
- Видеть количество skip и protected маркеров в настройках
- Сбросить все маркеры (кнопка в настройках с подтверждением)
- Снять protected с конкретного файла (в будущих версиях)
"""

import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH

class MarkerManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def mark_as_skip(self, file_id: str, skip_days: int = 90):
        """
        Помечает файл как временно исключённый.
        Если файл УЖЕ имеет skip-маркер и вызывается повторно
        (из review_bundle), автоматически повышается до protected.
        """
        expires_at = (
            datetime.now() + timedelta(days=skip_days)
        ).isoformat()

        with self._conn() as conn:
            existing = conn.execute(
                "SELECT marker_type, skip_count FROM file_markers "
                "WHERE file_id = ?",
                (file_id,)
            ).fetchone()

            if existing is None:
                # Первый отказ → skip
                conn.execute(
                    "INSERT INTO file_markers "
                    "(file_id, marker_type, expires_at, skip_count) "
                    "VALUES (?, 'skip', ?, 1)",
                    (file_id, expires_at)
                )
            elif existing[0] == "skip":
                # Повторный отказ → protected
                conn.execute(
                    "UPDATE file_markers SET "
                    "marker_type='protected', expires_at=NULL, "
                    "skip_count=skip_count+1 WHERE file_id=?",
                    (file_id,)
                )
            # Если уже protected — ничего не делаем

    def promote_to_protected(self, file_id: str):
        """Явное повышение до protected (из review_bundle)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE file_markers SET "
                "marker_type='protected', expires_at=NULL, "
                "skip_count=skip_count+1 WHERE file_id=?",
                (file_id,)
            )

    def get_excluded_file_ids(self) -> set:
        """
        Возвращает множество file_id, которые нужно исключить
        из обычных бандлов.

        Включает:
        - Все protected файлы (навсегда)
        - Все skip файлы, чей срок ЕЩЁ НЕ истёк
        """
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT file_id FROM file_markers "
                "WHERE marker_type='protected' "
                "   OR (marker_type='skip' AND expires_at > ?)",
                (now,)
            ).fetchall()
        return {row[0] for row in rows}

    def get_review_files(self) -> list[dict]:
        """
        Возвращает файлы с ИСТЁКШИМИ skip-маркерами.
        Эти файлы нужно показать в review_bundle.
        """
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT fm.file_id, sf.path, sf.filename, "
                "sf.size_bytes, sf.modified_at, fm.created_at "
                "FROM file_markers fm "
                "JOIN scanned_files sf ON fm.file_id = sf.file_id "
                "WHERE fm.marker_type = 'skip' "
                "  AND fm.expires_at <= ?",
                (now,)
            ).fetchall()

        return [
            {
                "file_id": r[0], "path": r[1], "filename": r[2],
                "size_bytes": r[3], "modified_at": r[4],
                "skipped_at": r[5],
            }
            for r in rows
        ]

    def get_stats(self) -> dict:
        """Статистика маркеров для отображения в настройках."""
        with self._conn() as conn:
            skip = conn.execute(
                "SELECT COUNT(*) FROM file_markers "
                "WHERE marker_type='skip'"
            ).fetchone()[0]
            protected = conn.execute(
                "SELECT COUNT(*) FROM file_markers "
                "WHERE marker_type='protected'"
            ).fetchone()[0]
        return {
            "skip": skip,
            "protected": protected,
            "pending_review": len(self.get_review_files()),
        }

    def reset_all_markers(self):
        """Сбрасывает ВСЕ маркеры. Требует подтверждения в GUI."""
        with self._conn() as conn:
            conn.execute("DELETE FROM file_markers")
```

---

## 10. API-КЛИЕНТ (коммуникация с бэкендом)

### 10.1 Аутентификация

```python
# client/api_client/auth.py

"""
Клиент хранит JWT-токен в файле auth_token.json.
При запуске проверяет, есть ли сохранённый токен.
Если есть — пытается использовать его.
Если нет или токен протух — показывает окно логина.

ВАЖНО:
- Используем httpx, НЕ requests
- Все запросы к бэкенду — асинхронные (httpx.AsyncClient)
- Таймаут: 10 секунд на connect, 30 секунд на read
- При ошибке сети — показываем понятное сообщение пользователю
"""

import json
import os
import httpx
from config import BACKEND_URL, AUTH_ENDPOINT, TOKEN_PATH

class AuthClient:
    def __init__(self):
        self.token: str | None = None
        self.user_id: str | None = None
        self._load_saved_token()

    def _load_saved_token(self):
        """Пытается загрузить сохранённый токен."""
        try:
            if os.path.exists(TOKEN_PATH):
                with open(TOKEN_PATH, "r") as f:
                    data = json.load(f)
                    self.token = data.get("access_token")
                    self.user_id = data.get("user_id")
        except (json.JSONDecodeError, IOError):
            self.token = None

    def _save_token(self, data: dict):
        """Сохраняет токен на диск."""
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            json.dump(data, f)

    async def register(self, username: str, password: str) -> dict:
        """
        Регистрация нового пользователя.
        Возвращает: {"user_id": ..., "access_token": ...}
        Исключения: httpx.HTTPStatusError при ошибке
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BACKEND_URL}{AUTH_ENDPOINT}/register",
                json={"username": username, "password": password}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data["access_token"]
            self.user_id = data["user_id"]
            self._save_token(data)
            return data

    async def login(self, username: str, password: str) -> dict:
        """Вход существующего пользователя."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BACKEND_URL}{AUTH_ENDPOINT}/login",
                json={"username": username, "password": password}
            )
            response.raise_for_status()
            data = response.json()
            self.token = data["access_token"]
            self.user_id = data["user_id"]
            self._save_token(data)
            return data

    def get_auth_headers(self) -> dict:
        """Заголовки для авторизованных запросов."""
        if not self.token:
            raise RuntimeError("Not authenticated")
        return {"Authorization": f"Bearer {self.token}"}

    def is_authenticated(self) -> bool:
        return self.token is not None

    def logout(self):
        """Выход: удаляем токен."""
        self.token = None
        self.user_id = None
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
```

### 10.2 Отправка на анализ

```python
# client/api_client/analysis.py

"""
ПРИНЦИП БАТЧИНГА:

У нас может быть 2000-5000 файлов для анализа.
Отправлять всё одним запросом — опасно:
- Таймаут на стороне бэкенда
- Превышение лимита токенов нейросети

Поэтому разбиваем на батчи по MAX_BATCH_SIZE (200) файлов.
Каждый батч — отдельный POST-запрос.
Результаты собираем в общий список.

ВАЖНО:
- Между батчами делаем паузу 1 сек (rate limiting API нейросети)
- При ошибке одного батча — продолжаем с остальными
- Файлы, для которых ИИ не вернул ответ, получают дефолтную
  классификацию (confidence=0.5, category="other")
- Результаты кешируем в analysis_cache
"""

import httpx
import asyncio
import sqlite3
from config import BACKEND_URL, ANALYSIS_ENDPOINT, MAX_BATCH_SIZE, DB_PATH

class AnalysisClient:
    def __init__(self, auth_client):
        self.auth = auth_client

    async def analyze_files(
        self, files: list[dict],
        progress_callback=None
    ) -> list[dict]:
        """
        Отправляет файлы на анализ батчами.

        Аргументы:
            files: отфильтрованные файлы (после filters.filter_files)
            progress_callback: callable(batch_num, total_batches)

        Возвращает:
            список классификаций [{file_id, confidence, category, reason}]
        """
        # Убираем файлы, уже есть в кеше
        uncached_files = self._get_uncached(files)
        cached_results = self._get_from_cache(files)

        if not uncached_files:
            return cached_results

        # Разбиваем на батчи
        batches = [
            uncached_files[i:i + MAX_BATCH_SIZE]
            for i in range(0, len(uncached_files), MAX_BATCH_SIZE)
        ]

        new_results = []
        total_batches = len(batches)

        async with httpx.AsyncClient(timeout=60.0) as client:
            for batch_num, batch in enumerate(batches, 1):
                if progress_callback:
                    progress_callback(batch_num, total_batches)

                try:
                    # Формируем payload — только нужные поля,
                    # БЕЗ полного пути (приватность)
                    payload = {
                        "scan_id": f"batch-{batch_num}",
                        "files": [
                            {
                                "file_id": f["file_id"],
                                "filename": f["filename"],
                                "extension": f["extension"],
                                "size_bytes": f["size_bytes"],
                                "modified_at": f["modified_at"],
                                "accessed_at": f["accessed_at"],
                                "parent_dir": f["parent_dir"],
                            }
                            for f in batch
                        ],
                    }

                    response = await client.post(
                        f"{BACKEND_URL}{ANALYSIS_ENDPOINT}",
                        json=payload,
                        headers=self.auth.get_auth_headers(),
                    )
                    response.raise_for_status()
                    data = response.json()

                    batch_results = data.get("classifications", [])
                    new_results.extend(batch_results)

                except (httpx.HTTPError, Exception) as e:
                    # Ошибка батча — логируем, продолжаем
                    print(f"Batch {batch_num} failed: {e}")
                    # Генерируем дефолтные классификации
                    for f in batch:
                        new_results.append({
                            "file_id": f["file_id"],
                            "confidence": 0.5,
                            "category": "other",
                            "reason": "Не удалось классифицировать",
                        })

                # Пауза между батчами (rate limiting)
                if batch_num < total_batches:
                    await asyncio.sleep(1.0)

        # Сохраняем в кеш
        self._save_to_cache(new_results)

        return cached_results + new_results

    def _get_uncached(self, files: list[dict]) -> list[dict]:
        """Возвращает файлы, отсутствующие в кеше."""
        conn = sqlite3.connect(DB_PATH)
        cached_ids = set()
        for row in conn.execute(
            "SELECT file_id FROM analysis_cache"
        ).fetchall():
            cached_ids.add(row[0])
        conn.close()
        return [f for f in files if f["file_id"] not in cached_ids]

    def _get_from_cache(self, files: list[dict]) -> list[dict]:
        """Возвращает классификации из кеша."""
        file_ids = [f["file_id"] for f in files]
        if not file_ids:
            return []

        conn = sqlite3.connect(DB_PATH)
        results = []
        # SQLite лимит параметров ~999
        for i in range(0, len(file_ids), 900):
            chunk = file_ids[i:i + 900]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT file_id, confidence, category, reason "
                f"FROM analysis_cache "
                f"WHERE file_id IN ({placeholders})",
                chunk
            ).fetchall()
            for r in rows:
                results.append({
                    "file_id": r[0], "confidence": r[1],
                    "category": r[2], "reason": r[3],
                })
        conn.close()
        return results

    def _save_to_cache(self, classifications: list[dict]):
        """Сохраняет классификации в кеш."""
        conn = sqlite3.connect(DB_PATH)
        for c in classifications:
            conn.execute(
                "INSERT OR REPLACE INTO analysis_cache "
                "(file_id, confidence, category, reason) "
                "VALUES (?, ?, ?, ?)",
                (c["file_id"], c["confidence"],
                 c["category"], c["reason"])
            )
        conn.commit()
        conn.close()
```

---

## 11. GUI (PyQt6)

### 11.1 Общие принципы GUI

```
АРХИТЕКТУРА GUI:

Главное окно (MainWindow) содержит QStackedWidget с экранами:
1. LoginScreen      — вход / регистрация
2. DiskSelectScreen  — выбор дисков
3. ScanScreen        — прогресс сканирования
4. BundleListScreen  — список бандлов
5. BundleDetailScreen — файлы внутри бандла
6. SettingsScreen    — настройки

Навигация:
- Login → DiskSelect → Scan → BundleList → BundleDetail
- Из BundleList можно перейти в Settings
- Из BundleDetail — назад в BundleList

КРИТИЧЕСКИ ВАЖНО для GUI:
- Сканирование и HTTP-запросы — В ОТДЕЛЬНОМ ПОТОКЕ (QThread)
- НИКОГДА не делай блокирующие операции в главном потоке GUI
- Для обновления GUI из фонового потока используй сигналы (pyqtSignal)
- Не используй threading.Thread — используй QThread
- Не используй asyncio.run() в GUI-потоке — оно блокирует

Паттерн для фоновых задач:

    class ScanWorker(QThread):
        progress = pyqtSignal(int)         # Прогресс
        finished = pyqtSignal(dict)        # Результат
        error = pyqtSignal(str)            # Ошибка

        def run(self):
            try:
                result = scanner.scan(...)
                self.finished.emit(result)
            except Exception as e:
                self.error.emit(str(e))

    # В GUI:
    worker = ScanWorker()
    worker.progress.connect(self.update_progress_bar)
    worker.finished.connect(self.on_scan_complete)
    worker.error.connect(self.show_error)
    worker.start()

Для async-операций (HTTP-запросы) в QThread:

    class AnalysisWorker(QThread):
        finished = pyqtSignal(list)

        def run(self):
            import asyncio
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                analysis_client.analyze_files(self.files)
            )
            self.finished.emit(result)
```

### 11.2 Экран списка бандлов

```
ТРЕБОВАНИЯ К BUNDLE LIST:

Отображение:
- QListWidget или QTableWidget
- Каждая строка: [Иконка периода] [Название] [Кол-во файлов] [Размер]
- Пример: "📁 Март 2022    |  34 файла  |  2.4 ГБ"
- Review-бандл показывается ПЕРВЫМ и выделяется цветом (жёлтый/оранжевый)
- Внизу: итоговая строка "Всего: X бандлов, Y файлов, Z ГБ"

Взаимодействие:
- Двойной клик по бандлу → переход в BundleDetailScreen
- Кнопка «Удалить все выбранные бандлы» внизу
- Кнопка «Настройки» в углу

Размер отображать через format_size():
    < 1 КБ → "XXX Б"
    < 1 МБ → "XXX.X КБ"
    < 1 ГБ → "XXX.X МБ"
    < 1 ТБ → "XXX.X ГБ"
    ≥ 1 ТБ → "X.XX ТБ"
```

### 11.3 Экран содержимого бандла

```
ТРЕБОВАНИЯ К BUNDLE DETAIL:

Отображение — QTableWidget с колонками:
| ☑ | Имя файла | Размер | Категория | Уверенность | Причина |

- Чекбокс включён по умолчанию (файл будет удалён)
- Уверенность: цветовая индикация
    0.85-1.0  → зелёный (безопасно)
    0.5-0.84  → жёлтый  (средний риск)
    0.0-0.49  → красный (опасно, вероятно нужный файл)
- Файлы с confidence < 0.5 имеют чекбокс ВЫКЛЮЧЕННЫЙ по умолчанию

Взаимодействие:
- Клик по строке → выделение
- Двойной клик / кнопка «Открыть» → os.startfile(path) (открывает файл)
- Кнопка «Не удалять» → снимает чекбокс + ставит маркер skip
- Кнопка «Удалить выбранные» → диалог подтверждения
- Кнопка «Назад» → возврат в BundleList

Для review-бандла:
- Кнопка «Не удалять» → ставит маркер protected (навсегда)
- Показывает уведомление: "Файл навсегда исключён из рекомендаций"

ВАЖНО: кнопка «Открыть файл» нужна для того, чтобы пользователь мог
просмотреть файл перед удалением. Например, увидеть что это за видео
или документ, прежде чем решить удалять его или нет.
```

### 11.4 Диалог подтверждения удаления

```
ТРЕБОВАНИЯ К CONFIRMATION DIALOG:

Это QMessageBox.warning() с текстом:

    "Вы уверены, что хотите удалить {N} файлов
     общим размером {SIZE}?

     Это действие необратимо!"

    [Удалить]  [Отмена]

Кнопка по умолчанию — «Отмена» (StandardButton.No).
Это защита от случайного нажатия Enter.

После удаления показать отчёт:
    "Удалено: {N} файлов ({SIZE})
     Ошибок: {M} (файлы заблокированы или недоступны)"
```

---

## 12. УДАЛЕНИЕ ФАЙЛОВ

```python
# client/utils/file_operations.py

"""
ВАЖНО О УДАЛЕНИИ:

Вариант 1 (текущий): os.remove() — безвозвратное удаление.
Вариант 2 (рекомендуемый): send2trash — перемещение в корзину.

send2trash — сторонняя библиотека (pip install send2trash).
Плюс: пользователь может восстановить файлы из корзины.
Минус: файлы всё ещё занимают место на диске.

Для учебного проекта используем os.remove() с подтверждением.
В продакшене стоит использовать send2trash как опцию
с переключателем в настройках.
"""

import os

def delete_files(files: list[dict]) -> dict:
    """
    Удаляет файлы из списка.

    Возвращает:
    {
        "deleted": 45,
        "errors": [
            {"path": "C:\\...", "error": "Permission denied"},
        ],
        "total_freed_bytes": 123456789,
    }
    """
    deleted = 0
    errors = []
    freed = 0

    for f in files:
        try:
            size = f["size_bytes"]
            os.remove(f["path"])
            deleted += 1
            freed += size
        except OSError as e:
            errors.append({
                "path": f["path"],
                "error": str(e),
            })

    return {
        "deleted": deleted,
        "errors": errors,
        "total_freed_bytes": freed,
    }


def open_file(path: str):
    """Открывает файл стандартным приложением ОС."""
    import platform
    import subprocess

    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def open_in_explorer(path: str):
    """Открывает папку с файлом в проводнике."""
    import platform
    import subprocess

    folder = os.path.dirname(path)
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(f'explorer /select,"{path}"')
    elif system == "Darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", folder])
```

---

## 13. УТИЛИТЫ

```python
# client/utils/formatters.py

def format_size(size_bytes: int) -> str:
    """
    Форматирует размер в человекочитаемый вид.
    123 → "123 Б"
    1536 → "1.5 КБ"
    1572864 → "1.5 МБ"
    """
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    for unit in ["КБ", "МБ", "ГБ", "ТБ"]:
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} ПБ"


def format_date(iso_date: str) -> str:
    """
    Форматирует ISO-дату в читаемый формат.
    "2022-03-15T10:30:00" → "15 марта 2022"
    """
    from datetime import datetime
    months_ru = {
        1: "января", 2: "февраля", 3: "марта",
        4: "апреля", 5: "мая", 6: "июня",
        7: "июля", 8: "августа", 9: "сентября",
        10: "октября", 11: "ноября", 12: "декабря",
    }
    try:
        dt = datetime.fromisoformat(iso_date)
        return f"{dt.day} {months_ru[dt.month]} {dt.year}"
    except (ValueError, TypeError):
        return iso_date or "—"
```

---

## 14. ТОЧКА ВХОДА

```python
# client/main.py

import sys
import os
from PyQt6.QtWidgets import QApplication
from database.local_db import init_database
from client.gui.main_window import MainWindow


def main():
    # Инициализация БД при первом запуске
    init_database()

    # Создание приложения
    app = QApplication(sys.argv)
    app.setApplicationName("SmartCleaner")
    app.setOrganizationName("SmartCleaner")

    # Главное окно
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

## 15. ОПТИМИЗАЦИИ И ЛУЧШИЕ ПРАКТИКИ

### Производительность:
1. os.scandir() вместо os.walk() — в 2 раза быстрее
2. Батчевые INSERT в SQLite с commit каждые 500 записей
3. WAL-режим SQLite для параллельного чтения/записи
4. Кеш классификаций — не запрашиваем ИИ повторно
5. Инкрементальное сканирование — 10-30 сек вместо 1-3 мин
6. Фоновые потоки (QThread) для всех тяжёлых операций

### Безопасность:
1. Содержимое файлов НИКОГДА не покидает машину пользователя
2. Полный путь НЕ отправляется на бэкенд (только parent_dir + filename)
3. JWT-токен хранится в %APPDATA% (не в открытом виде)
4. Удаление только с подтверждением (кнопка «Отмена» по умолчанию)
5. Системные файлы (.sys, .dll) фильтруются на этапе сканирования

### UX:
1. Прогресс-бар при сканировании и анализе
2. Файлы с низким confidence (< 0.5) не отмечены по умолчанию
3. Review-бандл визуально выделен и показан первым
4. Возможность открыть файл перед удалением
5. Отчёт после удаления (сколько удалено, сколько ошибок)

### Что НЕ нужно делать:
- НЕ использовать requests (блокирует GUI)
- НЕ использовать os.walk() (медленнее os.scandir)
- НЕ использовать pathlib.rglob() (медленнее os.scandir)
- НЕ использовать threading.Thread (использовать QThread из PyQt6)
- НЕ делать commit после каждого INSERT (убивает производительность)
- НЕ отправлять ВСЕ файлы на ИИ (фильтровать локально)
- НЕ хранить API-ключ на клиенте (только на бэкенде)
- НЕ удалять файлы без подтверждения
- НЕ группировать и не сортировать в промпте ИИ (делаем на клиенте)
- НЕ хардкодить URL бэкенда (использовать get_backend_url() с GitHub Gist)
