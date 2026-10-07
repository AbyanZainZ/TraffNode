# 🌐 TraffNode Engine

> **VPS Multi-Proxy Passive Income & Bandwidth Monetization Harvester**
> *Port Dashboard: `8888` (Terpisah dari ProxyChain di port `8080`)*

TraffNode adalah sistem automasi dan orchestration server untuk menjalankan ratusan instance **TraffMonetizer** yang terisolasi per proxy node menggunakan `proxychains4` secara 24/7 di VPS Linux, dilengkapi **Cyber Cockpit Web Dashboard** real-time untuk memantau bandwidth usage, utilisasi CPU/RAM, dan status worker.

---

## ✨ Fitur Unggulan

* **🎛️ Cyber Cockpit Web Dashboard (Port 8888):** Visualisasi modern (`#070f1a` & `#00e5ff`) untuk mengontrol dan memantau ratusan node langsung dari browser.
* **⚡ Isolated Multi-Node Workers:** Setiap proxy node diisolasi menggunakan `proxychains4` dengan dynamic routing dan directory mandiri.
* **🩺 Integrated High-Speed Health-Checker:** Menguji proxy secara paralel (tanpa rate-limit) dan mendeteksi GeoIP negara asal (`Country - IP`).
* **📊 Akurat Bandwidth & Traffic Monitor:** Menghitung total data (GB) yang terkirim dan diterima (Up/Down speed) per node dan secara sistem.
* **🔄 Auto-Recovery & Self-Healing:** Worker yang terputus atau drop otomatis dideteksi dan di-restart setiap 30 detik.
* **🚀 Dual Mode:** Siap pakai di **VPS Linux Ubuntu/Debian 24/7 (Systemd)** dan **Windows Localhost**.

---

## ☁️ Cara Deploy ke VPS Linux (1 Perintah)

Jalankan perintah berikut di terminal SSH VPS Anda:

```bash
git clone https://github.com/AbyanZainZ/TraffNode.git traffnode && cd traffnode && sudo bash deploy_vps.sh
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
