
## 2024-10-26 - Iterative File System Scanning Over Recursion and os.walk
**Learning:** Python's recursion overhead and strict limits can cause unexpected `RecursionError` and performance drops in deep/wide directory structures. Also, `os.walk` is consistently ~2x slower than a custom iterative `os.scandir` implementation due to the implicit multiple `os.stat` calls required per file.
**Action:** Replace `os.walk` and recursive `os.scandir` patterns with stack-based `os.scandir` loops to maximize scanning performance and stability during intensive filesystem sweeps (like disk analyzing and junk cleaning).
