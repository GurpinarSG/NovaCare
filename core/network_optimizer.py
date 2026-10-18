"""
NovaCare System Suite - Network & DNS Optimizer Engine
Flushes DNS cache, resets Winsock/TCP stack, benchmarks DNS latencies in real-time,
and seamlessly configures the fastest DNS server on active network adapters.
"""
import socket
import time
import subprocess
import re
from dataclasses import dataclass
from typing import Optional
import psutil
import winreg

@dataclass
class DNSServerInfo:
    id: str
    name: str
    provider: str
    primary: str
    secondary: str
    description: str
    latency_ms: Optional[float] = None

DNS_CATALOG = [
    DNSServerInfo(
        id="cloudflare",
        name="Cloudflare DNS",
        provider="Cloudflare",
        primary="1.1.1.1",
        secondary="1.0.0.1",
        description="Dünyanın en hızlı ve gizlilik odaklı genel DNS sunucusu (1.1.1.1)."
    ),
    DNSServerInfo(
        id="google",
        name="Google Public DNS",
        provider="Google",
        primary="8.8.8.8",
        secondary="8.8.4.4",
        description="Küresel altyapıya sahip, son derece kararlı ve hızlı DNS sunucusu."
    ),
    DNSServerInfo(
        id="quad9",
        name="Quad9 (Zararlı Yazılım Engelleyici)",
        provider="Quad9",
        primary="9.9.9.9",
        secondary="149.112.112.112",
        description="Zararlı siteleri ve kimlik avı (phishing) adreslerini otomatik engeller."
    ),
    DNSServerInfo(
        id="adguard",
        name="AdGuard DNS",
        provider="AdGuard",
        primary="94.140.14.14",
        secondary="94.140.15.15",
        description="Ağ genelinde reklamları, izleyicileri ve pop-up'ları DNS düzeyinde engeller."
    ),
    DNSServerInfo(
        id="opendns",
        name="OpenDNS (Cisco)",
        provider="Cisco",
        primary="208.67.222.222",
        secondary="208.67.220.220",
        description="Cisco altyapısıyla güvenli, yüksek erişilebilirlikli DNS servisi."
    )
]

class NetworkOptimizer:
    def __init__(self):
        pass

    def get_network_interfaces(self) -> list[dict]:
        """Returns list of network interfaces and their connection status using ultra-fast psutil."""
        interfaces = []
        try:
            stats = psutil.net_if_stats()
            for name, stat in stats.items():
                low = name.lower()
                if "loopback" in low or "isatap" in low or "teredo" in low or "bluetooth" in low:
                    continue
                is_connected = bool(stat.isup)
                interfaces.append({
                    "name": name,
                    "state": "Connected" if is_connected else "Disconnected",
                    "connected": is_connected
                })
        except Exception:
            pass

        if not interfaces:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                out = subprocess.check_output(["netsh", "interface", "show", "interface"], creationflags=flags).decode("cp1254", errors="ignore")
                for line in out.splitlines():
                    if "Enabled" in line or "Etkin" in line:
                        parts = re.split(r"\s{2,}", line.strip())
                        if len(parts) >= 4:
                            state = parts[1]
                            name = parts[-1]
                            is_connected = ("Connected" in state or "Bağlandı" in state)
                            interfaces.append({
                                "name": name,
                                "state": state,
                                "connected": is_connected
                            })
            except Exception:
                pass
        return interfaces

    def get_active_adapter(self) -> Optional[str]:
        """Finds the currently active/connected network interface name."""
        interfaces = self.get_network_interfaces()
        # Prefer connected Ethernet or Wi-Fi
        for iface in interfaces:
            if iface["connected"]:
                return iface["name"]
        return interfaces[0]["name"] if interfaces else None

    def get_current_dns(self, adapter_name: str) -> dict:
        """
        Retrieves currently configured DNS servers for the specified adapter.
        Uses ultra-fast Windows Registry lookup (< 1 ms), avoiding UI thread blocking.
        Falls back to netsh subprocess only if registry keys cannot be resolved.
        """
        result = {"is_dhcp": True, "servers": []}
        
        # 1. Fast Registry Query
        try:
            net_path = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"
            target_guid = None
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, net_path) as net_key:
                count = winreg.QueryInfoKey(net_key)[0]
                for i in range(count):
                    guid = winreg.EnumKey(net_key, i)
                    try:
                        with winreg.OpenKey(net_key, rf"{guid}\Connection") as conn_key:
                            name, _ = winreg.QueryValueEx(conn_key, "Name")
                            if name.lower() == adapter_name.lower():
                                target_guid = guid
                                break
                    except Exception:
                        pass
            
            if target_guid:
                tcp_path = rf"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{target_guid}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, tcp_path) as tcp_key:
                    try:
                        ns, _ = winreg.QueryValueEx(tcp_key, "NameServer")
                    except Exception:
                        ns = ""
                    try:
                        dhcp_ns, _ = winreg.QueryValueEx(tcp_key, "DhcpNameServer")
                    except Exception:
                        dhcp_ns = ""

                    raw = ns.strip() if ns.strip() else dhcp_ns.strip()
                    servers = [s.strip() for s in re.split(r"[, ]+", raw) if s.strip()]
                    if servers:
                        result["servers"] = servers
                        result["is_dhcp"] = not bool(ns.strip())
                        return result
        except Exception:
            pass

        # 2. Fallback to netsh if registry query yielded no servers
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            cmd = ["netsh", "interface", "ipv4", "show", "dns", f"name={adapter_name}"]
            out = subprocess.check_output(cmd, creationflags=flags).decode("cp1254", errors="ignore")
            ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out)
            result["servers"] = ips
            if "DHCP" in out:
                result["is_dhcp"] = True
            elif "Statically" in out or "Statik" in out:
                result["is_dhcp"] = False
        except Exception:
            pass
        return result

    def test_dns_latency(self, server_ip: str, timeout: float = 1.0, repeats: int = 2) -> Optional[float]:
        """
        Measures round-trip DNS resolution latency (ms) for a given IP using raw DNS query.
        """
        # DNS query packet for google.com (A record, class IN)
        query = b"\xaa\xbb\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06google\x03com\x00\x00\x01\x00\x01"
        latencies = []

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        try:
            for _ in range(repeats):
                t0 = time.perf_counter()
                try:
                    sock.sendto(query, (server_ip, 53))
                    data, _ = sock.recvfrom(512)
                    lat = (time.perf_counter() - t0) * 1000.0
                    latencies.append(lat)
                except Exception:
                    pass
        finally:
            sock.close()

        return min(latencies) if latencies else None

    def benchmark_all_dns(self) -> list[DNSServerInfo]:
        """Tests latency for all catalog DNS servers and returns them sorted by fastest ping."""
        servers = []
        for item in DNS_CATALOG:
            # Test primary IP
            lat = self.test_dns_latency(item.primary)
            servers.append(DNSServerInfo(
                id=item.id,
                name=item.name,
                provider=item.provider,
                primary=item.primary,
                secondary=item.secondary,
                description=item.description,
                latency_ms=round(lat, 1) if lat is not None else None
            ))

        # Sort: valid latencies first (ascending), then timeouts
        servers.sort(key=lambda s: s.latency_ms if s.latency_ms is not None else 999999)
        return servers

    def set_dns(self, adapter_name: str, primary: str, secondary: Optional[str] = None) -> tuple[bool, str]:
        """Sets static DNS servers on the designated adapter."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            # 1. Set Primary
            cmd1 = f'netsh interface ipv4 set dns name="{adapter_name}" static {primary} primary'
            p1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True, creationflags=flags)
            if p1.returncode != 0:
                return False, f"Birincil DNS ayarlanamadı: {p1.stderr}"

            # 2. Add Secondary if provided
            if secondary:
                cmd2 = f'netsh interface ipv4 add dns name="{adapter_name}" {secondary} index=2'
                subprocess.run(cmd2, shell=True, capture_output=True, creationflags=flags)

            # Flush DNS cache after change
            self.flush_dns()
            return True, f"{adapter_name} için DNS başarıyla ayarlandı ({primary}, {secondary or ''})."
        except Exception as e:
            return False, str(e)

    def reset_dns_to_dhcp(self, adapter_name: str) -> tuple[bool, str]:
        """Resets adapter DNS configuration back to automatic (DHCP)."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            cmd = f'netsh interface ipv4 set dns name="{adapter_name}" dhcp'
            p = subprocess.run(cmd, shell=True, capture_output=True, text=True, creationflags=flags)
            if p.returncode == 0:
                self.flush_dns()
                return True, f"{adapter_name} DNS ayarları otomatik (DHCP) olarak sıfırlandı."
            return False, p.stderr or "İşlem başarısız oldu."
        except Exception as e:
            return False, str(e)

    def flush_dns(self) -> tuple[bool, str]:
        """Flushes the Windows DNS Resolver Cache (ipconfig /flushdns)."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            p = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, creationflags=flags)
            if p.returncode == 0:
                return True, "DNS çözümleyici önbelleği başarıyla temizlendi."
            return False, "DNS önbelleği temizlenirken hata oluştu."
        except Exception as e:
            return False, str(e)

    def reset_network_stack(self) -> tuple[bool, str]:
        """
        Executes a complete Winsock and TCP/IP stack reset.
        Fixes corrupted sockets, network slowdowns, and dropped connections.
        """
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(["netsh", "winsock", "reset"], capture_output=True, timeout=10, creationflags=flags)
            subprocess.run(["netsh", "int", "ip", "reset"], capture_output=True, timeout=10, creationflags=flags)
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5, creationflags=flags)
            subprocess.run(["ipconfig", "/renew"], capture_output=True, timeout=10, creationflags=flags)
            return True, "Winsock ve TCP/IP ağ yığını sıfırlandı. Ağ bağdaştırıcısı yenilendi."
        except Exception as e:
            return False, str(e)

