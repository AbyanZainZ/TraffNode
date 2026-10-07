import re
import time
import asyncio
import httpx
from typing import Optional, List, Dict, Any

_IP_REGEX = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
_GEOIP_CACHE: Dict[str, str] = {}

CHECK_TARGETS = [
    "http://api.ipify.org",
    "http://icanhazip.com",
    "http://checkip.amazonaws.com"
]

class ProxyNode:
    def __init__(self, raw_str: str, index: int = 0):
        self.id = index
        self.raw = raw_str.strip()
        self.protocol = "http"
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.user: Optional[str] = None
        self.password: Optional[str] = None

        self.node_type: str = "proxy"  # "proxy" or "surfshark"
        self.endpoint: Optional[str] = None
        self.pub_key: Optional[str] = None
        self.city: str = ""

        # Health info
        self.is_alive: Optional[bool] = None
        self.latency_ms: Optional[float] = None
        self.exit_ip: Optional[str] = None
        self.country: str = "Unknown"
        self.device_name: str = ""
        self.error: Optional[str] = None
        self.last_checked: Optional[float] = None

        # Worker status
        self.status: str = "IDLE"  # IDLE, STARTING, RUNNING, STOPPED, ERROR
        self.pid: Optional[int] = None
        self.wp_pid: Optional[int] = None  # Wireproxy PID for surfshark
        self.started_at: Optional[float] = None
        self.bytes_in: int = 0
        self.bytes_out: int = 0

        self._parse()

    def _parse(self):
        raw = self.raw
        if not raw or raw.startswith("#"):
            return
        if "#" in raw:
            raw = raw.split("#", 1)[0].strip()
        raw = re.sub(r'^(?:LIVE\s+|\d+[\.\)]\s+)', '', raw, flags=re.I).strip()
        if "|" in raw:
            raw = raw.replace("|", ":").strip()
        if not raw or raw.startswith("{"):
            return

        ptype = "http"
        m_proto = re.match(r'^(socks5|socks4|https?|http)(?::/+|[;:]{1,2})(.*)$', raw, re.I)
        if m_proto:
            ptype = m_proto.group(1).lower().replace("https", "http")
            raw = m_proto.group(2).strip()

        self.protocol = ptype

        if "@" in raw:
            auth_part, host_part = raw.rsplit("@", 1)
            u, p = auth_part.split(":", 1) if ":" in auth_part else (auth_part, "")
            if ":" in host_part:
                h, po = host_part.split(":", 1)
                po_clean = re.sub(r'[^\d]', '', po)
                if po_clean and (1 <= int(po_clean) <= 65535):
                    self.host = h.strip()
                    self.port = int(po_clean)
                    self.user = u.strip() or None
                    self.password = p.strip() or None
            return

        cleaned = raw.replace(";", ":").replace("\t", ":").strip()
        if " " in cleaned:
            cleaned = cleaned.split()[0].strip()
        parts = [p.strip() for p in cleaned.split(":") if p.strip()]

        if len(parts) == 4:
            if parts[1].isdigit() and 1 <= int(parts[1]) <= 65535:
                self.host = parts[0]
                self.port = int(parts[1])
                self.user = parts[2]
                self.password = parts[3]
            elif parts[3].isdigit() and 1 <= int(parts[3]) <= 65535:
                self.host = parts[2]
                self.port = int(parts[3])
                self.user = parts[0]
                self.password = parts[1]
        elif len(parts) == 2:
            if parts[1].isdigit() and 1 <= int(parts[1]) <= 65535:
                self.host = parts[0]
                self.port = int(parts[1])

    @property
    def is_valid(self) -> bool:
        return bool(self.host and self.port and 1 <= self.port <= 65535)

    def to_url(self) -> str:
        if not self.is_valid:
            return ""
        proto = "socks5" if "socks5" in self.protocol else ("socks4" if "socks4" in self.protocol else "http")
        if self.user and self.password:
            return f"{proto}://{self.user}:{self.password}@{self.host}:{self.port}"
        return f"{proto}://{self.host}:{self.port}"

    @property
    def proxy_url(self) -> str:
        return self.to_url()

    def update_device_name(self):
        c = self.country if self.country and self.country != "Unknown" else "Node"
        ip = self.exit_ip or self.host or "IP"
        self.device_name = f"{c} - {ip}"

    def to_dict(self) -> Dict[str, Any]:
        uptime_sec = round(time.time() - self.started_at) if (self.status == "RUNNING" and self.started_at) else 0
        return {
            "id": self.id,
            "node_type": self.node_type,
            "raw": self.raw,
            "protocol": self.protocol.upper(),
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "has_auth": bool(self.user and self.password),
            "is_alive": self.is_alive,
            "latency_ms": self.latency_ms,
            "exit_ip": self.exit_ip or self.host,
            "country": self.country,
            "city": self.city,
            "endpoint": self.endpoint,
            "device_name": self.device_name or f"Node-{self.id}",
            "status": self.status,
            "pid": self.pid,
            "uptime_seconds": uptime_sec,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "error": self.error,
            "last_checked": self.last_checked
        }


def parse_proxies_text(content: str) -> List[ProxyNode]:
    nodes = []
    seen = set()
    idx = 1
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = ProxyNode(line, index=idx)
        if p.is_valid:
            key = (p.protocol, p.host, p.port, p.user)
            if key not in seen:
                seen.add(key)
                nodes.append(p)
                idx += 1
    return nodes


async def fetch_geoip_country(ip: str) -> str:
    global _GEOIP_CACHE
    if not ip or not _IP_REGEX.match(ip):
        return "Unknown"
    if ip in _GEOIP_CACHE:
        return _GEOIP_CACHE[ip]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    code = data.get("country_code") or data.get("country") or "Unknown"
                    _GEOIP_CACHE[ip] = code
                    return code
    except Exception:
        pass
    return "Unknown"


async def check_single_proxy(proxy: ProxyNode, timeout: float = 5.0) -> ProxyNode:
    if not proxy.is_valid:
        proxy.is_alive = False
        proxy.error = "Format proxy tidak valid"
        return proxy

    proxy_url = proxy.to_url()
    t0 = time.time()
    last_err = "Gagal terkoneksi"

    for target_url in CHECK_TARGETS:
        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout, verify=False) as client:
                resp = await client.get(target_url, timeout=timeout)
                elapsed = (time.time() - t0) * 1000.0
                proxy.last_checked = time.time()

                if resp.status_code == 200:
                    text_ip = resp.text.strip()
                    if _IP_REGEX.match(text_ip):
                        proxy.is_alive = True
                        proxy.latency_ms = round(elapsed, 1)
                        proxy.exit_ip = text_ip
                        proxy.error = None
                        # Resolve GeoIP
                        proxy.country = await fetch_geoip_country(text_ip)
                        proxy.update_device_name()
                        return proxy
                    else:
                        last_err = "Respon bukan IP valid"
                else:
                    last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            proxy.last_checked = time.time()
            err_str = str(e).strip()
            if "timed out" in err_str.lower() or "timeout" in err_str.lower():
                last_err = f"Timeout ({timeout}s)"
            else:
                last_err = err_str[:35] or "Connection Failed"

    proxy.is_alive = False
    proxy.error = last_err
    proxy.update_device_name()
    return proxy


async def check_all_proxies(proxies: List[ProxyNode], max_concurrency: int = 20, timeout: float = 5.0) -> List[ProxyNode]:
    sem = asyncio.Semaphore(max_concurrency)

    async def _worker(p):
        async with sem:
            return await check_single_proxy(p, timeout=timeout)

    tasks = [_worker(p) for p in proxies]
    return await asyncio.gather(*tasks)


if __name__ == "__main__":
    print("Checker module loaded.")
