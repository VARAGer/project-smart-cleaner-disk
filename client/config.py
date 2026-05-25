import os
import re


DEFAULT_BACKEND_URL = "http://localhost:8000"
BACKEND_URL_FILE = "backend_url.txt"


def get_data_dir() -> str:
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local_app_data:
        return os.path.join(local_app_data, "SmartCleaner")
    return os.path.join(os.path.expanduser("~"), ".smartcleaner")


DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "smartcleaner.db")


def _parse_backend_urls(raw_value: str) -> list[str]:
    urls: list[str] = []
    for item in re.split(r"[\s,;]+", raw_value):
        url = item.strip().lstrip("\ufeff").rstrip("/")
        if url and url not in urls:
            urls.append(url)
    return urls


def resolve_backend_urls(data_dir: str | None = None) -> list[str]:
    env_value = os.getenv("SMARTCLEANER_BACKEND", "").strip()
    if env_value:
        return _parse_backend_urls(env_value) or [DEFAULT_BACKEND_URL]

    config_dir = data_dir or DATA_DIR
    config_path = os.path.join(config_dir, BACKEND_URL_FILE)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            file_value = f.read().strip()
    except OSError:
        return [DEFAULT_BACKEND_URL]
    return _parse_backend_urls(file_value) or [DEFAULT_BACKEND_URL]


def resolve_backend_url(data_dir: str | None = None) -> str:
    return resolve_backend_urls(data_dir=data_dir)[0]


BACKEND_URLS = resolve_backend_urls()
BACKEND_URL = BACKEND_URLS[0]
API_TIMEOUT_SECONDS = float(os.getenv("SMARTCLEANER_API_TIMEOUT_SECONDS", "30"))
ANALYSIS_BATCH_SIZE = int(os.getenv("SMARTCLEANER_ANALYSIS_BATCH_SIZE", "80"))

DEFAULT_THEME = "light"
DEFAULT_MIN_AGE_MONTHS = 6
DEFAULT_MIN_SIZE_BYTES = 1024
DEFAULT_SKIP_DURATION_DAYS = 30
DEMO_SKIP_DURATION_MINUTES = 1

SKIP_DIRS = {
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "$Recycle.Bin",
    "System Volume Information",
    ".git",
    "__pycache__",
    "node_modules",
}

SYSTEM_EXTENSIONS = {
    ".sys",
    ".dll",
}
