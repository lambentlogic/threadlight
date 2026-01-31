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

        // Conversation management state
        conversations: [],
        currentConversationId: null,
        conversationSearch: '',
        showArchivedConversations: false,
        renamingConversationId: null,
        renameConversationName: '',
        openConversationMenu: null,
        showConversationPanel: false,  // For mobile slide-in panel

        // Group chat state
        isGroupChat: false,  // Current conversation is a group chat
        selectedGroupProfiles: [],  // Profile IDs for new group chat
        showGroupChatModal: false,  // Modal for creating group chat
        groupChatResponding: false,  // Currently getting group responses

        // Message editing state
        editingMessageId: null,
        editedMessageContent: '',

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

        // Embeddings state
        embeddingsEnabled: false,
        embeddingsProvider: 'local',
        embeddingsModel: 'intfloat/e5-small-v2',
        embeddingStats: {},
        semanticSearch: false,
        generatingEmbeddings: false,
        clearingEmbeddings: false,
        embeddingProgress: {
            totalItems: 0,
            processed: 0,
            percentComplete: 0,
            capsulesUpdated: 0,
            messagesUpdated: 0,
            statusText: '',
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
            memory: { decay_enabled: true, per_profile_isolation: false, default_shared: false },
        },

        // Provider configuration state
        providerConfig: {
            provider_type: 'nous',
            api_base: '',
            endpoints: [],  // List of {url, name, priority, purpose, is_healthy, last_checked}
            has_api_key: false,
            model: '',
        },
        providerApiKey: '',  // Separate field for API key input
        providerApiKeyChanged: false,  // Track if key was modified
        showProviderApiKey: false,  // Toggle visibility
        testingProviderConnection: false,
        providerConnectionStatus: null,  // 'success', 'error', or null
        providerConnectionMessage: '',
        savingProviderConfig: false,
        testingEndpointIndex: null,  // Index of endpoint being tested

        // Provider models state (fetched from API)
        providerModels: [],  // List of available models from provider
        providerModelsLoading: false,
        providerModelsError: null,
        providerModelsLastFetched: null,  // Timestamp for cache invalidation
        providerModelsCacheDuration: 5 * 60 * 1000,  // Cache for 5 minutes

        // Model configuration state
        currentModelId: '',
        currentModelConfig: {
            system_prompt: '',
            style_profile: null,
            memory_enabled: true,
            decay_enabled: false,
            temperature: 0.7,
            max_tokens: null,
            top_p: 1.0,
        },
        availableModels: [],
        showAddModelModal: false,
        newModelData: {
            model_id: '',
            system_prompt: 'You are a helpful AI assistant.',
            style_profile: '',
            memory_enabled: true,
            decay_enabled: false,
            temperature: 0.7,
        },
        configSaved: false,  // Auto-save indicator

        // Style editing state
        styles: [],
        selectedStyle: null,
        selectedStyleDetails: null,
        showStyleEditor: false,
        editingStyleMode: false,  // true when editing existing style, false when creating
        stylePreviewVisible: false,
        stylePreviewContent: '',
        newStyle: {
            style_id: '',
            tone_base: '',
            permissionsStr: '',
            constraintsStr: '',
            vocalMotifsStr: '',
            use_freeform: false,
            freeform_description: '',
        },

        // Stats
        stats: {},

        // Memory Types state
        memoryTypes: [],
        exampleTypes: [],
        selectedMemoryType: null,
        showMemoryTypeEditor: false,
        showExampleTypes: false,
        newMemoryType: {
            type_id: '',
            description: '',
            display_template: '',
            fields: [],
        },

        // Import state
        importText: '',
        importFile: null,
        importSource: 'web-import',
        importTags: '',
        importResult: null,
        isDragging: false,
        // Conversation import state
        conversationFile: null,
        isDraggingConversation: false,
        importingConversations: false,
        conversationImportResult: null,
        // Profile import state (from Import view)
        profileImportFile: null,
        isDraggingProfile: false,
        importingProfile: false,
        profileImportResult: null,

        // Profile state
        profiles: [],
        activeProfileId: null,
        selectedProfile: null,
        showProfileEditor: false,
        editingProfileMode: false,  // true when editing existing profile
        savedProfileId: null,  // For flash animation after save
        newProfile: {
            name: '',
            description: '',
            system_prompt: '',
            style_profile_id: '',
            model_strategy: 'single',
            primary_model: '',
            model_pool: [],
            model_pool_str: '',  // For comma-separated input
            memory_scope: 'isolated',
            access_shared_memories: true,
            tags: [],
            tags_str: '',  // For comma-separated input
            philosophy: '',  // Freeform philosophy description
            approach_to_rituals: '',  // Freeform approach to rituals
            routing_rules: [],  // For content-routed strategy
        },

        // Routing rule editor state
        showRoutingRuleEditor: false,
        editingRoutingRule: null,  // Index of rule being edited, or null for new
        newRoutingRule: {
            match_type: 'keyword',
            pattern: '',
            target_model: '',
            priority: 50,
        },
        routingRuleValidationError: '',

        // Toast notifications
        toasts: [],

        // Confirmation modal state
        confirmModal: {
            visible: false,
            title: '',
            message: '',
            confirmText: 'Confirm',
            cancelText: 'Cancel',
            confirmClass: 'bg-red-600 hover:bg-red-700',
            onConfirm: null,
        },

        // Prompt modal state
        promptModal: {
            visible: false,
            title: '',
            message: '',
            placeholder: '',
            value: '',
            confirmText: 'Submit',
            cancelText: 'Cancel',
            onConfirm: null,
        },

        // Per-profile memory isolation state
        perProfileIsolation: false,
        defaultShared: false,
        profileScopeStats: {},

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
            await this.loadModels();
            await this.loadStats();
            await this.loadRituals();
            await this.loadMemories();
            await this.loadStyles();
            await this.loadEmbeddingStats();
            await this.loadConversations();
            await this.loadMemoryTypes();
            await this.loadModelScopeConfig();
            await this.loadProfiles();
            await this.loadProviderConfig();

            // Connect WebSocket
            this.connectWebSocket();

            // Refresh stats periodically
            setInterval(() => this.loadStats(), 30000);

            // Close conversation menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.conversation-menu-btn') && !e.target.closest('.conversation-menu')) {
                    this.openConversationMenu = null;
                }
            });
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

            // If this is a group chat, use the group chat endpoint
            if (this.isGroupChat && this.currentConversationId) {
                await this.sendGroupMessage();
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
            this.currentConversationId = null;
            this.isGroupChat = false;
            this.groupChatResponding = false;
            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'clear_history' }));
            }
        },

        // ============================================
        // Conversation Management Functions
        // ============================================

        async loadConversations() {
            try {
                const params = new URLSearchParams();
                params.append('limit', '50');
                if (this.showArchivedConversations) {
                    params.append('include_archived', 'true');
                }

                const response = await fetch(`/api/conversations?${params}`);
                const data = await response.json();
                this.conversations = data.conversations || [];

                // Load most recent conversation if none selected
                if (!this.currentConversationId && this.conversations.length > 0) {
                    await this.loadConversation(this.conversations[0].id);
                }
            } catch (error) {
                console.error('Failed to load conversations:', error);
            }
        },

        get filteredConversations() {
            if (!this.conversationSearch) {
                return this.conversations;
            }
            const search = this.conversationSearch.toLowerCase();
            return this.conversations.filter(c =>
                (c.name || '').toLowerCase().includes(search) ||
                (c.summary || '').toLowerCase().includes(search)
            );
        },

        async createNewConversation() {
            try {
                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'New Chat' }),
                });

                if (!response.ok) throw new Error('Failed to create conversation');

                const data = await response.json();
                this.currentConversationId = data.id || data.conversation_id;
                this.messages = [];
                this.chatHistory = [];
                this.isGroupChat = false;
                await this.loadConversations();
            } catch (error) {
                this.showToast('Failed to create conversation: ' + error.message, 'error');
            }
        },

        async createGroupConversation() {
            if (this.selectedGroupProfiles.length < 2) {
                this.showToast('Group chat requires at least 2 profiles', 'error');
                return;
            }

            try {
                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: 'Group Chat',
                        participant_profiles: this.selectedGroupProfiles,
                    }),
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to create group conversation');
                }

                const data = await response.json();
                this.currentConversationId = data.id;
                this.messages = [];
                this.chatHistory = [];
                this.isGroupChat = true;
                this.showGroupChatModal = false;
                this.selectedGroupProfiles = [];
                await this.loadConversations();
                this.showToast('Group chat created');
            } catch (error) {
                this.showToast('Failed to create group chat: ' + error.message, 'error');
            }
        },

        openGroupChatModal() {
            this.selectedGroupProfiles = [];
            this.showGroupChatModal = true;
        },

        toggleGroupProfile(profileId) {
            const idx = this.selectedGroupProfiles.indexOf(profileId);
            if (idx === -1) {
                this.selectedGroupProfiles.push(profileId);
            } else {
                this.selectedGroupProfiles.splice(idx, 1);
            }
        },

        isProfileSelectedForGroup(profileId) {
            return this.selectedGroupProfiles.includes(profileId);
        },

        async loadConversation(conversationId) {
            try {
                // First get conversation details to check if it's a group chat
                const convResponse = await fetch(`/api/conversations/${conversationId}`);
                if (convResponse.ok) {
                    const convData = await convResponse.json();
                    this.isGroupChat = convData.participant_profiles && convData.participant_profiles.length > 1;
                }

                const response = await fetch(`/api/conversations/${conversationId}/messages`);
                if (!response.ok) throw new Error('Failed to load conversation');

                const data = await response.json();
                this.currentConversationId = conversationId;
                this.messages = (data.messages || []).map(msg => ({
                    id: msg.id,
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.timestamp,
                    profile_id: msg.profile_id,
                    profile_name: this.getProfileNameById(msg.profile_id),
                    memories: [],
                }));

                // Rebuild chat history for context
                this.chatHistory = this.messages.slice(-20).map(m => ({
                    role: m.role,
                    content: m.content,
                }));

                this.scrollToBottom();
            } catch (error) {
                this.showToast('Failed to load conversation: ' + error.message, 'error');
            }
        },

        getProfileNameById(profileId) {
            if (!profileId) return null;
            const profile = this.profiles.find(p => p.id === profileId);
            return profile ? profile.name : profileId;
        },

        getProfileColorClass(profileId) {
            // Assign colors based on profile position
            if (!profileId) return '';
            const idx = this.profiles.findIndex(p => p.id === profileId);
            const colors = [
                'border-l-4 border-threadlight-accent',
                'border-l-4 border-threadlight-memory',
                'border-l-4 border-threadlight-ritual',
                'border-l-4 border-threadlight-warm',
                'border-l-4 border-green-400',
            ];
            return colors[idx % colors.length];
        },

        getCurrentConversationProfiles() {
            const conv = this.conversations.find(c => c.id === this.currentConversationId);
            if (!conv || !conv.participant_profiles) return [];
            return conv.participant_profiles.map(pid => this.profiles.find(p => p.id === pid)).filter(p => p);
        },

        // Send message to group chat - gets responses from all profiles
        async sendGroupMessage() {
            const message = this.inputMessage.trim();
            if (!message || !this.currentConversationId || !this.isGroupChat) return;

            // Add user message to display
            this.messages.push({
                role: 'user',
                content: message,
            });
            this.inputMessage = '';
            this.scrollToBottom();

            this.groupChatResponding = true;
            this.isTyping = true;

            try {
                const response = await fetch(`/api/conversations/${this.currentConversationId}/group-chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                    }),
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to send group message');
                }

                const data = await response.json();

                // Add each profile's response
                for (const resp of data.responses) {
                    this.messages.push({
                        role: 'assistant',
                        content: resp.content,
                        profile_id: resp.profile_id,
                        profile_name: this.getProfileNameById(resp.profile_id),
                        memories: resp.memories_recalled || [],
                    });
                    this.scrollToBottom();
                }

                // Update history
                this.chatHistory.push({ role: 'user', content: message });
                for (const resp of data.responses) {
                    this.chatHistory.push({ role: 'assistant', content: resp.content });
                }

                // Keep history manageable
                if (this.chatHistory.length > 40) {
                    this.chatHistory = this.chatHistory.slice(-40);
                }

            } catch (error) {
                this.showToast('Failed to send group message: ' + error.message, 'error');
            } finally {
                this.groupChatResponding = false;
                this.isTyping = false;
                this.scrollToBottom();
            }
        },

        // Get profile badge color for display
        getProfileBadgeColor(profileId) {
            if (!profileId) return 'bg-gray-500';
            const idx = this.profiles.findIndex(p => p.id === profileId);
            const colors = [
                'bg-threadlight-accent',
                'bg-threadlight-memory',
                'bg-threadlight-ritual',
                'bg-threadlight-warm',
                'bg-green-500',
                'bg-blue-500',
                'bg-pink-500',
                'bg-orange-500',
            ];
            return colors[idx % colors.length];
        },

        async renameConversation(conversationId, newName) {
            try {
                const response = await fetch(`/api/conversations/${conversationId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: newName }),
                });

                if (!response.ok) throw new Error('Failed to rename conversation');

                this.renamingConversationId = null;
                this.renameConversationName = '';
                await this.loadConversations();
            } catch (error) {
                this.showToast('Failed to rename: ' + error.message, 'error');
            }
        },

        startRenameConversation(conv) {
            this.renamingConversationId = conv.id;
            this.renameConversationName = conv.name || '';
            this.openConversationMenu = null;
            this.$nextTick(() => {
                const input = document.querySelector(`input[data-rename-id="${conv.id}"]`);
                if (input) input.focus();
            });
        },

        async archiveConversation(conversationId) {
            try {
                const response = await fetch(`/api/conversations/${conversationId}/archive`, {
                    method: 'POST',
                });

                if (!response.ok) throw new Error('Failed to archive conversation');

                this.showToast('Conversation archived');
                this.openConversationMenu = null;

                if (this.currentConversationId === conversationId) {
                    this.currentConversationId = null;
                    this.messages = [];
                }

                await this.loadConversations();
            } catch (error) {
                this.showToast('Failed to archive: ' + error.message, 'error');
            }
        },

        async unarchiveConversation(conversationId) {
            try {
                const response = await fetch(`/api/conversations/${conversationId}/unarchive`, {
                    method: 'POST',
                });

                if (!response.ok) throw new Error('Failed to unarchive conversation');

                this.showToast('Conversation restored');
                this.openConversationMenu = null;
                await this.loadConversations();
            } catch (error) {
                this.showToast('Failed to unarchive: ' + error.message, 'error');
            }
        },

        async deleteConversation(conversationId) {
            const confirmed = await this.showConfirm({
                title: 'Delete Conversation',
                message: 'Delete this conversation? This cannot be undone.',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

            try {
                const response = await fetch(`/api/conversations/${conversationId}`, {
                    method: 'DELETE',
                });

                if (!response.ok) throw new Error('Failed to delete conversation');

                this.showToast('Conversation deleted');
                this.openConversationMenu = null;

                if (this.currentConversationId === conversationId) {
                    this.currentConversationId = null;
                    this.messages = [];
                }

                await this.loadConversations();
            } catch (error) {
                this.showToast('Failed to delete: ' + error.message, 'error');
            }
        },

        toggleConversationMenu(conversationId) {
            if (this.openConversationMenu === conversationId) {
                this.openConversationMenu = null;
            } else {
                this.openConversationMenu = conversationId;
            }
        },

        toggleConversationPanel() {
            this.showConversationPanel = !this.showConversationPanel;
        },

        formatRelativeDate(dateStr) {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return date.toLocaleDateString();
        },

        // ============================================
        // Model Label Functions (for conversation list)
        // ============================================

        /**
         * Get a short label for the model/source of a conversation.
         * Shows the model name if available, otherwise falls back to source.
         */
        getModelLabel(conv) {
            // If we have a model name, use a shortened version
            if (conv.model) {
                return this.shortenModelName(conv.model);
            }
            // Fall back to source-based labels for imported conversations
            if (conv.source === 'claude') return 'Claude';
            if (conv.source === 'chatgpt') return 'GPT';
            // For local conversations without a model, show a generic label
            return 'Local';
        },

        /**
         * Shorten a model name for display in badges.
         * Examples: "gpt-4o" -> "4o", "Claude Opus" -> "Opus", "Hermes-4.3-36B" -> "Hermes"
         */
        shortenModelName(modelName) {
            if (!modelName) return 'Local';
            const name = modelName.toLowerCase();

            // GPT models
            if (name.includes('gpt-4o')) return '4o';
            if (name.includes('gpt-4-turbo')) return '4T';
            if (name.includes('gpt-4')) return 'GPT4';
            if (name.includes('gpt-3.5')) return '3.5';
            if (name.includes('o1')) return 'o1';
            if (name.includes('o3')) return 'o3';

            // Claude models
            if (name.includes('opus')) return 'Opus';
            if (name.includes('sonnet')) return 'Sonnet';
            if (name.includes('haiku')) return 'Haiku';
            if (name.includes('claude')) return 'Claude';

            // Hermes and other local models
            if (name.includes('hermes')) return 'Hermes';
            if (name.includes('llama')) return 'Llama';
            if (name.includes('mistral')) return 'Mistral';
            if (name.includes('mixtral')) return 'Mixtral';
            if (name.includes('qwen')) return 'Qwen';
            if (name.includes('gemma')) return 'Gemma';
            if (name.includes('phi')) return 'Phi';

            // If it's a profile name (often longer), take first word
            const words = modelName.split(/[\s-_]+/);
            if (words[0].length <= 8) return words[0];
            return words[0].substring(0, 6);
        },

        /**
         * Get tooltip text showing full model/source info.
         */
        getModelTooltip(conv) {
            if (conv.model) {
                return `Model: ${conv.model}`;
            }
            if (conv.source === 'claude') return 'Imported from Claude';
            if (conv.source === 'chatgpt') return 'Imported from ChatGPT';
            return 'Local conversation';
        },

        /**
         * Get CSS classes for the model badge based on source/model.
         */
        getModelBadgeClass(conv) {
            const source = conv.source || 'local';
            const model = (conv.model || '').toLowerCase();

            // Claude colors (warm orange)
            if (source === 'claude' || model.includes('claude') || model.includes('opus') || model.includes('sonnet') || model.includes('haiku')) {
                return 'bg-orange-500/20 text-orange-300';
            }

            // ChatGPT/OpenAI colors (green)
            if (source === 'chatgpt' || model.includes('gpt') || model.includes('o1') || model.includes('o3')) {
                return 'bg-green-500/20 text-green-300';
            }

            // Hermes and other Nous models (accent purple)
            if (model.includes('hermes') || model.includes('nous')) {
                return 'bg-threadlight-accent/20 text-threadlight-accent2';
            }

            // Llama/Meta models (blue)
            if (model.includes('llama')) {
                return 'bg-blue-500/20 text-blue-300';
            }

            // Mistral models (yellow)
            if (model.includes('mistral') || model.includes('mixtral')) {
                return 'bg-yellow-500/20 text-yellow-300';
            }

            // Default local style
            return 'bg-threadlight-border/50 text-threadlight-muted';
        },

        // ============================================
        // Message Action Functions
        // ============================================

        startEditMessage(msg) {
            this.editingMessageId = msg.id;
            this.editedMessageContent = msg.content;
        },

        cancelEditMessage() {
            this.editingMessageId = null;
            this.editedMessageContent = '';
        },

        async saveEditedMessage(msg) {
            if (!this.editingMessageId || !this.editedMessageContent.trim()) return;

            try {
                const response = await fetch(`/api/messages/${this.editingMessageId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: this.editedMessageContent }),
                });

                if (!response.ok) throw new Error('Failed to update message');

                // Update local state
                const msgIndex = this.messages.findIndex(m => m.id === this.editingMessageId);
                if (msgIndex !== -1) {
                    this.messages[msgIndex].content = this.editedMessageContent;
                }

                this.editingMessageId = null;
                this.editedMessageContent = '';
                this.showToast('Message updated');
            } catch (error) {
                this.showToast('Failed to update message: ' + error.message, 'error');
            }
        },

        async deleteMessage(msg) {
            if (!msg.id) return;
            const confirmed = await this.showConfirm({
                title: 'Delete Message',
                message: 'Delete this message?',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

            try {
                const response = await fetch(`/api/messages/${msg.id}`, {
                    method: 'DELETE',
                });

                if (!response.ok) throw new Error('Failed to delete message');

                // Remove from local state
                const msgIndex = this.messages.findIndex(m => m.id === msg.id);
                if (msgIndex !== -1) {
                    this.messages.splice(msgIndex, 1);
                }

                this.showToast('Message deleted');
            } catch (error) {
                this.showToast('Failed to delete message: ' + error.message, 'error');
            }
        },

        async regenerateResponse(msg) {
            // Find the user message that came before this assistant message
            const msgIndex = this.messages.findIndex(m => m.id === msg.id);
            if (msgIndex <= 0) {
                this.showToast('Cannot regenerate: no previous user message', 'error');
                return;
            }

            // Find the previous user message
            let userMsgIndex = msgIndex - 1;
            while (userMsgIndex >= 0 && this.messages[userMsgIndex].role !== 'user') {
                userMsgIndex--;
            }

            if (userMsgIndex < 0) {
                this.showToast('Cannot regenerate: no previous user message', 'error');
                return;
            }

            const userMessage = this.messages[userMsgIndex].content;

            // Delete this message and all after it
            if (msg.id) {
                try {
                    await fetch(`/api/messages/${msg.id}/and-after`, {
                        method: 'DELETE',
                    });
                } catch (error) {
                    console.error('Failed to delete messages from server:', error);
                }
            }

            // Remove from local state
            this.messages = this.messages.slice(0, msgIndex);

            // Resend the user message
            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'chat',
                    message: userMessage,
                }));
            } else {
                await this.sendMessageHTTP(userMessage);
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
            // Apply syntax highlighting to code blocks that haven't been highlighted yet
            this.$nextTick(() => {
                document.querySelectorAll('pre code:not([data-highlighted])').forEach((block) => {
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

        // Search memories (keyword or semantic based on toggle)
        async searchMemories() {
            if (this.semanticSearch && this.memorySearch && this.embeddingsEnabled) {
                await this.semanticSearchMemories();
            } else {
                await this.loadMemories();
            }
        },

        async semanticSearchMemories() {
            if (!this.memorySearch) {
                await this.loadMemories();
                return;
            }

            try {
                const response = await fetch('/api/search/semantic', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: this.memorySearch,
                        limit: 50,
                        threshold: 0.3,
                        include_memories: true,
                        include_conversations: false,
                    }),
                });

                if (!response.ok) {
                    throw new Error('Semantic search failed');
                }

                const data = await response.json();

                // Transform results to match memory format
                this.memories = (data.results || []).map(r => ({
                    id: r.capsule_id,
                    type: r.capsule_type,
                    content: r.content?.content || r.content || {},
                    preview: r.content?.preview || this.getPreviewFromContent(r.content),
                    cue_phrases: r.content?.cue_phrases || [],
                    presence_score: r.content?.presence_score || 0,
                    similarity_score: r.similarity_score,
                    ...r.content,
                }));
            } catch (error) {
                console.error('Semantic search failed:', error);
                this.showToast('Semantic search failed: ' + error.message, 'error');
                // Fall back to keyword search
                await this.loadMemories();
            }
        },

        getPreviewFromContent(content) {
            if (!content) return '';
            if (content.preview) return content.preview;
            if (content.content) {
                const c = content.content;
                if (c.seed) return c.seed;
                if (c.entity) return `${c.entity}: ${c.summary || ''}`;
                if (c.name) return `${c.name}: ${c.description || ''}`;
                if (c.text) return c.text;
            }
            return '';
        },

        // Embedding functions
        async loadEmbeddingStats() {
            try {
                const response = await fetch('/api/embeddings/stats');
                const data = await response.json();

                this.embeddingsEnabled = data.enabled || false;
                if (data.enabled) {
                    this.embeddingStats = data;
                    this.embeddingsProvider = data.provider || 'local';
                    this.embeddingsModel = data.model || 'intfloat/e5-small-v2';
                }
            } catch (error) {
                console.error('Failed to load embedding stats:', error);
            }
        },

        async toggleEmbeddings() {
            const oldState = this.embeddingsEnabled;
            const newState = !oldState;

            // Optimistically update UI
            this.embeddingsEnabled = newState;

            try {
                // Ensure we have valid values (use defaults if undefined)
                const payload = {
                    enabled: newState,
                    provider: this.embeddingsProvider || 'local',
                    model: this.embeddingsModel || 'intfloat/e5-small-v2',
                };
                console.log('Embeddings toggle payload:', payload);

                const response = await fetch('/api/embeddings/enable', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    let errorMsg = 'Failed to update embeddings config';

                    // Handle FastAPI validation errors (detail is an array)
                    if (Array.isArray(data.detail)) {
                        errorMsg = data.detail.map(err => err.msg || JSON.stringify(err)).join(', ');
                    } else if (data.detail) {
                        errorMsg = data.detail;
                    } else if (data.error) {
                        errorMsg = data.error;
                    } else if (data.message) {
                        errorMsg = data.message;
                    }

                    throw new Error(errorMsg);
                }

                this.showToast(newState ? 'Embeddings enabled' : 'Embeddings disabled');

                if (newState) {
                    await this.loadEmbeddingStats();
                }
            } catch (error) {
                // Revert optimistic update on error
                this.embeddingsEnabled = oldState;

                // Debug: log the actual error
                console.error('Toggle embeddings error:', error);
                console.error('Error type:', typeof error);
                console.error('Error keys:', error ? Object.keys(error) : 'N/A');

                // Extract message more robustly
                let errorMsg = 'Unknown error';
                if (error instanceof Error) {
                    errorMsg = error.message;
                } else if (typeof error === 'string') {
                    errorMsg = error;
                } else if (error && typeof error === 'object') {
                    errorMsg = error.detail || error.error || error.message || JSON.stringify(error);
                }

                this.showToast('Failed to toggle embeddings: ' + errorMsg, 'error');
            }
        },

        async updateEmbeddingsConfig() {
            if (!this.embeddingsEnabled) return;

            try {
                // Ensure we have valid values (use defaults if undefined)
                const payload = {
                    enabled: true,
                    provider: this.embeddingsProvider || 'local',
                    model: this.embeddingsModel || 'intfloat/e5-small-v2',
                };
                console.log('Update embeddings config payload:', payload);

                await fetch('/api/embeddings/enable', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                this.showToast('Embeddings configuration updated');
            } catch (error) {
                this.showToast('Failed to update config: ' + error.message, 'error');
            }
        },

        async generateEmbeddings() {
            this.generatingEmbeddings = true;
            this.embeddingProgress = {
                totalItems: 0,
                processed: 0,
                percentComplete: 0,
                capsulesUpdated: 0,
                messagesUpdated: 0,
                statusText: 'Starting...',
            };

            try {
                // Use SSE for real-time progress updates
                const response = await fetch('/api/embeddings/generate/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        include_memories: true,
                        include_conversations: true,
                    }),
                });

                if (!response.ok) {
                    throw new Error('Embedding generation failed');
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });

                    // Process complete SSE events
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || ''; // Keep incomplete line in buffer

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                this.handleEmbeddingProgress(data);
                            } catch (e) {
                                console.warn('Failed to parse SSE data:', line);
                            }
                        }
                    }
                }

                // Process any remaining data in buffer
                if (buffer.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(buffer.slice(6));
                        this.handleEmbeddingProgress(data);
                    } catch (e) {
                        // Ignore incomplete data
                    }
                }

                await this.loadEmbeddingStats();
            } catch (error) {
                this.showToast('Failed to generate embeddings: ' + error.message, 'error');
                this.embeddingProgress.statusText = 'Error: ' + error.message;
            } finally {
                this.generatingEmbeddings = false;
            }
        },

        handleEmbeddingProgress(data) {
            if (data.type === 'progress') {
                const processed = data.capsules_updated + data.messages_updated;
                this.embeddingProgress = {
                    totalItems: data.total_items,
                    processed: processed,
                    percentComplete: data.percent_complete,
                    capsulesUpdated: data.capsules_updated,
                    messagesUpdated: data.messages_updated,
                    statusText: `Processing: ${processed}/${data.total_items} items (${data.percent_complete}%)`,
                };
            } else if (data.type === 'complete') {
                this.embeddingProgress = {
                    totalItems: data.total_items,
                    processed: data.capsules_updated + data.messages_updated,
                    percentComplete: 100,
                    capsulesUpdated: data.capsules_updated,
                    messagesUpdated: data.messages_updated,
                    statusText: 'Complete!',
                };
                this.showToast(
                    `Generated embeddings: ${data.capsules_updated} memories, ${data.messages_updated} messages in ${data.duration_seconds.toFixed(1)}s`
                );
            } else if (data.type === 'error') {
                this.embeddingProgress.statusText = 'Error: ' + data.error;
                this.showToast('Embedding generation error: ' + data.error, 'error');
            }
        },

        async clearEmbeddings() {
            const confirmed = await this.showConfirm({
                title: 'Clear All Embeddings?',
                message: 'This will delete all existing embeddings. You will need to regenerate them with the new model. This action cannot be undone.',
                confirmText: 'Clear All',
            });

            if (!confirmed) return;

            this.clearingEmbeddings = true;

            try {
                const response = await fetch('/api/embeddings', {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to clear embeddings');
                }

                const result = await response.json();
                this.showToast(
                    `Cleared ${result.count} embeddings (${result.capsules_cleared} memories, ${result.messages_cleared} messages)`,
                    'success'
                );

                // Refresh stats to show 0 coverage
                await this.loadEmbeddingStats();
            } catch (error) {
                this.showToast('Failed to clear embeddings: ' + error.message, 'error');
            } finally {
                this.clearingEmbeddings = false;
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
            const confirmed = await this.showConfirm({
                title: 'Delete Memory',
                message: 'Delete this memory?',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

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
                identity_phrase: 'bg-purple-500/20 text-purple-400',
                ritual: 'bg-indigo-500/20 text-indigo-400',
                witness: 'bg-pink-500/20 text-pink-400',
                style: 'bg-green-500/20 text-green-400',
                custom: 'bg-gray-500/20 text-gray-400',
            };
            return colors[type] || colors.custom;
        },

        // Get display name for memory types (maps internal names to user-friendly labels)
        getTypeDisplayName(type) {
            const displayNames = {
                relational: 'Relational',
                myth_seed: 'Identity Phrase',
                identity_phrase: 'Identity Phrase',
                ritual: 'Command',
                witness: 'Witness',
                style: 'Style',
                custom: 'Custom',
            };
            return displayNames[type] || type;
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
            const confirmed = await this.showConfirm({
                title: 'Delete Ritual',
                message: 'Delete this ritual? This cannot be undone.',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

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

                // Update embeddings state from config
                if (this.config.memory?.embeddings) {
                    this.embeddingsEnabled = this.config.memory.embeddings.enabled || false;
                    this.embeddingsProvider = this.config.memory.embeddings.provider || 'local';
                    this.embeddingsModel = this.config.memory.embeddings.model || 'intfloat/e5-small-v2';
                }

                // Update per-profile isolation state from config
                this.perProfileIsolation = this.config.memory?.per_profile_isolation || false;
                this.defaultShared = this.config.memory?.default_shared || false;
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

        // Provider configuration functions
        async loadProviderConfig() {
            try {
                const response = await fetch('/api/provider/config');
                if (!response.ok) throw new Error('Failed to load provider config');
                const data = await response.json();
                this.providerConfig = data;

                // Ensure endpoints array exists (backward compatibility)
                if (!this.providerConfig.endpoints || !Array.isArray(this.providerConfig.endpoints)) {
                    // Create from legacy api_base if present
                    if (this.providerConfig.api_base) {
                        this.providerConfig.endpoints = [{
                            url: this.providerConfig.api_base,
                            name: 'Primary',
                            priority: 0,
                            purpose: '',
                            is_healthy: null,
                            last_checked: null,
                        }];
                    } else {
                        this.providerConfig.endpoints = [];
                    }
                }

                // Reset API key state when loading
                // Don't show a fake placeholder - just leave empty and show status via has_api_key
                this.providerApiKey = '';
                this.providerApiKeyChanged = false;
                this.showProviderApiKey = false;
                this.providerConnectionStatus = null;
                this.providerConnectionMessage = '';
                this.testingEndpointIndex = null;
            } catch (error) {
                console.error('Failed to load provider config:', error);
            }
        },

        onProviderApiKeyInput() {
            // Mark the key as changed when user types anything
            this.providerApiKeyChanged = true;
        },

        getDefaultApiBase(providerType) {
            const defaults = {
                'openai': 'https://api.openai.com/v1',
                'anthropic': 'https://api.anthropic.com',
                'nous': 'https://inference-api.nousresearch.com/v1',
                'local': '',
                'custom': '',
            };
            return defaults[providerType] || '';
        },

        onProviderTypeChange() {
            // Update default API base when provider type changes
            const defaultUrl = this.getDefaultApiBase(this.providerConfig.provider_type);
            this.providerConfig.api_base = defaultUrl;

            // Also update endpoints - reset to single default endpoint
            if (defaultUrl) {
                this.providerConfig.endpoints = [{
                    url: defaultUrl,
                    name: 'Primary',
                    priority: 0,
                    purpose: '',
                    is_healthy: null,
                    last_checked: null,
                }];
            } else {
                this.providerConfig.endpoints = [];
            }

            // Clear connection status
            this.providerConnectionStatus = null;
            this.providerConnectionMessage = '';
            this.testingEndpointIndex = null;
            // Clear cached models since provider changed
            this.clearProviderModelsCache();
        },

        async testProviderConnection() {
            this.testingProviderConnection = true;
            this.providerConnectionStatus = null;
            this.providerConnectionMessage = '';

            try {
                const payload = {
                    provider_type: this.providerConfig.provider_type,
                    api_base: this.providerConfig.api_base,
                    model: this.providerConfig.model,
                };

                // Only include API key if it was changed and has a value
                if (this.providerApiKeyChanged && this.providerApiKey) {
                    payload.api_key = this.providerApiKey;
                }

                const response = await fetch('/api/provider/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                const data = await response.json();
                this.providerConnectionStatus = data.status;
                this.providerConnectionMessage = data.message;
            } catch (error) {
                this.providerConnectionStatus = 'error';
                this.providerConnectionMessage = 'Connection test failed: ' + error.message;
            } finally {
                this.testingProviderConnection = false;
            }
        },

        async saveProviderConfig() {
            this.savingProviderConfig = true;

            try {
                const payload = {
                    provider_type: this.providerConfig.provider_type,
                    model: this.providerConfig.model,
                };

                // Send endpoints if we have any configured
                if (this.providerConfig.endpoints && this.providerConfig.endpoints.length > 0) {
                    payload.endpoints = this.providerConfig.endpoints.map((ep, idx) => ({
                        url: ep.url,
                        name: ep.name || `Endpoint ${idx + 1}`,
                        priority: ep.priority ?? idx,
                        purpose: ep.purpose || '',
                    }));
                } else {
                    // Fallback to legacy api_base
                    payload.api_base = this.providerConfig.api_base;
                }

                // Only include API key if it was changed and has a value
                if (this.providerApiKeyChanged && this.providerApiKey) {
                    payload.api_key = this.providerApiKey;
                }

                const response = await fetch('/api/provider/config', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to save provider config');
                }

                // Reload config to get updated state
                await this.loadProviderConfig();
                // Clear cached models since config may have changed
                this.clearProviderModelsCache();
                this.showToast('API configuration saved');
            } catch (error) {
                this.showToast('Failed to save API config: ' + error.message, 'error');
            } finally {
                this.savingProviderConfig = false;
            }
        },

        getProviderStatusIcon(providerType) {
            // Check if the provider is configured (has API key or is local)
            if (providerType === 'local') {
                return 'check';
            }
            if (this.providerConfig.provider_type === providerType && this.providerConfig.has_api_key) {
                return 'check';
            }
            return 'warning';
        },

        getProviderHelpText(providerType) {
            const helpTexts = {
                'openai': 'Get your API key from platform.openai.com/api-keys',
                'anthropic': 'Get your API key from console.anthropic.com/settings/keys',
                'nous': 'Get your API key from nous.dev/api-keys or use Hermes inference API',
                'local': 'Using local models via sentence-transformers or llama.cpp',
                'custom': 'Configure a custom OpenAI-compatible API endpoint',
            };
            return helpTexts[providerType] || '';
        },

        // Endpoint management functions
        addEndpoint() {
            const newPriority = this.providerConfig.endpoints.length;
            this.providerConfig.endpoints.push({
                url: '',
                name: newPriority === 0 ? 'Primary' : `Fallback ${newPriority}`,
                priority: newPriority,
                purpose: newPriority === 0 ? 'main' : 'fallback',
                is_healthy: null,
                last_checked: null,
            });
        },

        removeEndpoint(index) {
            if (this.providerConfig.endpoints.length <= 1) {
                this.showToast('At least one endpoint is required', 'error');
                return;
            }
            this.providerConfig.endpoints.splice(index, 1);
            // Re-assign priorities
            this.providerConfig.endpoints.forEach((ep, idx) => {
                ep.priority = idx;
            });
            // Update api_base to match primary endpoint
            if (this.providerConfig.endpoints.length > 0) {
                this.providerConfig.api_base = this.providerConfig.endpoints[0].url;
            }
        },

        moveEndpointUp(index) {
            if (index <= 0) return;
            const endpoints = this.providerConfig.endpoints;
            [endpoints[index], endpoints[index - 1]] = [endpoints[index - 1], endpoints[index]];
            // Update priorities
            endpoints.forEach((ep, idx) => {
                ep.priority = idx;
            });
            // Update api_base to match primary endpoint
            this.providerConfig.api_base = endpoints[0].url;
        },

        moveEndpointDown(index) {
            const endpoints = this.providerConfig.endpoints;
            if (index >= endpoints.length - 1) return;
            [endpoints[index], endpoints[index + 1]] = [endpoints[index + 1], endpoints[index]];
            // Update priorities
            endpoints.forEach((ep, idx) => {
                ep.priority = idx;
            });
            // Update api_base to match primary endpoint
            this.providerConfig.api_base = endpoints[0].url;
        },

        onEndpointUrlChange(index) {
            // Update api_base if this is the primary endpoint
            if (index === 0) {
                this.providerConfig.api_base = this.providerConfig.endpoints[0].url;
            }
            // Clear health status when URL changes
            this.providerConfig.endpoints[index].is_healthy = null;
            this.providerConfig.endpoints[index].last_checked = null;
        },

        async testEndpoint(index) {
            const endpoint = this.providerConfig.endpoints[index];
            if (!endpoint.url) {
                this.showToast('Endpoint URL is required', 'error');
                return;
            }

            this.testingEndpointIndex = index;

            try {
                const response = await fetch(`/api/provider/endpoints/test?endpoint_url=${encodeURIComponent(endpoint.url)}&provider_type=${encodeURIComponent(this.providerConfig.provider_type)}`, {
                    method: 'POST',
                });

                const data = await response.json();

                // Update endpoint health status
                endpoint.is_healthy = data.status === 'success';
                endpoint.last_checked = new Date().toISOString();

                if (data.status === 'success') {
                    this.showToast(`Endpoint "${endpoint.name || 'Unnamed'}" is healthy`);
                } else {
                    this.showToast(`Endpoint test failed: ${data.message}`, 'error');
                }
            } catch (error) {
                endpoint.is_healthy = false;
                endpoint.last_checked = new Date().toISOString();
                this.showToast('Endpoint test failed: ' + error.message, 'error');
            } finally {
                this.testingEndpointIndex = null;
            }
        },

        async testAllEndpoints() {
            for (let i = 0; i < this.providerConfig.endpoints.length; i++) {
                await this.testEndpoint(i);
            }
        },

        getEndpointHealthIcon(endpoint) {
            if (endpoint.is_healthy === null) return 'unknown';
            return endpoint.is_healthy ? 'healthy' : 'unhealthy';
        },

        getEndpointHealthClass(endpoint) {
            if (endpoint.is_healthy === null) return 'text-threadlight-muted';
            return endpoint.is_healthy ? 'text-green-400' : 'text-red-400';
        },

        // Provider models functions
        async loadProviderModels(forceRefresh = false) {
            // Check cache validity
            const now = Date.now();
            const cacheValid = this.providerModelsLastFetched &&
                (now - this.providerModelsLastFetched) < this.providerModelsCacheDuration;

            if (!forceRefresh && cacheValid && this.providerModels.length > 0) {
                console.log('[loadProviderModels] Using cached models');
                return;
            }

            this.providerModelsLoading = true;
            this.providerModelsError = null;

            try {
                const response = await fetch('/api/provider/models');
                const data = await response.json();

                if (data.status === 'success') {
                    this.providerModels = data.models || [];
                    this.providerModelsLastFetched = now;
                    console.log('[loadProviderModels] Loaded', this.providerModels.length, 'models');
                } else {
                    this.providerModelsError = data.message || 'Failed to load models';
                    console.warn('[loadProviderModels] Error:', this.providerModelsError);
                    // Keep any existing cached models on error
                }
            } catch (error) {
                this.providerModelsError = 'Network error: ' + error.message;
                console.error('[loadProviderModels] Exception:', error);
            } finally {
                this.providerModelsLoading = false;
            }
        },

        async refreshProviderModels() {
            // Force refresh, bypassing cache
            await this.loadProviderModels(true);
            if (!this.providerModelsError) {
                this.showToast(`Loaded ${this.providerModels.length} models`);
            }
        },

        clearProviderModelsCache() {
            this.providerModels = [];
            this.providerModelsLastFetched = null;
            this.providerModelsError = null;
        },

        // Check if the model dropdown should be shown vs text input
        shouldShowModelDropdown() {
            return this.providerModels.length > 0 || this.providerModelsLoading;
        },

        // Get a display name for a model
        getModelDisplayName(modelId) {
            const model = this.providerModels.find(m => m.id === modelId);
            return model?.name || modelId;
        },

        // Per-profile memory isolation functions
        async togglePerProfileIsolation() {
            const oldValue = this.perProfileIsolation;
            const newValue = !oldValue;

            // Optimistically update UI
            this.perProfileIsolation = newValue;

            try {
                // Ensure we have valid values (use defaults if undefined)
                const payload = {
                    enabled: Boolean(newValue),
                    default_shared: this.defaultShared !== undefined ? this.defaultShared : false,
                };
                console.log('Isolation toggle payload:', payload);

                const response = await fetch('/api/memory/isolation', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    let errorMsg = 'Failed to update isolation setting';

                    // Handle FastAPI validation errors (detail is an array)
                    if (Array.isArray(data.detail)) {
                        errorMsg = data.detail.map(err => err.msg || JSON.stringify(err)).join(', ');
                    } else if (data.detail) {
                        errorMsg = data.detail;
                    } else if (data.error) {
                        errorMsg = data.error;
                    } else if (data.message) {
                        errorMsg = data.message;
                    }

                    throw new Error(errorMsg);
                }

                this.config.memory.per_profile_isolation = newValue;
                this.showToast(newValue ? 'Per-profile memory isolation enabled' : 'Memory isolation disabled (shared mode)');

                // Reload memories and stats to reflect the new scope
                await this.loadMemories();
                await this.loadProfileScopeStats();
            } catch (error) {
                // Revert optimistic update on error
                this.perProfileIsolation = oldValue;

                // Debug: log the actual error
                console.error('Toggle isolation error:', error);
                console.error('Error type:', typeof error);
                console.error('Error keys:', error ? Object.keys(error) : 'N/A');

                // Extract message more robustly
                let errorMsg = 'Unknown error';
                if (error instanceof Error) {
                    errorMsg = error.message;
                } else if (typeof error === 'string') {
                    errorMsg = error;
                } else if (error && typeof error === 'object') {
                    errorMsg = error.detail || error.error || error.message || JSON.stringify(error);
                }

                this.showToast('Failed to toggle isolation: ' + errorMsg, 'error');
            }
        },

        async toggleDefaultShared() {
            const oldValue = this.defaultShared;
            const newValue = !oldValue;

            // Optimistically update UI
            this.defaultShared = newValue;

            try {
                // Ensure we have valid values (use defaults if undefined)
                const payload = {
                    enabled: Boolean(this.perProfileIsolation),
                    default_shared: newValue,
                };
                console.log('Default shared toggle payload:', payload);

                const response = await fetch('/api/memory/isolation', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    let errorMsg = 'Failed to update default shared setting';

                    // Handle FastAPI validation errors (detail is an array)
                    if (Array.isArray(data.detail)) {
                        errorMsg = data.detail.map(err => err.msg || JSON.stringify(err)).join(', ');
                    } else if (data.detail) {
                        errorMsg = data.detail;
                    } else if (data.error) {
                        errorMsg = data.error;
                    } else if (data.message) {
                        errorMsg = data.message;
                    }

                    throw new Error(errorMsg);
                }

                this.config.memory.default_shared = newValue;
                this.showToast(newValue ? 'New memories shared by default' : 'New memories scoped to profile by default');
            } catch (error) {
                // Revert optimistic update on error
                this.defaultShared = oldValue;

                // Debug: log the actual error
                console.error('Toggle default shared error:', error);
                console.error('Error type:', typeof error);
                console.error('Error keys:', error ? Object.keys(error) : 'N/A');

                // Extract message more robustly
                let errorMsg = 'Unknown error';
                if (error instanceof Error) {
                    errorMsg = error.message;
                } else if (typeof error === 'string') {
                    errorMsg = error;
                } else if (error && typeof error === 'object') {
                    errorMsg = error.detail || error.error || error.message || JSON.stringify(error);
                }

                this.showToast('Failed to update setting: ' + errorMsg, 'error');
            }
        },

        async shareMemory(memoryId) {
            try {
                const response = await fetch(`/api/memories/${memoryId}/share`, {
                    method: 'POST',
                });

                if (!response.ok) throw new Error('Failed to share memory');

                this.showToast('Memory is now shared across all profiles');
                await this.loadMemories();
            } catch (error) {
                this.showToast('Failed to share memory: ' + error.message, 'error');
            }
        },

        async assignMemoryToProfile(memoryId, profileId = null) {
            try {
                const response = await fetch(`/api/memories/${memoryId}/assign`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ profile_id: profileId }),
                });

                if (!response.ok) throw new Error('Failed to assign memory');

                const data = await response.json();
                const profileName = this.profiles.find(p => p.id === data.profile_scope)?.name || data.profile_scope;
                this.showToast(`Memory assigned to ${profileName}`);
                await this.loadMemories();
            } catch (error) {
                this.showToast('Failed to assign memory: ' + error.message, 'error');
            }
        },

        /**
         * Get profile scope badge for a memory.
         * Shows which profile a memory is scoped to, if any.
         */
        getProfileScopeBadge(memory) {
            if (!memory.profile_scope) return null;

            // Find the profile name from our profiles list
            const profile = this.profiles.find(p => p.id === memory.profile_scope);
            const profileName = profile ? profile.name : memory.profile_scope;

            // Check if this is the active profile
            if (memory.profile_scope === this.activeProfileId) {
                return {
                    text: profileName,
                    class: 'bg-threadlight-accent/20 text-threadlight-accent',
                    title: `Profile: ${profileName} (active)`
                };
            }
            return {
                text: profileName,
                class: 'bg-threadlight-warm/20 text-threadlight-warm',
                title: `Profile: ${profileName}`
            };
        },

        async loadProfileScopeStats() {
            try {
                const response = await fetch('/api/profile-scope/stats');
                if (response.ok) {
                    this.profileScopeStats = await response.json();
                }
            } catch (error) {
                console.error('Failed to load profile scope stats:', error);
            }
        },

        async loadProfileScopeConfig() {
            try {
                const response = await fetch('/api/memory/isolation');
                if (response.ok) {
                    const data = await response.json();
                    this.perProfileIsolation = data.per_profile_isolation || false;
                    this.defaultShared = data.default_shared || false;
                }
            } catch (error) {
                console.error('Failed to load profile scope config:', error);
            }
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

        // Model configuration functions
        async loadModels() {
            try {
                const response = await fetch('/api/models');
                const data = await response.json();
                this.availableModels = data.models || [];
                this.currentModelId = data.current_model;

                // Load current model config
                await this.loadCurrentModelConfig();
            } catch (error) {
                console.error('Failed to load models:', error);
            }
        },

        async loadCurrentModelConfig() {
            try {
                const response = await fetch('/api/models/current');
                const data = await response.json();
                this.currentModelId = data.model_id;
                this.currentModelConfig = data.config?.config || data.config || {
                    system_prompt: '',
                    style_profile: null,
                    memory_enabled: true,
                    decay_enabled: false,
                    temperature: 0.7,
                    max_tokens: null,
                    top_p: 1.0,
                };
                // Extract from nested config if needed
                if (this.currentModelConfig.memory) {
                    this.currentModelConfig.memory_enabled = this.currentModelConfig.memory.enabled;
                    this.currentModelConfig.decay_enabled = this.currentModelConfig.memory.decay_enabled;
                }
            } catch (error) {
                console.error('Failed to load current model config:', error);
            }
        },

        async switchModel(modelId) {
            if (!modelId || modelId === this.currentModelId) return;

            try {
                const response = await fetch('/api/models/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_id: modelId }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to switch model');
                }

                const data = await response.json();
                this.currentModelId = modelId;
                this.currentModelConfig = data.config?.config || data.config || {};
                // Extract from nested config if needed
                if (this.currentModelConfig.memory) {
                    this.currentModelConfig.memory_enabled = this.currentModelConfig.memory.enabled;
                    this.currentModelConfig.decay_enabled = this.currentModelConfig.memory.decay_enabled;
                }

                // Reload config and models
                await this.loadConfig();
                await this.loadModels();

                this.showConfigSaved();
                this.showToast(`Switched to ${modelId}`);
            } catch (error) {
                this.showToast('Failed to switch model: ' + error.message, 'error');
            }
        },

        async updateCurrentModelConfig(updates) {
            try {
                const response = await fetch(`/api/models/${this.currentModelId}/config`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to update model config');
                }

                const data = await response.json();
                // Update local state
                Object.assign(this.currentModelConfig, updates);

                this.showConfigSaved();
            } catch (error) {
                this.showToast('Failed to update model config: ' + error.message, 'error');
            }
        },

        async addNewModel() {
            if (!this.newModelData.model_id) {
                this.showToast('Please enter a model ID', 'error');
                return;
            }

            try {
                const response = await fetch(`/api/models/${this.newModelData.model_id}/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        system_prompt: this.newModelData.system_prompt,
                        style_profile: this.newModelData.style_profile || null,
                        memory_enabled: this.newModelData.memory_enabled,
                        decay_enabled: this.newModelData.decay_enabled,
                        temperature: this.newModelData.temperature,
                    }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to add model');
                }

                this.showToast(`Added model: ${this.newModelData.model_id}`);
                this.showAddModelModal = false;
                this.newModelData = {
                    model_id: '',
                    system_prompt: 'You are a helpful AI assistant.',
                    style_profile: '',
                    memory_enabled: true,
                    decay_enabled: false,
                    temperature: 0.7,
                };
                await this.loadModels();
            } catch (error) {
                this.showToast('Failed to add model: ' + error.message, 'error');
            }
        },

        async copySettingsToAllModels() {
            const confirmed = await this.showConfirm({
                title: 'Copy Settings',
                message: 'Copy current model settings to all other models?',
                confirmText: 'Copy',
                confirmClass: 'bg-threadlight-accent hover:bg-threadlight-accent/80',
            });
            if (!confirmed) return;

            try {
                // Get all model IDs
                for (const model of this.availableModels) {
                    if (model.model_id !== this.currentModelId && model.model_id !== 'default') {
                        await fetch(`/api/models/${this.currentModelId}/copy-to/${model.model_id}`, {
                            method: 'POST',
                        });
                    }
                }

                this.showToast('Settings copied to all models');
                await this.loadModels();
            } catch (error) {
                this.showToast('Failed to copy settings: ' + error.message, 'error');
            }
        },

        async setAsDefaultSettings() {
            try {
                await fetch(`/api/models/${this.currentModelId}/set-as-default`, {
                    method: 'POST',
                });

                this.showToast('Settings set as default for new models');
            } catch (error) {
                this.showToast('Failed to set as default: ' + error.message, 'error');
            }
        },

        showConfigSaved() {
            this.configSaved = true;
            setTimeout(() => {
                this.configSaved = false;
            }, 2000);
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
            const builtinStyles = ['minimal', 'professional', 'creative'];
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
                use_freeform: false,
                freeform_description: '',
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
                use_freeform: style.use_freeform || false,
                freeform_description: style.freeform_description || '',
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
                use_freeform: false,
                freeform_description: '',
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
                        use_freeform: this.newStyle.use_freeform,
                        freeform_description: this.newStyle.freeform_description,
                    }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || `Failed to ${this.editingStyleMode ? 'update' : 'create'} style`);
                }

                this.showToast(`Style ${this.editingStyleMode ? 'updated' : 'created'} successfully`);
                this.showStyleEditor = false;
                this.editingStyleMode = false;
                this.newStyle = { style_id: '', tone_base: '', permissionsStr: '', constraintsStr: '', vocalMotifsStr: '', use_freeform: false, freeform_description: '' };
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
            const confirmed = await this.showConfirm({
                title: 'Delete Style',
                message: 'Delete this style profile?',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

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

        // Preview what the style will look like in the system prompt
        previewStyle() {
            if (this.newStyle.use_freeform && this.newStyle.freeform_description) {
                this.stylePreviewContent = `## Style\n${this.newStyle.freeform_description}`;
            } else {
                let sections = [];
                if (this.newStyle.tone_base) {
                    sections.push(`## Voice\nYour base tone is ${this.newStyle.tone_base}.`);
                }
                const permissions = this.newStyle.permissionsStr.split('\n').map(s => s.trim()).filter(s => s);
                if (permissions.length > 0) {
                    sections.push(`## Permissions\nYou are allowed to:\n${permissions.map(p => '- ' + p).join('\n')}`);
                }
                const constraints = this.newStyle.constraintsStr.split('\n').map(s => s.trim()).filter(s => s);
                if (constraints.length > 0) {
                    sections.push(`## Constraints\nYou should avoid:\n${constraints.map(c => '- ' + c).join('\n')}`);
                }
                const motifs = this.newStyle.vocalMotifsStr.split(',').map(s => s.trim()).filter(s => s);
                if (motifs.length > 0) {
                    sections.push(`## Motifs\nThese phrases are part of your voice: ${motifs.map(m => '"' + m + '"').join(', ')}`);
                }
                this.stylePreviewContent = sections.join('\n\n') || '(No style content defined)';
            }
            this.stylePreviewVisible = true;
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

        // Conversation Import functions
        handleConversationSelect(event) {
            this.conversationFile = event.target.files[0];
            this.conversationImportResult = null;
        },

        handleConversationDrop(event) {
            this.isDraggingConversation = false;
            const files = event.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                const ext = file.name.split('.').pop().toLowerCase();
                if (ext === 'zip' || ext === 'json') {
                    this.conversationFile = file;
                    this.conversationImportResult = null;
                } else {
                    this.showToast('Please upload a .zip or .json file', 'error');
                }
            }
        },

        formatFileSize(bytes) {
            if (!bytes) return '';
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        },

        async importConversations() {
            if (!this.conversationFile) return;

            this.importingConversations = true;
            this.conversationImportResult = null;

            try {
                const formData = new FormData();
                formData.append('file', this.conversationFile);

                // Pass active profile ID for scoping imported conversations
                if (this.activeProfileId) {
                    formData.append('profile_id', this.activeProfileId);
                }

                const response = await fetch('/api/import/conversations', {
                    method: 'POST',
                    body: formData,
                });

                const result = await response.json();
                this.conversationImportResult = result;

                if (result.success) {
                    this.conversationFile = null;
                    // Reload conversations list
                    await this.loadConversations();
                    await this.loadStats();
                    const profileInfo = result.profile_name ? ` to profile "${result.profile_name}"` : '';
                    this.showToast(`Imported ${result.conversations_imported || 0} conversations${profileInfo}`);
                }
            } catch (error) {
                this.conversationImportResult = { error: error.message };
            } finally {
                this.importingConversations = false;
            }
        },

        viewImportedConversations() {
            this.conversationImportResult = null;
            this.currentView = 'chat';
            // Reload conversations to show the newly imported ones
            this.loadConversations();
        },

        // Profile Import functions (from Import view)
        handleProfileSelect(event) {
            this.profileImportFile = event.target.files[0];
            this.profileImportResult = null;
        },

        handleProfileDrop(event) {
            this.isDraggingProfile = false;
            const files = event.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                const ext = file.name.split('.').pop().toLowerCase();
                if (ext === 'json') {
                    this.profileImportFile = file;
                    this.profileImportResult = null;
                } else {
                    this.showToast('Please upload a .json profile file', 'error');
                }
            }
        },

        async importProfileFromFile() {
            if (!this.profileImportFile) return;

            this.importingProfile = true;
            this.profileImportResult = null;

            try {
                const text = await this.profileImportFile.text();
                const data = JSON.parse(text);

                const response = await fetch('/api/profiles/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data }),
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Failed to import profile');
                }

                const result = await response.json();
                this.profileImportResult = result;
                this.profileImportFile = null;
                await this.loadProfiles();
                this.showToast(`Profile "${result.profile?.name}" imported successfully`);
            } catch (error) {
                this.profileImportResult = { error: error.message };
            } finally {
                this.importingProfile = false;
            }
        },

        viewImportedProfile() {
            this.profileImportResult = null;
            this.currentView = 'profiles';
            this.loadProfiles();
        },

        // Memory Type functions
        async loadMemoryTypes() {
            try {
                const response = await fetch('/api/memory-types');
                const data = await response.json();
                this.memoryTypes = data.types || [];
            } catch (error) {
                console.error('Failed to load memory types:', error);
            }
        },

        async loadExampleTypes() {
            try {
                const response = await fetch('/api/memory-types/examples');
                const data = await response.json();
                this.exampleTypes = data.examples || [];
            } catch (error) {
                console.error('Failed to load example types:', error);
            }
        },

        viewMemoryType(memType) {
            this.selectedMemoryType = memType;
        },

        openMemoryTypeEditor() {
            this.newMemoryType = {
                type_id: '',
                description: '',
                display_template: '',
                fields: [{ name: '', field_type: 'string', required: false }],
            };
            this.showMemoryTypeEditor = true;
        },

        addMemoryTypeField() {
            this.newMemoryType.fields.push({ name: '', field_type: 'string', required: false });
        },

        removeMemoryTypeField(index) {
            this.newMemoryType.fields.splice(index, 1);
        },

        async createMemoryType() {
            if (!this.newMemoryType.type_id || this.newMemoryType.fields.length === 0) {
                this.showToast('Please provide a type ID and at least one field', 'error');
                return;
            }

            // Filter out empty fields
            const validFields = this.newMemoryType.fields.filter(f => f.name.trim());
            if (validFields.length === 0) {
                this.showToast('At least one field must have a name', 'error');
                return;
            }

            try {
                const response = await fetch('/api/memory-types', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type_id: this.newMemoryType.type_id,
                        description: this.newMemoryType.description || null,
                        display_template: this.newMemoryType.display_template || null,
                        fields: validFields.map(f => ({
                            name: f.name.trim(),
                            field_type: f.field_type,
                            required: f.required,
                            description: f.description || null,
                        })),
                    }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to create memory type');
                }

                this.showToast('Memory type created successfully');
                this.showMemoryTypeEditor = false;
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to create memory type: ' + error.message, 'error');
            }
        },

        async deleteMemoryType(typeId) {
            if (!typeId) return;
            const confirmed = await this.showConfirm({
                title: 'Delete Memory Type',
                message: 'Delete this memory type? Existing memories of this type will become orphaned.',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

            try {
                const response = await fetch(`/api/memory-types/${typeId}`, {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to delete memory type');
                }

                this.showToast('Memory type deleted');
                this.selectedMemoryType = null;
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to delete memory type: ' + error.message, 'error');
            }
        },

        async importExampleType(typeId) {
            try {
                const response = await fetch(`/api/memory-types/import/${typeId}`, {
                    method: 'POST',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to import example type');
                }

                this.showToast('Example type imported successfully');
                this.showExampleTypes = false;
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to import example type: ' + error.message, 'error');
            }
        },

        // Legacy function name - now calls loadProfileScopeConfig
        async loadModelScopeConfig() {
            await this.loadProfileScopeConfig();
            await this.loadProfileScopeStats();
        },

        // Profile functions
        async loadProfiles() {
            try {
                console.log('[loadProfiles] Fetching profiles...');
                // Add cache-busting parameter to prevent browser caching
                const response = await fetch(`/api/profiles?_=${Date.now()}`);
                if (response.ok) {
                    const data = await response.json();
                    console.log('[loadProfiles] Received', data.profiles?.length, 'profiles');
                    // Log all profiles with their descriptions
                    data.profiles?.forEach(p => {
                        console.log(`[loadProfiles] Profile "${p.name}": description="${p.description}"`);
                    });
                    this.profiles = data.profiles || [];
                    this.activeProfileId = data.active_profile_id;
                } else {
                    console.error('[loadProfiles] Response not ok:', response.status);
                }
            } catch (error) {
                console.error('Failed to load profiles:', error);
            }
        },

        async switchProfile(profileId) {
            try {
                const response = await fetch(`/api/profiles/${profileId}/switch`, {
                    method: 'POST',
                });
                if (response.ok) {
                    const data = await response.json();
                    this.activeProfileId = data.profile.id;
                    this.showToast(`Switched to profile: ${data.profile.name}`);
                    await this.loadConfig();  // Reload config to reflect profile changes
                } else {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to switch profile');
                }
            } catch (error) {
                this.showToast('Failed to switch profile: ' + error.message, 'error');
            }
        },

        async clearActiveProfile() {
            try {
                const response = await fetch('/api/profiles/clear', {
                    method: 'POST',
                });
                if (response.ok) {
                    this.activeProfileId = null;
                    this.showToast('Profile cleared, using default settings');
                    await this.loadConfig();
                }
            } catch (error) {
                this.showToast('Failed to clear profile: ' + error.message, 'error');
            }
        },

        openProfileEditor(profile = null) {
            // Load provider models when opening the editor
            this.loadProviderModels();

            if (profile) {
                // Edit mode
                this.editingProfileMode = true;
                this.selectedProfile = profile;
                this.newProfile = {
                    name: profile.name || '',
                    description: profile.description || '',
                    system_prompt: profile.system_prompt || '',
                    style_profile_id: profile.style_profile_id || '',
                    model_strategy: profile.model_strategy || 'single',
                    primary_model: profile.primary_model || '',
                    model_pool: profile.model_pool || [],
                    model_pool_str: (profile.model_pool || []).join(', '),
                    memory_scope: profile.memory_scope || 'isolated',
                    access_shared_memories: profile.access_shared_memories !== false,
                    tags: profile.tags || [],
                    tags_str: (profile.tags || []).join(', '),
                    philosophy: profile.philosophy || '',
                    approach_to_rituals: profile.approach_to_rituals || '',
                    routing_rules: profile.routing_rules || [],
                    useManualModelInput: false,  // Start with dropdown if models available
                };
            } else {
                // Create mode
                this.editingProfileMode = false;
                this.selectedProfile = null;
                this.newProfile = {
                    name: '',
                    description: '',
                    system_prompt: '',
                    style_profile_id: '',
                    model_strategy: 'single',
                    primary_model: this.config.provider.model || '',
                    model_pool: [],
                    model_pool_str: '',
                    memory_scope: 'isolated',
                    access_shared_memories: true,
                    tags: [],
                    tags_str: '',
                    philosophy: '',
                    approach_to_rituals: '',
                    routing_rules: [],
                    useManualModelInput: false,  // Start with dropdown if models available
                };
            }
            this.showProfileEditor = true;
        },

        cancelProfileEditor() {
            this.showProfileEditor = false;
            this.selectedProfile = null;
            this.editingProfileMode = false;
        },

        async saveProfile() {
            // Parse comma-separated fields
            const modelPool = this.newProfile.model_pool_str
                ? this.newProfile.model_pool_str.split(',').map(s => s.trim()).filter(s => s)
                : [];
            const tags = this.newProfile.tags_str
                ? this.newProfile.tags_str.split(',').map(s => s.trim()).filter(s => s)
                : [];

            const profileData = {
                name: this.newProfile.name,
                description: this.newProfile.description,
                system_prompt: this.newProfile.system_prompt,
                style_profile_id: this.newProfile.style_profile_id || null,
                model_strategy: this.newProfile.model_strategy,
                primary_model: this.newProfile.primary_model || null,
                model_pool: modelPool.length > 0 ? modelPool : null,
                memory_scope: this.newProfile.memory_scope,
                access_shared_memories: this.newProfile.access_shared_memories,
                tags: tags.length > 0 ? tags : null,
                philosophy: this.newProfile.philosophy || '',
                approach_to_rituals: this.newProfile.approach_to_rituals || '',
                routing_rules: this.newProfile.routing_rules.length > 0 ? this.newProfile.routing_rules : null,
            };

            console.log('[saveProfile] Saving profile:', profileData.name);
            console.log('[saveProfile] Description being sent:', profileData.description);

            try {
                let response;
                if (this.editingProfileMode && this.selectedProfile) {
                    // Update existing profile
                    console.log('[saveProfile] PUT to /api/profiles/' + this.selectedProfile.id);
                    response = await fetch(`/api/profiles/${this.selectedProfile.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(profileData),
                    });
                } else {
                    // Create new profile
                    console.log('[saveProfile] POST to /api/profiles');
                    response = await fetch('/api/profiles', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(profileData),
                    });
                }

                console.log('[saveProfile] Response status:', response.status);
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to save profile');
                }

                const data = await response.json();
                console.log('[saveProfile] Response data:', data);
                console.log('[saveProfile] Returned profile description:', data.profile?.description);
                this.showToast(this.editingProfileMode ? 'Profile updated' : 'Profile created');

                // Trigger flash animation for the saved profile
                const profileId = this.editingProfileMode ? this.selectedProfile.id : data.profile?.id;
                if (profileId) {
                    this.savedProfileId = profileId;
                    setTimeout(() => { this.savedProfileId = null; }, 1000);
                }

                this.showProfileEditor = false;
                this.selectedProfile = null;
                await this.loadProfiles();
            } catch (error) {
                console.error('[saveProfile] Error:', error);
                this.showToast('Failed to save profile: ' + error.message, 'error');
            }
        },

        async deleteProfile(profileId) {
            if (!profileId) return;
            const confirmed = await this.showConfirm({
                title: 'Delete Profile',
                message: 'Delete this profile? This cannot be undone.',
                confirmText: 'Delete',
            });
            if (!confirmed) return;

            try {
                const response = await fetch(`/api/profiles/${profileId}`, {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to delete profile');
                }

                this.showToast('Profile deleted');
                this.selectedProfile = null;
                await this.loadProfiles();
            } catch (error) {
                this.showToast('Failed to delete profile: ' + error.message, 'error');
            }
        },

        async exportProfile(profileId) {
            try {
                const response = await fetch(`/api/profiles/${profileId}/export`);
                if (!response.ok) {
                    throw new Error('Failed to export profile');
                }

                const data = await response.json();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `profile-${data.name || profileId}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                this.showToast('Profile exported');
            } catch (error) {
                this.showToast('Failed to export profile: ' + error.message, 'error');
            }
        },

        async importProfile(event) {
            const file = event.target.files[0];
            if (!file) return;

            try {
                const text = await file.text();
                const data = JSON.parse(text);

                const response = await fetch('/api/profiles/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data }),
                });

                if (!response.ok) {
                    const responseData = await response.json();
                    throw new Error(responseData.detail || 'Failed to import profile');
                }

                this.showToast('Profile imported successfully');
                await this.loadProfiles();
            } catch (error) {
                this.showToast('Failed to import profile: ' + error.message, 'error');
            }

            // Reset file input
            event.target.value = '';
        },

        getActiveProfile() {
            return this.profiles.find(p => p.id === this.activeProfileId) || null;
        },

        // ============================================
        // Routing Rules Functions
        // ============================================

        openRoutingRuleEditor(ruleIndex = null) {
            if (ruleIndex !== null && this.newProfile.routing_rules[ruleIndex]) {
                // Edit existing rule
                this.editingRoutingRule = ruleIndex;
                const rule = this.newProfile.routing_rules[ruleIndex];
                this.newRoutingRule = {
                    match_type: rule.match_type || 'keyword',
                    pattern: rule.pattern || '',
                    target_model: rule.target_model || '',
                    priority: rule.priority ?? 50,
                };
            } else {
                // Create new rule
                this.editingRoutingRule = null;
                this.newRoutingRule = {
                    match_type: 'keyword',
                    pattern: '',
                    target_model: this.newProfile.model_pool_str
                        ? this.newProfile.model_pool_str.split(',')[0]?.trim() || ''
                        : this.newProfile.primary_model || '',
                    priority: 50,
                };
            }
            this.routingRuleValidationError = '';
            this.showRoutingRuleEditor = true;
        },

        cancelRoutingRuleEditor() {
            this.showRoutingRuleEditor = false;
            this.editingRoutingRule = null;
            this.routingRuleValidationError = '';
        },

        validateRoutingRule() {
            const rule = this.newRoutingRule;

            // Pattern is required
            if (!rule.pattern.trim()) {
                this.routingRuleValidationError = 'Pattern is required';
                return false;
            }

            // Target model is required
            if (!rule.target_model.trim()) {
                this.routingRuleValidationError = 'Target model is required';
                return false;
            }

            // Validate regex pattern
            if (rule.match_type === 'regex') {
                try {
                    new RegExp(rule.pattern);
                } catch (e) {
                    this.routingRuleValidationError = 'Invalid regex pattern: ' + e.message;
                    return false;
                }
            }

            // Validate length pattern (must be a positive number)
            if (rule.match_type === 'length') {
                const length = parseInt(rule.pattern, 10);
                if (isNaN(length) || length <= 0) {
                    this.routingRuleValidationError = 'Length must be a positive number';
                    return false;
                }
            }

            // Priority must be a number between 0 and 100
            if (rule.priority < 0 || rule.priority > 100) {
                this.routingRuleValidationError = 'Priority must be between 0 and 100';
                return false;
            }

            this.routingRuleValidationError = '';
            return true;
        },

        saveRoutingRule() {
            if (!this.validateRoutingRule()) {
                return;
            }

            const rule = {
                match_type: this.newRoutingRule.match_type,
                pattern: this.newRoutingRule.pattern.trim(),
                target_model: this.newRoutingRule.target_model.trim(),
                priority: parseInt(this.newRoutingRule.priority, 10) || 50,
            };

            if (this.editingRoutingRule !== null) {
                // Update existing rule
                this.newProfile.routing_rules[this.editingRoutingRule] = rule;
            } else {
                // Add new rule
                this.newProfile.routing_rules.push(rule);
            }

            // Sort rules by priority (descending)
            this.newProfile.routing_rules.sort((a, b) => (b.priority || 0) - (a.priority || 0));

            this.cancelRoutingRuleEditor();
        },

        deleteRoutingRule(index) {
            this.newProfile.routing_rules.splice(index, 1);
        },

        moveRoutingRuleUp(index) {
            if (index <= 0) return;
            const rules = this.newProfile.routing_rules;
            // Swap priorities instead of array positions (since array is sorted by priority)
            const currentPriority = rules[index].priority || 0;
            const abovePriority = rules[index - 1].priority || 0;
            rules[index].priority = abovePriority + 1;
            // Re-sort
            this.newProfile.routing_rules.sort((a, b) => (b.priority || 0) - (a.priority || 0));
        },

        moveRoutingRuleDown(index) {
            const rules = this.newProfile.routing_rules;
            if (index >= rules.length - 1) return;
            // Swap priorities instead of array positions
            const currentPriority = rules[index].priority || 0;
            const belowPriority = rules[index + 1].priority || 0;
            rules[index].priority = belowPriority - 1;
            // Re-sort
            this.newProfile.routing_rules.sort((a, b) => (b.priority || 0) - (a.priority || 0));
        },

        getMatchTypeLabel(matchType) {
            const labels = {
                'keyword': 'Contains',
                'regex': 'Regex',
                'length': 'Length >',
                'starts_with': 'Starts with',
                'ends_with': 'Ends with',
            };
            return labels[matchType] || matchType;
        },

        getMatchTypeHelpText(matchType) {
            const help = {
                'keyword': 'Message contains this word or phrase (case-insensitive)',
                'regex': 'Message matches this regular expression pattern',
                'length': 'Message has more than this many characters',
                'starts_with': 'Message begins with this text',
                'ends_with': 'Message ends with this text',
            };
            return help[matchType] || '';
        },

        getPatternPlaceholder(matchType) {
            const placeholders = {
                'keyword': 'e.g., code, help, explain',
                'regex': 'e.g., ^/[a-z]+, \\bcode\\b',
                'length': 'e.g., 500',
                'starts_with': 'e.g., /, Hey, Can you',
                'ends_with': 'e.g., ?, please, thanks',
            };
            return placeholders[matchType] || '';
        },

        // Model Strategy metadata and helpers
        getStrategyInfo(strategy) {
            const strategies = {
                'single': {
                    name: 'Single Model',
                    category: 'basic',
                    description: 'Use one model for all requests. Simple and predictable.',
                    when_to_use: 'Best for: Most use cases, consistent behavior, debugging',
                    requires: 'Primary model only',
                    example: 'All messages go to GPT-4o',
                },
                'alternating': {
                    name: 'Alternating',
                    category: 'basic',
                    description: 'Cycle through models in order. Each request goes to the next model in the pool.',
                    when_to_use: 'Best for: Distributing load, comparing model outputs over time',
                    requires: 'Model pool (order matters)',
                    example: 'Request 1 → GPT-4o, Request 2 → Claude, Request 3 → GPT-4o, ...',
                },
                'round_robin': {
                    name: 'Round Robin',
                    category: 'basic',
                    description: 'Similar to alternating - cycles through models sequentially with conversation context.',
                    when_to_use: 'Best for: Load balancing across equivalent models',
                    requires: 'Model pool (order matters)',
                    example: 'Distributes requests evenly across all pool models',
                },
                'weighted': {
                    name: 'Weighted Random',
                    category: 'advanced',
                    description: 'Randomly select models with configurable probability weights.',
                    when_to_use: 'Best for: Gradual migration, A/B testing, cost optimization',
                    requires: 'Model pool with weights (format: model:weight)',
                    example: 'gpt-4o:70, claude-3-opus:30 → 70% GPT-4o, 30% Claude',
                },
                'dynamic': {
                    name: 'Ratio-Based',
                    category: 'advanced',
                    description: 'Select models based on defined ratios. Deterministic distribution over time.',
                    when_to_use: 'Best for: Precise cost control, guaranteed distribution percentages',
                    requires: 'Model pool with ratios (format: model:ratio)',
                    example: '3:1 ratio ensures exactly 75%/25% split over requests',
                },
                'routed': {
                    name: 'Content Routed',
                    category: 'advanced',
                    description: 'Route to different models based on message content using pattern matching rules.',
                    when_to_use: 'Best for: Specialized models for different tasks (code, creative, analysis)',
                    requires: 'Routing rules with patterns and target models',
                    example: 'Code questions → GPT-4o, Creative writing → Claude',
                },
            };
            return strategies[strategy] || strategies['single'];
        },

        getStrategyDescription(strategy) {
            return this.getStrategyInfo(strategy).description;
        },

        getStrategyWhenToUse(strategy) {
            return this.getStrategyInfo(strategy).when_to_use;
        },

        getStrategyRequires(strategy) {
            return this.getStrategyInfo(strategy).requires;
        },

        getStrategyExample(strategy) {
            return this.getStrategyInfo(strategy).example;
        },

        isBasicStrategy(strategy) {
            return ['single', 'alternating', 'round_robin'].includes(strategy);
        },

        isAdvancedStrategy(strategy) {
            return ['weighted', 'dynamic', 'routed'].includes(strategy);
        },

        strategyNeedsModelPool(strategy) {
            return strategy !== 'single';
        },

        strategyNeedsWeights(strategy) {
            return strategy === 'weighted';
        },

        strategyNeedsRatios(strategy) {
            return strategy === 'dynamic';
        },

        strategyNeedsRoutingRules(strategy) {
            return strategy === 'routed';
        },

        strategyPoolOrderMatters(strategy) {
            return ['alternating', 'round_robin'].includes(strategy);
        },

        getModelPoolPlaceholder(strategy) {
            if (this.strategyNeedsWeights(strategy)) {
                return 'gpt-4o:70, claude-3-opus:30 (model:weight pairs)';
            }
            if (this.strategyNeedsRatios(strategy)) {
                return 'gpt-4o:3, claude-3-opus:1 (model:ratio pairs)';
            }
            return 'gpt-4o, claude-3-opus, gemini-pro';
        },

        getModelPoolHelpText(strategy) {
            if (this.strategyNeedsWeights(strategy)) {
                return 'Enter models with weights (0-100). Weights determine selection probability. Example: gpt-4o:70, claude:30 means 70% chance for GPT-4o.';
            }
            if (this.strategyNeedsRatios(strategy)) {
                return 'Enter models with ratios. Ratios determine distribution over time. Example: gpt-4o:3, claude:1 means 3 out of every 4 requests go to GPT-4o.';
            }
            if (this.strategyPoolOrderMatters(strategy)) {
                return 'Models are used in order. Drag to reorder or list them in your preferred sequence.';
            }
            return 'List of models available for this strategy to use.';
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

        // Show confirmation modal and return a promise
        showConfirm(options) {
            return new Promise((resolve) => {
                this.confirmModal = {
                    visible: true,
                    title: options.title || 'Confirm',
                    message: options.message || 'Are you sure?',
                    confirmText: options.confirmText || 'Confirm',
                    cancelText: options.cancelText || 'Cancel',
                    confirmClass: options.confirmClass || 'bg-red-600 hover:bg-red-700',
                    onConfirm: () => {
                        this.confirmModal.visible = false;
                        resolve(true);
                    },
                };
                // Store cancel handler for escape key or cancel button
                this.confirmModal.onCancel = () => {
                    this.confirmModal.visible = false;
                    resolve(false);
                };
            });
        },

        // Show prompt modal and return a promise
        showPrompt(options) {
            return new Promise((resolve) => {
                this.promptModal = {
                    visible: true,
                    title: options.title || 'Enter Value',
                    message: options.message || '',
                    placeholder: options.placeholder || '',
                    value: options.defaultValue || '',
                    confirmText: options.confirmText || 'Submit',
                    cancelText: options.cancelText || 'Cancel',
                    onConfirm: () => {
                        const value = this.promptModal.value;
                        this.promptModal.visible = false;
                        this.promptModal.value = '';
                        resolve(value);
                    },
                };
                // Store cancel handler
                this.promptModal.onCancel = () => {
                    this.promptModal.visible = false;
                    this.promptModal.value = '';
                    resolve(null);
                };
            });
        },
    };
}
