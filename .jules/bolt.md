## 2024-05-17 - os.walk vs stack-based os.scandir in deeply nested structures
**Learning:** `os.walk` is implemented recursively using `yield from` in Python. For tasks like disk analysis that can hit deeply nested folders, this is noticeably slower (~50-100% overhead) and can trigger `RecursionError`.
**Action:** Always prefer an iterative stack-based approach using `os.scandir()` for disk/file intensive operations (like junk cleaning or disk analysis) instead of `os.walk`. `JunkCleaner` already did this natively, but `DiskAnalyzer` was missing it.
