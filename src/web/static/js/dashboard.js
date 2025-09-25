// Dashboard JavaScript
class Dashboard {
    constructor() {
        this.apiBase = '/api';
        this.ws = null;
        this.refreshInterval = null;
        this.init();
    }
    
    async init() {
        await this.loadSystemStatus();
        await this.loadAgents();
        await this.loadTasks();
        this.setupEventListeners();
        this.startAutoRefresh();
    }
    
    async loadSystemStatus() {
        try {
            const response = await fetch(`${this.apiBase}/status`);
            const data = await response.json();
            
            document.getElementById('agent-count').textContent = 
                Object.keys(data.agents || {}).length;
            document.getElementById('tool-count').textContent = 
                data.tools?.total_tools || 0;
            document.getElementById('memory-count').textContent = 
                data.memory?.total_memories || 0;
                
        } catch (error) {
            console.error('Failed to load system status:', error);
        }
    }
    
    async loadAgents() {
        try {
            const response = await fetch(`${this.apiBase}/agents`);
            const agents = await response.json();
            
            const agentsList = document.getElementById('agents-list');
            agentsList.innerHTML = '';
            
            agents.forEach(agent => {
                const card = this.createAgentCard(agent);
                agentsList.appendChild(card);
            });
            
        } catch (error) {
            console.error('Failed to load agents:', error);
        }
    }
    
    createAgentCard(agent) {
        const card = document.createElement('div');
        card.className = 'agent-card bg-white rounded-lg shadow p-4 mb-4';
        
        const statusClass = this.getStatusClass(agent.status);
        
        card.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-lg font-semibold text-gray-900">${agent.agent_id}</h3>
                    <p class="text-sm text-gray-600">${agent.type}</p>
                </div>
                <div class="flex items-center">
                    <span class="status-${statusClass} text-white px-2 py-1 rounded-full text-xs">
                        ${agent.status}
                    </span>
                </div>
            </div>
            <div class="mt-2">
                <p class="text-sm text-gray-600">Capabilities: ${agent.capabilities.join(', ')}</p>
                ${agent.current_task ? `<p class="text-sm text-gray-500">Current Task: ${agent.current_task}</p>` : ''}
            </div>
        `;
        
        return card;
    }
    
    getStatusClass(status) {
        switch (status) {
            case 'success':
            case 'completed':
                return 'active';
            case 'idle':
                return 'idle';
            case 'error':
                return 'error';
            default:
                return 'idle';
        }
    }
    
    async loadTasks() {
        try {
            const response = await fetch(`${this.apiBase}/tasks`);
            const tasks = await response.json();
            
            // Update task count
            const taskCount = tasks.summary?.task_count || 0;
            document.getElementById('task-count').textContent = taskCount;
            
        } catch (error) {
            console.error('Failed to load tasks:', error);
        }
    }
    
    setupEventListeners() {
        // Task form submission
        document.getElementById('task-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.submitTask();
        });
        
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshData();
        });
    }
    
    async submitTask() {
        const description = document.getElementById('task-description').value;
        const priority = document.getElementById('task-priority').value;
        
        if (!description.trim()) {
            this.showError('Please enter a task description');
            return;
        }
        
        const task = {
            id: `task_${Date.now()}`,
            description: description,
            priority: priority
        };
        
        try {
            this.addLog('Submitting task...', 'info');
            
            const response = await fetch(`${this.apiBase}/tasks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(task)
            });
            
            const result = await response.json();
            this.displayTaskResult(result);
            this.addLog(`Task completed: ${result.status}`, result.status === 'success' ? 'success' : 'error');
            
            // Refresh data
            await this.refreshData();
            
            // Clear form
            document.getElementById('task-description').value = '';
            
        } catch (error) {
            console.error('Failed to submit task:', error);
            this.showError('Failed to submit task: ' + error.message);
        }
    }
    
    displayTaskResult(result) {
        const container = document.getElementById('task-results');
        const div = document.createElement('div');
        div.className = `p-3 rounded-lg mb-2 ${result.status === 'success' ? 'bg-green-100' : 'bg-red-100'}`;
        div.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-sm font-medium">${result.task_id}</span>
                <span class="text-xs px-2 py-1 rounded ${result.status === 'success' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}">
                    ${result.status}
                </span>
            </div>
        `;
        container.appendChild(div);
        
        // Keep only last 5 results
        while (container.children.length > 5) {
            container.removeChild(container.firstChild);
        }
    }
    
    addLog(message, type = 'info') {
        const container = document.getElementById('logs-container');
        const div = document.createElement('div');
        div.className = `text-sm mb-1 ${type === 'error' ? 'text-red-600' : type === 'success' ? 'text-green-600' : 'text-blue-600'}`;
        div.innerHTML = `<span class="text-gray-500">[${new Date().toLocaleTimeString()}]</span> ${message}`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        
        // Keep only last 100 logs
        while (container.children.length > 100) {
            container.removeChild(container.firstChild);
        }
    }
    
    showError(message) {
        this.addLog(message, 'error');
    }
    
    async refreshData() {
        await this.loadSystemStatus();
        await this.loadAgents();
        await this.loadTasks();
    }
    
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.refreshData();
        }, 5000); // Refresh every 5 seconds
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new Dashboard();
});