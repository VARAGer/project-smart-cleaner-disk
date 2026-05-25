import os
import sqlite3
from datetime import datetime

from client.config import (DB_PATH, SKIP_DIRS, SYSTEM_EXTENSIONS)
from client.database.local_db import init_database
from client.scanner.file_ids import generate_file_id


class IncrementalScanner:
    BATCH_SIZE = 500
    
    
    def __init__(self, db_path = DB_PATH):
        self.db_path = db_path
        self.data_dir = os.path.dirname(db_path) or None
        
    
    def scan(self, root_path, disk_label, progress_callback=None, cancel_requested=None):
        init_database(self.db_path)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            existing = {}
            rows = conn.execute(
                "SELECT file_id, path, modified_at FROM scanned_files WHERE disk_label = ?",
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
            was_cancelled = False
            
            for file_info in self._walk(root_path, disk_label):
                if cancel_requested and cancel_requested():
                    was_cancelled = True
                    break
                path = file_info["path"]
                seen_paths.add(path)
                
                if path in existing:
                     if existing[path]["modified_at"] == file_info["modified_at"]:
                         stats["unchanged"] += 1
                         continue
                     else:
                         file_info["file_id"] = existing[path]["file_id"]
                         batch.append(("update", file_info))
                         stats["update"] += 1
                else:
                    batch.append(("insert", file_info))
                    stats["new"] += 1
                if len(batch) >= self.BATCH_SIZE:
                    self._flush_batch(conn, batch)
                    batch.clear()

                total = stats["new"] + stats["update"] + stats["unchanged"]
                if progress_callback and total % self.BATCH_SIZE == 0:
                    progress_callback(total)
            if was_cancelled:
                conn.rollback()
                stats["total"] = sum(stats.values())
                return stats
            if batch:
                self._flush_batch(conn,batch)
            if progress_callback:
                total = stats["new"] + stats["update"] + stats["unchanged"]
                progress_callback(total)
            deleted_paths = set(existing.keys()) - seen_paths
            if deleted_paths:
                for chunk in self._chunk(list(deleted_paths), 900):
                    placeholders = ",".join("?" * len(chunk))
                    conn.execute(
                        f"DELETE FROM scanned_files WHERE path IN ({placeholders})",
                        chunk
                    )
                conn.commit()
                stats["deleted"] = len(deleted_paths)
            conn.execute("INSERT OR REPLACE INTO user_settings (key, value) "
                         "VALUES (?, ?)",
                         ("last_scan_date", datetime.now().isoformat())
                        )
            conn.commit()
            stats["total"] = sum(stats.values())
            return stats
        finally:
            conn.close()
    
    
    
    
    def _walk(self, root_path: str, disk_label: str):
        """Yield file metadata while keeping full paths local-only."""
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
                            "file_id": generate_file_id(
                                entry.path,
                                data_dir=self.data_dir,
                            ),
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
    @staticmethod
    def _chunk(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
