"""
NovaCare System Suite - Real-Time Internet Speed Test Engine
Measures latency (Ping), jitter, download bandwidth, and upload bandwidth
using globally distributed Cloudflare edge nodes with zero external binary dependencies.
"""
import time
import statistics
import requests
from dataclasses import dataclass
from typing import Optional, Callable

AIRPORT_COLO_MAP = {
    "IST": "İstanbul",
    "SAW": "İstanbul",
    "ESB": "Ankara",
    "ADB": "İzmir",
    "AYT": "Antalya",
    "ADA": "Adana",
    "TZX": "Trabzon",
    "FRA": "Frankfurt",
    "AMS": "Amsterdam",
    "LHR": "Londra",
    "CDG": "Paris",
    "VIE": "Viyana",
    "ATH": "Atina",
    "SOF": "Sofya",
    "OTP": "Bükreş",
    "WAW": "Varşova",
    "BEG": "Belgrad",
    "DXB": "Dubai",
    "DOH": "Doha",
    "JFK": "New York",
    "LAX": "Los Angeles",
    "ORD": "Chicago",
    "NRT": "Tokyo",
    "SIN": "Singapur"
}

@dataclass
class SpeedTestResult:
    ping_ms: float
    jitter_ms: float
    download_mbps: float
    upload_mbps: float
    client_ip: str
    server_location: str
    grade: str
    grade_description: str
    timestamp: str

class SpeedTester:
    def __init__(self):
        self._cancelled = False
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NovaCare-SpeedTester/1.0"
        })

    def cancel(self):
        """Signals the running test to cancel safely."""
        self._cancelled = True

    def get_network_meta(self) -> tuple[str, str]:
        """
        Retrieves public IP and nearest Cloudflare Edge server location.
        Returns: (client_ip, location_string)
        """
        try:
            r = self.session.get("https://speed.cloudflare.com/cdn-cgi/trace", timeout=4)
            if r.status_code == 200:
                trace = dict(line.split("=", 1) for line in r.text.strip().splitlines() if "=" in line)
                ip = trace.get("ip", "Bilinmiyor")
                colo = trace.get("colo", "").upper()
                loc = trace.get("loc", "TR")
                city = AIRPORT_COLO_MAP.get(colo, colo)
                loc_str = f"{city} ({colo}), {loc} (Cloudflare Edge)" if colo else f"{loc} (Cloudflare Edge)"
                return ip, loc_str
        except Exception:
            pass
        return "Otomatik Tespit", "Türkiye / Avrupa Edge Sunucusu"

    def run_ping_and_jitter(self, count: int = 5) -> tuple[float, float]:
        """
        Measures HTTP RTT and jitter over consecutive round-trips.
        Returns: (ping_ms, jitter_ms)
        """
        pings: list[float] = []
        for _ in range(count):
            if self._cancelled:
                break
            t0 = time.perf_counter()
            try:
                self.session.get("https://speed.cloudflare.com/__down?bytes=0", timeout=3)
                pings.append((time.perf_counter() - t0) * 1000.0)
            except Exception:
                pass
            time.sleep(0.04)

        if not pings:
            return 999.0, 0.0

        # Discard the initial TLS handshake outlier if multiple samples exist
        valid_pings = pings[1:] if len(pings) > 2 else pings
        ping_val = round(min(valid_pings), 1)

        diffs = [abs(valid_pings[i] - valid_pings[i-1]) for i in range(1, len(valid_pings))]
        jitter_val = round(statistics.mean(diffs), 1) if diffs else 0.0
        return ping_val, jitter_val

    def run_download_test(
        self,
        progress_callback: Optional[Callable[[float, int], None]] = None
    ) -> float:
        """
        Measures download speed with adaptive chunk sizing and real-time speed progress.
        progress_callback(current_mbps, percent_0_to_100)
        Returns: download_mbps
        """
        # Step 1: Initial warm-up chunk (2.5 MB)
        t_start = time.perf_counter()
        initial_bytes = 2_500_000
        dl_total = 0
        try:
            r = self.session.get(f"https://speed.cloudflare.com/__down?bytes={initial_bytes}", stream=True, timeout=8)
            for chunk in r.iter_content(chunk_size=32768):
                if self._cancelled:
                    return 0.0
                if chunk:
                    dl_total += len(chunk)
                    elapsed = max(0.05, time.perf_counter() - t_start)
                    cur_speed = (dl_total * 8.0) / (elapsed * 1_000_000.0)
                    if progress_callback:
                        progress_callback(round(cur_speed, 1), min(45, int((dl_total / initial_bytes) * 45)))
        except Exception:
            pass

        t_initial = max(0.05, time.perf_counter() - t_start)
        initial_mbps = (dl_total * 8.0) / (t_initial * 1_000_000.0)

        # Step 2: Adaptive sizing based on initial speed
        if initial_mbps >= 60.0:
            target_bytes = 20_000_000  # 20 MB for fast fiber connections
        elif initial_mbps >= 25.0:
            target_bytes = 10_000_000  # 10 MB for standard broadband
        else:
            target_bytes = 5_000_000   # 5 MB for slower connections

        t_stage2 = time.perf_counter()
        stage2_dl = 0
        try:
            r2 = self.session.get(f"https://speed.cloudflare.com/__down?bytes={target_bytes}", stream=True, timeout=15)
            for chunk in r2.iter_content(chunk_size=65536):
                if self._cancelled:
                    return 0.0
                if chunk:
                    stage2_dl += len(chunk)
                    elapsed = max(0.05, time.perf_counter() - t_stage2)
                    cur_speed = (stage2_dl * 8.0) / (elapsed * 1_000_000.0)
                    pct = 45 + int((stage2_dl / target_bytes) * 55)
                    if progress_callback:
                        progress_callback(round(cur_speed, 1), min(99, pct))
        except Exception:
            pass

        t_total = max(0.1, time.perf_counter() - t_stage2)
        final_mbps = (stage2_dl * 8.0) / (t_total * 1_000_000.0) if stage2_dl > 0 else initial_mbps
        if progress_callback:
            progress_callback(round(final_mbps, 1), 100)
        return round(final_mbps, 1)

    def run_upload_test(
        self,
        progress_callback: Optional[Callable[[float, int], None]] = None
    ) -> float:
        """
        Measures upload speed with payload streaming to Cloudflare upload test endpoint.
        progress_callback(current_mbps, percent_0_to_100)
        Returns: upload_mbps
        """
        payload_size = 2_000_000  # 2 MB payload
        payload = b"0" * payload_size
        t0 = time.perf_counter()

        try:
            if progress_callback:
                progress_callback(0.0, 15)
            self.session.post("https://speed.cloudflare.com/__up", data=payload, timeout=12)
            dur = max(0.08, time.perf_counter() - t0)
            up_mbps = (payload_size * 8.0) / (dur * 1_000_000.0)
            if progress_callback:
                progress_callback(round(up_mbps, 1), 60)

            # If fast, perform a second larger verification payload
            if up_mbps >= 15.0 and not self._cancelled:
                larger_size = 5_000_000  # 5 MB
                larger_payload = b"0" * larger_size
                t1 = time.perf_counter()
                self.session.post("https://speed.cloudflare.com/__up", data=larger_payload, timeout=15)
                dur2 = max(0.1, time.perf_counter() - t1)
                up_mbps = (larger_size * 8.0) / (dur2 * 1_000_000.0)

            if progress_callback:
                progress_callback(round(up_mbps, 1), 100)
            return round(up_mbps, 1)
        except Exception:
            return 0.0

    @staticmethod
    def evaluate_connection_grade(download_mbps: float, ping_ms: float) -> tuple[str, str]:
        """Returns friendly connection grade and real-world performance capability assessment."""
        if download_mbps >= 100.0 and ping_ms <= 25.0:
            return "Olağanüstü (Ultra Hızlı Fiber)", "4K/8K canlı yayın, e-spor rekabetçi oyunlar ve çoklu eşzamanlı cihaz için mükemmel performans."
        elif download_mbps >= 50.0 and ping_ms <= 40.0:
            return "Mükemmel (Yüksek Hızlı Genişbant)", "4K HDR video izleme, hızlı dosya indirme ve düşük gecikmeli online oyunlar için son derece ideal."
        elif download_mbps >= 25.0:
            return "Çok İyi (Hızlı İnternet)", "Full HD video konferans, Netflix/YouTube 1080p ve kesintisiz çoklu web gezintisi sağlar."
        elif download_mbps >= 10.0:
            return "İyi (Standart Bağlantı)", "Sosyal medya, HD video ve standart internet kullanımı için yeterli bant genişliği."
        elif download_mbps > 0.0:
            return "Temel / Düşük Hız", "Temel web aramaları ve mesajlaşma için uygundur. Büyük indirmelerde gecikme yaşanabilir."
        return "Bağlantı Yok / Test Edilemedi", "İnternet bağlantınızı ve ağ bağdaştırıcınızı kontrol ediniz."

    def run_full_test(
        self,
        phase_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[[float, int], None]] = None
    ) -> SpeedTestResult:
        """
        Executes complete internet benchmark: metadata -> ping/jitter -> download -> upload.
        """
        self._cancelled = False

        # Phase 1: Network & Server metadata
        if phase_callback:
            phase_callback("meta", "En yakın Cloudflare Edge sunucusu tespit ediliyor...")
        client_ip, server_loc = self.get_network_meta()

        if self._cancelled:
            return self._empty_result(client_ip, server_loc)

        # Phase 2: Ping & Jitter
        if phase_callback:
            phase_callback("ping", "Gecikme süresi (Ping) ve kararlılık (Jitter) ölçülüyor...")
        ping_val, jitter_val = self.run_ping_and_jitter()

        if self._cancelled:
            return self._empty_result(client_ip, server_loc, ping_val, jitter_val)

        # Phase 3: Download Speed
        if phase_callback:
            phase_callback("download", "İndirme hızı (Download) test ediliyor...")
        dl_mbps = self.run_download_test(progress_callback=progress_callback)

        if self._cancelled:
            return self._empty_result(client_ip, server_loc, ping_val, jitter_val, dl_mbps)

        # Phase 4: Upload Speed
        if phase_callback:
            phase_callback("upload", "Yükleme hızı (Upload) test ediliyor...")
        up_mbps = self.run_upload_test(progress_callback=progress_callback)

        grade, grade_desc = self.evaluate_connection_grade(dl_mbps, ping_val)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

        if phase_callback:
            phase_callback("done", f"Hız testi tamamlandı! ({grade})")

        return SpeedTestResult(
            ping_ms=ping_val,
            jitter_ms=jitter_val,
            download_mbps=dl_mbps,
            upload_mbps=up_mbps,
            client_ip=client_ip,
            server_location=server_loc,
            grade=grade,
            grade_description=grade_desc,
            timestamp=ts
        )

    def _empty_result(
        self,
        ip: str = "",
        loc: str = "",
        ping: float = 0.0,
        jitter: float = 0.0,
        dl: float = 0.0,
        up: float = 0.0
    ) -> SpeedTestResult:
        return SpeedTestResult(
            ping_ms=ping,
            jitter_ms=jitter,
            download_mbps=dl,
            upload_mbps=up,
            client_ip=ip,
            server_location=loc,
            grade="İptal Edildi",
            grade_description="Test kullanıcı tarafından iptal edildi.",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
