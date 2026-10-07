import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from checker import ProxyNode

TM_LINUX_PATH = "/usr/local/bin/cli"
TM_LINUX_SYMLINK = "/usr/local/bin/traffmonetizer"
RUN_DIR = Path("/tmp/traffnode") if os.name != "nt" else Path(os.environ.get("TEMP", "C:/Temp")) / "traffnode"

class NodeSupervisor:
    def __init__(self):
        self.procs: Dict[int, subprocess.Popen] = {}
        self.log_paths: Dict[int, Path] = {}
        RUN_DIR.mkdir(parents=True, exist_ok=True)

    def _get_tm_binary(self) -> Optional[str]:
        if os.name == "nt":
            # Windows mock / exe if available
            return "simulated"
        if os.path.exists(TM_LINUX_PATH):
            return TM_LINUX_PATH
        if os.path.exists(TM_LINUX_SYMLINK):
            return TM_LINUX_SYMLINK
        return None

    def start_node(self, node: ProxyNode, token: str) -> bool:
        if not token or not token.strip():
            node.error = "Token TraffMonetizer kosong"
            node.status = "ERROR"
            return False

        if not node.is_valid:
            node.error = "Format proxy tidak valid"
            node.status = "ERROR"
            return False

        self.stop_node(node)

        node_home = RUN_DIR / f"node_{node.id}"
        node_home.mkdir(parents=True, exist_ok=True)

        conf_path = node_home / "proxychains.conf"
        log_path = node_home / "worker.log"
        self.log_paths[node.id] = log_path

        # Generate per-node proxychains config
        pc_type = "socks5" if "socks5" in node.protocol.lower() else ("socks4" if "socks4" in node.protocol.lower() else "http")
        auth_part = f" {node.user} {node.password}" if (node.user and node.password) else ""

        with open(conf_path, "w", encoding="utf-8") as f:
            f.write(
                "strict_chain\n"
                "proxy_dns\n"
                "remote_dns_subnet 224\n"
                "tcp_read_time_out 15000\n"
                "tcp_connect_time_out 8000\n\n"
                "[ProxyList]\n"
                f"{pc_type} {node.host} {node.port}{auth_part}\n"
            )

        node.update_device_name()
        dev_name = node.device_name

        env = os.environ.copy()
        env["HOME"] = str(node_home)
        env["USERPROFILE"] = str(node_home)

        tm_bin = self._get_tm_binary()

        try:
            log_f = open(log_path, "w", encoding="utf-8", errors="ignore")
            if os.name != "nt" and tm_bin:
                # Real Linux Execution via proxychains4
                cmd = [
                    "proxychains4", "-f", str(conf_path), "-q",
                    tm_bin, "start", "accept",
                    "--token", token.strip(),
                    "--device-name", dev_name
                ]
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(node_home),
                    env=env,
                    stdout=log_f,
                    stderr=subprocess.STDOUT
                )
            else:
                # Development / Simulation mode on Windows
                log_f.write(f"[TraffNode Simulator] Starting node {node.id} via {node.protocol}://{node.host}:{node.port}\n")
                log_f.write(f"[TraffNode Simulator] Device Name: {dev_name}\n")
                log_f.write("[TraffNode Simulator] Worker online & sharing bandwidth simulated.\n")
                log_f.flush()
                # Run lightweight sleep process on Windows
                proc = subprocess.Popen(["cmd.exe", "/c", "ping -n 99999 127.0.0.1 > nul"], stdout=log_f, stderr=subprocess.STDOUT)

            log_f.close()
            self.procs[node.id] = proc
            node.pid = proc.pid
            node.status = "RUNNING"
            node.started_at = time.time()
            node.error = None
            return True
        except Exception as e:
            node.status = "ERROR"
            node.error = str(e)[:40]
            return False

    def stop_node(self, node: ProxyNode):
        proc = self.procs.pop(node.id, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        node.pid = None
        node.status = "STOPPED"

    def restart_node(self, node: ProxyNode, token: str) -> bool:
        self.stop_node(node)
        time.sleep(0.5)
        return self.start_node(node, token)

    def start_all(self, nodes: List[ProxyNode], token: str) -> int:
        started = 0
        for node in nodes:
            # Prioritaskan proxy yang hidup atau valid
            if node.is_valid:
                ok = self.start_node(node, token)
                if ok:
                    started += 1
                time.sleep(0.05)
        return started

    def stop_all(self, nodes: List[ProxyNode]):
        for node in nodes:
            self.stop_node(node)

    def get_node_logs(self, node: ProxyNode, max_lines: int = 50) -> str:
        log_path = self.log_paths.get(node.id)
        if not log_path or not log_path.exists():
            return "Belum ada log untuk node ini."
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return "".join(lines[-max_lines:])
        except Exception as e:
            return f"Error membaca log: {e}"

    def auto_heal_check(self, nodes: List[ProxyNode], token: str):
        for node in nodes:
            if node.status == "RUNNING" and node.pid:
                proc = self.procs.get(node.id)
                if proc and proc.poll() is not None:
                    # Process died, heal it
                    node.error = "Process terminated unexpectedly, auto-restarting..."
                    self.start_node(node, token)
