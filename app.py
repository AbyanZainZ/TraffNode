import os
import json
import time
import asyncio
import socket
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

import psutil
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from checker import ProxyNode, parse_proxies_text, check_all_proxies
from supervisor import NodeSupervisor
from bandwidth import BandwidthTracker, format_bytes

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
PROXIES_PATH = BASE_DIR / "proxies.txt"
STATIC_DIR = BASE_DIR / "static"

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "dashboard_port": 8888,
    "traff_token": "",
    "check_timeout": 5.0,
    "max_instances": 500,
    "auto_heal_interval_seconds": 30,
    "auto_start_on_boot": False
}

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def load_proxies_file() -> str:
    if PROXIES_PATH.exists():
        with open(PROXIES_PATH, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

def save_proxies_file(content: str):
    with open(PROXIES_PATH, "w", encoding="utf-8") as f:
        f.write(content)

_cached_public_ip = None

def get_server_ip() -> str:
    global _cached_public_ip
    if _cached_public_ip:
        return _cached_public_ip

    import urllib.request
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
        "https://checkip.amazonaws.com"
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                detected = resp.read().decode("utf-8").strip()
                if detected and not detected.startswith(("10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "192.168.", "127.")):
                    _cached_public_ip = detected
                    return detected
        except Exception:
            pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =============================================================================
# APP STATE
# =============================================================================
config = load_config()
supervisor = NodeSupervisor()
bandwidth_tracker = BandwidthTracker()

nodes: List[ProxyNode] = []
is_checking = False

async def run_health_check_task():
    global is_checking, nodes
    if is_checking or not nodes:
        return
    is_checking = True
    try:
        nodes = await check_all_proxies(nodes, max_concurrency=20, timeout=config.get("check_timeout", 5.0))
    finally:
        is_checking = False

async def auto_supervisor_loop():
    while True:
        try:
            await asyncio.sleep(config.get("auto_heal_interval_seconds", 30))
            token = config.get("traff_token", "")
            if token and nodes:
                supervisor.auto_heal_check(nodes, token)
                # Update bandwidth per node
                for n in nodes:
                    if n.pid:
                        bandwidth_tracker.update_proc_traffic(n.pid, n)
        except Exception:
            pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    global nodes
    raw_text = load_proxies_file()
    nodes = parse_proxies_text(raw_text)

    # Start auto-heal supervisor loop
    asyncio.create_task(auto_supervisor_loop())

    if nodes:
        asyncio.create_task(run_health_check_task())

    yield

    supervisor.stop_all(nodes)


app = FastAPI(title="TraffNode — VPS Multi-Proxy Passive Income Engine", lifespan=lifespan)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# =============================================================================
# REQUEST MODELS
# =============================================================================
class ProxiesUpdateRequest(BaseModel):
    raw_text: str

class ConfigUpdateRequest(BaseModel):
    traff_token: str
    dashboard_port: Optional[int] = 8888
    max_instances: Optional[int] = 500


# =============================================================================
# ROUTES
# =============================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return "<h1>TraffNode is Running</h1><p>static/index.html not found yet.</p>"

@app.get("/api/status")
async def get_status():
    mem = psutil.virtual_memory()
    cpu_pct = psutil.cpu_percent(interval=None)
    bw = bandwidth_tracker.get_system_bandwidth()

    running_count = sum(1 for n in nodes if n.status == "RUNNING")
    alive_count = sum(1 for n in nodes if n.is_alive is True)
    dead_count = sum(1 for n in nodes if n.is_alive is False)

    total_in = sum(n.bytes_in for n in nodes)
    total_out = sum(n.bytes_out for n in nodes)

    return {
        "status": "online",
        "server_ip": get_server_ip(),
        "system": {
            "cpu_percent": cpu_pct,
            "ram_used_mb": round(mem.used / (1024 * 1024)),
            "ram_total_mb": round(mem.total / (1024 * 1024)),
            "ram_percent": mem.percent
        },
        "config": {
            "traff_token": config.get("traff_token", ""),
            "dashboard_port": config.get("dashboard_port", 8888),
            "max_instances": config.get("max_instances", 500)
        },
        "metrics": {
            "total_nodes": len(nodes),
            "running_nodes": running_count,
            "alive_nodes": alive_count,
            "dead_nodes": dead_count,
            "is_checking": is_checking,
            "bandwidth": {
                "total_bytes_in": total_in or bw["total_recv_bytes"],
                "total_bytes_out": total_out or bw["total_sent_bytes"],
                "speed_down_bps": bw["speed_down_bps"],
                "speed_up_bps": bw["speed_up_bps"],
                "formatted_in": format_bytes(total_in or bw["total_recv_bytes"]),
                "formatted_out": format_bytes(total_out or bw["total_sent_bytes"])
            }
        },
        "nodes": [n.to_dict() for n in nodes]
    }

@app.get("/api/proxies/raw", response_class=PlainTextResponse)
async def get_raw_proxies():
    return load_proxies_file()

@app.post("/api/proxies")
async def update_proxies(payload: ProxiesUpdateRequest, bg_tasks: BackgroundTasks):
    global nodes
    save_proxies_file(payload.raw_text)
    # Stop existing if any
    supervisor.stop_all(nodes)
    nodes = parse_proxies_text(payload.raw_text)
    bg_tasks.add_task(run_health_check_task)
    return {
        "success": True,
        "count": len(nodes),
        "message": f"Berhasil memuat {len(nodes)} proxy node!"
    }

@app.post("/api/config")
async def update_config(payload: ConfigUpdateRequest):
    global config
    config["traff_token"] = payload.traff_token.strip()
    if payload.dashboard_port:
        config["dashboard_port"] = max(1024, min(65000, payload.dashboard_port))
    if payload.max_instances:
        config["max_instances"] = max(1, min(2500, payload.max_instances))
    save_config(config)
    return {"success": True, "config": config, "message": "Konfigurasi token disimpan!"}

@app.post("/api/check")
async def trigger_check(bg_tasks: BackgroundTasks):
    global is_checking
    if is_checking:
        return {"success": False, "message": "Pengecekan proxy sedang berlangsung."}
    bg_tasks.add_task(run_health_check_task)
    return {"success": True, "message": "Pengecekan kesehatan semua node dimulai!"}

@app.post("/api/start-all")
async def start_all_nodes():
    token = config.get("traff_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="Token TraffMonetizer belum diisi di konfigurasi!")
    if not nodes:
        raise HTTPException(status_code=400, detail="Belum ada proxy yang dimasukkan!")

    started = supervisor.start_all(nodes, token)
    return {
        "success": True,
        "started": started,
        "message": f"🚀 Berhasil menjalankan {started} worker node TraffMonetizer!"
    }

@app.post("/api/stop-all")
async def stop_all_nodes():
    supervisor.stop_all(nodes)
    return {"success": True, "message": "Semua worker node telah dihentikan."}

@app.post("/api/restart-all")
async def restart_all_nodes():
    token = config.get("traff_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="Token TraffMonetizer belum diisi!")
    supervisor.stop_all(nodes)
    await asyncio.sleep(1.0)
    started = supervisor.start_all(nodes, token)
    return {"success": True, "started": started, "message": f"Semua {started} node berhasil di-restart!"}

@app.post("/api/node/{node_id}/start")
async def start_single_node(node_id: int):
    token = config.get("traff_token", "")
    node = next((n for n in nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    ok = supervisor.start_node(node, token)
    if not ok:
        raise HTTPException(status_code=500, detail=node.error or "Gagal menjalankan node")
    return {"success": True, "node": node.to_dict()}

@app.post("/api/node/{node_id}/stop")
async def stop_single_node(node_id: int):
    node = next((n for n in nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    supervisor.stop_node(node)
    return {"success": True, "node": node.to_dict()}

@app.get("/api/node/{node_id}/logs", response_class=PlainTextResponse)
async def get_node_logs(node_id: int):
    node = next((n for n in nodes if n.id == node_id), None)
    if not node:
        return "Node tidak ditemukan."
    return supervisor.get_node_logs(node)


if __name__ == "__main__":
    import uvicorn
    cfg = load_config()
    port = cfg.get("dashboard_port", 8888)
    print(f"⚡ TraffNode Dashboard starting on http://{cfg.get('host', '0.0.0.0')}:{port}")
    uvicorn.run("app:app", host=cfg.get("host", "0.0.0.0"), port=port, reload=False)
