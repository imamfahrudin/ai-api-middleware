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

// Debounce utility function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

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

async function displayMCPMonitoring() {
    // Destroy old charts to prevent conflicts when switching views
    Object.keys(charts).forEach(id => {
        if (charts[id]) {
            charts[id].destroy();
            delete charts[id];
        }
    });

    document.getElementById('dashboard-content').innerHTML = `
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold">MCP (Model Context Protocol) Monitoring</h1>
            <div class="flex gap-2">
                <button id="mcp-manage-servers-btn" class="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded flex items-center gap-2">
                    <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Manage Servers
                </button>
                <button id="mcp-reload-btn" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded flex items-center gap-2">
                    <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Reload Configuration
                </button>
            </div>
        </div>

        <!-- MCP Status Cards -->
        <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
            <div class="glass-card p-4" id="mcp-enabled-card"></div>
            <div class="glass-card p-4" id="mcp-servers-card"></div>
            <div class="glass-card p-4" id="mcp-tools-card"></div>
            <div class="glass-card p-4" id="mcp-requests-card"></div>
        </div>

        <!-- Charts Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <div class="glass-card p-4 h-[28rem]">
                <canvas id="mcpUsageChart"></canvas>
            </div>
            <div class="glass-card p-4 h-[28rem]">
                <canvas id="mcpToolsChart"></canvas>
            </div>
        </div>

        <!-- Server Health Section -->
        <div class="glass-card p-4 mb-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold">MCP Server Health</h2>
                <button id="mcp-add-server-btn" class="bg-green-600 hover:bg-green-700 text-white text-sm font-bold py-2 px-4 rounded flex items-center gap-2">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                    </svg>
                    Add Server
                </button>
            </div>
            <div id="mcp-servers-container" class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                <div class="text-center text-gray-400">Loading server health information...</div>
            </div>
        </div>

        <!-- Recent Tool Calls -->
        <div class="glass-card p-4">
            <h2 class="text-xl font-bold mb-4">Recent Tool Calls</h2>
            <div id="mcp-recent-calls" class="space-y-2 max-h-64 overflow-y-auto">
                <div class="text-center text-gray-400">Loading recent tool calls...</div>
            </div>
        </div>
    `;

    // Add event listener for manage servers button
    document.getElementById('mcp-manage-servers-btn').addEventListener('click', () => {
        openMCPServerModal();
    });

    // Add event listener for add server button
    document.getElementById('mcp-add-server-btn').addEventListener('click', () => {
        openMCPServerModal();
    });

    // Add event listener for reload button
    document.getElementById('mcp-reload-btn').addEventListener('click', async () => {
        const btn = document.getElementById('mcp-reload-btn');
        btn.disabled = true;
        btn.innerHTML = `
            <svg class="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Reloading...
        `;

        try {
            const response = await fetch('/middleware/api/mcp/reload', { method: 'POST' });
            const result = await response.json();
            showToast(result.message, !response.ok);
            if (response.ok) {
                await updateMCPData();
            }
        } catch (error) {
            showToast('Failed to reload MCP configuration', true);
            console.error('MCP reload error:', error);
        } finally {
            btn.disabled = false;
            btn.innerHTML = `
                <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Reload Configuration
            `;
        }
    });

    await updateMCPData();
}

async function updateMCPData() {
    try {
        // Get MCP statistics and health
        const [statsResponse, healthResponse] = await Promise.all([
            fetch('/middleware/api/mcp/stats'),
            fetch('/middleware/api/mcp/health')
        ]);

        const stats = await statsResponse.json();
        const health = await healthResponse.json();

        // Update status cards
        updateMCPStatusCards(stats, health);

        // Update charts
        updateMCPCharts(stats);

        // Update server health
        updateMCPServerHealth(health);

        // Update recent calls (placeholder for now)
        updateMCPRecentCalls();

    } catch (error) {
        console.error('Failed to update MCP data:', error);
        document.getElementById('dashboard-content').innerHTML = `
            <div class="text-center text-gray-400 p-8">
                <h2 class="text-2xl font-bold mb-4">MCP Monitoring Error</h2>
                <p>Failed to load MCP data. Please check if MCP is properly configured.</p>
                <p class="text-sm mt-2">${error.message}</p>
            </div>
        `;
    }
}

function updateMCPStatusCards(stats, health) {
    // MCP Enabled Status
    const enabledCard = document.getElementById('mcp-enabled-card');
    const enabled = health.enabled || false;
    const enabledColor = enabled ? 'text-green-400' : 'text-gray-400';
    const enabledStatus = enabled ? 'Enabled' : 'Disabled';
    enabledCard.innerHTML = `
        <div class="text-gray-400 text-sm">MCP Status</div>
        <div class="text-2xl font-bold ${enabledColor}">${enabledStatus}</div>
        <div class="text-xs text-gray-500 mt-1">${health.error || 'System operational'}</div>
    `;

    // Servers Status
    const serversCard = document.getElementById('mcp-servers-card');
    const serverStats = health.statistics?.servers || {};
    serversCard.innerHTML = `
        <div class="text-gray-400 text-sm">Active Servers</div>
        <div class="text-2xl font-bold text-blue-400">${serverStats.active || 0}/${serverStats.total || 0}</div>
        <div class="text-xs text-gray-500 mt-1">${serverStats.connected || 0} connected</div>
    `;

    // Tools Status
    const toolsCard = document.getElementById('mcp-tools-card');
    const totalTools = stats.summary?.total_tools || 0;
    toolsCard.innerHTML = `
        <div class="text-gray-400 text-sm">Available Tools</div>
        <div class="text-2xl font-bold text-purple-400">${totalTools}</div>
        <div class="text-xs text-gray-500 mt-1">${Object.keys(stats.tool_categories || {}).length} categories</div>
    `;

    // Requests Status
    const requestsCard = document.getElementById('mcp-requests-card');
    const totalRequests = stats.summary?.total_calls || 0;
    const successRate = stats.summary?.success_rate || 0;
    requestsCard.innerHTML = `
        <div class="text-gray-400 text-sm">Tool Calls (7d)</div>
        <div class="text-2xl font-bold text-yellow-400">${totalRequests.toLocaleString()}</div>
        <div class="text-xs text-gray-500 mt-1">${successRate.toFixed(1)}% success rate</div>
    `;
}

function updateMCPCharts(stats) {
    // Usage over time chart
    const usageByDay = stats.usage_by_day || [];
    const usageLabels = usageByDay.map(u => new Date(u.usage_date).toLocaleDateString());
    const usageData = usageByDay.map(u => u.total_calls || 0);

    updateChart('mcpUsageChart', 'line', 'MCP Tool Usage (Last 7 Days)', usageLabels, [
        { label: 'Tool Calls', data: usageData, borderColor: CHART_COLORS.blue, backgroundColor: CHART_COLORS.blue + '20' }
    ]);

    // Tools by category chart
    const categories = Object.keys(stats.tool_categories || {});
    const categoryData = Object.values(stats.tool_categories || {});

    updatePieChart('mcpToolsChart', 'Tools by Category', categories, categoryData);
}

function updateMCPServerHealth(health) {
    const container = document.getElementById('mcp-servers-container');
    const servers = health.servers || [];

    if (servers.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-400">No MCP servers configured</div>';
        return;
    }

    container.innerHTML = servers.map(server => {
        const statusColor = server.status === 'Active' ? 'text-green-400' :
                           server.status === 'Inactive' ? 'text-yellow-400' : 'text-red-400';
        const statusIcon = server.status === 'Active' ? '✓' :
                           server.status === 'Inactive' ? '⚠' : '✗';

        return `
            <div class="glass-card p-4">
                <div class="flex justify-between items-start mb-2">
                    <h3 class="font-bold text-white">${server.name}</h3>
                    <span class="${statusColor} text-lg">${statusIcon}</span>
                </div>
                <div class="text-sm text-gray-400 mb-2">${server.url}</div>
                <div class="text-xs mb-3">
                    <span class="${statusColor}">Status: ${server.status}</span>
                    ${server.last_check ? `<br>Last check: ${new Date(server.last_check).toLocaleTimeString()}` : ''}
                </div>
                <div class="flex gap-2">
                    <button onclick="editMCPServer('${server.id}')" class="text-blue-400 hover:text-blue-300 text-xs font-medium">
                        <svg class="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Edit
                    </button>
                    <button onclick="testMCPServerConnection('${server.id}')" class="text-green-400 hover:text-green-300 text-xs font-medium">
                        <svg class="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Test
                    </button>
                    <button onclick="deleteMCPServer('${server.id}')" class="text-red-400 hover:text-red-300 text-xs font-medium">
                        <svg class="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        Delete
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function updateMCPRecentCalls() {
    // Placeholder for recent calls - would need additional API endpoint
    const container = document.getElementById('mcp-recent-calls');
    container.innerHTML = `
        <div class="text-center text-gray-400 text-sm">
            <p>Recent tool calls will appear here</p>
            <p class="text-xs mt-1">(Detailed call history requires additional logging)</p>
        </div>
    `;
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

// MCP Server Management Functions
function openMCPServerModal() {
    document.getElementById('mcp-server-modal').classList.remove('hidden');
    updateAuthFields();
}

function closeMCPServerModal() {
    document.getElementById('mcp-server-modal').classList.add('hidden');
    document.getElementById('mcp-server-form').reset();
    document.getElementById('mcp-server-id').value = '';
    updateAuthFields();
}

function updateAuthFields() {
    const authType = document.getElementById('mcp-auth-type').value;
    const authCredentials = document.getElementById('mcp-auth-credentials');

    authCredentials.innerHTML = '';

    if (authType === 'bearer') {
        authCredentials.innerHTML = `
            <div>
                <label for="mcp-bearer-token" class="block mb-2 text-sm font-medium">Bearer Token</label>
                <input type="password" id="mcp-bearer-token"
                    class="w-full bg-gray-700 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter Bearer token">
            </div>
        `;
    } else if (authType === 'api_key') {
        authCredentials.innerHTML = `
            <div>
                <label for="mcp-api-key" class="block mb-2 text-sm font-medium">API Key</label>
                <input type="password" id="mcp-api-key"
                    class="w-full bg-gray-700 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter API key">
            </div>
            <div>
                <label for="mcp-api-key-header" class="block mb-2 text-sm font-medium">Header Name</label>
                <input type="text" id="mcp-api-key-header" value="X-API-Key"
                    class="w-full bg-gray-700 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Header name (e.g., X-API-Key)">
            </div>
        `;
    } else if (authType === 'oauth') {
        authCredentials.innerHTML = `
            <div>
                <label for="mcp-client-id" class="block mb-2 text-sm font-medium">Client ID</label>
                <input type="text" id="mcp-client-id"
                    class="w-full bg-gray-700 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter OAuth client ID">
            </div>
            <div>
                <label for="mcp-client-secret" class="block mb-2 text-sm font-medium">Client Secret</label>
                <input type="password" id="mcp-client-secret"
                    class="w-full bg-gray-700 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter OAuth client secret">
            </div>
            <div>
                <label for="mcp-token-url" class="block mb-2 text-sm font-medium">Token URL</label>
                <input type="url" id="mcp-token-url"
                    class="w-full bg-gray-700 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://oauth.example.com/token">
            </div>
        `;
    }
}

async function testMCPConnection() {
    const serverId = document.getElementById('mcp-server-id').value;
    const name = document.getElementById('mcp-server-name').value;
    const url = document.getElementById('mcp-server-url').value;
    const authType = document.getElementById('mcp-auth-type').value;
    const timeout = parseInt(document.getElementById('mcp-timeout').value);

    if (!name || !url) {
        showToast('Please fill in server name and URL', true);
        return;
    }

    const authCredentials = {};
    if (authType === 'bearer') {
        authCredentials.token = document.getElementById('mcp-bearer-token')?.value;
    } else if (authType === 'api_key') {
        authCredentials.key = document.getElementById('mcp-api-key')?.value;
        authCredentials.header = document.getElementById('mcp-api-key-header')?.value || 'X-API-Key';
    } else if (authType === 'oauth') {
        authCredentials.client_id = document.getElementById('mcp-client-id')?.value;
        authCredentials.client_secret = document.getElementById('mcp-client-secret')?.value;
        authCredentials.token_url = document.getElementById('mcp-token-url')?.value;
    }

    const testBtn = document.getElementById('test-connection-btn');
    const originalText = testBtn.innerHTML;
    testBtn.disabled = true;
    testBtn.innerHTML = '<div class="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div> Testing...';

    try {
        const response = await fetch('/middleware/api/mcp/servers/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                url,
                auth_type: authType,
                auth_credentials: authCredentials,
                timeout
            })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            showToast('Connection test successful!');
            updateServerDetails(result.server_info);
            if (result.available_tools) {
                updateToolsList(result.available_tools);
            }
        } else {
            showToast(result.error || 'Connection test failed', true);
        }
    } catch (error) {
        showToast('Connection test failed: ' + error.message, true);
    } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = originalText;
    }
}

function updateServerDetails(serverInfo) {
    const detailsDiv = document.getElementById('mcp-server-details');
    detailsDiv.innerHTML = `
        <div class="space-y-2">
            <p><strong>Name:</strong> ${serverInfo.name}</p>
            <p><strong>URL:</strong> ${serverInfo.url}</p>
            <p><strong>Protocol:</strong> ${serverInfo.protocol || 'WebSocket/HTTP'}</p>
            <p><strong>Authentication:</strong> ${serverInfo.auth_type || 'None'}</p>
            <p><strong>Status:</strong> <span class="text-green-400">Connected</span></p>
            <p><strong>Database Status:</strong> <span class="text-blue-400">Active</span></p>
        </div>
    `;
}

function updateToolsList(tools) {
    const toolsList = document.getElementById('mcp-tools-list');
    if (tools && tools.length > 0) {
        toolsList.innerHTML = tools.map(tool => `
            <div class="bg-gray-800 rounded p-3 border border-gray-600">
                <div class="font-semibold text-white mb-1">${tool.name}</div>
                <div class="text-sm text-gray-400 mb-2">${tool.description || 'No description'}</div>
                <div class="text-xs text-gray-500">
                    <span class="font-mono">${tool.input_schema ? JSON.stringify(tool.input_schema).slice(0, 100) + '...' : 'No parameters'}</span>
                </div>
            </div>
        `).join('');
    } else {
        toolsList.innerHTML = '<p class="text-sm text-gray-400">No tools available</p>';
    }
}

async function refreshMCPTools() {
    const testBtn = document.getElementById('refresh-tools-btn');
    const originalText = testBtn.innerHTML;
    testBtn.disabled = true;
    testBtn.innerHTML = '<div class="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div> Refreshing...';

    try {
        await testMCPConnection(); // Re-run connection test to refresh tools
    } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = originalText;
    }
}

async function saveMCPServer() {
    const serverId = document.getElementById('mcp-server-id').value;
    const name = document.getElementById('mcp-server-name').value;
    const url = document.getElementById('mcp-server-url').value;
    const authType = document.getElementById('mcp-auth-type').value;
    const timeout = parseInt(document.getElementById('mcp-timeout').value);
    const maxConcurrent = parseInt(document.getElementById('mcp-max-concurrent').value);
    const healthUrl = document.getElementById('mcp-health-url').value;
    const status = document.getElementById('mcp-server-status').value;

    if (!name || !url) {
        showToast('Please fill in server name and URL', true);
        return;
    }

    const authCredentials = {};
    if (authType === 'bearer') {
        authCredentials.token = document.getElementById('mcp-bearer-token')?.value;
    } else if (authType === 'api_key') {
        authCredentials.key = document.getElementById('mcp-api-key')?.value;
        authCredentials.header = document.getElementById('mcp-api-key-header')?.value || 'X-API-Key';
    } else if (authType === 'oauth') {
        authCredentials.client_id = document.getElementById('mcp-client-id')?.value;
        authCredentials.client_secret = document.getElementById('mcp-client-secret')?.value;
        authCredentials.token_url = document.getElementById('mcp-token-url')?.value;
    }

    const serverData = {
        name,
        url,
        auth_type: authType,
        auth_credentials: authCredentials,
        timeout,
        max_concurrent: maxConcurrent,
        health_check_url: healthUrl,
        status
    };

    try {
        const url = serverId ? `/middleware/api/mcp/servers/${serverId}` : '/middleware/api/mcp/servers';
        const method = serverId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(serverData)
        });

        const result = await response.json();

        if (response.ok) {
            showToast(serverId ? 'MCP server updated successfully!' : 'MCP server created successfully!');
            closeMCPServerModal();
            // Refresh MCP monitoring if it's currently active
            if (document.querySelector('.sidebar-item.active')?.id === 'mcp-btn-li') {
                await displayMCPMonitoring();
            }
        } else {
            showToast(result.error || 'Failed to save MCP server', true);
        }
    } catch (error) {
        showToast('Failed to save MCP server: ' + error.message, true);
    }
}

async function editMCPServer(serverId) {
    try {
        const response = await fetch(`/middleware/api/mcp/servers/${serverId}`);
        const server = await response.json();

        if (response.ok) {
            // Populate modal with server data
            document.getElementById('mcp-server-id').value = server.id;
            document.getElementById('mcp-server-name').value = server.name;
            document.getElementById('mcp-server-url').value = server.url;
            document.getElementById('mcp-auth-type').value = server.auth_type || 'none';
            document.getElementById('mcp-timeout').value = server.timeout || 30;
            document.getElementById('mcp-max-concurrent').value = server.max_concurrent || 10;
            document.getElementById('mcp-health-url').value = server.health_check_url || '';
            document.getElementById('mcp-server-status').value = server.status || 'Active';

            updateAuthFields();

            // Fill auth credentials
            if (server.auth_credentials) {
                if (server.auth_type === 'bearer') {
                    document.getElementById('mcp-bearer-token').value = server.auth_credentials.token || '';
                } else if (server.auth_type === 'api_key') {
                    document.getElementById('mcp-api-key').value = server.auth_credentials.key || '';
                    document.getElementById('mcp-api-key-header').value = server.auth_credentials.header || 'X-API-Key';
                } else if (server.auth_type === 'oauth') {
                    document.getElementById('mcp-client-id').value = server.auth_credentials.client_id || '';
                    document.getElementById('mcp-client-secret').value = server.auth_credentials.client_secret || '';
                    document.getElementById('mcp-token-url').value = server.auth_credentials.token_url || '';
                }
            }

            openMCPServerModal();
        } else {
            showToast('Failed to load server details', true);
        }
    } catch (error) {
        showToast('Failed to load server details: ' + error.message, true);
    }
}

async function testMCPServerConnection(serverId) {
    try {
        const response = await fetch(`/middleware/api/mcp/servers/${serverId}/test`, { method: 'POST' });
        const result = await response.json();

        if (response.ok && result.success) {
            showToast('Server connection test successful!');
            // Refresh server health display
            if (document.querySelector('.sidebar-item.active')?.id === 'mcp-btn-li') {
                await displayMCPMonitoring();
            }
        } else {
            showToast(result.error || 'Connection test failed', true);
        }
    } catch (error) {
        showToast('Connection test failed: ' + error.message, true);
    }
}

async function deleteMCPServer(serverId) {
    if (!confirm('Are you sure you want to delete this MCP server? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`/middleware/api/mcp/servers/${serverId}`, { method: 'DELETE' });
        const result = await response.json();

        if (response.ok) {
            showToast('MCP server deleted successfully!');
            // Refresh MCP monitoring if it's currently active
            if (document.querySelector('.sidebar-item.active')?.id === 'mcp-btn-li') {
                await displayMCPMonitoring();
            }
        } else {
            showToast(result.error || 'Failed to delete MCP server', true);
        }
    } catch (error) {
        showToast('Failed to delete MCP server: ' + error.message, true);
    }
}

// Initial setup and intervals
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('add-new-key-btn').addEventListener('click', () => openModal());
    document.getElementById('key-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('global-overview-btn-li').addEventListener('click', (e) => { e.preventDefault(); setActiveView(e.currentTarget, displayGlobalOverview); });
    document.getElementById('mcp-btn-li').addEventListener('click', (e) => { e.preventDefault(); setActiveView(e.currentTarget, displayMCPMonitoring); });
    document.getElementById('mcp-servers-btn-li').addEventListener('click', (e) => { e.preventDefault(); openMCPServerModal(); });
    document.getElementById('key-search').addEventListener('keyup', debounce(filterKeys, 300));
    document.getElementById('status-filter')?.addEventListener('change', filterKeys);
    document.getElementById('apply-bulk-action').addEventListener('click', applyBulkAction);
    document.getElementById('keys-sidebar-list').addEventListener('change', updateBulkActionsMenu);
    document.getElementById('import-export-btn').addEventListener('click', openImportExportModal);
    document.getElementById('export-btn').addEventListener('click', exportKeys);
    document.getElementById('import-btn').addEventListener('click', importKeys);

    // MCP Server Modal Event Listeners
    document.getElementById('mcp-server-form').addEventListener('submit', (e) => {
        e.preventDefault();
        saveMCPServer();
    });
    document.getElementById('test-connection-btn').addEventListener('click', testMCPConnection);
    document.getElementById('refresh-tools-btn').addEventListener('click', refreshMCPTools);
    
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
            const mcpModal = document.getElementById('mcp-server-modal');
            if (!keyModal.classList.contains('hidden')) closeModal();
            if (!importModal.classList.contains('hidden')) closeImportExportModal();
            if (!mcpModal.classList.contains('hidden')) closeMCPServerModal();
        }
    });
    
    // Close modals on backdrop click
    document.getElementById('key-modal').addEventListener('click', (e) => {
        if (e.target.id === 'key-modal') closeModal();
    });
    document.getElementById('import-export-modal').addEventListener('click', (e) => {
        if (e.target.id === 'import-export-modal') closeImportExportModal();
    });
    document.getElementById('mcp-server-modal').addEventListener('click', (e) => {
        if (e.target.id === 'mcp-server-modal') closeMCPServerModal();
    });
    
    fetchKeys();
    setActiveView(document.getElementById('global-overview-btn-li'), displayGlobalOverview);

    setInterval(async () => {
        await fetchKeys();
        if (document.querySelector('.sidebar-item.active')?.id === 'global-overview-btn-li') {
            await updateGlobalData();
        }
    }, 15000);
    setInterval(fetchLogs, 5000);
    setInterval(updateClock, 1000);
});
