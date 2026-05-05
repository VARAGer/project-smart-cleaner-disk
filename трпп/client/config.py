import os
import platform

# ===== DB =====
def get_data_dir():
    return os.path.expanduser("~/.smartcleaner")

DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "smartcleaner.db")

# ===== SCAN =====
SKIP_DIRS = {
    "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information",
    ".git", "__pycache__", "node_modules"
}

SYSTEM_EXTENSIONS = {
    ".sys", ".dll", ".exe"
}