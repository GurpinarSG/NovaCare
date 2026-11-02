"""
NovaCare System Suite - Real-Time Hardware & Temperature Monitor Engine
Monitors CPU load, CPU temperature (WMI/ACPI), GPU temperature & load (via NVML or WMI fallback),
RAM metrics, Disk I/O throughput, top consumer process, and system uptime.
"""
import time
import threading
import subprocess
import psutil
from typing import Optional
from core.utils import log_debug, get_system32_path

def _fmt_speed(bps: float) -> str:
    """Fast network and disk speed formatter."""
    if bps >= 1048576.0:
        return f"{bps / 1048576.0:.1f} MB/s"
    elif bps >= 1024.0:
        return f"{bps / 1024.0:.0f} KB/s"
    return f"{int(bps)} B/s"

def _fmt_uptime(seconds: int) -> str:
    """Formats uptime seconds into human-readable Turkish representation."""
    if seconds <= 0:
        return "Yeni başlatıldı"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0:
        return f"{days}g {hours}s {mins}d"
    elif hours > 0:
        return f"{hours} sa {mins} dk"
    return f"{mins} dk"

class HardwareMonitor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HardwareMonitor, cls).__new__(cls)
                cls._instance._init_monitor()
            return cls._instance

    def _init_monitor(self):
        self.has_nvml = False
        self.nvml_handle = None
        self._pynvml = None
        self.gpu_name = "Harici GPU Yok"
        self.gpu_vram_total_mb = 0
        self.cpu_temp: Optional[float] = None
        self.last_cpu_temp_update = 0
        self._running = True
        self._net_lock = threading.Lock()
        self._disk_lock = threading.Lock()
        self._proc_lock = threading.Lock()
        self._cpu_lock = threading.Lock()
        self._cached_cpu_percent = 0.0
        self._last_cpu_sample_time = 0.0
        try:
            self._cached_cpu_percent = psutil.cpu_percent(interval=None)
        except Exception:
            pass

        # Top consumer process cache
        self.top_consumer_name = "-"
        self.top_consumer_str = "Hesaplanıyor..."
        self.top_consumer_cpu = 0.0

        # Non-blocking async hardware probes to keep UI completely free from stutters
        threading.Thread(target=self._init_nvml_worker, daemon=True).start()
        self._cpu_thread = threading.Thread(target=self._poll_cpu_worker, daemon=True)
        self._cpu_thread.start()
        self._temp_thread = threading.Thread(target=self._poll_cpu_temp_worker, daemon=True)
        self._temp_thread.start()
        self._top_proc_thread = threading.Thread(target=self._poll_top_process_worker, daemon=True)
        self._top_proc_thread.start()


    def _init_nvml_worker(self):
        """Asynchronously initialize NVML for NVIDIA GPUs; fallback to WMI if not available."""
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                raw_name = pynvml.nvmlDeviceGetName(self.nvml_handle)
                self.gpu_name = raw_name if isinstance(raw_name, str) else raw_name.decode("utf-8", errors="ignore")
                self._pynvml = pynvml
                self.has_nvml = True
                try:
                    mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
                    self.gpu_vram_total_mb = int(mem_info.total / (1024 ** 2))
                except Exception:
                    pass
                return
        except Exception as e:
            log_debug(f"HardwareMonitor: NVML init info: {e}")
            self.has_nvml = False

        # Fallback: Query Windows Video Controllers via PowerShell/WMI (AMD/Intel/generic)
        try:
            cmd = [
                get_system32_path("powershell"), "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -Property Name, AdapterRAM | ConvertTo-Json"
            ]
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=6, creationflags=flags)
            if p.returncode == 0 and p.stdout.strip():
                import json
                data = json.loads(p.stdout.strip())
                items = data if isinstance(data, list) else [data]
                # Prioritize dedicated GPUs (NVIDIA / AMD Radeon / Intel Arc)
                selected = None
                for it in items:
                    name = it.get("Name", "")
                    low = name.lower()
                    if "nvidia" in low or "geforce" in low or "radeon" in low or "rtx" in low or "gtx" in low or "arc" in low:
                        selected = it
                        break
                if not selected and items:
                    selected = items[0]
                if selected:
                    self.gpu_name = selected.get("Name", "Ekran Kartı")
                    ram_bytes = selected.get("AdapterRAM") or 0
                    norm_ram = self._normalize_adapter_ram(ram_bytes)
                    if norm_ram > 0:
                        self.gpu_vram_total_mb = int(norm_ram / (1024 ** 2))
                    self.has_gpu_fallback = True
        except Exception as e:
            log_debug(f"HardwareMonitor: WMI GPU detection error: {e}")

    @staticmethod
    def _normalize_adapter_ram(ram_bytes: int | float) -> int:
        """Converts signed 32-bit WMI AdapterRAM overflow to unsigned bytes."""
        if not ram_bytes or not isinstance(ram_bytes, (int, float)):
            return 0
        val = int(ram_bytes)
        if val < 0:
            val += (1 << 32)
        return val

    @staticmethod
    def _calc_acpi_backoff_sleep(consecutive_failures: int) -> float:
        """Calculates exponential backoff delay in seconds for ACPI thermal zone polling."""
        if consecutive_failures <= 0:
            return 5.0
        elif consecutive_failures == 1:
            return 15.0
        elif consecutive_failures < 5:
            return 60.0
        elif consecutive_failures < 8:
            return 300.0  # 5 min
        elif consecutive_failures < 10:
            return 900.0  # 15 min
        return 1800.0  # 30 min max backoff

    def stop(self):
        """Stops the background hardware polling workers."""
        self._running = False

    def set_throttled(self, throttled: bool):
        """Throttles or unthrottles background polling based on window and widget visibility."""
        self._is_throttled = throttled

    def _poll_cpu_worker(self):
        """Dedicated background thread to sample CPU percent smoothly without collisions."""
        while self._running:
            try:
                interval = 3.0 if getattr(self, '_is_throttled', False) else 1.0
                val = psutil.cpu_percent(interval=interval)
                with self._cpu_lock:
                    self._cached_cpu_percent = float(val)
                    self._last_cpu_sample_time = time.time()
            except Exception:
                time.sleep(1.0)

    def _poll_cpu_temp_worker(self):
        """Background daemon thread to query CPU temperature without stalling the UI thread."""
        consecutive_failures = 0
        while self._running:
            try:
                cmd = [
                    get_system32_path("powershell"), "-NoProfile", "-Command",
                    "$t = (Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue).CurrentTemperature; "
                    "if (-not $t) { $t = (Get-CimInstance -ClassName Win32_PerfFormattedData_Counters_ThermalZoneInformation -ErrorAction SilentlyContinue).Temperature }; "
                    "if ($t) { $t }"
                ]
                kwargs = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace", "timeout": 3}
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

                p = subprocess.run(cmd, **kwargs)
                if p.returncode == 0 and p.stdout.strip():
                    raw_val = p.stdout.strip().split()[0]
                    num = float(raw_val)
                    if num > 1000:
                        celsius = (num / 10.0) - 273.15
                    elif 200 < num < 400:
                        celsius = num - 273.15
                    else:
                        celsius = num
                    if 0 < celsius < 125:
                        self.cpu_temp = round(celsius, 1)
                        self.last_cpu_temp_update = time.time()
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                else:
                    consecutive_failures += 1
            except Exception:
                consecutive_failures += 1

            # Smart polling interval: on success, sleep 30.0s (or 60.0s if throttled) to eliminate powershell CPU/RAM churn.
            # On failure, apply exponential backoff.
            if consecutive_failures == 0:
                sleep_target = 60.0 if getattr(self, '_is_throttled', False) else 30.0
            else:
                sleep_target = self._calc_acpi_backoff_sleep(consecutive_failures)
            steps = int(sleep_target)
            for _ in range(steps):
                if not self._running:
                    break
                time.sleep(1.0)


    def _poll_top_process_worker(self):
        """Background daemon thread to detect the highest CPU/RAM consuming application smoothly."""
        cpu_count = psutil.cpu_count() or 1
        # Warm-up initial psutil CPU sampling
        try:
            for p in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
                pass
        except Exception:
            pass

        first_loop = True
        while self._running:
            try:
                # Fast 0.25s sample on initial startup so UI isn't blank, then throttled/standard thereafter
                if first_loop:
                    wait_sec = 0.25
                    first_loop = False
                elif getattr(self, '_is_throttled', False):
                    wait_sec = 10.0
                else:
                    wait_sec = 2.0
                time.sleep(wait_sec)
                if not self._running:
                    break

                highest_cpu_proc = None
                highest_cpu_val = 0.0
                highest_mem_proc = None
                highest_mem_val = 0.0

                for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
                    try:
                        pname = proc.info.get('name') or ""
                        if not pname or "idle" in pname.lower() or pname.lower() == "system":
                            continue

                        cpu_val = proc.info.get('cpu_percent') or 0.0
                        if cpu_val > highest_cpu_val:
                            highest_cpu_val = cpu_val
                            highest_cpu_proc = pname

                        mem_info = proc.info.get('memory_info')
                        if mem_info:
                            mem_mb = mem_info.rss / (1024 ** 2)
                            if mem_mb > highest_mem_val:
                                highest_mem_val = mem_mb
                                highest_mem_proc = pname
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

                # Format clean presentation
                # Normalize CPU percentage across cores (matching Windows Task Manager)
                norm_cpu = min(100.0, round(highest_cpu_val / cpu_count, 1))

                with self._proc_lock:
                    if norm_cpu >= 1.5 and highest_cpu_proc:
                        clean_name = highest_cpu_proc.replace(".exe", "").capitalize()
                        self.top_consumer_name = clean_name
                        self.top_consumer_cpu = norm_cpu
                        self.top_consumer_str = f"{clean_name}: %{norm_cpu:.0f} CPU"
                    elif highest_mem_proc:
                        clean_name = highest_mem_proc.replace(".exe", "").capitalize()
                        self.top_consumer_name = clean_name
                        self.top_consumer_cpu = 0.0
                        if highest_mem_val >= 1024.0:
                            self.top_consumer_str = f"{clean_name}: {highest_mem_val / 1024.0:.1f} GB RAM"
                        else:
                            self.top_consumer_str = f"{clean_name}: {int(highest_mem_val)} MB RAM"
                    else:
                        self.top_consumer_str = "Sistem Normal"
            except Exception as e:
                log_debug(f"HardwareMonitor top proc worker error: {e}")
                time.sleep(3.0)

    def get_cpu_percent(self) -> float:
        """Returns smooth, cached CPU percentage free from concurrent sampling collisions."""
        with self._cpu_lock:
            if self._last_cpu_sample_time == 0.0:
                try:
                    val = psutil.cpu_percent(interval=0.1)
                    self._cached_cpu_percent = float(val)
                    self._last_cpu_sample_time = time.time()
                except Exception:
                    pass
            return self._cached_cpu_percent

    def get_hardware_stats(self) -> dict:
        """
        Gathers real-time hardware telemetry in < 3ms without blocking.
        """
        # 1. CPU stats
        cpu_percent = self.get_cpu_percent()
        cpu_freq = psutil.cpu_freq()
        cpu_freq_ghz = round(cpu_freq.current / 1000.0, 2) if cpu_freq else 0.0

        # 2. RAM stats
        mem = psutil.virtual_memory()
        ram_percent = mem.percent
        ram_used_gb = round(mem.used / (1024 ** 3), 2)
        ram_total_gb = round(mem.total / (1024 ** 3), 2)

        # 3. GPU stats (NVIDIA via NVML or Fallback)
        gpu_temp = None
        gpu_load = 0
        gpu_mem_used_mb = 0
        gpu_mem_total_mb = self.gpu_vram_total_mb

        if self.has_nvml and self.nvml_handle and self._pynvml:
            try:
                gpu_temp = self._pynvml.nvmlDeviceGetTemperature(self.nvml_handle, self._pynvml.NVML_TEMPERATURE_GPU)
                rates = self._pynvml.nvmlDeviceGetUtilizationRates(self.nvml_handle)
                gpu_load = rates.gpu
                mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
                gpu_mem_used_mb = int(mem_info.used / (1024 ** 2))
                gpu_mem_total_mb = int(mem_info.total / (1024 ** 2))
            except Exception:
                pass

        # 4. Real-time network speed (thread-safe telemetry calculation)
        with self._net_lock:
            now = time.time()
            net = psutil.net_io_counters()
            down_bps = getattr(self, '_last_down_bps', 0.0)
            up_bps = getattr(self, '_last_up_bps', 0.0)
            if net is not None:
                if hasattr(self, '_last_net_bytes') and hasattr(self, '_last_net_time'):
                    dt = now - self._last_net_time
                    if dt >= 0.2:
                        down_bps = max(0.0, (net.bytes_recv - self._last_net_bytes[0]) / dt)
                        up_bps = max(0.0, (net.bytes_sent - self._last_net_bytes[1]) / dt)
                        self._last_down_bps = down_bps
                        self._last_up_bps = up_bps
                        self._last_net_bytes = (net.bytes_recv, net.bytes_sent)
                        self._last_net_time = now
                else:
                    self._last_net_bytes = (net.bytes_recv, net.bytes_sent)
                    self._last_net_time = now

        # 5. Real-time disk I/O throughput (thread-safe telemetry calculation)
        with self._disk_lock:
            disk_read_bps = getattr(self, '_last_disk_read_bps', 0.0)
            disk_write_bps = getattr(self, '_last_disk_write_bps', 0.0)
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io is not None:
                    if hasattr(self, '_last_disk_bytes') and hasattr(self, '_last_disk_time'):
                        dt_disk = now - self._last_disk_time
                        if dt_disk >= 0.2:
                            disk_read_bps = max(0.0, (disk_io.read_bytes - self._last_disk_bytes[0]) / dt_disk)
                            disk_write_bps = max(0.0, (disk_io.write_bytes - self._last_disk_bytes[1]) / dt_disk)
                            self._last_disk_read_bps = disk_read_bps
                            self._last_disk_write_bps = disk_write_bps
                            self._last_disk_bytes = (disk_io.read_bytes, disk_io.write_bytes)
                            self._last_disk_time = now
                    else:
                        self._last_disk_bytes = (disk_io.read_bytes, disk_io.write_bytes)
                        self._last_disk_time = now
            except Exception:
                pass

        # 6. Top consumer process
        with self._proc_lock:
            top_name = self.top_consumer_name
            top_str = self.top_consumer_str

        # 7. System Uptime
        try:
            boot_time = psutil.boot_time()
            uptime_sec = max(0, int(now - boot_time))
            uptime_str = _fmt_uptime(uptime_sec)
        except Exception:
            uptime_sec = 0
            uptime_str = "Bilinmiyor"

        return {
            "cpu_percent": cpu_percent,
            "cpu_freq_ghz": cpu_freq_ghz,
            "cpu_temp": self.cpu_temp,
            "ram_percent": ram_percent,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "gpu_name": self.gpu_name,
            "gpu_temp": gpu_temp,
            "gpu_load": gpu_load,
            "gpu_mem_used_mb": gpu_mem_used_mb,
            "gpu_mem_total_mb": gpu_mem_total_mb,
            "has_gpu": self.has_nvml or getattr(self, "has_gpu_fallback", False),
            "net_down_bps": down_bps,
            "net_up_bps": up_bps,
            "net_down_str": _fmt_speed(down_bps),
            "net_up_str": _fmt_speed(up_bps),
            "disk_read_bps": disk_read_bps,
            "disk_write_bps": disk_write_bps,
            "disk_read_str": _fmt_speed(disk_read_bps),
            "disk_write_str": _fmt_speed(disk_write_bps),
            "top_consumer_name": top_name,
            "top_consumer_str": top_str,
            "uptime_seconds": uptime_sec,
            "uptime_str": uptime_str
        }
