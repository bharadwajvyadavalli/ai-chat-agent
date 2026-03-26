/**
 * Chat Application JavaScript
 * Handles SSE streaming, tool visualization, and UI interactions
 */

class ChatApp {
    constructor() {
        this.conversationId = null;
        this.isStreaming = false;
        this.theme = localStorage.getItem('theme') || 'light';

        this.initElements();
        this.initEventListeners();
        this.loadConversations();
        this.applyTheme();
    }

    initElements() {
        this.chatForm = document.getElementById('chat-form');
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.chatMessages = document.getElementById('chat-messages');
        this.welcome = document.getElementById('welcome');
        this.conversationList = document.getElementById('conversation-list');
        this.chatTitle = document.getElementById('chat-title');
        this.status = document.getElementById('status');
        this.infoPanel = document.getElementById('info-panel');
        this.infoPanelContent = document.getElementById('info-panel-content');
        this.infoPanelTitle = document.getElementById('info-panel-title');
        this.newChatBtn = document.getElementById('new-chat-btn');
        this.themeToggle = document.getElementById('theme-toggle');
        this.sidebarToggle = document.getElementById('sidebar-toggle');
        this.sidebar = document.getElementById('sidebar');
        this.closeInfoPanel = document.getElementById('close-info-panel');
    }

    initEventListeners() {
        // Chat form submission
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 200) + 'px';
        });

        // Enter to send (Shift+Enter for newline)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // New chat button
        this.newChatBtn.addEventListener('click', () => this.createNewChat());

        // Theme toggle
        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        // Sidebar toggle (mobile)
        this.sidebarToggle.addEventListener('click', () => this.toggleSidebar());

        // Close info panel
        this.closeInfoPanel.addEventListener('click', () => this.hideInfoPanel());
    }

    async loadConversations() {
        try {
            const response = await fetch('/api/conversations');
            const data = await response.json();
            this.renderConversationList(data.conversations);
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }

    renderConversationList(conversations) {
        this.conversationList.innerHTML = conversations.map(conv => `
            <div class="conversation-item ${conv.id === this.conversationId ? 'active' : ''}"
                 data-id="${conv.id}">
                <div class="title">${this.escapeHtml(conv.title)}</div>
                <div class="meta">${conv.message_count} messages</div>
            </div>
        `).join('');

        // Add click handlers
        this.conversationList.querySelectorAll('.conversation-item').forEach(item => {
            item.addEventListener('click', () => {
                this.loadConversation(item.dataset.id);
            });
        });
    }

    async loadConversation(conversationId) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}`);
            const data = await response.json();

            this.conversationId = conversationId;
            this.chatTitle.textContent = data.title;
            this.welcome.style.display = 'none';

            // Clear and render messages
            this.chatMessages.innerHTML = '';
            data.messages.forEach(msg => {
                this.renderMessage(msg.role, msg.content, msg.metadata);
            });

            // Update sidebar
            this.conversationList.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.toggle('active', item.dataset.id === conversationId);
            });

            // Scroll to bottom
            this.scrollToBottom();
        } catch (error) {
            console.error('Failed to load conversation:', error);
        }
    }

    async createNewChat() {
        try {
            const response = await fetch('/api/conversations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Chat' })
            });
            const data = await response.json();

            this.conversationId = data.id;
            this.chatTitle.textContent = data.title;
            this.chatMessages.innerHTML = '';
            this.welcome.style.display = 'block';

            await this.loadConversations();
        } catch (error) {
            console.error('Failed to create conversation:', error);
        }
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isStreaming) return;

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // Hide welcome
        this.welcome.style.display = 'none';

        // Render user message
        this.renderMessage('user', message);

        // Start streaming
        this.isStreaming = true;
        this.setLoading(true);

        // Create assistant message container
        const assistantDiv = this.createMessageElement('assistant', '');
        const contentDiv = assistantDiv.querySelector('.message-content');
        this.chatMessages.appendChild(assistantDiv);
        this.scrollToBottom();

        try {
            const response = await fetch('/api/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message,
                    conversation_id: this.conversationId
                })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') continue;

                        try {
                            const event = JSON.parse(data);
                            this.handleStreamEvent(event, contentDiv, assistantDiv);
                        } catch (e) {
                            console.error('Failed to parse event:', e);
                        }
                    }
                }
            }

            // Update conversation ID if new
            await this.loadConversations();

        } catch (error) {
            console.error('Streaming error:', error);
            contentDiv.textContent = 'Error: ' + error.message;
        } finally {
            this.isStreaming = false;
            this.setLoading(false);
        }
    }

    handleStreamEvent(event, contentDiv, messageDiv) {
        switch (event.type) {
            case 'start':
                if (!this.conversationId) {
                    this.conversationId = event.conversation_id;
                }
                break;

            case 'memory':
                if (event.memories.length > 0) {
                    const memoryIndicator = document.createElement('div');
                    memoryIndicator.className = 'memory-indicator';
                    memoryIndicator.innerHTML = `
                        <span class="icon">🧠</span>
                        <span>${event.memories.length} memories retrieved</span>
                    `;
                    memoryIndicator.addEventListener('click', () => {
                        this.showInfoPanel('Retrieved Memories', this.formatMemories(event.memories));
                    });
                    messageDiv.insertBefore(memoryIndicator, contentDiv);
                }
                break;

            case 'tool_start':
                const toolIndicator = document.createElement('div');
                toolIndicator.className = 'tool-indicator loading';
                toolIndicator.id = `tool-${event.tool}`;
                toolIndicator.innerHTML = `
                    <span class="icon">🔧</span>
                    <span>Using ${event.tool}...</span>
                `;
                messageDiv.insertBefore(toolIndicator, contentDiv);
                this.scrollToBottom();
                break;

            case 'tool_end':
                const indicator = document.getElementById(`tool-${event.tool}`);
                if (indicator) {
                    indicator.classList.remove('loading');
                    indicator.innerHTML = `
                        <span class="icon">✓</span>
                        <span>${event.tool} completed</span>
                    `;

                    // Add collapsible result
                    const resultDiv = document.createElement('div');
                    resultDiv.className = 'tool-result';
                    resultDiv.innerHTML = `
                        <div class="tool-result-header">
                            <span>Result</span>
                            <span class="tool-result-toggle">Show</span>
                        </div>
                        <div class="tool-result-content" style="display: none;">
                            <pre>${this.escapeHtml(JSON.stringify(event.result, null, 2))}</pre>
                        </div>
                    `;

                    const toggle = resultDiv.querySelector('.tool-result-toggle');
                    const content = resultDiv.querySelector('.tool-result-content');
                    toggle.addEventListener('click', () => {
                        const isHidden = content.style.display === 'none';
                        content.style.display = isHidden ? 'block' : 'none';
                        toggle.textContent = isHidden ? 'Hide' : 'Show';
                    });

                    indicator.after(resultDiv);
                }
                break;

            case 'token':
                contentDiv.textContent += event.content;
                this.scrollToBottom();
                break;

            case 'end':
                // Add metadata
                if (event.message.metadata) {
                    const meta = document.createElement('div');
                    meta.className = 'message-meta';
                    const parts = [];
                    if (event.message.metadata.latency_ms) {
                        parts.push(`${Math.round(event.message.metadata.latency_ms)}ms`);
                    }
                    if (event.message.metadata.memories_retrieved) {
                        parts.push(`${event.message.metadata.memories_retrieved} memories`);
                    }
                    meta.textContent = parts.join(' • ');
                    messageDiv.appendChild(meta);
                }
                break;

            case 'error':
                contentDiv.textContent = 'Error: ' + event.error;
                contentDiv.style.color = 'var(--error-color)';
                break;
        }
    }

    createMessageElement(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerHTML = `
            <div class="message-header">
                <span>${role === 'user' ? 'You' : 'Assistant'}</span>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        return div;
    }

    renderMessage(role, content, metadata = {}) {
        const div = this.createMessageElement(role, content);

        if (metadata && Object.keys(metadata).length > 0) {
            const meta = document.createElement('div');
            meta.className = 'message-meta';
            const parts = [];
            if (metadata.latency_ms) {
                parts.push(`${Math.round(metadata.latency_ms)}ms`);
            }
            if (metadata.tool_calls && metadata.tool_calls.length > 0) {
                parts.push(`${metadata.tool_calls.length} tool(s) used`);
            }
            meta.textContent = parts.join(' • ');
            div.appendChild(meta);
        }

        this.chatMessages.appendChild(div);
        this.scrollToBottom();
    }

    formatMemories(memories) {
        return memories.map((m, i) => `
            <div style="margin-bottom: 12px; padding: 8px; background: var(--bg-tertiary); border-radius: 4px;">
                <div style="font-weight: 500; margin-bottom: 4px;">${i + 1}. ${m.source || 'Memory'}</div>
                <div style="font-size: 13px;">${this.escapeHtml(m.content)}</div>
                ${m.relevance_score ? `<div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">Relevance: ${(m.relevance_score * 100).toFixed(0)}%</div>` : ''}
            </div>
        `).join('');
    }

    showInfoPanel(title, content) {
        this.infoPanelTitle.textContent = title;
        this.infoPanelContent.innerHTML = content;
        this.infoPanel.classList.remove('collapsed');
    }

    hideInfoPanel() {
        this.infoPanel.classList.add('collapsed');
    }

    setLoading(loading) {
        this.sendBtn.disabled = loading;
        this.status.classList.toggle('loading', loading);
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.theme);
        this.applyTheme();
    }

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
    }

    toggleSidebar() {
        this.sidebar.classList.toggle('collapsed');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});
