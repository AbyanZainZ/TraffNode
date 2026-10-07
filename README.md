# 🌐 TraffNode Engine

> **VPS Multi-Proxy & Surfshark VPN Passive Income & Bandwidth Monetization Harvester**  
> *Port Dashboard: `8888` (Terpisah dari ProxyChain di port `8080`)*

TraffNode adalah sistem automasi dan orchestration server untuk menjalankan ratusan instance **TraffMonetizer** yang terisolasi secara 24/7 di VPS Linux. Dilengkapi **Cyber Cockpit Web Dashboard** real-time untuk memantau bandwidth usage, utilisasi CPU/RAM, dan status worker.

Mendukung **Dual Network Engine**:
1. 🦈 **Surfshark VPN Multi-Node (WireGuard Userspace / WireProxy):** Menghubungkan puluhan hingga ratusan node ke 142 lokasi server Surfshark di seluruh dunia secara otomatis dengan IP bersih residensial/VPN dan bandwidth tanpa batas.
2. 🌐 **Custom Proxy Pool (HTTP / SOCKS5):** Menjalankan worker dari daftar proxy residential/datacenter Anda sendiri via `proxychains4`.

---

## ✨ Fitur Unggulan

* **🎛️ Cyber Cockpit Web Dashboard (Port 8888):** Visualisasi modern (`#070f1a` & `#00e5ff`) untuk mengontrol dan memantau ratusan node langsung dari browser.
* **🦈 Built-in 142 Surfshark Servers:** Database lengkap server WireGuard Surfshark global dengan preset region: *Global Random, Premium Countries, Asia Pasifik, Eropa*.
* **⚡ Multi-Port Isolated Workers:** Setiap proxy atau VPN node diisolasi menggunakan `wireproxy` dan `proxychains4` dengan directory mandiri.
* **🩺 Integrated Health-Checker:** Menguji proxy publik secara paralel (anti rate-limit 429) dan mendeteksi GeoIP negara asal (`Country - IP`).
* **📊 Akurat Bandwidth & Traffic Monitor:** Menghitung total data (GB) yang terkirim dan diterima (Up/Down speed) per node dan secara sistem.
* **🔄 Auto-Recovery & Self-Healing:** Worker atau tunnel VPN yang terputus otomatis dideteksi dan di-restart setiap 30 detik.
* **🚀 Dual Platform:** Siap pakai di **VPS Linux Ubuntu/Debian 24/7 (Systemd)** dan **Windows Localhost**.

---

## ☁️ Cara Deploy ke VPS Linux (1 Perintah)

Jalankan perintah berikut di terminal SSH VPS Anda:

```bash
git clone https://github.com/AbyanZainZ/TraffNode.git /opt/traffnode && cd /opt/traffnode && sudo bash deploy_vps.sh
```

Atau cukup gunakan 1 baris cURL:

```bash
curl -sSL https://raw.githubusercontent.com/AbyanZainZ/TraffNode/main/deploy_vps.sh | sudo bash
```

Setelah selesai, buka browser Anda di:  
👉 **`http://IP_VPS:8888`**

---

## 💻 Cara Menjalankan di Localhost Windows

1. Klik ganda file:
   ```cmd
   run_localhost.bat
   ```
2. Buka browser di: `http://127.0.0.1:8888`
