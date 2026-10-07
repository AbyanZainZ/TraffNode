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
WP_LINUX_PATH = "/usr/local/bin/wireproxy"
RUN_DIR = Path("/tmp/traffnode") if os.name != "nt" else Path(os.environ.get("TEMP", "C:/Temp")) / "traffnode"

class NodeSupervisor:
    def __init__(self):
        self.procs: Dict[int, subprocess.Popen] = {}      # TraffMonetizer CLI procs
        self.wp_procs: Dict[int, subprocess.Popen] = {}   # WireProxy daemon procs
        self.log_paths: Dict[int, Path] = {}
        RUN_DIR.mkdir(parents=True, exist_ok=True)

    def _get_tm_binary(self) -> Optional[str]:
        if os.name == "nt":
            return "simulated"
        if os.path.exists(TM_LINUX_PATH):
            return TM_LINUX_PATH
        if os.path.exists(TM_LINUX_SYMLINK):
            return TM_LINUX_SYMLINK
        return None

    def _get_wp_binary(self) -> Optional[str]:
        if os.name == "nt":
            return "simulated"
        if os.path.exists(WP_LINUX_PATH):
            return WP_LINUX_PATH
        return None

    def start_node(self, node: ProxyNode, token: str, surfshark_privkey: str = "") -> bool:
        if not token or not token.strip():
            node.error = "Token TraffMonetizer kosong"
            node.status = "ERROR"
            return False

        self.stop_node(node)

        node_home = RUN_DIR / f"node_{node.id}"
        node_home.mkdir(parents=True, exist_ok=True)
        log_path = node_home / "worker.log"
        self.log_paths[node.id] = log_path

        env = os.environ.copy()
        env["HOME"] = str(node_home)
        env["USERPROFILE"] = str(node_home)
        # .NET Workstation GC & Low-Memory Tuning (Menghemat RAM di VPS kecil)
        env["DOTNET_gcServer"] = "0"
        env["COMPlus_gcServer"] = "0"
        env["DOTNET_GCHeapHardLimit"] = "35000000"

        tm_bin = self._get_tm_binary()

        # ======================================================================
        # CASE 1: SURFSHARK VPN NODE (WIREGUARD VIA WIREPROXY)
        # ======================================================================
        if getattr(node, "node_type", "proxy") == "surfshark":
            if not surfshark_privkey or not surfshark_privkey.strip():
                node.error = "WireGuard Private Key kosong"
                node.status = "ERROR"
                return False

            if not node.endpoint or not node.pub_key:
                node.error = "Endpoint atau PubKey Surfshark tidak valid"
                node.status = "ERROR"
                return False

            wg_conf_path = node_home / "wg.conf"
            with open(wg_conf_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Interface]\n"
                    "Address = 10.14.0.2/16\n"
                    f"PrivateKey = {surfshark_privkey.strip()}\n"
                    "DNS = 162.252.172.57, 149.154.159.92\n\n"
                    "[Peer]\n"
                    f"PublicKey = {node.pub_key.strip()}\n"
                    "AllowedIPs = 0.0.0.0/0\n"
                    f"Endpoint = {node.endpoint.strip()}\n"
                )

            wp_conf_path = node_home / "wireproxy.conf"
            local_port = node.port or (21000 + node.id)
            node.port = local_port
            with open(wp_conf_path, "w", encoding="utf-8") as f:
                f.write(
                    f"WGConfig = {wg_conf_path}\n\n"
                    "[socks5]\n"
                    f"BindAddress = 127.0.0.1:{local_port}\n"
                )

            pc_conf_path = node_home / "proxychains.conf"
            with open(pc_conf_path, "w", encoding="utf-8") as f:
                f.write(
                    "strict_chain\n"
                    "proxy_dns\n"
                    "remote_dns_subnet 224\n"
                    "tcp_read_time_out 15000\n"
                    "tcp_connect_time_out 8000\n\n"
                    "[ProxyList]\n"
                    f"socks5 127.0.0.1 {local_port}\n"
                )

            node.update_device_name()
            dev_name = node.device_name

            wp_bin = self._get_wp_binary()
            wp_log_path = node_home / "wireproxy.log"

            try:
                # 1. Start WireProxy
                wp_log_f = open(wp_log_path, "w", encoding="utf-8", errors="ignore")
                if os.name != "nt" and wp_bin:
                    wp_proc = subprocess.Popen(
                        [wp_bin, "-c", str(wp_conf_path)],
                        cwd=str(node_home),
                        stdout=wp_log_f,
                        stderr=subprocess.STDOUT
                    )
                else:
                    wp_log_f.write(f"[WireProxy Simulator] Binding socks5 127.0.0.1:{local_port} for {node.endpoint}\n")
                    wp_log_f.flush()
                    wp_proc = subprocess.Popen(["cmd.exe", "/c", "ping -n 99999 127.0.0.1 > nul"], stdout=wp_log_f, stderr=subprocess.STDOUT)
                
                wp_log_f.close()
                self.wp_procs[node.id] = wp_proc
                node.wp_pid = wp_proc.pid

                time.sleep(0.3)

                # 2. Start TraffMonetizer inside proxychains4
                log_f = open(log_path, "w", encoding="utf-8", errors="ignore")
                if os.name != "nt" and tm_bin:
                    cmd = [
                        "proxychains4", "-f", str(pc_conf_path), "-q",
                        tm_bin, "start", "accept",
                        "--token", token.strip(),
                        "--device-name", dev_name
                    ]
                    tm_proc = subprocess.Popen(
                        cmd,
                        cwd=str(node_home),
                        env=env,
                        stdout=log_f,
                        stderr=subprocess.STDOUT
                    )
                else:
                    log_f.write(f"[TraffNode Simulator] Starting Surfshark Node #{node.id} ({node.country} - {node.endpoint})\n")
                    log_f.write(f"[TraffNode Simulator] Tunneling via WireGuard socks5://127.0.0.1:{local_port}\n")
                    log_f.write(f"[TraffNode Simulator] Device Name: {dev_name}\n")
                    log_f.write("[TraffNode Simulator] Worker online & sharing bandwidth simulated.\n")
                    log_f.flush()
                    tm_proc = subprocess.Popen(["cmd.exe", "/c", "ping -n 99999 127.0.0.1 > nul"], stdout=log_f, stderr=subprocess.STDOUT)

                log_f.close()
                self.procs[node.id] = tm_proc
                node.pid = tm_proc.pid
                node.status = "RUNNING"
                node.started_at = time.time()
                node.error = None
                return True
            except Exception as e:
                node.status = "ERROR"
                node.error = str(e)[:50]
                return False

        # ======================================================================
        # CASE 2: REGULAR CUSTOM PROXY NODE (HTTP / SOCKS5)
        # ======================================================================
        if not node.is_valid:
            node.error = "Format proxy tidak valid"
            node.status = "ERROR"
            return False

        conf_path = node_home / "proxychains.conf"
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

        try:
            log_f = open(log_path, "w", encoding="utf-8", errors="ignore")
            if os.name != "nt" and tm_bin:
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
                log_f.write(f"[TraffNode Simulator] Starting node {node.id} via {node.protocol}://{node.host}:{node.port}\n")
                log_f.write(f"[TraffNode Simulator] Device Name: {dev_name}\n")
                log_f.write("[TraffNode Simulator] Worker online & sharing bandwidth simulated.\n")
                log_f.flush()
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
            node.error = str(e)[:50]
            return False

    def stop_node(self, node: ProxyNode):
        # Stop TM proc
        proc = self.procs.pop(node.id, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        # Stop WireProxy proc if any
        wp_proc = self.wp_procs.pop(node.id, None)
        if wp_proc:
            try:
                wp_proc.terminate()
                wp_proc.wait(timeout=1.5)
            except Exception:
                try:
                    wp_proc.kill()
                except Exception:
                    pass

        node.pid = None
        node.wp_pid = None
        node.status = "STOPPED"

    def restart_node(self, node: ProxyNode, token: str, surfshark_privkey: str = "") -> bool:
        self.stop_node(node)
        time.sleep(0.5)
        return self.start_node(node, token, surfshark_privkey=surfshark_privkey)

    def start_all(self, nodes: List[ProxyNode], token: str, surfshark_privkey: str = "") -> int:
        started = 0
        for node in nodes:
            is_valid_type = (node.node_type == "surfshark") or node.is_valid
            if is_valid_type:
                ok = self.start_node(node, token, surfshark_privkey=surfshark_privkey)
                if ok:
                    started += 1
                time.sleep(0.5)
        return started

    def stop_all(self, nodes: List[ProxyNode]):
        for node in nodes:
            self.stop_node(node)

        # Emergency cleanup on Linux
        if os.name != "nt":
            try:
                subprocess.run(["pkill", "-f", "wireproxy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def get_node_logs(self, node: ProxyNode, max_lines: int = 60) -> str:
        log_path = self.log_paths.get(node.id)
        if not log_path or not log_path.exists():
            return "Belum ada log untuk node ini."
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                output = "".join(lines[-max_lines:])

            # Check if wireproxy log exists
            if getattr(node, "node_type", "") == "surfshark":
                wp_log_path = log_path.parent / "wireproxy.log"
                if wp_log_path.exists():
                    try:
                        with open(wp_log_path, "r", encoding="utf-8", errors="ignore") as fwp:
                            wp_lines = fwp.readlines()
                            output += "\n--- WireProxy Tunnel Log ---\n" + "".join(wp_lines[-20:])
                    except Exception:
                        pass
            return output
        except Exception as e:
            return f"Error membaca log: {e}"

    def auto_heal_check(self, nodes: List[ProxyNode], token: str, surfshark_privkey: str = ""):
        for node in nodes:
            if node.status == "RUNNING":
                tm_died = False
                wp_died = False

                proc = self.procs.get(node.id)
                if proc and proc.poll() is not None:
                    tm_died = True

                if getattr(node, "node_type", "") == "surfshark":
                    wp_proc = self.wp_procs.get(node.id)
                    if wp_proc and wp_proc.poll() is not None:
                        wp_died = True

                if tm_died or wp_died:
                    reason = "WireProxy down" if wp_died else "TraffMonetizer terminated"
                    node.error = f"Auto-heal: {reason}, restarting..."
                    self.start_node(node, token, surfshark_privkey=surfshark_privkey)
