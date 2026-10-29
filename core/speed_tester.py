"""
NovaCare System Suite - Real-Time Internet Speed Test Engine
Measures latency (Ping), jitter, download bandwidth, and upload bandwidth
using globally distributed Cloudflare edge nodes with zero external binary dependencies.
Multi-stream adaptive benchmarking with TCP slow-start compensation and rate-limit resilience.
"""
import time
import collections
import statistics
import threading
import requests
from dataclasses import dataclass
from typing import Optional, Callable
from core.utils import log_debug

AIRPORT_COLO_MAP = {
    "IST": "İstanbul",
    "SAW": "İstanbul",
    "ESB": "Ankara",
    "ADB": "İzmir",
    "AYT": "Antalya",
    "ADA": "Adana",
    "TZX": "Trabzon",
    "DLM": "Muğla/Dalaman",
    "BJV": "Muğla/Bodrum",
    "GZT": "Gaziantep",
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
    "MUC": "Münih",
    "BER": "Berlin",
    "ZRH": "Zürih",
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


class UploadChunkReader:
    """
    Fixed-size payload generator for HTTP POST uploads.
    Streams synthetic chunks and triggers on_read callbacks as bytes leave the socket.
    """
    def __init__(self, size: int, on_read: Optional[Callable[[int], None]] = None):
        self.size = size
        self.sent = 0
        self.on_read = on_read
        self.chunk = b"0" * 32768

    def read(self, amt: int = -1) -> bytes:
        if self.sent >= self.size:
            return b""
        to_read = min(len(self.chunk), self.size - self.sent)
        if amt > 0:
            to_read = min(to_read, amt)
        self.sent += to_read
        if self.on_read:
            self.on_read(to_read)
        return self.chunk[:to_read]


class TimedUploadStream:
    """
    Chunked HTTP streaming generator for upload speed testing.
    Kept for backward compatibility and single-stream benchmarking.
    """
    def __init__(
        self,
        duration: float,
        chunk_size: int = 32768,
        on_chunk: Optional[Callable[[int, float, float], None]] = None
    ):
        self.duration = duration
        self.chunk_size = chunk_size
        self.chunk = b"0" * chunk_size
        self.on_chunk = on_chunk
        self.t_start: Optional[float] = None
        self.t_last_chunk: Optional[float] = None
        self.total_bytes = 0
        self.cancelled = False

    def __iter__(self):
        self.t_start = time.perf_counter()
        while not self.cancelled:
            t_cur = time.perf_counter()
            elapsed = t_cur - self.t_start
            if elapsed >= self.duration:
                break
            self.total_bytes += self.chunk_size
            self.t_last_chunk = t_cur
            if self.on_chunk:
                self.on_chunk(self.total_bytes, t_cur, elapsed)
            yield self.chunk


class SpeedTester:
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
        self._current_responses: list[requests.Response] = []
        self._current_upload_stream: Optional[TimedUploadStream] = None
        self.session: Optional[requests.Session] = None
        self._init_session()

    def _init_session(self):
        """Initializes or resets the requests Session with high-concurrency connection pooling."""
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://speed.cloudflare.com/"
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=1
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def cancel(self):
        """Signals the running test to cancel safely and immediately aborts connections."""
        self._cancelled = True
        if self._current_upload_stream:
            self._current_upload_stream.cancelled = True

        with self._lock:
            for r in self._current_responses:
                try:
                    r.close()
                except Exception:
                    pass
            self._current_responses.clear()

        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

    def close(self):
        """Safely closes the underlying requests session and socket pools."""
        self.cancel()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_session(self):
        """Ensures an active session is available before running requests."""
        if self.session is None:
            self._init_session()

    def get_network_meta(self) -> tuple[str, str]:
        """
        Retrieves public IP and nearest Cloudflare Edge server location.
        Returns: (client_ip, location_string)
        """
        self._ensure_session()
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
        except Exception as e:
            log_debug(f"SpeedTester.get_network_meta failed: {e}")

        # Secondary fallback trace
        try:
            r2 = self.session.get("https://1.1.1.1/cdn-cgi/trace", timeout=3)
            if r2.status_code == 200:
                trace = dict(line.split("=", 1) for line in r2.text.strip().splitlines() if "=" in line)
                ip = trace.get("ip", "Otomatik Tespit")
                colo = trace.get("colo", "").upper()
                city = AIRPORT_COLO_MAP.get(colo, colo)
                return ip, f"{city} Edge Sunucusu"
        except Exception:
            pass

        return "Otomatik Tespit", "Türkiye / Avrupa Edge Sunucusu"

    def run_ping_and_jitter(self, count: int = 6) -> tuple[float, float]:
        """
        Measures HTTP RTT and jitter over consecutive round-trips.
        Returns: (ping_ms, jitter_ms)
        """
        self._ensure_session()
        pings: list[float] = []
        for _ in range(count):
            if self._cancelled:
                break
            t0 = time.perf_counter()
            try:
                self.session.get("https://speed.cloudflare.com/__down?bytes=0", timeout=3)
                pings.append((time.perf_counter() - t0) * 1000.0)
            except Exception:
                try:
                    self.session.get("https://1.1.1.1/cdn-cgi/trace", timeout=3)
                    pings.append((time.perf_counter() - t0) * 1000.0)
                except Exception:
                    pass
            time.sleep(0.03)

        if not pings or self._cancelled:
            return (999.0, 0.0) if not pings else (round(pings[0], 1), 0.0)

        # Discard the initial TLS handshake outlier if multiple samples exist
        valid_pings = pings[1:] if len(pings) > 2 else pings
        ping_val = round(min(valid_pings), 1)

        diffs = [abs(valid_pings[i] - valid_pings[i - 1]) for i in range(1, len(valid_pings))]
        jitter_val = round(statistics.mean(diffs), 1) if diffs else 0.0
        return ping_val, jitter_val

    def run_download_test(
        self,
        duration: float = 5.5,
        progress_callback: Optional[Callable[[float, int], None]] = None
    ) -> float:
        """
        Measures download bandwidth over a sustained testing duration using multi-stream
        chunk downloads with TCP slow-start compensation and rate-limit resilience.
        Guarantees realistic saturation for broadband/fiber connections without early exits.
        progress_callback(current_mbps, percent_0_to_100)
        Returns: download_mbps
        """
        self._ensure_session()
        t_start = time.perf_counter()
        total_bytes = 0
        bytes_lock = threading.Lock()
        stop_workers = False

        # Multi-CDN resilient endpoints (Cloudflare 5MB/2.5MB/1MB + OVH CDN)
        download_endpoints = [
            "https://speed.cloudflare.com/__down?bytes=5000000",
            "https://speed.cloudflare.com/__down?bytes=2500000",
            "https://proof.ovh.net/files/10Mb.dat",
            "https://speed.cloudflare.com/__down?bytes=1000000"
        ]

        def worker(worker_id: int):
            nonlocal total_bytes
            ep_idx = worker_id % len(download_endpoints)
            while not self._cancelled and not stop_workers:
                now = time.perf_counter()
                if (now - t_start) >= duration:
                    break

                url = download_endpoints[ep_idx]
                try:
                    with self.session.get(url, stream=True, timeout=5) as r:
                        with self._lock:
                            if self._cancelled or stop_workers:
                                r.close()
                                break
                            self._current_responses.append(r)

                        if r.status_code == 200:
                            for chunk in r.iter_content(chunk_size=65536):
                                if self._cancelled or stop_workers or (time.perf_counter() - t_start) >= duration:
                                    break
                                if chunk:
                                    with bytes_lock:
                                        total_bytes += len(chunk)
                        elif r.status_code == 429:
                            # Rate limit encountered: rotate endpoint and back off briefly
                            ep_idx = (ep_idx + 1) % len(download_endpoints)
                            time.sleep(0.1)

                        r.close()
                        with self._lock:
                            if r in self._current_responses:
                                self._current_responses.remove(r)
                except Exception:
                    ep_idx = (ep_idx + 1) % len(download_endpoints)
                    time.sleep(0.08)

        # Launch 3 concurrent streaming workers to saturate line capacity
        concurrency = 3
        threads = [
            threading.Thread(target=worker, args=(i,), daemon=True)
            for i in range(concurrency)
        ]
        for t in threads:
            t.start()

        window = collections.deque()
        warmup_cutoff = 1.0  # Discard initial 1.0s slow-start ramp-up
        bytes_at_warmup = 0
        t_warmup = t_start
        warmup_recorded = False

        # Monitor loop: smooth 20 updates/second calculation
        while not self._cancelled:
            now = time.perf_counter()
            elapsed = now - t_start
            if elapsed >= duration:
                break

            with bytes_lock:
                cur_bytes = total_bytes

            if not warmup_recorded and elapsed >= warmup_cutoff:
                bytes_at_warmup = cur_bytes
                t_warmup = now
                warmup_recorded = True

            window.append((now, cur_bytes))
            while window and (now - window[0][0]) > 0.8:
                window.popleft()

            if len(window) > 1 and (now - window[0][0]) >= 0.15:
                w_dt = now - window[0][0]
                w_db = cur_bytes - window[0][1]
                cur_mbps = (w_db * 8.0) / (w_dt * 1_000_000.0)
            else:
                cur_mbps = (cur_bytes * 8.0) / (max(0.05, elapsed) * 1_000_000.0)

            pct = min(100, int((elapsed / duration) * 100))
            if progress_callback:
                progress_callback(round(cur_mbps, 1), pct)

            time.sleep(0.05)

        stop_workers = True
        with self._lock:
            for r in self._current_responses:
                try:
                    r.close()
                except Exception:
                    pass
            self._current_responses.clear()

        for t in threads:
            t.join(timeout=0.3)

        t_end = time.perf_counter()
        with bytes_lock:
            final_bytes = total_bytes

        if final_bytes <= 0 or self._cancelled:
            return 0.0

        # Compute sustained download throughput excluding TCP slow-start
        if warmup_recorded and (t_end - t_warmup) >= 0.5 and (final_bytes - bytes_at_warmup) > 0:
            sustained_bytes = final_bytes - bytes_at_warmup
            sustained_time = t_end - t_warmup
            final_mbps = (sustained_bytes * 8.0) / (sustained_time * 1_000_000.0)
        else:
            final_mbps = (final_bytes * 8.0) / (max(0.1, t_end - t_start) * 1_000_000.0)

        final_mbps = round(final_mbps, 1)
        if progress_callback:
            progress_callback(final_mbps, 100)
        return final_mbps

    def run_upload_test(
        self,
        duration: float = 4.5,
        progress_callback: Optional[Callable[[float, int], None]] = None
    ) -> float:
        """
        Measures upload bandwidth over sustained testing duration using multi-stream
        chunk uploads with real-time socket tracking.
        Accurately calculates throughput based on active transmission time without post-response latency.
        progress_callback(current_mbps, percent_0_to_100)
        Returns: upload_mbps
        """
        self._ensure_session()
        t_start = time.perf_counter()
        total_bytes = 0
        bytes_lock = threading.Lock()
        last_chunk_time = t_start
        stop_workers = False

        def on_chunk_read(n: int):
            nonlocal total_bytes, last_chunk_time
            if self._cancelled:
                return
            t_now = time.perf_counter()
            with bytes_lock:
                total_bytes += n
                last_chunk_time = t_now

        def upload_worker():
            while not self._cancelled and not stop_workers:
                now = time.perf_counter()
                if (now - t_start) >= duration:
                    break

                try:
                    reader = UploadChunkReader(size=1024 * 1024, on_read=on_chunk_read)
                    r = self.session.post(
                        "https://speed.cloudflare.com/__up",
                        data=reader,
                        timeout=5
                    )
                    with self._lock:
                        if self._cancelled or stop_workers:
                            r.close()
                            break
                        self._current_responses.append(r)
                    r.close()
                    with self._lock:
                        if r in self._current_responses:
                            self._current_responses.remove(r)
                except Exception:
                    time.sleep(0.08)

        # Launch 2 concurrent upload streams
        concurrency = 2
        threads = [
            threading.Thread(target=upload_worker, daemon=True)
            for _ in range(concurrency)
        ]
        for t in threads:
            t.start()

        window = collections.deque()
        warmup_cutoff = 1.0  # Discard initial 1.0s buffer ramp-up
        bytes_at_warmup = 0
        t_warmup = t_start
        warmup_recorded = False

        while not self._cancelled:
            now = time.perf_counter()
            elapsed = now - t_start
            if elapsed >= duration:
                break

            with bytes_lock:
                cur_bytes = total_bytes

            if not warmup_recorded and elapsed >= warmup_cutoff:
                bytes_at_warmup = cur_bytes
                t_warmup = now
                warmup_recorded = True

            window.append((now, cur_bytes))
            while window and (now - window[0][0]) > 0.8:
                window.popleft()

            if len(window) > 1 and (now - window[0][0]) >= 0.15:
                w_dt = now - window[0][0]
                w_db = cur_bytes - window[0][1]
                cur_mbps = (w_db * 8.0) / (w_dt * 1_000_000.0)
            else:
                cur_mbps = (cur_bytes * 8.0) / (max(0.05, elapsed) * 1_000_000.0)

            pct = min(100, int((elapsed / duration) * 100))
            if progress_callback:
                progress_callback(round(cur_mbps, 1), pct)

            time.sleep(0.05)

        stop_workers = True
        with self._lock:
            for r in self._current_responses:
                try:
                    r.close()
                except Exception:
                    pass
            self._current_responses.clear()

        for t in threads:
            t.join(timeout=0.3)

        t_end = time.perf_counter()
        with bytes_lock:
            final_bytes = total_bytes
            t_last = last_chunk_time

        if final_bytes <= 0 or self._cancelled:
            return 0.0

        # Calculate sustained upload based on active transmission window
        t_calc_end = t_last if t_last > t_warmup else t_end
        if warmup_recorded and (t_calc_end - t_warmup) >= 0.5:
            sustained_bytes = final_bytes - bytes_at_warmup
            sustained_time = t_calc_end - t_warmup
            final_mbps = (sustained_bytes * 8.0) / (sustained_time * 1_000_000.0)
        else:
            final_mbps = (final_bytes * 8.0) / (max(0.1, t_calc_end - t_start) * 1_000_000.0)

        final_mbps = round(final_mbps, 1)
        if progress_callback:
            progress_callback(final_mbps, 100)
        return final_mbps

    @staticmethod
    def evaluate_connection_grade(download_mbps: float, ping_ms: float) -> tuple[str, str]:
        """Returns friendly connection grade and real-world performance capability assessment."""
        if download_mbps >= 100.0:
            if ping_ms <= 35.0:
                return (
                    "Olağanüstü (Ultra Hızlı Fiber)",
                    "4K/8K canlı yayın, e-spor rekabetçi oyunlar ve çoklu eşzamanlı cihaz için mükemmel performans."
                )
            else:
                return (
                    "Çok Hızlı (Yüksek Bant Genişliği)",
                    "Büyük dosya indirmeleri, çoklu 4K video akışı ve yüksek bant genişliği gerektiren işlemler için mükemmel."
                )
        elif download_mbps >= 50.0:
            if ping_ms <= 45.0:
                return (
                    "Mükemmel (Yüksek Hızlı Genişbant)",
                    "4K HDR video izleme, hızlı dosya indirme ve düşük gecikmeli online oyunlar için son derece ideal."
                )
            else:
                return (
                    "Mükemmel (Hızlı Genişbant)",
                    "4K video izleme, hızlı indirme ve kesintisiz internet gezintisi için ideal."
                )
        elif download_mbps >= 25.0:
            return (
                "Çok İyi (Hızlı İnternet)",
                "Full HD video konferans, Netflix/YouTube 1080p ve kesintisiz çoklu web gezintisi sağlar."
            )
        elif download_mbps >= 10.0:
            return (
                "İyi (Standart Bağlantı)",
                "Sosyal medya, HD video ve standart internet kullanımı için yeterli bant genişliği."
            )
        elif download_mbps > 0.0:
            return (
                "Temel / Düşük Hız",
                "Temel web aramaları ve mesajlaşma için uygundur. Büyük indirmelerde gecikme yaşanabilir."
            )
        return (
            "Bağlantı Yok / Test Edilemedi",
            "İnternet bağlantınızı ve ağ bağdaştırıcınızı kontrol ediniz."
        )

    def run_full_test(
        self,
        phase_callback: Optional[Callable[[str, str], None]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
        stats_callback: Optional[Callable[[str, float], None]] = None
    ) -> SpeedTestResult:
        """
        Executes complete internet benchmark: metadata -> ping/jitter -> download -> upload.
        Guarantees realistic testing duration, smooth UI animations, and accurate throughput.
        """
        self._cancelled = False
        self._ensure_session()

        def _emit_progress(phase: str, mbps: float, overall_pct: int):
            if not progress_callback:
                return
            try:
                progress_callback(phase, mbps, overall_pct)
            except TypeError:
                progress_callback(mbps, overall_pct)

        # Phase 1: Network & Server metadata
        if phase_callback:
            phase_callback("meta", "En yakın Cloudflare Edge sunucusu tespit ediliyor...")
        client_ip, server_loc = self.get_network_meta()

        if self._cancelled:
            return self._empty_result(client_ip, server_loc)

        if phase_callback:
            phase_callback("server_info", f"📍 Sunucu: {server_loc}  |  IP: {client_ip}")

        # Phase 2: Ping & Jitter
        if phase_callback:
            phase_callback("ping", "Gecikme süresi (Ping) ve kararlılık (Jitter) ölçülüyor...")
        ping_val, jitter_val = self.run_ping_and_jitter()

        if not self._cancelled and stats_callback:
            stats_callback("ping", ping_val)
            stats_callback("jitter", jitter_val)

        if self._cancelled:
            return self._empty_result(client_ip, server_loc, ping_val, jitter_val)

        # Phase 3: Download Speed (Target duration ~5.5s)
        if phase_callback:
            phase_callback("download", "İndirme hızı (Download) test ediliyor...")

        def _dl_progress(cur_speed: float, pct_stage: int):
            overall_pct = 20 + int(pct_stage * 0.40)  # Map 0-100% stage -> 20-60% overall
            _emit_progress("download", cur_speed, min(60, overall_pct))

        dl_mbps = self.run_download_test(duration=5.5, progress_callback=_dl_progress)

        if not self._cancelled and stats_callback:
            stats_callback("download", dl_mbps)

        if self._cancelled:
            return self._empty_result(client_ip, server_loc, ping_val, jitter_val, dl_mbps)

        # Phase 4: Upload Speed (Target duration ~4.5s)
        if phase_callback:
            phase_callback("upload", "Yükleme hızı (Upload) test ediliyor...")

        def _ul_progress(cur_speed: float, pct_stage: int):
            overall_pct = 60 + int(pct_stage * 0.35)  # Map 0-100% stage -> 60-95% overall
            _emit_progress("upload", cur_speed, min(95, overall_pct))

        up_mbps = self.run_upload_test(duration=4.5, progress_callback=_ul_progress)

        if not self._cancelled and stats_callback:
            stats_callback("upload", up_mbps)

        if self._cancelled:
            return self._empty_result(client_ip, server_loc, ping_val, jitter_val, dl_mbps, up_mbps)

        grade, grade_desc = self.evaluate_connection_grade(dl_mbps, ping_val)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")

        _emit_progress("done", dl_mbps, 100)
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
