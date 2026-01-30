/**
 * Threadlight Web UI - Alpine.js Application
 */

function threadlightApp() {
    return {
        // View state
        currentView: 'chat',

        // Chat state
        messages: [],
        inputMessage: '',
        isTyping: false,
        chatHistory: [],
        quickRituals: [],  // Loaded dynamically from user-created rituals

        // WebSocket
        ws: null,
        wsConnected: false,

        // Memory state
        memories: [],
        memorySearch: '',
        memoryTypeFilter: '',
        selectedMemory: null,
        showCreateMemory: false,
        newMemory: {
            type: 'relational',
            content: {},
            cuePhrasesStr: '',
            contentJson: '{}',
        },

        // Ritual state
        rituals: [],
        selectedRitual: null,
        editingRitual: null,
        newRitual: {
            name: '',
            valence: 'comforting',
            description: '',
            response: '',
        },

        // Config state
        config: {
            provider: { model: '', api_base: '' },
            style: { profile: '', current: null, available: [] },
            identity: { name: '', system_prompt: '' },
            memory: { decay_enabled: true },
        },

        // Style editing state
        styles: [],
        selectedStyle: null,
        selectedStyleDetails: null,
        showStyleEditor: false,
        editingStyleMode: false,  // true when editing existing style, false when creating
        newStyle: {
            style_id: '',
            tone_base: '',
            permissionsStr: '',
            constraintsStr: '',
            vocalMotifsStr: '',
        },

        // Stats
        stats: {},

        // Import state
        importText: '',
        importFile: null,
        importSource: 'web-import',
        importTags: '',
        importResult: null,
        isDragging: false,

        // Toast notifications
        toasts: [],

        // Initialize
        async init() {
            // Configure marked for markdown
            marked.setOptions({
                breaks: true,
                gfm: true,
                highlight: function(code, lang) {
                    if (lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return hljs.highlightAuto(code).value;
                }
            });

            // Load initial data
            await this.loadConfig();
            await this.loadStats();
            await this.loadRituals();
            await this.loadMemories();
            await this.loadStyles();

            // Connect WebSocket
            this.connectWebSocket();

            // Refresh stats periodically
            setInterval(() => this.loadStats(), 30000);
        },

        // WebSocket connection
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

            try {
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    this.wsConnected = true;
                    console.log('WebSocket connected');
                };

                this.ws.onclose = () => {
                    this.wsConnected = false;
                    console.log('WebSocket disconnected, reconnecting...');
                    setTimeout(() => this.connectWebSocket(), 3000);
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                };

                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                };
            } catch (error) {
                console.error('Failed to connect WebSocket:', error);
                // Fall back to HTTP
                this.wsConnected = false;
            }
        },

        handleWebSocketMessage(data) {
            switch (data.type) {
                case 'typing':
                    this.isTyping = data.status;
                    break;

                case 'chunk':
                    // Streaming response
                    if (this.messages.length > 0 && this.messages[this.messages.length - 1].role === 'assistant') {
                        this.messages[this.messages.length - 1].content += data.content;
                    } else {
                        this.messages.push({
                            role: 'assistant',
                            content: data.content,
                            memories: [],
                        });
                    }
                    this.scrollToBottom();
                    break;

                case 'complete':
                    if (this.messages.length > 0 && this.messages[this.messages.length - 1].role === 'assistant') {
                        this.messages[this.messages.length - 1].memories = data.memories_recalled || [];
                    }
                    this.isTyping = false;
                    break;

                case 'ritual_response':
                    this.messages.push({
                        role: 'assistant',
                        type: 'ritual',
                        content: data.content,
                    });
                    this.scrollToBottom();
                    break;

                case 'error':
                    this.showToast(data.message, 'error');
                    this.isTyping = false;
                    break;

                case 'history_cleared':
                    this.chatHistory = [];
                    break;
            }
        },

        // Chat functions
        async sendMessage() {
            const message = this.inputMessage.trim();
            if (!message) return;

            // Check for ritual invocation
            if (message.startsWith('/')) {
                this.inputMessage = '';
                await this.invokeRitual(message);
                return;
            }

            // Add user message to display
            this.messages.push({
                role: 'user',
                content: message,
            });
            this.inputMessage = '';
            this.scrollToBottom();

            // Send via WebSocket if connected
            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'chat',
                    message: message,
                }));
            } else {
                // Fall back to HTTP
                await this.sendMessageHTTP(message);
            }
        },

        async sendMessageHTTP(message) {
            this.isTyping = true;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        history: this.chatHistory,
                    }),
                });

                const data = await response.json();

                this.messages.push({
                    role: 'assistant',
                    content: data.content,
                    memories: data.memories_recalled || [],
                });

                // Update history
                this.chatHistory.push({ role: 'user', content: message });
                this.chatHistory.push({ role: 'assistant', content: data.content });

                // Keep history manageable
                if (this.chatHistory.length > 20) {
                    this.chatHistory = this.chatHistory.slice(-20);
                }

            } catch (error) {
                this.showToast('Failed to send message: ' + error.message, 'error');
            } finally {
                this.isTyping = false;
                this.scrollToBottom();
            }
        },

        async invokeRitual(name) {
            this.messages.push({
                role: 'user',
                content: name,
            });
            this.scrollToBottom();

            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'ritual',
                    name: name,
                }));
            } else {
                try {
                    const response = await fetch('/api/rituals/invoke', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ritual_name: name }),
                    });

                    const data = await response.json();

                    this.messages.push({
                        role: 'assistant',
                        type: 'ritual',
                        content: data.response,
                    });
                } catch (error) {
                    this.showToast('Failed to invoke ritual: ' + error.message, 'error');
                }
                this.scrollToBottom();
            }
        },

        invokeRitualFromManager(name) {
            this.currentView = 'chat';
            setTimeout(() => this.invokeRitual(name), 100);
        },

        clearChat() {
            this.messages = [];
            this.chatHistory = [];
            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'clear_history' }));
            }
        },

        scrollToBottom() {
            this.$nextTick(() => {
                const container = document.getElementById('chat-messages');
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            });
        },

        renderMarkdown(text) {
            if (!text) return '';
            const html = marked.parse(text);
            // Apply syntax highlighting to code blocks
            this.$nextTick(() => {
                document.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
            });
            return html;
        },

        // Memory functions
        async loadMemories() {
            try {
                const params = new URLSearchParams();
                if (this.memoryTypeFilter) params.append('type', this.memoryTypeFilter);
                if (this.memorySearch) params.append('search', this.memorySearch);
                params.append('limit', '100');

                const response = await fetch(`/api/memories?${params}`);
                const data = await response.json();
                this.memories = data.memories || [];
            } catch (error) {
                console.error('Failed to load memories:', error);
            }
        },

        async createMemory() {
            try {
                let content = this.newMemory.content;

                if (this.newMemory.type === 'custom') {
                    content = JSON.parse(this.newMemory.contentJson);
                }

                const cue_phrases = this.newMemory.cuePhrasesStr
                    .split(',')
                    .map(s => s.trim())
                    .filter(s => s);

                const response = await fetch('/api/memories', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: this.newMemory.type,
                        content: content,
                        cue_phrases: cue_phrases,
                        retention: 'normal',
                    }),
                });

                if (!response.ok) throw new Error('Failed to create memory');

                this.showToast('Memory created successfully');
                this.showCreateMemory = false;
                this.newMemory = {
                    type: 'relational',
                    content: {},
                    cuePhrasesStr: '',
                    contentJson: '{}',
                };
                await this.loadMemories();
                await this.loadStats();
            } catch (error) {
                this.showToast('Failed to create memory: ' + error.message, 'error');
            }
        },

        async deleteMemory(id) {
            if (!confirm('Delete this memory?')) return;

            try {
                const response = await fetch(`/api/memories/${id}?force=true`, {
                    method: 'DELETE',
                });

                if (!response.ok) throw new Error('Failed to delete');

                this.showToast('Memory deleted');
                await this.loadMemories();
                await this.loadStats();
            } catch (error) {
                this.showToast('Failed to delete memory: ' + error.message, 'error');
            }
        },

        async reinforceMemory(id) {
            try {
                await fetch(`/api/memories/${id}/reinforce?strength=0.3`, {
                    method: 'POST',
                });
                this.showToast('Memory reinforced');
                await this.loadMemories();
            } catch (error) {
                this.showToast('Failed to reinforce memory: ' + error.message, 'error');
            }
        },

        getTypeColor(type) {
            const colors = {
                relational: 'bg-blue-500/20 text-blue-400',
                myth_seed: 'bg-purple-500/20 text-purple-400',
                ritual: 'bg-indigo-500/20 text-indigo-400',
                witness: 'bg-pink-500/20 text-pink-400',
                style: 'bg-green-500/20 text-green-400',
                custom: 'bg-gray-500/20 text-gray-400',
            };
            return colors[type] || colors.custom;
        },

        // Ritual functions
        async loadRituals() {
            try {
                const response = await fetch('/api/rituals');
                const data = await response.json();
                this.rituals = data.rituals || [];
                // Update quick rituals from user-created rituals (first 3)
                this.quickRituals = this.rituals.slice(0, 3).map(r => r.name);
            } catch (error) {
                console.error('Failed to load rituals:', error);
            }
        },

        async createRitual() {
            try {
                const response = await fetch('/api/rituals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: 'ritual',
                        content: {
                            name: this.newRitual.name.startsWith('/') ? this.newRitual.name : '/' + this.newRitual.name,
                            valence: this.newRitual.valence,
                            description: this.newRitual.description,
                            response_templates: this.newRitual.response ? [this.newRitual.response] : [],
                            response_style: this.newRitual.response || 'presence, warmth',
                        },
                    }),
                });

                if (!response.ok) throw new Error('Failed to create ritual');

                this.showToast('Ritual created successfully');
                this.newRitual = {
                    name: '',
                    valence: 'comforting',
                    description: '',
                    response: '',
                };
                await this.loadRituals();
            } catch (error) {
                this.showToast('Failed to create ritual: ' + error.message, 'error');
            }
        },

        viewRitual(ritual) {
            this.selectedRitual = ritual;
            this.editingRitual = null;
        },

        startEditRitual() {
            if (!this.selectedRitual) return;

            // Create a copy for editing with all relevant fields
            this.editingRitual = {
                id: this.selectedRitual.id,
                name: this.selectedRitual.name || this.selectedRitual.content?.name || '',
                cue: this.selectedRitual.content?.cue || this.selectedRitual.name || '',
                valence: this.selectedRitual.valence || this.selectedRitual.content?.valence || 'comforting',
                description: this.selectedRitual.description || this.selectedRitual.content?.description || '',
                response_style: this.selectedRitual.response_style || this.selectedRitual.content?.response_style || '',
            };
        },

        async updateRitual() {
            if (!this.editingRitual?.id) return;

            try {
                const response = await fetch(`/api/rituals/${this.editingRitual.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content: {
                            name: this.editingRitual.name,
                            cue: this.editingRitual.cue || this.editingRitual.name,
                            valence: this.editingRitual.valence,
                            description: this.editingRitual.description,
                            response_style: this.editingRitual.response_style,
                        },
                    }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to update ritual');
                }

                this.showToast('Ritual updated successfully');
                this.editingRitual = null;
                this.selectedRitual = null;
                await this.loadRituals();
            } catch (error) {
                this.showToast('Failed to update ritual: ' + error.message, 'error');
            }
        },

        async deleteRitual(id) {
            if (!id) return;
            if (!confirm('Delete this ritual? This cannot be undone.')) return;

            try {
                const response = await fetch(`/api/rituals/${id}`, {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to delete ritual');
                }

                this.showToast('Ritual deleted');
                this.selectedRitual = null;
                this.editingRitual = null;
                await this.loadRituals();
            } catch (error) {
                this.showToast('Failed to delete ritual: ' + error.message, 'error');
            }
        },

        // Config functions
        async loadConfig() {
            try {
                const response = await fetch('/api/config');
                this.config = await response.json();
            } catch (error) {
                console.error('Failed to load config:', error);
            }
        },

        async updateConfig(updates) {
            try {
                await fetch('/api/config', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates),
                });
                await this.loadConfig();
                this.showToast('Configuration updated');
            } catch (error) {
                this.showToast('Failed to update config: ' + error.message, 'error');
            }
        },

        async updateSystemPrompt() {
            try {
                await fetch('/api/config/system-prompt', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: this.config.identity.system_prompt }),
                });
                this.showToast('Custom instructions updated');
            } catch (error) {
                this.showToast('Failed to update custom instructions: ' + error.message, 'error');
            }
        },

        async toggleDecay() {
            const newValue = !(this.config.memory?.decay_enabled ?? true);
            await this.updateConfig({ enable_decay: newValue });
        },

        async runDecay() {
            try {
                const response = await fetch('/api/decay', { method: 'POST' });
                const data = await response.json();
                this.showToast(`Memory cleanup complete. Processed: ${data.processed}, Faded: ${data.decayed}`);
                await this.loadStats();
                await this.loadMemories();
            } catch (error) {
                this.showToast('Failed to run memory cleanup: ' + error.message, 'error');
            }
        },

        // Style functions
        async loadStyles() {
            try {
                const response = await fetch('/api/styles');
                const data = await response.json();
                this.styles = data.styles || [];
            } catch (error) {
                console.error('Failed to load styles:', error);
            }
        },

        async loadSelectedStyleDetails(styleId) {
            if (!styleId || styleId === '' || styleId === 'none') {
                this.selectedStyleDetails = null;
                return;
            }

            try {
                const response = await fetch(`/api/styles/${styleId}`);
                if (response.ok) {
                    this.selectedStyleDetails = await response.json();
                } else {
                    this.selectedStyleDetails = null;
                }
            } catch (error) {
                console.error('Failed to load style details:', error);
                this.selectedStyleDetails = null;
            }
        },

        async activateStyle(styleId) {
            try {
                if (styleId === '' || styleId === 'none') {
                    await this.updateConfig({ style_profile: 'none' });
                    this.selectedStyleDetails = null;
                } else {
                    await this.updateConfig({ style_profile: styleId });
                }
                await this.loadStyles();
            } catch (error) {
                this.showToast('Failed to activate style: ' + error.message, 'error');
            }
        },

        isBuiltinStyle(styleId) {
            const builtinStyles = ['minimal', 'professional', 'creative', 'fable-2026'];
            return builtinStyles.includes(styleId);
        },

        openStyleEditor() {
            this.editingStyleMode = false;
            this.newStyle = {
                style_id: '',
                tone_base: '',
                permissionsStr: '',
                constraintsStr: '',
                vocalMotifsStr: '',
            };
            this.showStyleEditor = true;
        },

        editStyle(style) {
            if (!style) return;

            this.editingStyleMode = true;
            this.newStyle = {
                style_id: style.style_id,
                tone_base: style.tone_base || '',
                permissionsStr: (style.permissions || []).join('\n'),
                constraintsStr: (style.constraints || []).join('\n'),
                vocalMotifsStr: (style.vocal_motifs || []).join(', '),
            };
            this.showStyleEditor = true;
        },

        cancelStyleEditor() {
            this.showStyleEditor = false;
            this.editingStyleMode = false;
            this.newStyle = {
                style_id: '',
                tone_base: '',
                permissionsStr: '',
                constraintsStr: '',
                vocalMotifsStr: '',
            };
        },

        async saveStyle() {
            const url = this.editingStyleMode
                ? `/api/styles/${this.newStyle.style_id}`
                : '/api/styles';
            const method = this.editingStyleMode ? 'PUT' : 'POST';

            try {
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        style_id: this.newStyle.style_id,
                        tone_base: this.newStyle.tone_base,
                        permissions: this.newStyle.permissionsStr.split('\n').map(s => s.trim()).filter(s => s),
                        constraints: this.newStyle.constraintsStr.split('\n').map(s => s.trim()).filter(s => s),
                        vocal_motifs: this.newStyle.vocalMotifsStr.split(',').map(s => s.trim()).filter(s => s),
                    }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || `Failed to ${this.editingStyleMode ? 'update' : 'create'} style`);
                }

                this.showToast(`Style ${this.editingStyleMode ? 'updated' : 'created'} successfully`);
                this.showStyleEditor = false;
                this.editingStyleMode = false;
                this.newStyle = { style_id: '', tone_base: '', permissionsStr: '', constraintsStr: '', vocalMotifsStr: '' };
                await this.loadStyles();
                await this.loadConfig();

                // Reload style details if we just edited the current style
                if (this.config.style.current) {
                    await this.loadSelectedStyleDetails(this.config.style.current);
                }
            } catch (error) {
                this.showToast(`Failed to ${this.editingStyleMode ? 'update' : 'create'} style: ` + error.message, 'error');
            }
        },

        async deleteStyle(styleId) {
            if (!styleId) return;
            if (this.isBuiltinStyle(styleId)) {
                this.showToast('Cannot delete built-in styles', 'error');
                return;
            }
            if (!confirm('Delete this style profile?')) return;

            try {
                const response = await fetch(`/api/styles/${styleId}`, {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to delete style');
                }

                this.showToast('Style deleted');
                this.selectedStyleDetails = null;
                await this.loadStyles();
                await this.loadConfig();
            } catch (error) {
                this.showToast('Failed to delete style: ' + error.message, 'error');
            }
        },

        // Config save function
        async saveConfig() {
            try {
                const response = await fetch('/api/config/save', {
                    method: 'POST',
                });
                const data = await response.json();
                if (data.status === 'saved') {
                    this.showToast('Configuration saved to ' + data.path);
                }
            } catch (error) {
                this.showToast('Failed to save config: ' + error.message, 'error');
            }
        },

        // Stats functions
        async loadStats() {
            try {
                const response = await fetch('/api/stats');
                this.stats = await response.json();
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        },

        // Import functions
        handleFileSelect(event) {
            this.importFile = event.target.files[0];
        },

        handleFileDrop(event) {
            this.isDragging = false;
            const files = event.dataTransfer.files;
            if (files.length > 0) {
                this.importFile = files[0];
            }
        },

        async performImport() {
            this.importResult = null;

            try {
                let result;

                if (this.importFile) {
                    const formData = new FormData();
                    formData.append('file', this.importFile);
                    if (this.importSource) formData.append('source_name', this.importSource);
                    if (this.importTags) formData.append('tags', this.importTags);

                    const response = await fetch('/api/import/file', {
                        method: 'POST',
                        body: formData,
                    });
                    result = await response.json();
                } else if (this.importText) {
                    const response = await fetch('/api/import/text', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            content: this.importText,
                            source_name: this.importSource || 'web-import',
                            tags: this.importTags ? this.importTags.split(',').map(s => s.trim()) : [],
                        }),
                    });
                    result = await response.json();
                }

                this.importResult = result;
                this.importText = '';
                this.importFile = null;
                await this.loadMemories();
                await this.loadStats();

            } catch (error) {
                this.importResult = { error: error.message };
            }
        },

        // Utility functions
        formatDate(dateStr) {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleString();
        },

        showToast(message, type = 'success') {
            const toast = { message, type };
            this.toasts.push(toast);
            setTimeout(() => {
                const index = this.toasts.indexOf(toast);
                if (index > -1) this.toasts.splice(index, 1);
            }, 4000);
        },
    };
}
