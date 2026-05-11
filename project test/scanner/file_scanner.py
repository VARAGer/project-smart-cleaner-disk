# хэш будем использовать для определения изменения файла
import os
import hashlib
from datetime import datetime
from config import SKIP_DIRS, SYSTEM_EXTENSIONS


def generate_file_id(file_path: str) -> str:
    return hashlib.md5(file_path.encode("utf-8")).hexdigest()[:12] #переводит в ютф8 после этого перерводит в 16ричьную и отрезает 12 цифр хэша


def scan_directory(root_path:str, disk_label:str, progress_callback = None, _counter = None):
    if _counter is None:
        _counter = [0]
    try:
        for entry in os.scandir(root_path):
            try:
                if entry.is_dir(follow_symlinks = False): #скипаем ссылки (symlinks нужно чтоб мы не тспользовали как папку а использовали как ссылку на файл)
                    
                    if entry.name in SKIP_DIRS:
                        continue
                    if entry.name.startswith(".") or entry.name.startswith("$"): #пропускам скрытые папки 
                        continue
                    yield from scan_directory(
                        entry.path, disk_label, 
                        progress_callback, _counter
                        )
                elif entry.is_file(follow_symlinks = False):
                    stat = entry.stat()
                    extension = os.path.splittext(enrty.name)[1].lower()

                    if extension in SYSTEM_EXTENSION:
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
        
        
            except(PermissionError, OSError):
                 continue
    except(PermissionError, OSError):
        pass