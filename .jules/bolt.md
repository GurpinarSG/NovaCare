
## 2024-05-24 - [Replaced os.walk with os.scandir for disk scanning]
**Learning:** `os.walk` in Python performs redundant `os.stat` calls internally during deep file system traversals, making it slow on Windows where `os.scandir` caches entry attributes like `st_size` when querying directories.
**Action:** Always favor iterative stack-based `os.scandir` over `os.walk` when scanning deeply nested structures where file sizes or metadata are immediately needed, ensuring to protect against infinite loops from Windows junctions manually by checking `entry.is_symlink()` and `hasattr(entry, 'is_junction') and entry.is_junction()`.
