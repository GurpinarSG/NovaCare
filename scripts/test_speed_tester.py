"""
NovaCare System Suite - Internet Speed Test Engine & Network View Verification
Tests latency, jitter, sustained download, sustained upload, cancellation,
TCP slow-start compensation, and NetworkView UI signal integration.
"""
import sys
import os
import time

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from core.speed_tester import SpeedTester, SpeedTestResult
from ui.views.network_view import NetworkView

print("1. Testing SpeedTester connection grade evaluation...")
test_cases = [
    (120.0, 18.0, "Olağanüstü (Ultra Hızlı Fiber)"),
    (150.0, 48.0, "Çok Hızlı (Yüksek Bant Genişliği)"),
    (65.0, 22.0, "Mükemmel (Yüksek Hızlı Genişbant)"),
    (70.0, 50.0, "Mükemmel (Hızlı Genişbant)"),
    (35.0, 30.0, "Çok İyi (Hızlı İnternet)"),
    (18.0, 40.0, "İyi (Standart Bağlantı)"),
    (6.0, 60.0, "Temel / Düşük Hız"),
    (0.0, 999.0, "Bağlantı Yok / Test Edilemedi"),
]
for dl, ping, expected_prefix in test_cases:
    grade, desc = SpeedTester.evaluate_connection_grade(dl, ping)
    assert grade == expected_prefix, f"Expected {expected_prefix}, got {grade}"
    assert len(desc) > 10
print("✓ Grade evaluation works across all bandwidth and latency profiles.")

print("2. Testing network metadata retrieval (Cloudflare trace)...")
tester = SpeedTester()
ip, loc = tester.get_network_meta()
assert ip and ip != "Bilinmiyor", f"Invalid IP: {ip}"
assert "Cloudflare" in loc or "Edge" in loc, f"Unexpected loc: {loc}"
print(f"✓ Network metadata resolved: IP={ip}, Location={loc}")

print("3. Testing ping and jitter benchmark...")
ping_ms, jitter_ms = tester.run_ping_and_jitter(count=4)
assert 0.0 < ping_ms < 1000.0, f"Unrealistic ping: {ping_ms}"
assert jitter_ms >= 0.0, f"Invalid jitter: {jitter_ms}"
print(f"✓ Ping & jitter measured: Ping={ping_ms} ms, Jitter={jitter_ms} ms")

print("4. Testing duration-based download test with TCP ramp-up...")
dl_updates = []
t0 = time.perf_counter()
dl_speed = tester.run_download_test(
    duration=3.0,
    progress_callback=lambda s, p: dl_updates.append((s, p))
)
dl_duration = time.perf_counter() - t0
assert 2.8 <= dl_duration <= 4.0, f"Download test duration out of range: {dl_duration:.2f}s"
assert dl_speed > 0.0, f"Download speed should be > 0: {dl_speed}"
assert len(dl_updates) >= 5, f"Expected streaming progress callbacks, got {len(dl_updates)}"
print(f"✓ Download test completed: {dl_speed} Mbps in {dl_duration:.2f}s with {len(dl_updates)} updates")

print("5. Testing duration-based upload test with streaming generator...")
ul_updates = []
t1 = time.perf_counter()
ul_speed = tester.run_upload_test(
    duration=3.0,
    progress_callback=lambda s, p: ul_updates.append((s, p))
)
ul_duration = time.perf_counter() - t1
assert 2.8 <= ul_duration <= 5.0, f"Upload test duration out of range: {ul_duration:.2f}s"
assert ul_speed > 0.0, f"Upload speed should be > 0: {ul_speed}"
assert len(ul_updates) >= 5, f"Expected streaming progress callbacks, got {len(ul_updates)}"
print(f"✓ Upload test completed: {ul_speed} Mbps in {ul_duration:.2f}s with {len(ul_updates)} updates")

print("6. Testing cancellation responsiveness...")
cancel_tester = SpeedTester()
import threading
def trigger_cancel():
    time.sleep(0.4)
    cancel_tester.cancel()

threading.Thread(target=trigger_cancel).start()
t_c0 = time.perf_counter()
c_res = cancel_tester.run_download_test(duration=5.0)
c_dur = time.perf_counter() - t_c0
assert c_dur < 1.5, f"Cancel took too long to abort: {c_dur:.2f}s"
assert c_res == 0.0, f"Cancelled download should return 0.0, got {c_res}"
print(f"✓ Cancel test aborted immediately in {c_dur:.2f}s")

print("7. Testing NetworkView UI state management and slots...")
view = NetworkView()
view.card_dl.set_value("-- Mbps", "Bekleniyor...")
view.card_ul.set_value("-- Mbps", "Bekleniyor...")

# Trigger phase updates
view._on_speed_phase_changed("meta", "Sunucu tespit ediliyor...")
assert view.speed_pbar.value() == 8

view._on_speed_phase_changed("ping", "Ping ölçülüyor...")
assert view.speed_pbar.value() == 15

view._on_speed_stats_updated("ping", 18.5)
assert "18.5 ms" in view.card_ping.value_lbl.text()

view._on_speed_stats_updated("jitter", 2.4)
assert "2.4 ms" in view.card_jitter.value_lbl.text()

# Trigger download phase
view._on_speed_phase_changed("download", "İndiriliyor...")
assert view.speed_pbar.value() == 20
assert "0.0 Mbps" in view.card_dl.value_lbl.text()

view._on_speed_progress("download", 250.4, 45)
assert view.speed_pbar.value() == 45
assert "250.4 Mbps" in view.card_dl.value_lbl.text()
assert "Bekleniyor" in view.card_ul.sub_lbl.text()

view._on_speed_stats_updated("download", 280.0)
assert "280.0 Mbps" in view.card_dl.value_lbl.text()

# Trigger upload phase
view._on_speed_phase_changed("upload", "Yükleniyor...")
assert view.speed_pbar.value() == 60
assert "0.0 Mbps" in view.card_ul.value_lbl.text()

view._on_speed_progress("upload", 42.1, 80)
assert view.speed_pbar.value() == 80
assert "42.1 Mbps" in view.card_ul.value_lbl.text()
# Ensure download card was untouched
assert "280.0 Mbps" in view.card_dl.value_lbl.text()

view._on_speed_stats_updated("upload", 45.0)
assert "45.0 Mbps" in view.card_ul.value_lbl.text()

# Finalize test
full_result = SpeedTestResult(
    ping_ms=18.5,
    jitter_ms=2.4,
    download_mbps=280.0,
    upload_mbps=45.0,
    client_ip=ip,
    server_location=loc,
    grade="Olağanüstü (Ultra Hızlı Fiber)",
    grade_description="Mükemmel bağlantı",
    timestamp="2026-10-29 21:30:00"
)
view._on_speed_finished(full_result)
assert view.speed_pbar.value() == 100
assert not view.frame_grade.isHidden()
assert "280.0 Mbps" in view.card_dl.value_lbl.text()
assert "45.0 Mbps" in view.card_ul.value_lbl.text()
print("✓ NetworkView UI slots and stat card state transitions verified.")

# Test cancel slot
view._on_speed_phase_changed("download", "İndiriliyor...")
view._on_speed_finished(None)
assert view.speed_pbar.value() == 0
assert "durduruldu" in view.lbl_speed_status.text()
assert "İptal Edildi" in view.card_dl.sub_lbl.text()
print("✓ Cancellation UI reset verified.")

print("8. Testing 429 rate-limit resilience during sustained download...")
resilience_tester = SpeedTester()
# Monkey-patch get to simulate Cloudflare returning 429 on first 2 calls
orig_get = resilience_tester.session.get
call_count = 0
def mock_get(url, *args, **kwargs):
    global call_count
    call_count += 1
    if "speed.cloudflare.com" in url and call_count <= 2:
        class Mock429:
            status_code = 429
            def close(self): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def iter_content(self, chunk_size=65536): return []
        return Mock429()
    return orig_get(url, *args, **kwargs)

resilience_tester.session.get = mock_get
t_resil_0 = time.perf_counter()
resil_speed = resilience_tester.run_download_test(duration=2.5)
resil_dur = time.perf_counter() - t_resil_0
assert resil_dur >= 2.4, f"Test broke early on 429 rate limit! Duration: {resil_dur:.2f}s"
assert resil_speed > 0.0, f"Expected non-zero speed after fallback, got: {resil_speed}"
print(f"✓ 429 rate-limit resilience confirmed: sustained {resil_dur:.2f}s yielding {resil_speed} Mbps.")

print("9. Testing rapid sub-second cancel and immediate restart...")
rapid_tester = SpeedTester()
rapid_tester.cancel()
# Immediate new session initialization and ping test
new_ping, new_jitter = rapid_tester.run_ping_and_jitter(count=2)
assert new_ping > 0.0, "Rapid restart ping failed"
print(f"✓ Rapid cancel and immediate restart clean: Ping={new_ping} ms")

print("10. Testing live server_info phase emission and offline UI handling...")
view._on_speed_phase_changed("server_info", "📍 Sunucu: Frankfurt (FRA), DE (Cloudflare Edge)  |  IP: 198.51.100.1")
assert "Frankfurt" in view.lbl_server_info.text()
offline_res = SpeedTestResult(
    ping_ms=999.0,
    jitter_ms=0.0,
    download_mbps=0.0,
    upload_mbps=0.0,
    client_ip="Otomatik Tespit",
    server_location="Bilinmiyor",
    grade="Bağlantı Yok / Test Edilemedi",
    grade_description="İnternet bağlantınızı kontrol ediniz.",
    timestamp="2026-10-29 21:40:00"
)
view._on_speed_finished(offline_res)
assert "0.0 Mbps" in view.card_dl.value_lbl.text()
assert not view.frame_grade.isHidden()
assert "Bağlantı Yok" in view.lbl_grade_title.text()
print("✓ Live server_info and offline UI handling verified.")

print("\n>>> ALL 10 SPEED TESTER & NETWORK VIEW TESTS PASSED SUCCESSFULLY! <<<")
os._exit(0)
