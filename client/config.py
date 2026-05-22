import os


# TODO: временный путь локальных данных, пока общая конфигурация клиента
# не согласована со сканером и остальными модулями.
def get_data_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".smartcleaner")


DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "smartcleaner.db")

DEFAULT_THEME = "light"
DEFAULT_MIN_AGE_MONTHS = 6
DEFAULT_MIN_SIZE_BYTES = 1024
DEFAULT_SKIP_DURATION_DAYS = 90

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
    ".exe",
}