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
    const selectedIds = new Set(Array.from(document.querySelectorAll('.bulk-key-checkbox:checked')).map(cb => cb.dataset.id));
    
    sidebarList.innerHTML = '';
    keys.forEach(key => {
        const li = document.createElement('li');
        li.className = 'sidebar-item p-3 rounded cursor-pointer hover:bg-gray-700';
        li.dataset.keyId = key.id; 
        li.dataset.keyName = key.name;
        li.dataset.keyStatus = key.status;
        const isChecked = selectedIds.has(String(key.id)) ? 'checked' : '';
        const keyDisplay = key.key_value.length > 12 ? `${key.key_value.slice(0, 4)}...${key.key_value.slice(-4)}` : key.key_value;
        li.innerHTML = `
            <div class="flex items-start gap-2">
                <input type="checkbox" class="bulk-key-checkbox mt-1" data-id="${key.id}" ${isChecked}>
                <div class="flex-grow">
                    <div class="flex items-center gap-2 mb-1">
                        ${getStatusBadge(key.status)}
                        <div class="font-bold flex-grow">${key.name}</div>
                        <div class="text-xs text-gray-400 font-mono">${keyDisplay}</div>
                    </div>
                    ${getHealthBar(key.kpi)}
                </div>
            </div>`;
        li.querySelector('.flex-grow').addEventListener('click', (e) => {
            e.stopPropagation();
            setActiveView(li, () => displayKeyDetails(key.id, key.name));
        });
        sidebarList.appendChild(li);
    });
    updateBulkActionsMenu();
    filterKeys();
}

function filterKeys() {
    const query = document.getElementById('key-search').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter')?.value || 'all';
    
    document.querySelectorAll('#keys-sidebar-list li').forEach(li => {
        const name = li.dataset.keyName.toLowerCase();
        const status = li.dataset.keyStatus;
        
        const matchesName = name.includes(query);
        const matchesStatus = statusFilter === 'all' || status === statusFilter;
        
        li.style.display = (matchesName && matchesStatus) ? '' : 'none';
    });
}

function updateBulkActionsMenu() {
    const selected = document.querySelectorAll('.bulk-key-checkbox:checked').length;
    document.getElementById('bulk-actions-menu').style.display = selected > 0 ? 'block' : 'none';
}

async function applyBulkAction() {
    const action = document.getElementById('bulk-action-select').value;
    if (!action) return;
    const selectedIds = Array.from(document.querySelectorAll('.bulk-key-checkbox:checked')).map(cb => cb.dataset.id);
    if (selectedIds.length === 0) return showToast('No keys selected.', true);

    const response = await fetch('/middleware/api/keys/bulk-action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key_ids: selectedIds, status: action })
    });
    const result = await response.json();
    showToast(result.message, !response.ok);
    if (response.ok) fetchKeys();
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
             <button onclick="openModal(true, ${keyId}, '${keyName}')" class="bg-yellow-500 hover:bg-yellow-600 text-white font-bold py-2 px-4 rounded-md flex items-center gap-2">
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L15.232 5.232z" /></svg>
                Edit
             </button>
             <button onclick="removeKey(${keyId}, '${keyName}')" class="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-md flex items-center gap-2">
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                Delete
             </button>
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

    charts[canvasId] = new Chart(ctx, { type: 'bar', data: { labels: keyNames, datasets: datasets },
        options: { maintainAspectRatio: false, indexAxis: 'y', responsive: true, plugins: { title: { display: false }, legend: { position: 'bottom', labels: { color: textColor } } },
            scales: { x: { stacked: true, ticks: { color: textColor }, grid: { color: gridColor } }, y: { stacked: true, ticks: { color: textColor }, grid: { color: gridColor } } }
        }
    });
}

function updatePieChart(canvasId, title, labels, data) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if(!ctx) return;
    
    if (charts[canvasId]) {
        charts[canvasId].data.labels = labels;
        charts[canvasId].data.datasets[0].data = data;
        charts[canvasId].update('none');
        return;
    }
    
    const textColor = '#e5e7eb';
    const borderColor = '#1f2937';
    const chartColors = [CHART_COLORS.green, CHART_COLORS.yellow, CHART_COLORS.red, CHART_COLORS.blue, CHART_COLORS.purple, CHART_COLORS.orange, CHART_COLORS.grey];
    charts[canvasId] = new Chart(ctx, { type: 'doughnut', data: { labels, datasets: [{ data, backgroundColor: chartColors, borderColor: borderColor, borderWidth: 2 }] },
        options: { responsive: true, plugins: { title: { display: true, text: title, color: textColor, font: {size: 14} }, legend: { position: 'bottom', labels: { color: textColor } } } }
    });
}

function showToast(message, isError = false, type = null) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    
    // Determine toast type
    let toastType = type;
    if (!toastType) {
        toastType = isError ? 'error' : 'success';
    }
    
    // Set base classes and add type-specific class
    toast.className = `fixed bottom-8 right-8 text-white py-3 px-6 rounded-lg shadow-xl z-50 toast-${toastType} slide-in-right show`;
    
    // Auto dismiss after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show', 'slide-in-right');
        toast.classList.add('opacity-0', 'translate-y-4');
    }, 3000);
}

// Add ripple effect to buttons
function createRipple(event) {
    const button = event.currentTarget;
    const ripple = document.createElement('span');
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.classList.add('ripple');
    
    button.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 600);
}

async function openModal(isEdit = false, id = null, name = '') {
    const modal = document.getElementById('key-modal');
    document.getElementById('modal-title').innerText = isEdit ? `Edit Key: ${name}` : 'Add New API Key';
    document.getElementById('key-id').value = id;
    document.getElementById('key-name').value = name;
    const valueInput = document.getElementById('key-value');
    const noteInput = document.getElementById('key-note');
    const statusDiv = document.getElementById('manual-status-div');
    
    valueInput.value = '';
    valueInput.placeholder = isEdit ? 'Leave blank to keep current' : 'Enter new API key';
    valueInput.required = !isEdit;
    statusDiv.style.display = isEdit ? 'block' : 'none';

    if (isEdit) {
        const response = await fetch(`/middleware/api/keys/${id}`);
        const details = await response.json();
        noteInput.value = details.note || '';
    } else {
        noteInput.value = '';
    }

    modal.classList.remove('hidden');
}

function closeModal() { 
    document.getElementById('key-modal').classList.add('hidden'); 
}

async function handleFormSubmit(event) {
    event.preventDefault();
    const id = document.getElementById('key-id').value;
    const nameInput = document.getElementById('key-name');
    const valueInput = document.getElementById('key-value');
    const name = nameInput.value;
    const value = valueInput.value;
    const note = document.getElementById('key-note').value;
    const status = document.getElementById('key-status').value;
    const isEdit = !!id;
    
    // Basic validation
    if (!name.trim()) {
        nameInput.classList.add('shake');
        showToast('Name is required!', true, 'warning');
        setTimeout(() => nameInput.classList.remove('shake'), 500);
        nameInput.focus();
        return;
    }
    
    if (!isEdit && !value.trim()) {
        valueInput.classList.add('shake');
        showToast('Key value is required!', true, 'warning');
        setTimeout(() => valueInput.classList.remove('shake'), 500);
        valueInput.focus();
        return;
    }

    const url = isEdit ? `/middleware/api/keys/${id}` : '/middleware/api/keys';
    const method = isEdit ? 'PUT' : 'POST';
    const body = JSON.stringify({ name, key: value || null, status: isEdit ? status : null, note });

    const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body });
    const result = await response.json();
    showToast(result.message, !response.ok);
    if(response.ok) {
        closeModal();
        await fetchKeys();
        if (document.querySelector('.sidebar-item.active')?.id === 'global-overview-btn-li') {
            await displayGlobalOverview();
        } else {
            // If we were editing a key, refresh its details view
            await displayKeyDetails(id, name);
        }
    }
}

async function removeKey(id, name) {
    if (!confirm(`Delete key "${name}"? This is permanent.`)) return;
    const li = document.querySelector(`li[data-key-id='${id}']`);
    if(li) {
        li.classList.add('fade-out');
    }
    
    setTimeout(async () => {
        const response = await fetch(`/middleware/api/keys/${id}`, { method: 'DELETE' });
        if(response.ok) {
            showToast(`Key "${name}" deleted.`);
            await fetchKeys();
            setActiveView(document.getElementById('global-overview-btn-li'), displayGlobalOverview);
        } else { 
            showToast('Failed to delete key.', true);
            if(li) li.classList.remove('fade-out');
        }
    }, 300);
}

function openImportExportModal() {
    document.getElementById('import-export-modal').classList.remove('hidden');
}

function closeImportExportModal() {
    document.getElementById('import-export-modal').classList.add('hidden');
}

async function exportKeys() {
    const response = await fetch('/middleware/api/keys/export');
    const keys = await response.json();
    const jsonString = JSON.stringify(keys, null, 2);
    
    try {
        await navigator.clipboard.writeText(jsonString);
        showToast('Keys copied to clipboard!');
    } catch (err) {
        console.error('Failed to copy keys: ', err);
        showToast('Failed to copy. See console for details.', true);
    }
}

async function importKeys() {
    const jsonString = document.getElementById('import-textarea').value;
    try {
        const keysData = JSON.parse(jsonString);
        const response = await fetch('/middleware/api/keys/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(keysData)
        });
        const result = await response.json();
        showToast(result.message);
        if (response.ok) {
            await fetchKeys();
            if (document.querySelector('.sidebar-item.active')?.id === 'global-overview-btn-li') {
                await displayGlobalOverview();
            }
            closeImportExportModal();
        }
    } catch (err) {
        console.error('Invalid JSON format:', err);
        showToast('Invalid JSON format. Please check your input.', true);
    }
}

function updateClock() {
    const clock = document.getElementById('live-clock');
    if (clock) {
        clock.textContent = new Date().toLocaleTimeString();
    }
}

// Initial setup and intervals
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('add-new-key-btn').addEventListener('click', () => openModal());
    document.getElementById('key-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('global-overview-btn-li').addEventListener('click', (e) => { e.preventDefault(); setActiveView(e.currentTarget, displayGlobalOverview); });
    document.getElementById('key-search').addEventListener('keyup', filterKeys);
    document.getElementById('status-filter')?.addEventListener('change', filterKeys);
    document.getElementById('apply-bulk-action').addEventListener('click', applyBulkAction);
    document.getElementById('keys-sidebar-list').addEventListener('change', updateBulkActionsMenu);
    document.getElementById('import-export-btn').addEventListener('click', openImportExportModal);
    document.getElementById('export-btn').addEventListener('click', exportKeys);
    document.getElementById('import-btn').addEventListener('click', importKeys);
    
    // Add ripple effect to all buttons
    document.addEventListener('click', (e) => {
        if (e.target.matches('button:not(:disabled)') || e.target.closest('button:not(:disabled)')) {
            const button = e.target.matches('button') ? e.target : e.target.closest('button');
            createRipple(e.target === button ? e : { 
                currentTarget: button, 
                clientX: e.clientX, 
                clientY: e.clientY 
            });
        }
    });
    
    // Close modals on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const keyModal = document.getElementById('key-modal');
            const importModal = document.getElementById('import-export-modal');
            if (!keyModal.classList.contains('hidden')) closeModal();
            if (!importModal.classList.contains('hidden')) closeImportExportModal();
        }
    });
    
    // Close modals on backdrop click
    document.getElementById('key-modal').addEventListener('click', (e) => {
        if (e.target.id === 'key-modal') closeModal();
    });
    document.getElementById('import-export-modal').addEventListener('click', (e) => {
        if (e.target.id === 'import-export-modal') closeImportExportModal();
    });
    
    fetchKeys();
    setActiveView(document.getElementById('global-overview-btn-li'), displayGlobalOverview);

    setInterval(async () => {
        await fetchKeys();
        if (document.querySelector('.sidebar-item.active')?.id === 'global-overview-btn-li') {
            await updateGlobalData();
        }
    }, 5000);
    setInterval(fetchLogs, 2000);
    setInterval(updateClock, 1000);
});
