"""
NovaCare System Suite - Smart Cookie Shield (Akıllı Çerez Kalkanı)
Protects essential login sessions (Google, YouTube, GitHub, Banks, e-Devlet, etc.)
while eliminating cross-site tracking cookies, advertiser tokens, and privacy remnants.
"""
import os
import glob
import sqlite3
import subprocess
import psutil
from dataclasses import dataclass
from typing import Optional
from core.config import ConfigManager

DEFAULT_WHITELIST = [
    "google.com", "youtube.com", "github.com", "microsoft.com",
    "live.com", "outlook.com", "twitter.com", "x.com",
    "turkiye.gov.tr", "isbank.com.tr", "garantibbva.com.tr",
    "yapikredi.com.tr", "akbank.com.tr", "ziraatbank.com.tr",
    "vakifbank.com.tr", "bip.com", "whatsapp.com", "instagram.com",
    "facebook.com", "linkedin.com", "reddit.com", "discord.com",
    "spotify.com", "netflix.com", "amazon.com", "amazon.com.tr",
    "hepsiburada.com", "trendyol.com", "sahibinden.com", "gemini.google.com"
]

KNOWN_TRACKERS = {
    "doubleclick.net", "google-analytics.com", "criteo.com", "adform.net",
    "taboola.com", "outbrain.com", "scorecardresearch.com", "adnxs.com",
    "rubiconproject.com", "casalemedia.com", "pubmatic.com", "openx.net",
    "adroll.com", "quantserve.com", "hotjar.com", "clarity.ms",
    "facebook.net", "adservice.google.com", "statcounter.com", "zemanta.com",
    "chartbeat.com", "newrelic.com", "teads.tv", "indexww.com",
    "sharethrough.com", "advertising.com", "yandex.ru"
}

@dataclass
class CookieDomainItem:
    browser: str
    host: str
    count: int
    is_protected: bool
    is_known_tracker: bool

class CookieShield:
    def __init__(self):
        self.config = ConfigManager()

    def get_whitelist(self) -> list[str]:
        """Returns the list of domains protected from cookie purge."""
        return self.config.get("cookie_whitelist", list(DEFAULT_WHITELIST))

    def save_whitelist(self, domains: list[str]):
        """Persists custom whitelist."""
        clean = sorted(list(set(d.strip().lower() for d in domains if d.strip())))
        self.config.set("cookie_whitelist", clean)

    def add_domain(self, domain: str) -> bool:
        """Adds a domain to the protected whitelist."""
        d = domain.strip().lower().lstrip(".").replace("https://", "").replace("http://", "").split("/")[0]
        if not d:
            return False
        wl = self.get_whitelist()
        if d not in wl:
            wl.append(d)
            self.save_whitelist(wl)
            return True
        return False

    def remove_domain(self, domain: str) -> bool:
        """Removes a domain from whitelist."""
        wl = self.get_whitelist()
        clean_d = domain.strip().lower()
        if clean_d in wl:
            wl.remove(clean_d)
            self.save_whitelist(wl)
            return True
        return False

    def reset_whitelist(self):
        """Resets protected whitelist to defaults."""
        self.save_whitelist(list(DEFAULT_WHITELIST))

    def is_protected_domain(self, host: str, whitelist: Optional[list[str]] = None) -> bool:
        """Checks if a given cookie host matches protected domains."""
        wl = whitelist if whitelist is not None else self.get_whitelist()
        clean_host = host.lower().lstrip(".")
        for protected in wl:
            if clean_host == protected or clean_host.endswith("." + protected):
                return True
        return False

    def get_browser_targets(self) -> list[dict]:
        """Discovers all installed browser cookie database locations."""
        local = os.environ.get('LOCALAPPDATA', '')
        roaming = os.environ.get('APPDATA', '')

        targets = []

        # 1. Edge (Chromium)
        edge_base = os.path.join(local, r'Microsoft\Edge\User Data')
        if os.path.exists(edge_base):
            for pattern in ['Default', 'Profile *']:
                for prof in glob.glob(os.path.join(edge_base, pattern)):
                    cpath = os.path.join(prof, 'Network', 'Cookies')
                    if os.path.exists(cpath):
                        targets.append({
                            'browser': 'Microsoft Edge',
                            'exe': 'msedge.exe',
                            'type': 'chromium',
                            'profile': os.path.basename(prof),
                            'path': cpath
                        })

        # 2. Google Chrome
        chrome_base = os.path.join(local, r'Google\Chrome\User Data')
        if os.path.exists(chrome_base):
            for pattern in ['Default', 'Profile *']:
                for prof in glob.glob(os.path.join(chrome_base, pattern)):
                    cpath = os.path.join(prof, 'Network', 'Cookies')
                    if os.path.exists(cpath):
                        targets.append({
                            'browser': 'Google Chrome',
                            'exe': 'chrome.exe',
                            'type': 'chromium',
                            'profile': os.path.basename(prof),
                            'path': cpath
                        })

        # 3. Brave Browser
        brave_base = os.path.join(local, r'BraveSoftware\Brave-Browser\User Data')
        if os.path.exists(brave_base):
            for pattern in ['Default', 'Profile *']:
                for prof in glob.glob(os.path.join(brave_base, pattern)):
                    cpath = os.path.join(prof, 'Network', 'Cookies')
                    if os.path.exists(cpath):
                        targets.append({
                            'browser': 'Brave Browser',
                            'exe': 'brave.exe',
                            'type': 'chromium',
                            'profile': os.path.basename(prof),
                            'path': cpath
                        })

        # 4. Opera & Opera GX
        opera_path = os.path.join(roaming, r'Opera Software\Opera Stable\Network\Cookies')
        if os.path.exists(opera_path):
            targets.append({
                'browser': 'Opera',
                'exe': 'opera.exe',
                'type': 'chromium',
                'profile': 'Stable',
                'path': opera_path
            })

        operagx_path = os.path.join(roaming, r'Opera Software\Opera GX Stable\Network\Cookies')
        if os.path.exists(operagx_path):
            targets.append({
                'browser': 'Opera GX',
                'exe': 'opera.exe',
                'type': 'chromium',
                'profile': 'GX Stable',
                'path': operagx_path
            })

        # 5. Mozilla Firefox
        ff_base = os.path.join(roaming, r'Mozilla\Firefox\Profiles')
        if os.path.exists(ff_base):
            for prof in glob.glob(os.path.join(ff_base, '*')):
                cpath = os.path.join(prof, 'cookies.sqlite')
                if os.path.exists(cpath):
                    targets.append({
                        'browser': 'Mozilla Firefox',
                        'exe': 'firefox.exe',
                        'type': 'firefox',
                        'profile': os.path.basename(prof),
                        'path': cpath
                    })

        return targets

    def is_browser_running(self, exe_name: str) -> bool:
        """Checks if a browser process is currently holding database locks."""
        low_exe = exe_name.lower()
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and p.info['name'].lower() == low_exe:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def close_browser(self, exe_name: str) -> bool:
        """Gracefully closes a browser to release file locks."""
        try:
            kwargs = {"capture_output": True, "text": True, "timeout": 5}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.run(["taskkill", "/F", "/IM", exe_name], **kwargs)
            return True
        except Exception:
            return False

    def scan_cookies(self) -> dict:
        """
        Scans all accessible browser cookie stores and classifies them.
        """
        whitelist = self.get_whitelist()
        targets = self.get_browser_targets()

        # O(1) batched process lookup cache
        running_exes = set()
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name']:
                    running_exes.add(p.info['name'].lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        total_cookies = 0
        protected_count = 0
        tracking_count = 0
        domain_items: list[CookieDomainItem] = []
        locked_browsers: set[str] = set()

        for t in targets:
            browser_name = t['browser']
            db_path = t['path']
            b_type = t['type']
            exe = t['exe']

            if exe.lower() in running_exes:
                locked_browsers.add(browser_name)
                # Try reading anyway in case read sharing is open
            con = None
            try:
                con = sqlite3.connect(db_path, timeout=1.0)
                cur = con.cursor()

                if b_type == 'chromium':
                    cur.execute("SELECT host_key, COUNT(*) FROM cookies GROUP BY host_key")
                else:
                    cur.execute("SELECT host, COUNT(*) FROM moz_cookies GROUP BY host")

                for host, count in cur.fetchall():
                    total_cookies += count
                    is_prot = self.is_protected_domain(host, whitelist)
                    is_track = any(t in host.lower() for t in KNOWN_TRACKERS)

                    if is_prot:
                        protected_count += count
                    else:
                        tracking_count += count

                    domain_items.append(CookieDomainItem(
                        browser=browser_name,
                        host=host,
                        count=count,
                        is_protected=is_prot,
                        is_known_tracker=is_track
                    ))
            except Exception:
                # If locked, record browser as locked
                locked_browsers.add(browser_name)
            finally:
                if con:
                    try:
                        con.close()
                    except Exception:
                        pass

        # Sort: Trackers first, then protected, then alphabetical
        domain_items.sort(key=lambda d: (not d.is_known_tracker, d.is_protected, d.host))

        return {
            'total_cookies': total_cookies,
            'protected_count': protected_count,
            'tracking_count': tracking_count,
            'locked_browsers': list(locked_browsers),
            'domain_items': domain_items,
            'targets': targets
        }

    def clean_tracking_cookies(self) -> tuple[int, int, list[str]]:
        """
        Purges all non-whitelisted tracking and advertising cookies while strictly
        preserving protected user login sessions.
        Returns (deleted_count, preserved_count, locked_browsers).
        """
        whitelist = self.get_whitelist()
        targets = self.get_browser_targets()

        # O(1) batched process lookup cache
        running_exes = set()
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name']:
                    running_exes.add(p.info['name'].lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        deleted_total = 0
        preserved_total = 0
        locked_browsers = []

        for t in targets:
            browser_name = t['browser']
            db_path = t['path']
            b_type = t['type']
            exe = t['exe']

            if exe.lower() in running_exes:
                locked_browsers.append(browser_name)
                continue

            con = None
            try:
                con = sqlite3.connect(db_path, timeout=1.0)
                cur = con.cursor()

                host_col = "host_key" if b_type == "chromium" else "host"
                table_name = "cookies" if b_type == "chromium" else "moz_cookies"

                cur.execute(f"SELECT rowid, {host_col} FROM {table_name}")
                rows = cur.fetchall()

                delete_rowids = []
                for rowid, host in rows:
                    if self.is_protected_domain(host, whitelist):
                        preserved_total += 1
                    else:
                        delete_rowids.append(rowid)

                if delete_rowids:
                    # Batch delete in chunks of 500
                    for i in range(0, len(delete_rowids), 500):
                        chunk = delete_rowids[i:i + 500]
                        placeholders = ",".join("?" for _ in chunk)
                        cur.execute(f"DELETE FROM {table_name} WHERE rowid IN ({placeholders})", chunk)

                    con.commit()
                    deleted_total += len(delete_rowids)
                    try:
                        cur.execute("VACUUM")
                    except Exception:
                        pass
            except Exception:
                locked_browsers.append(browser_name)
            finally:
                if con:
                    try:
                        con.close()
                    except Exception:
                        pass

        return deleted_total, preserved_total, list(set(locked_browsers))
