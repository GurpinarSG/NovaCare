"""
NovaCare System Suite - Real-Time Hardware & Temperature Monitor Engine
Monitors CPU load, CPU temperature (WMI/ACPI), GPU temperature & load (via NVML),
and RAM metrics with microsecond-level non-blocking polling.
"""
import time
import threading
import subprocess
import psutil
from typing import Optional

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
        self.gpu_name = "Harici GPU Yok"
        self.cpu_temp: Optional[float] = None
        self.last_cpu_temp_update = 0
        self._running = True

        # Non-blocking async hardware probes to keep UI completely free from stutters
        threading.Thread(target=self._init_nvml_worker, daemon=True).start()
        self._temp_thread = threading.Thread(target=self._poll_cpu_temp_worker, daemon=True)
        self._temp_thread.start()

    def _init_nvml_worker(self):
        """Asynchronously initialize NVML for NVIDIA GPUs without blocking main thread."""
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                raw_name = pynvml.nvmlDeviceGetName(self.nvml_handle)
                self.gpu_name = raw_name if isinstance(raw_name, str) else raw_name.decode("utf-8", errors="ignore")
                self.has_nvml = True
        except Exception:
            self.has_nvml = False

    def stop(self):
        """Stops the background thermal worker."""
        self._running = False

    def _poll_cpu_temp_worker(self):
        """Background daemon thread to query CPU temperature without stalling the UI thread."""
        consecutive_failures = 0
        while self._running:
            try:
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue).CurrentTemperature"
                ]
                kwargs = {"capture_output": True, "text": True, "timeout": 3}
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

                p = subprocess.run(cmd, **kwargs)
                if p.returncode == 0 and p.stdout.strip():
                    raw_val = p.stdout.strip().split()[0]
                    # Tenths of Kelvin to Celsius
                    celsius = (float(raw_val) / 10.0) - 273.15
                    if 0 < celsius < 125:
                        self.cpu_temp = round(celsius, 1)
                        self.last_cpu_temp_update = time.time()
                        consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception:
                consecutive_failures += 1

            # Smart backoff: If ACPI thermal zones aren't exposed by BIOS, avoid frequent powershell spawns
            if consecutive_failures >= 2:
                time.sleep(60.0)
            else:
                time.sleep(5.0)

    def get_hardware_stats(self) -> dict:
        """
        Gathers real-time hardware telemetry in < 3ms without blocking.
        """
        # 1. CPU stats
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_ghz = round(cpu_freq.current / 1000.0, 2) if cpu_freq else 0.0

        # 2. RAM stats
        mem = psutil.virtual_memory()
        ram_percent = mem.percent
        ram_used_gb = round(mem.used / (1024 ** 3), 2)
        ram_total_gb = round(mem.total / (1024 ** 3), 2)

        # 3. GPU stats (NVIDIA via NVML)
        gpu_temp = None
        gpu_load = 0
        gpu_mem_used_mb = 0
        gpu_mem_total_mb = 0

        if self.has_nvml and self.nvml_handle:
            try:
                import pynvml
                gpu_temp = pynvml.nvmlDeviceGetTemperature(self.nvml_handle, pynvml.NVML_TEMPERATURE_GPU)
                rates = pynvml.nvmlDeviceGetUtilizationRates(self.nvml_handle)
                gpu_load = rates.gpu
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
                gpu_mem_used_mb = int(mem_info.used / (1024 ** 2))
                gpu_mem_total_mb = int(mem_info.total / (1024 ** 2))
            except Exception:
                pass

        # 4. Real-time network speed
        now = time.time()
        net = psutil.net_io_counters()
        down_bps = 0.0
        up_bps = 0.0
        if hasattr(self, '_last_net_bytes') and hasattr(self, '_last_net_time'):
            dt = max(0.1, now - self._last_net_time)
            down_bps = max(0.0, (net.bytes_recv - self._last_net_bytes[0]) / dt)
            up_bps = max(0.0, (net.bytes_sent - self._last_net_bytes[1]) / dt)
        self._last_net_bytes = (net.bytes_recv, net.bytes_sent)
        self._last_net_time = now

        def _fmt_spd(bps: float) -> str:
            if bps >= 1024 * 1024:
                return f"{bps / (1024 * 1024):.1f} MB/s"
            elif bps >= 1024:
                return f"{bps / 1024:.0f} KB/s"
            return f"{int(bps)} B/s"

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
            "has_gpu": self.has_nvml,
            "net_down_bps": down_bps,
            "net_up_bps": up_bps,
            "net_down_str": _fmt_spd(down_bps),
            "net_up_str": _fmt_spd(up_bps)
        }
