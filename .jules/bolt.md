
## 2024-05-24 - File System Traversal Optimization
**Learning:** `os.walk` builds lists of subdirectories and files and typically requires a separate `os.stat` call on each file. Using `os.scandir` in a custom traversal loop yields `DirEntry` objects, caching `stat()` results and substantially improving I/O performance on large directory structures (e.g. up to 60% faster during large file scans).
**Action:** When inspecting file attributes (like size or modification time) on a large number of files recursively, always prefer `os.scandir` over `os.walk` to reduce syscall overhead.
