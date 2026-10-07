// ==============================================================================
// TRAFFNODE CYBER COCKPIT JAVASCRIPT (PORT 8888)
// ==============================================================================

let currentStatusData = null;
let pollTimer = null;

// DOM ELEMENTS — HEADER & METRICS
const valServerIp = document.getElementById('val-server-ip');
const statRunningNodes = document.getElementById('stat-running-nodes');
const statTotalNodes = document.getElementById('stat-total-nodes');
const statAliveNodes = document.getElementById('stat-alive-nodes');
const statAlivePct = document.getElementById('stat-alive-pct');
const statBandwidthTotal = document.getElementById('stat-bandwidth-total');
const statBandwidthSpeed = document.getElementById('stat-bandwidth-speed');
const statCpuRam = document.getElementById('stat-cpu-ram');
const statRamDetail = document.getElementById('stat-ram-detail');

// DOM ELEMENTS — CONFIG & INPUTS
const cfgToken = document.getElementById('cfg-token');
const tagParseCount = document.getElementById('tag-parse-count');
const proxiesTextarea = document.getElementById('proxies-textarea');
const btnSaveProxies = document.getElementById('btn-save-proxies');
const btnCheckProxies = document.getElementById('btn-check-proxies');

// DOM ELEMENTS — CONTROLS & BARS
const btnStartAll = document.getElementById('btn-start-all');
const btnStopAll = document.getElementById('btn-stop-all');
const btnRestartAll = document.getElementById('btn-restart-all');
const barCpu = document.getElementById('bar-cpu');
const barRam = document.getElementById('bar-ram');
const txtCpu = document.getElementById('txt-cpu');
const txtRam = document.getElementById('txt-ram');

// DOM ELEMENTS — TABLE & MODAL
const tableFilter = document.getElementById('table-filter');
const nodesTbody = document.getElementById('nodes-tbody');
const toastEl = document.getElementById('tn-toast');
const healthStatusText = document.getElementById('health-status-text');

const logModal = document.getElementById('log-modal');
const logModalTitle = document.getElementById('log-modal-title');
const logModalBody = document.getElementById('log-modal-body');
const btnCloseModal = document.getElementById('btn-close-modal');

// FORMAT HELPER
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    if (!seconds || seconds <= 0) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}j ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

function showToast(msg, isError = false) {
    toastEl.textContent = msg;
    toastEl.style.borderColor = isError ? '#ff5252' : '#00e5ff';
    toastEl.style.color = isError ? '#ff5252' : '#00e5ff';
    toastEl.style.display = 'block';
    setTimeout(() => {
        toastEl.style.display = 'none';
    }, 3500);
}

// COUNT HELPER
function updateParseCount() {
    const lines = proxiesTextarea.value.split('\n').filter(l => l.trim().length > 0 && !l.trim().startsWith('#'));
    tagParseCount.textContent = `${lines.length} Proxy`;
}
proxiesTextarea.addEventListener('input', updateParseCount);

// FETCH STATUS
async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        currentStatusData = data;
        renderDashboard(data);
    } catch (err) {
        console.error("Error fetching status:", err);
    }
}

// FETCH RAW PROXIES ON LOAD
async function fetchRawProxies() {
    try {
        const res = await fetch('/api/proxies/raw');
        if (res.ok && proxiesTextarea.value === "") {
            proxiesTextarea.value = await res.text();
            updateParseCount();
        }
    } catch (e) {}
}

// RENDER DASHBOARD
function renderDashboard(data) {
    valServerIp.textContent = data.server_ip || '127.0.0.1';

    // Token
    if (document.activeElement !== cfgToken && data.config.traff_token) {
        cfgToken.value = data.config.traff_token;
    }

    // Metrics
    const m = data.metrics || {};
    const total = m.total_nodes || 0;
    const running = m.running_nodes || 0;
    const alive = m.alive_nodes || 0;

    statRunningNodes.textContent = running;
    statTotalNodes.textContent = `${total} Total Nodes`;

    statAliveNodes.textContent = alive;
    const alivePct = total > 0 ? Math.round((alive / total) * 100) : 0;
    statAlivePct.textContent = `${alivePct}% Alive & Siap`;

    // Bandwidth
    const bw = m.bandwidth || {};
    const totalBytes = (bw.total_bytes_in || 0) + (bw.total_bytes_out || 0);
    statBandwidthTotal.textContent = formatBytes(totalBytes);
    statBandwidthSpeed.textContent = `↑ ${formatBytes(bw.speed_up_bps || 0)}/s • ↓ ${formatBytes(bw.speed_down_bps || 0)}/s`;

    // System Vitals
    const sys = data.system || {};
    const cpu = sys.cpu_percent || 0;
    const ramPct = sys.ram_percent || 0;

    statCpuRam.textContent = `${cpu}% CPU`;
    statRamDetail.textContent = `RAM: ${sys.ram_used_mb || 0} MB / ${sys.ram_total_mb || 0} MB`;

    barCpu.style.width = `${Math.min(100, cpu)}%`;
    barCpu.style.background = cpu > 80 ? '#ff5252' : (cpu > 50 ? '#ffd600' : '#00e676');
    txtCpu.textContent = `${cpu}%`;

    barRam.style.width = `${Math.min(100, ramPct)}%`;
    barRam.style.background = ramPct > 85 ? '#ff5252' : '#00e5ff';
    txtRam.textContent = `${ramPct}%`;

    if (m.is_checking) {
        healthStatusText.innerHTML = `<span style="color: #ffd600;">🩺 Sedang menguji kesehatan proxy di latar belakang...</span>`;
    } else {
        healthStatusText.textContent = `TraffNode Daemon Running (Port ${data.config.dashboard_port || 8888})`;
    }

    renderTable(data.nodes || []);
}

// RENDER TABLE
function renderTable(nodes) {
    const filter = tableFilter.value.toLowerCase().trim();

    if (!nodes || nodes.length === 0) {
        nodesTbody.innerHTML = `<tr><td colspan="8" class="tn-text-center tn-muted">Belum ada proxy node. Masukkan proxy di atas lalu klik "SIMPAN PROXY".</td></tr>`;
        return;
    }

    const filtered = nodes.filter(n => {
        if (!filter) return true;
        const str = `${n.id} ${n.device_name} ${n.country} ${n.host} ${n.status}`.toLowerCase();
        return str.includes(filter);
    });

    if (filtered.length === 0) {
        nodesTbody.innerHTML = `<tr><td colspan="8" class="tn-text-center tn-muted">Tidak ada node yang cocok dengan pencarian "${filter}".</td></tr>`;
        return;
    }

    let html = '';
    filtered.forEach(n => {
        // Status Badge
        let badge = '';
        if (n.status === "RUNNING") {
            badge = `<span class="tn-badge tn-badge-running">🟢 RUNNING</span>`;
        } else if (n.status === "ERROR") {
            badge = `<span class="tn-badge tn-badge-stopped">🔴 ERROR</span>`;
        } else if (n.status === "STOPPED") {
            badge = `<span class="tn-badge tn-badge-stopped">⚪ STOPPED</span>`;
        } else {
            badge = `<span class="tn-badge tn-badge-idle">⚡ IDLE</span>`;
        }

        // Latency
        let lat = '-';
        if (n.latency_ms) {
            const col = n.latency_ms < 300 ? '#00e676' : (n.latency_ms < 800 ? '#ffd600' : '#ff5252');
            lat = `<span style="color: ${col}; font-weight: bold;">${n.latency_ms} ms</span>`;
        } else if (n.error) {
            lat = `<span style="color: #ff5252; font-size: 10px;">${n.error}</span>`;
        }

        // Data traffic
        const tf = `↑ ${formatBytes(n.bytes_out)} / ↓ ${formatBytes(n.bytes_in)}`;

        // Device name
        const dev = `<span style="color: #00e5ff; font-weight: bold;">${n.device_name}</span>`;

        // Action buttons
        let actBtns = '';
        if (n.status === "RUNNING") {
            actBtns += `<button class="tn-btn-action" onclick="stopNode(${n.id})" title="Stop Node">⏹️ Stop</button>`;
        } else {
            actBtns += `<button class="tn-btn-action" onclick="startNode(${n.id})" title="Start Node">▶️ Start</button>`;
        }
        actBtns += `<button class="tn-btn-action" onclick="viewLogs(${n.id})" title="Lihat Logs">📋 Log</button>`;

        html += `
        <tr>
            <td style="color: #90caf9; font-weight: bold;">#${n.id}</td>
            <td>${badge}</td>
            <td>${dev}</td>
            <td><span style="color: #cfd8dc;">[${n.protocol}] ${n.host}:${n.port}</span></td>
            <td>${lat}</td>
            <td>${tf}</td>
            <td>${formatUptime(n.uptime_seconds)}</td>
            <td>${actBtns}</td>
        </tr>
        `;
    });

    nodesTbody.innerHTML = html;
}

tableFilter.addEventListener('input', () => {
    if (currentStatusData) renderTable(currentStatusData.nodes || []);
});

// ACTIONS
btnSaveProxies.addEventListener('click', async () => {
    const raw = proxiesTextarea.value.trim();
    const token = cfgToken.value.trim();

    btnSaveProxies.disabled = true;
    btnSaveProxies.innerHTML = `<span>⏳ Menyimpan...</span>`;

    try {
        if (token) {
            await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ traff_token: token })
            });
        }
        const res = await fetch('/api/proxies', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ raw_text: raw })
        });
        const data = await res.json();
        showToast(data.message || "Proxy berhasil disimpan!");
        await fetchStatus();
    } catch (e) {
        showToast("Gagal menyimpan proxy.", true);
    } finally {
        btnSaveProxies.disabled = false;
        btnSaveProxies.innerHTML = `<span>💾 SIMPAN PROXY</span>`;
    }
});

btnCheckProxies.addEventListener('click', async () => {
    try {
        const res = await fetch('/api/check', { method: 'POST' });
        const data = await res.json();
        showToast(data.message);
        await fetchStatus();
    } catch (e) {
        showToast("Gagal memulai tes proxy.", true);
    }
});

btnStartAll.addEventListener('click', async () => {
    const token = cfgToken.value.trim();
    if (!token) {
        showToast("⚠️ Harap isi Token TraffMonetizer terlebih dahulu!", true);
        cfgToken.focus();
        return;
    }

    btnStartAll.disabled = true;
    btnStartAll.innerHTML = `<span>⏳ Menjalankan Worker...</span>`;

    try {
        // Simpan token dulu
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ traff_token: token })
        });
        const res = await fetch('/api/start-all', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "Semua worker dimulai!");
        await fetchStatus();
    } catch (e) {
        showToast("Gagal menjalankan worker.", true);
    } finally {
        btnStartAll.disabled = false;
        btnStartAll.innerHTML = `<span>🚀 START ALL WORKERS</span>`;
    }
});

btnStopAll.addEventListener('click', async () => {
    if (!confirm("Hentikan semua worker node?")) return;
    try {
        const res = await fetch('/api/stop-all', { method: 'POST' });
        const data = await res.json();
        showToast(data.message);
        await fetchStatus();
    } catch (e) {
        showToast("Gagal menghentikan worker.", true);
    }
});

btnRestartAll.addEventListener('click', async () => {
    if (!confirm("Restart semua worker node?")) return;
    try {
        const res = await fetch('/api/restart-all', { method: 'POST' });
        const data = await res.json();
        showToast(data.message);
        await fetchStatus();
    } catch (e) {
        showToast("Gagal me-restart worker.", true);
    }
});

// SINGLE NODE ACTIONS
window.startNode = async function(id) {
    try {
        const res = await fetch(`/api/node/${id}/start`, { method: 'POST' });
        const data = await res.json();
        showToast(`Node #${id} berhasil dijalankan!`);
        await fetchStatus();
    } catch (e) {
        showToast(`Gagal menjalankan node #${id}.`, true);
    }
};

window.stopNode = async function(id) {
    try {
        const res = await fetch(`/api/node/${id}/stop`, { method: 'POST' });
        showToast(`Node #${id} dihentikan.`);
        await fetchStatus();
    } catch (e) {
        showToast(`Gagal menghentikan node #${id}.`, true);
    }
};

window.viewLogs = async function(id) {
    logModalTitle.textContent = `📋 Worker Log — Node #${id}`;
    logModalBody.textContent = "Mengambil log...";
    logModal.style.display = "block";
    try {
        const res = await fetch(`/api/node/${id}/logs`);
        const txt = await res.text();
        logModalBody.textContent = txt || "Log masih kosong.";
    } catch (e) {
        logModalBody.textContent = "Gagal mengambil log node.";
    }
};

btnCloseModal.addEventListener('click', () => {
    logModal.style.display = "none";
});

window.addEventListener('click', (e) => {
    if (e.target === logModal) logModal.style.display = "none";
});

// INITIALIZE
fetchRawProxies();
fetchStatus();
pollTimer = setInterval(fetchStatus, 4000);
