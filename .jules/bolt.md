## 2024-05-18 - Optimized Disk Space Analyzer
**Learning:** `os.walk` was causing slow disk analysis because it was redundantly calling `os.stat` when finding large files. `os.scandir` contains stat information directly which is much faster on Windows.
**Action:** Always prefer `os.scandir` when traversing directories if you need `os.stat` information later for that file. Iteratively use `os.scandir` with a stack.
