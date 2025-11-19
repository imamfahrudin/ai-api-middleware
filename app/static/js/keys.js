// Key Management Page JavaScript
let allKeys = [];
let filteredKeys = [];
let currentPage = 1;
let keysPerPage = 10;
let selectedKeys = new Set();
let metricsCharts = {};
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

function formatKeyDisplay(keyValue) {
    return keyValue.length > 12 ? `${keyValue.slice(0, 4)}...${keyValue.slice(-4)}` : keyValue;
}

function formatDate(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

async function fetchKeys() {
    showLoadingState();
    try {
        const response = await fetch('/middleware/api/keys');
        if (!response.ok) {
            throw new Error('Failed to fetch keys');
        }
        allKeys = await response.json();
        filteredKeys = [...allKeys];
        updateTotalCount();
        filterAndDisplayKeys();
    } catch (error) {
        console.error('Error fetching keys:', error);
        showToast('Failed to load keys', true);
        showErrorState();
    }
}

function updateTotalCount() {
    document.getElementById('total-keys-count').textContent = allKeys.length;
}

function filterAndDisplayKeys() {
    const query = document.getElementById('key-search').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;

    filteredKeys = allKeys.filter(key => {
        const matchesName = key.name.toLowerCase().includes(query);
        const matchesValue = key.key_value.toLowerCase().includes(query);
        const matchesStatus = statusFilter === 'all' || key.status === statusFilter;

        return (matchesName || matchesValue) && matchesStatus;
    });

    currentPage = 1;
    displayKeys();
}

function displayKeys() {
    const tbody = document.getElementById('keys-table-body');
    const startIndex = (currentPage - 1) * keysPerPage;
    const endIndex = startIndex + keysPerPage;
    const keysToDisplay = filteredKeys.slice(startIndex, endIndex);

    if (keysToDisplay.length === 0) {
        showEmptyState();
        return;
    }

    hideEmptyStates();

    tbody.innerHTML = keysToDisplay.map(key => `
        <tr class="hover:bg-gray-700 transition-colors">
            <td class="px-6 py-4">
                <input type="checkbox"
                       class="key-checkbox rounded border-gray-600 bg-gray-600 text-blue-500 focus:ring-blue-500"
                       data-id="${key.id}"
                       ${selectedKeys.has(key.id) ? 'checked' : ''}>
            </td>
            <td class="px-6 py-4">
                <button onclick="showKeyMetrics(${key.id}, '${key.name.replace(/'/g, "\\'")}')"
                        class="font-medium text-blue-400 hover:text-blue-300 text-left transition-colors">
                    ${key.name}
                </button>
                ${key.note ? `<div class="text-sm text-gray-400">${key.note}</div>` : ''}
            </td>
            <td class="px-6 py-4">
                <div class="font-mono text-sm">${formatKeyDisplay(key.key_value)}</div>
            </td>
            <td class="px-6 py-4">
                <span class="px-2 py-1 text-xs font-medium rounded-full ${
                    key.priority <= 3 ? 'bg-green-600' :
                    key.priority <= 6 ? 'bg-yellow-600' :
                    key.priority <= 9 ? 'bg-orange-600' : 'bg-gray-600'
                } text-white">
                    ${key.priority}
                </span>
            </td>
            <td class="px-6 py-4">
                ${getStatusBadge(key.status)}
            </td>
            <td class="px-6 py-4">
                <div class="text-sm">${key.usage_today || 0}</div>
            </td>
            <td class="px-6 py-4">
                <div class="text-sm">${key.total_usage || 0}</div>
            </td>
            <td class="px-6 py-4">
                <div class="text-sm">${formatDate(key.last_used)}</div>
            </td>
            <td class="px-6 py-4">
                <div class="flex space-x-2">
                    <button onclick="openModal(true, ${key.id}, '${key.name.replace(/'/g, "\\'")}')"
                            class="text-blue-400 hover:text-blue-300 transition-colors"
                            title="Edit">
                        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L15.232 5.232z" />
                        </svg>
                    </button>
                    <button onclick="removeKey(${key.id}, '${key.name.replace(/'/g, "\\'")}')"
                            class="text-red-400 hover:text-red-300 transition-colors"
                            title="Delete">
                        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');

    updatePagination();
    updateBulkActions();
}

function updatePagination() {
    const totalPages = Math.ceil(filteredKeys.length / keysPerPage);
    const startIndex = (currentPage - 1) * keysPerPage + 1;
    const endIndex = Math.min(currentPage * keysPerPage, filteredKeys.length);

    document.getElementById('showing-from').textContent = filteredKeys.length > 0 ? startIndex : 0;
    document.getElementById('showing-to').textContent = endIndex;
    document.getElementById('showing-total').textContent = filteredKeys.length;
    document.getElementById('currentPage').textContent = currentPage;
    document.getElementById('totalPages').textContent = totalPages;

    const prevBtn = document.getElementById('prev-page-btn');
    const nextBtn = document.getElementById('next-page-btn');

    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages || totalPages === 0;
}

function changePage(direction) {
    const totalPages = Math.ceil(filteredKeys.length / keysPerPage);
    const newPage = currentPage + direction;

    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        displayKeys();
    }
}

function updateBulkActions() {
    const selectedCount = selectedKeys.size;
    const bulkContainer = document.getElementById('bulk-actions-container');

    if (selectedCount > 0) {
        bulkContainer.classList.remove('hidden');
    } else {
        bulkContainer.classList.add('hidden');
    }
}

function selectAllKeys() {
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const keyCheckboxes = document.querySelectorAll('.key-checkbox');

    keyCheckboxes.forEach(checkbox => {
        const keyId = parseInt(checkbox.dataset.id);
        checkbox.checked = selectAllCheckbox.checked;

        if (selectAllCheckbox.checked) {
            selectedKeys.add(keyId);
        } else {
            selectedKeys.delete(keyId);
        }
    });

    updateBulkActions();
}

function toggleKeySelection(keyId) {
    if (selectedKeys.has(keyId)) {
        selectedKeys.delete(keyId);
    } else {
        selectedKeys.add(keyId);
    }
    updateBulkActions();
}

async function applyBulkAction() {
    const action = document.getElementById('bulk-action-select').value;
    if (!action) return;

    if (selectedKeys.size === 0) {
        showToast('No keys selected', true);
        return;
    }

    if (action === 'delete') {
        if (!confirm(`Delete ${selectedKeys.size} selected key(s)? This is permanent.`)) return;
    }

    try {
        const response = await fetch('/middleware/api/keys/bulk-action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                key_ids: Array.from(selectedKeys),
                status: action === 'delete' ? null : action
            })
        });

        const result = await response.json();
        showToast(result.message, !response.ok);

        if (response.ok) {
            selectedKeys.clear();
            await fetchKeys();
            document.getElementById('select-all-checkbox').checked = false;
        }
    } catch (error) {
        console.error('Error applying bulk action:', error);
        showToast('Failed to apply bulk action', true);
    }
}

// Modal functions
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
        document.getElementById('key-status').value = details.status;
        document.getElementById('key-priority').value = details.priority || 1;
    } else {
        noteInput.value = '';
        document.getElementById('key-status').value = 'Healthy';
        document.getElementById('key-priority').value = 1;
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
    const name = nameInput.value.trim();
    const value = valueInput.value.trim();
    const note = document.getElementById('key-note').value.trim();
    const status = document.getElementById('key-status').value;
    const isEdit = !!id;

    // Basic validation
    if (!name) {
        nameInput.classList.add('shake');
        showToast('Name is required!', true);
        setTimeout(() => nameInput.classList.remove('shake'), 500);
        nameInput.focus();
        return;
    }

    if (!isEdit && !value) {
        valueInput.classList.add('shake');
        showToast('Key value is required!', true);
        setTimeout(() => valueInput.classList.remove('shake'), 500);
        valueInput.focus();
        return;
    }

    const url = isEdit ? `/middleware/api/keys/${id}` : '/middleware/api/keys';
    const method = isEdit ? 'PUT' : 'POST';
    const priority = document.getElementById('key-priority').value;
    const body = JSON.stringify({ name, key: value || null, status: isEdit ? status : null, note, priority: parseInt(priority) || 1 });

    try {
        const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body });
        const result = await response.json();
        showToast(result.message, !response.ok);

        if(response.ok) {
            closeModal();
            await fetchKeys();
        }
    } catch (error) {
        console.error('Error saving key:', error);
        showToast('Failed to save key', true);
    }
}

async function removeKey(id, name) {
    if (!confirm(`Delete key "${name}"? This is permanent.`)) return;

    try {
        const response = await fetch(`/middleware/api/keys/${id}`, { method: 'DELETE' });
        const result = await response.json();

        if(response.ok) {
            showToast(result.message);
            await fetchKeys();
        } else {
            showToast(result.message, true);
        }
    } catch (error) {
        console.error('Error deleting key:', error);
        showToast('Failed to delete key', true);
    }
}

// Import/Export functions
function openImportExportModal() {
    document.getElementById('import-export-modal').classList.remove('hidden');
}

function closeImportExportModal() {
    document.getElementById('import-export-modal').classList.add('hidden');
    document.getElementById('import-textarea').value = '';
}

async function exportKeys() {
    try {
        const response = await fetch('/middleware/api/keys/export');
        const keys = await response.json();
        const jsonString = JSON.stringify(keys, null, 2);

        await navigator.clipboard.writeText(jsonString);
        showToast('Keys copied to clipboard!');
    } catch (error) {
        console.error('Failed to export keys:', error);
        showToast('Failed to copy keys to clipboard', true);
    }
}

async function importKeys() {
    const jsonString = document.getElementById('import-textarea').value.trim();

    if (!jsonString) {
        showToast('Please paste JSON data first', true);
        return;
    }

    try {
        const keysData = JSON.parse(jsonString);

        if (!Array.isArray(keysData)) {
            throw new Error('Data must be an array');
        }

        const response = await fetch('/middleware/api/keys/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(keysData)
        });

        const result = await response.json();
        showToast(result.message, !response.ok);

        if (response.ok) {
            await fetchKeys();
            closeImportExportModal();
        }
    } catch (error) {
        console.error('Invalid JSON format:', error);
        showToast('Invalid JSON format. Please check your input.', true);
    }
}

// Toast notification
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `fixed bottom-8 right-8 py-3 px-6 rounded-lg shadow-xl z-50 pointer-events-none transition-all duration-300 ${
        isError ? 'bg-red-600' : 'bg-green-600'
    } text-white`;

    toast.classList.remove('opacity-0', 'translate-y-4');
    toast.classList.add('opacity-100', 'translate-y-0');

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-4');
        toast.classList.remove('opacity-100', 'translate-y-0');
    }, 3000);
}

// State management
function showLoadingState() {
    document.getElementById('loading-state').classList.remove('hidden');
    document.getElementById('empty-state').classList.add('hidden');
    document.querySelector('.bg-gray-800.rounded-lg.overflow-hidden').classList.add('hidden');
}

function hideEmptyStates() {
    document.getElementById('loading-state').classList.add('hidden');
    document.getElementById('empty-state').classList.add('hidden');
    document.querySelector('.bg-gray-800.rounded-lg.overflow-hidden').classList.remove('hidden');
}

function showEmptyState() {
    document.getElementById('loading-state').classList.add('hidden');
    document.getElementById('empty-state').classList.remove('hidden');
    document.querySelector('.bg-gray-800.rounded-lg.overflow-hidden').classList.add('hidden');
}

function showErrorState() {
    showEmptyState();
    const emptyState = document.getElementById('empty-state');
    emptyState.querySelector('h3').textContent = 'Error Loading Keys';
    emptyState.querySelector('p').textContent = 'Please try refreshing the page.';
}

// Key Metrics Functions
async function showKeyMetrics(keyId, keyName) {
    document.getElementById('metrics-modal-title').textContent = `${keyName} - Analytics`;
    document.getElementById('key-metrics-modal').classList.remove('hidden');

    // Destroy existing charts
    Object.keys(metricsCharts).forEach(chartId => {
        if (metricsCharts[chartId]) {
            metricsCharts[chartId].destroy();
            delete metricsCharts[chartId];
        }
    });

    try {
        const [statsResponse, detailsResponse] = await Promise.all([
            fetch(`/middleware/api/keys/${keyId}/stats`),
            fetch(`/middleware/api/keys/${keyId}`)
        ]);

        if (!statsResponse.ok || !detailsResponse.ok) {
            throw new Error('Failed to fetch key metrics');
        }

        const stats = await statsResponse.json();
        const details = await detailsResponse.json();

        // Update stats cards
        updateMetricsStatsCards(stats);

        // Update charts
        updateMetricsCharts(stats, details);

    } catch (error) {
        console.error('Error fetching key metrics:', error);
        showToast('Failed to load key metrics', true);
        closeMetricsModal();
    }
}

function closeMetricsModal() {
    document.getElementById('key-metrics-modal').classList.add('hidden');

    // Destroy all charts
    Object.keys(metricsCharts).forEach(chartId => {
        if (metricsCharts[chartId]) {
            metricsCharts[chartId].destroy();
            delete metricsCharts[chartId];
        }
    });
}

function updateMetricsStatsCards(stats) {
    const totalRequests = stats.total_requests || 0;
    const successRate = totalRequests > 0 ? ((stats.successful_requests || 0) / totalRequests * 100).toFixed(1) : 0;
    const avgLatency = stats.avg_latency ? stats.avg_latency.toFixed(0) : 0;
    const totalTokens = (stats.total_tokens_in || 0) + (stats.total_tokens_out || 0);

    document.getElementById('metrics-total-requests').textContent = totalRequests.toLocaleString();
    document.getElementById('metrics-success-rate').textContent = `${successRate}%`;
    document.getElementById('metrics-avg-latency').textContent = `${avgLatency}ms`;
    document.getElementById('metrics-total-tokens').textContent = totalTokens.toLocaleString();
}

function updateMetricsCharts(stats, details) {
    // Daily requests chart
    const dailyLabels = stats.daily_stats?.map(s => new Date(s.date + 'T00:00:00Z').toLocaleDateString()) || [];
    const dailyData = stats.daily_stats?.map(s => s.total_requests || 0) || [];
    updateChart('metrics-requests-chart', 'line', 'Daily Requests (Last 7 Days)', dailyLabels.slice(-7), [{
        label: 'Requests',
        data: dailyData.slice(-7),
        borderColor: CHART_COLORS.blue,
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
        fill: true
    }]);

    // Model usage pie chart
    const modelUsage = stats.model_usage || {};
    const modelLabels = Object.keys(modelUsage);
    const modelData = Object.values(modelUsage);
    updatePieChart('metrics-models-chart', 'Model Usage', modelLabels, modelData);

    // Error types pie chart
    const errorTypes = stats.error_types || {};
    const errorLabels = Object.keys(errorTypes);
    const errorData = Object.values(errorTypes);
    updatePieChart('metrics-errors-chart', 'Error Types', errorLabels, errorData);

    // Latency trend chart
    const latencyLabels = stats.daily_stats?.map(s => new Date(s.date + 'T00:00:00Z').toLocaleDateString()) || [];
    const latencyData = stats.daily_stats?.map(s => s.avg_latency || 0) || [];
    updateChart('metrics-latency-chart', 'line', 'Average Latency (Last 7 Days)', latencyLabels.slice(-7), [{
        label: 'Latency (ms)',
        data: latencyData.slice(-7),
        borderColor: CHART_COLORS.orange,
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        tension: 0.4,
        fill: true
    }]);
}

function updateChart(canvasId, type, title, labels, datasets) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;

    const textColor = '#e5e7eb';
    const gridColor = '#4b5563';

    if (metricsCharts[canvasId]) {
        metricsCharts[canvasId].data.labels = labels;
        metricsCharts[canvasId].data.datasets = datasets;
        metricsCharts[canvasId].update('none');
        return;
    }

    metricsCharts[canvasId] = new Chart(ctx, {
        type,
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: title, color: textColor, font: { size: 14 } },
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: textColor },
                    grid: { color: gridColor }
                },
                y: {
                    ticks: { color: textColor },
                    grid: { color: gridColor }
                }
            }
        }
    });
}

function updatePieChart(canvasId, title, labels, data) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return;

    const textColor = '#e5e7eb';
    
    // Special color mapping for different chart types
    let colors;
    if (canvasId === 'metrics-errors-chart') {
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

    if (metricsCharts[canvasId]) {
        metricsCharts[canvasId].data.labels = labels;
        metricsCharts[canvasId].data.datasets[0].data = data;
        metricsCharts[canvasId].update('none');
        return;
    }

    metricsCharts[canvasId] = new Chart(ctx, {
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

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Add event listeners
    document.getElementById('add-new-key-btn').addEventListener('click', () => openModal());
    document.getElementById('add-first-key-btn')?.addEventListener('click', () => openModal());
    document.getElementById('key-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('key-search').addEventListener('keyup', debounce(filterAndDisplayKeys, 300));
    document.getElementById('status-filter').addEventListener('change', filterAndDisplayKeys);
    document.getElementById('select-all-checkbox').addEventListener('change', selectAllKeys);
    document.getElementById('apply-bulk-action').addEventListener('click', applyBulkAction);
    document.getElementById('import-export-btn').addEventListener('click', openImportExportModal);
    document.getElementById('export-btn').addEventListener('click', exportKeys);
    document.getElementById('import-btn').addEventListener('click', importKeys);
    document.getElementById('prev-page-btn').addEventListener('click', () => changePage(-1));
    document.getElementById('next-page-btn').addEventListener('click', () => changePage(1));

    // Dynamic event listener for key checkboxes
    document.getElementById('keys-table-body').addEventListener('change', (e) => {
        if (e.target.classList.contains('key-checkbox')) {
            toggleKeySelection(parseInt(e.target.dataset.id));
        }
    });

    // Close modals on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            closeImportExportModal();
            closeMetricsModal();
        }
    });

    // Initial load
    fetchKeys();
});