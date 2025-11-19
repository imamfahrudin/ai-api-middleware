let globalState = { isLogHovered: false };

async function fetchLogs() {
    try {
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
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up log container hover detection
    const logContainer = document.getElementById('live-log-container');
    if(logContainer) {
        logContainer.addEventListener('mouseenter', () => globalState.isLogHovered = true);
        logContainer.addEventListener('mouseleave', () => globalState.isLogHovered = false);
    }

    // Initial load
    fetchLogs();

    // Set up interval for live updates
    setInterval(fetchLogs, 2000);
});