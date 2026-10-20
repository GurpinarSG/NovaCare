## 2024-03-24 - Cookie Shield Whitelist Linear Search Bottleneck
**Learning:** Checking host suffixes against a whitelist using 'endswith' in a loop for every cookie causes O(N*M) operations, where N is the number of cookies and M is the whitelist size. This drastically slows down cookie scans across multiple browser databases.
**Action:** Splitting the domain host into parts and performing an O(1) hash map lookup against a 'set' of whitelisted domains reduces complexity to O(N) and significantly improves scan/clean speed.
