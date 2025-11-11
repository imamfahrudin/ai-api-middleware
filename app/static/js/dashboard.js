let charts = {};
let globalState = { previousStats: {}, isLogHovered: false };
const CHART_COLORS = {
    red: 'rgb(239, 68, 68)',
    orange: 'rgb(249, 115, 22)',
    yellow: 'rgb(234, 179, 8)',
    green: 'rgb(34, 197, 94)',
    blue: 'rgb(59, 130, 246)',
    purple: 'rgb(139, 92, 246)',
    grey: 'rgb(107, 114, 128)'
};

function getStatusBadge(status) {
    const colors = { Healthy: 'bg-green-600', Resting: 'bg-yellow-600', Disabled: 'bg-red-600' };
    const pulseClass = status === 'Healthy' ? 'status-pulse-healthy' : (status === 'Resting' ? 'status-pulse-resting' : '');
    return `<span class="px-2 py-1 text-xs font-bold text-white rounded-full ${colors[status] || 'bg-gray-500'} ${pulseClass}">${status}</span>`;
}

function getHealthBar(kpi) {
    const kpiColor = kpi > 85 ? 'bg-green-500' : kpi > 60 ? 'bg-yellow-500' : 'bg-red-500';
    return `<div class="w-full bg-gray-700 rounded-full h-2.5 mt-1"><div class="health-bar-fill ${kpiColor} h-2.5 rounded-full" style="width: ${kpi}%" title="Health: ${kpi}%"></div></div>`;
}

async function fetchKeys() {
    const response = await fetch('/middleware/api/keys');
    const keys = await response.json();
    const sidebarList = document.getElementById('keys-sidebar-list');

    sidebarList.innerHTML = '';
    keys.forEach(key => {
        const li = document.createElement('li');
        li.className = 'sidebar-item p-3 rounded cursor-pointer hover:bg-gray-700';
        li.dataset.keyId = key.id;
        li.dataset.keyName = key.name;
        li.dataset.keyStatus = key.status;
        const keyDisplay = key.key_value.length > 12 ? `${key.key_value.slice(0, 4)}...${key.key_value.slice(-4)}` : key.key_value;
        li.innerHTML = `
            <div class="flex items-center gap-2">
                ${getStatusBadge(key.status)}
                <div class="font-bold flex-grow">${key.name}</div>
                <div class="text-xs text-gray-400 font-mono">${keyDisplay}</div>
            </div>
            ${getHealthBar(key.kpi)}`;
        li.addEventListener('click', (e) => {
            e.stopPropagation();
            setActiveView(li, () => displayKeyDetails(key.id, key.name));
        });
        sidebarList.appendChild(li);
    });
}

function setActiveView(element, displayFunction) {
    document.querySelectorAll('.sidebar-item').forEach(item => item.classList.remove('active'));
    if (element) element.classList.add('active');
    displayFunction();
}

function pulseStatCard(cardId, newValue, previousValue) {
    if (newValue > previousValue) {
        const card = document.getElementById(cardId);
        if (card) {
            card.classList.add('pulse-once');
            setTimeout(() => card.classList.remove('pulse-once'), 500);
        }
    }
}

async function displayGlobalOverview() {
    // Destroy old charts to prevent conflicts when switching views
    Object.keys(charts).forEach(id => {
        if (charts[id]) {
            charts[id].destroy();
            delete charts[id];
        }
    });
    document.getElementById('dashboard-content').innerHTML = `
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold">Global Overview</h1>
            <div id="live-clock" class="text-xl font-semibold text-gray-400"></div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
             <div class="glass-card p-4" id="total-requests-card"></div><div class="glass-card p-4" id="avg-latency-card"></div>
             <div class="glass-card p-4" id="success-rate-card"></div><div class="glass-card p-4" id="tokens-today-card"></div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <div class="glass-card p-4 h-[28rem]"><canvas id="globalRequestChart"></canvas></div>
            <div class="glass-card p-4 flex flex-col h-[28rem]"><h3 class="text-sm font-semibold text-center mb-2 text-gray-300">Request Distribution (Today)</h3><div class="relative flex-grow overflow-y-auto pr-2"><div style="position: relative;" id="requestDistributionContainer"><canvas id="requestDistributionChart"></canvas></div></div></div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <div class="glass-card p-4"><canvas id="healthStatusChart"></canvas></div>
            <div class="glass-card p-4"><canvas id="globalModelChart"></canvas></div>
            <div class="glass-card p-4"><canvas id="errorTypeChart"></canvas></div>
        </div>
        <div class="grid grid-cols-1">
            <div id="live-log-container" class="glass-card p-4 h-48 overflow-y-scroll font-mono text-sm"><h3 class="text-lg font-bold mb-2">Live Mission Feed</h3><ul id="live-log-list"></ul></div>
        </div>`;

    const logContainer = document.getElementById('live-log-container');
    if(logContainer) {
        logContainer.addEventListener('mouseenter', () => globalState.isLogHovered = true);
        logContainer.addEventListener('mouseleave', () => globalState.isLogHovered = false);
    }
    await updateGlobalData();
}

async function updateGlobalData() {
    try {
        const response = await fetch('/middleware/api/global-stats');
        if (!response.ok) return;
        const stats = await response.json();

        const labels = stats.historical.map(s => new Date(s.date + 'T00:00:00Z').toLocaleDateString());
        const todayStats = stats.historical.slice(-1)[0] || {};

        const currentRequests = todayStats.total_requests || 0;
        pulseStatCard('total-requests-card', currentRequests, globalState.previousStats.requests || 0);
        document.getElementById('total-requests-card').innerHTML = `<div class="text-gray-400 text-sm">Requests (Today)</div><div class="text-2xl font-bold">${currentRequests.toLocaleString()}</div>`;
        globalState.previousStats.requests = currentRequests;

        const avgLatency = todayStats.total_requests > 0 ? (todayStats.total_latency / todayStats.total_requests).toFixed(0) : 0;
        document.getElementById('avg-latency-card').innerHTML = `<div class="text-gray-400 text-sm">Avg Latency</div><div class="text-2xl font-bold">${avgLatency} ms</div>`;
        const successRate = todayStats.total_requests > 0 ? (todayStats.total_successes / todayStats.total_requests * 100).toFixed(1) : 100;
        document.getElementById('success-rate-card').innerHTML = `<div class="text-gray-400 text-sm">Success Rate</div><div class="text-2xl font-bold">${successRate}%</div>`;
        const totalTokens = (todayStats.total_tokens_in || 0) + (todayStats.total_tokens_out || 0);
        document.getElementById('tokens-today-card').innerHTML = `<div class="text-gray-400 text-sm">Tokens (Today)</div><div class="text-2xl font-bold">${totalTokens.toLocaleString()}</div>`;

        updateChart('globalRequestChart', 'bar', 'Total Daily Requests', labels, [{ label: 'Requests', data: stats.historical.map(s => s.total_requests), backgroundColor: CHART_COLORS.blue }]);
        updateStackedBarChart('requestDistributionChart', 'Request Distribution (Today)', stats.request_distribution);
        updatePieChart('healthStatusChart', 'Key Health Status', Object.keys(stats.health_status), Object.values(stats.health_status));
        updatePieChart('globalModelChart', 'Model Usage (Today)', Object.keys(stats.model_usage_today), Object.values(stats.model_usage_today));
        updatePieChart('errorTypeChart', 'Error Codes (Today)', Object.keys(stats.error_codes_today), Object.values(stats.error_codes_today));
    } catch (error) {
        console.error("Failed to update global data:", error);
    }
}

async function displayKeyDetails(keyId, keyName) {
    // Destroy old charts to prevent conflicts when switching views
    Object.keys(charts).forEach(id => {
        if (charts[id]) {
            charts[id].destroy();
            delete charts[id];
        }
    });
    document.getElementById('dashboard-content').innerHTML = `
        <h1 class="text-3xl font-bold mb-6">${keyName} - Analytics</h1>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div class="glass-card p-4 lg:col-span-2">
                <h2 class="text-xl font-bold mb-2">Notes</h2>
                <p id="key-note-display" class="text-gray-300 whitespace-pre-wrap">Loading...</p>
            </div>
            <div class="glass-card p-4 h-80"><canvas id="tokenChart"></canvas></div><div class="glass-card p-4 h-80"><canvas id="requestChart"></canvas></div>
            <div class="lg:col-span-2 glass-card p-4 h-80"><canvas id="latencyChart"></canvas></div>
        </div>
        <div class="mt-8 flex gap-4">
             <a href="/middleware/keys" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md flex items-center gap-2">
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
                Manage Keys
             </a>
        </div>`;

    const [statsResponse, detailsResponse] = await Promise.all([
        fetch(`/middleware/api/keys/${keyId}/stats`),
        fetch(`/middleware/api/keys/${keyId}`)
    ]);

    const stats = await statsResponse.json();
    const details = await detailsResponse.json();

    document.getElementById('key-note-display').textContent = details.note || 'No notes for this key.';

    const labels = stats.map(s => new Date(s.date + 'T00:00:00Z').toLocaleDateString());
    updateChart('tokenChart', 'line', 'Tokens In/Out (30 Days)', labels, [{ label: 'In', data: stats.map(s => s.tokens_in), borderColor: CHART_COLORS.blue }, { label: 'Out', data: stats.map(s => s.tokens_out), borderColor: CHART_COLORS.purple }]);
    updateChart('requestChart', 'line', 'Requests (30 Days)', labels, [{ label: 'Success', data: stats.map(s => s.successes), borderColor: CHART_COLORS.green }, { label: 'Errors', data: stats.map(s => s.errors), borderColor: CHART_COLORS.red }]);
    updateChart('latencyChart', 'line', 'Average Latency (ms)', labels, [{ label: 'Avg Latency', data: stats.map(s => s.requests > 0 ? s.total_latency_ms / s.requests : 0), borderColor: CHART_COLORS.yellow }]);
}

async function fetchLogs() {
    const response = await fetch('/middleware/api/logs');
    const logs = await response.json();
    const logList = document.getElementById('live-log-list');
    if(!logList) return;

    logList.innerHTML = logs.map(log => `<li><span class="text-gray-500">${new Date(log.time).toLocaleTimeString()}</span> <span class="${log.color}">${log.msg}</span></li>`).join('');

    if(!globalState.isLogHovered) {
        const logContainer = document.getElementById('live-log-container');
        if(logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    }
}

function updateChart(canvasId, type, title, labels, datasets) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if(!ctx) return;
    const textColor = '#e5e7eb';
    const gridColor = '#4b5563';

    if (charts[canvasId]) {
        charts[canvasId].config.type = type;
        charts[canvasId].data.labels = labels;
        charts[canvasId].data.datasets = datasets;
        charts[canvasId].update('none'); // 'none' avoids re-animation
        return;
    }

    charts[canvasId] = new Chart(ctx, { type, data: { labels, datasets }, options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: title, color: textColor, font: {size: 14} } }, scales: { x: { ticks: { color: textColor }, grid: { color: gridColor } }, y: { ticks: { color: textColor }, grid: { color: gridColor } } } }});
}

function updateStackedBarChart(canvasId, title, data) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if(!ctx) return;

    const textColor = '#e5e7eb';
    const gridColor = '#4b5563';
    const keyNames = data.map(d => d.name);
    const allModels = [...new Set(data.flatMap(d => Object.keys(d.usage)))].filter(m => m !== 'unknown' && m !== 'model-discovery');
    const datasets = allModels.map((model, i) => {
        const colorValues = Object.values(CHART_COLORS);
        return { label: model, data: data.map(keyData => keyData.usage[model] || 0), backgroundColor: colorValues[(i + 3) % colorValues.length] };
    });

    const container = document.getElementById('requestDistributionContainer');
    if (container) {
        const barHeight = 35;
        const minHeight = 448; // h-[28rem]
        const newHeight = Math.max(minHeight - 50, keyNames.length * barHeight); // Adjust for title
        container.style.height = `${newHeight}px`;
    }

    if (charts[canvasId]) {
        charts[canvasId].data.labels = keyNames;
        charts[canvasId].data.datasets = datasets;
        charts[canvasId].update('none');
        return;
    }

    charts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels: keyNames, datasets },
        options: {
            maintainAspectRatio: false,
            indexAxis: 'y',
            responsive: true,
            plugins: {
                title: { display: false },
                legend: { position: 'bottom', labels: { color: textColor } }
            },
            scales: {
                x: {
                    stacked: true,
                    ticks: { color: textColor },
                    grid: { color: gridColor }
                },
                y: {
                    stacked: true,
                    ticks: { color: textColor },
                    grid: { color: gridColor }
                }
            }
        }
    });
}

function updatePieChart(canvasId, title, labels, data) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if(!ctx) return;
    const textColor = '#e5e7eb';
    
    // Special color mapping for different chart types
    let colors;
    if (canvasId === 'healthStatusChart') {
        const healthColorMap = {
            'Healthy': CHART_COLORS.green,
            'Resting': CHART_COLORS.yellow,
            'Disabled': CHART_COLORS.red
        };
        colors = labels.map(label => healthColorMap[label] || CHART_COLORS.grey);
    } else if (canvasId === 'errorTypeChart') {
        // Use red/orange tones for error types
        colors = labels.map((_, i) => {
            const errorColors = [CHART_COLORS.red, CHART_COLORS.orange, CHART_COLORS.yellow];
            return errorColors[i % errorColors.length];
        });
    } else {
        // Default color cycling for other charts
        const colorValues = Object.values(CHART_COLORS);
        colors = labels.map((_, i) => colorValues[i % colorValues.length]);
    }

    if (charts[canvasId]) {
        charts[canvasId].data.labels = labels;
        charts[canvasId].data.datasets[0].data = data;
        charts[canvasId].update('none');
        return;
    }

    charts[canvasId] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#1f2937'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: title, color: textColor, font: { size: 14 } },
                legend: { position: 'bottom', labels: { color: textColor } }
            }
        }
    });
}

function updateClock() {
    const clock = document.getElementById('live-clock');
    if (clock) {
        clock.textContent = new Date().toLocaleTimeString();
    }
}

// Toast notification
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `fixed bottom-8 right-8 text-white py-3 px-6 rounded-lg shadow-xl z-50 pointer-events-none transition-all duration-300 ${
        isError ? 'bg-red-600' : 'bg-green-600'
    }`;

    toast.classList.remove('opacity-0', 'translate-y-4');
    toast.classList.add('opacity-100', 'translate-y-0');

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-4');
        toast.classList.remove('opacity-100', 'translate-y-0');
    }, 3000);
}

// Initial setup and intervals
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('global-overview-btn-li').addEventListener('click', (e) => { e.preventDefault(); setActiveView(e.currentTarget, displayGlobalOverview); });

    // Initial load
    displayGlobalOverview();
    fetchKeys();

    // Set up intervals
    setInterval(updateGlobalData, 5000);
    setInterval(fetchLogs, 2000);
    setInterval(updateClock, 1000);
    setInterval(fetchKeys, 30000); // Refresh keys every 30 seconds
});