## 2024-10-24 - Process querying optimization pattern
**Learning:** Frequent calls to `psutil.process_iter()` inside loops cause significant overhead due to OS-level querying limits.
**Action:** When evaluating multiple targets against running processes (e.g. `core/cookie_shield.py`, `core/game_booster.py`), fetch process names in advance into a cached O(1) `set` rather than calling iteration on demand for each target.
