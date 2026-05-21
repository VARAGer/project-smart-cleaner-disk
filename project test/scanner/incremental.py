import os
import sqlite3
from datetime import datetime
import hashlib
from client.config import (DB_PATH, SKIP_DIRS, SYSTEM_EXTENSIONS)
class IncrementalScanner:
    BATCH_SIZE = 500
    
    
    def __init__(self, db_path = DB_PATH):
        self.db_path = db_path
        
    
    def scan(self, root_path, disk_label, progress_callback=None):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        existing = {}
        rows = conn.execute(
            "SELECT file_id, path, modified_at FROM scanned_filesWHERE disk_label = ?",
            (disk_label,)
        ).fetchall()
        for row in rows:
            existing[row[1]] = {
                "file_id": row[0],
                "modified_at": row[2]
            }
        stats = {"new": 0, "update": 0, "deleted":0, "unchanged":0}
        seen_paths = set()
        batch = []
        
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
                total = stats["new"] + stats["update"] + stats["unchanged"]
                progress_callback(total)
        if batch:
            self._flush_batch(conn,batch)
        deleted_paths = set(existing.keys()) - seen_paths
        if deleted_paths:
            for chunk in self._chunk(list(deleted_paths), 900):
                placeholders = ",".join("?" * len(chunk))
                conn.execute(
                    f"DELETE FROM scanned_files"
                    f"WHERE path IN ({placeholders})",
                    chunk
                )
            conn.commit()
            stats["deleted"] = len(deleted_paths)
        conn.execute("INSERT OR REPLACE INTO user_settings (key, value)"
                     "VALUES(?, ?)",
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
    def _chunk(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]