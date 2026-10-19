
## 2023-10-19 - Fast Directory Traversal on Windows
**Learning:** `os.walk` relies on `os.scandir` internally, but strips the `DirEntry` objects, forcing developers to use `os.stat()` on every file. On Windows, `entry.stat()` is cached directly from the `os.scandir` directory reading syscall, avoiding millions of slow `stat` syscalls during deep disk scans.
**Action:** When scanning deep file hierarchies (e.g. `DiskAnalyzer`), always use a stack-based `os.scandir` iterator instead of `os.walk` to take advantage of the cached `DirEntry.stat(follow_symlinks=False)`.
