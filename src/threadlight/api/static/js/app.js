/**
 * Threadlight Web UI - Alpine.js Application
 * Version: 2026-02-13-multimodal-images
 */

// Log when script loads to verify we're running the updated version
console.log('[app.js] Loading Threadlight app version 2026-02-13-multimodal-images');

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
        conversationSearchDebounce: null,
        isSearchingConversations: false,
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

        // Image attachment state
        pendingImages: [],       // Array of {file: File, preview: string (data URL)}
        maxImageSize: 10 * 1024 * 1024,  // 10 MB
        allowedImageTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],

        // Message editing state
        editingMessageId: null,
        editedMessageContent: '',

        // Message variant state (for response regeneration with history)
        // Map of variant_group_id -> {variants: [...], currentIndex: number}
        messageVariants: {},
        // Tracks which message IDs have variant groups (message_id -> variant_group_id)
        messageVariantGroups: {},

        // WebSocket
        ws: null,
        wsConnected: false,

        // Memory state
        memories: [],
        memorySearch: '',
        memoryTypeFilter: '',
        memoryScopeFilter: '',  // '' = auto (server decides), 'shared' = shared only, '<profile_id>' = that profile only
        selectedMemory: null,
        showCreateMemory: false,
        showProposalsModal: false,
        proposals: [],
        newMemory: {
            type: 'relational',
            content: {},
            cuePhrasesStr: '',
        },

        // Tier review state
        showTierReviewModal: false,
        tierReviewMemories: [],
        tierReviewChanges: [],
        isTierReviewConversation: false,

        // Type classification state
        isTypeClassificationConversation: false,

        // Bulk delete state
        selectedMemoryIds: [],

        // Archive state
        showArchived: false,

        // Memory links state
        showLinkCreationModal: false,
        linkCreationSource: null,  // Source capsule being linked from
        linkCreationForm: {
            target_capsule_id: '',
            link_type: 'clarifies',
            strength: 1.0,
            bidirectional: false,
            notes: '',
        },
        linkSearchQuery: '',
        linkSearchResults: [],
        selectedMemoryForLink: null,

        // Common link types (user can also type custom)
        linkTypeOptions: [
            { value: 'clarifies', label: 'Clarifies', description: 'Target clarifies the source' },
            { value: 'elaborates', label: 'Elaborates', description: 'Target adds detail to source' },
            { value: 'contradicts', label: 'Contradicts', description: 'Target conflicts with source' },
            { value: 'contextualizes', label: 'Contextualizes', description: 'Target provides background' },
            { value: 'deepens', label: 'Deepens', description: 'Target adds emotional depth' },
            { value: 'precedes', label: 'Precedes', description: 'Target happened before source' },
            { value: 'echoes', label: 'Echoes', description: 'Target resonates thematically' },
            { value: 'supports', label: 'Supports', description: 'Target reinforces source' },
        ],

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

        // Legacy provider configuration state (for migration detection)
        legacyProviderConfig: {
            provider_type: 'local',
            api_base: '',
            has_api_key: false,
        },

        // Computed property to check if legacy config exists
        get hasLegacyProviderConfig() {
            // Legacy config only exists if user has actually configured something worth migrating.
            // A fresh database with default settings is NOT legacy config.
            // The key indicator is has_api_key - without an API key, there's nothing to migrate.
            const cfg = this.legacyProviderConfig;
            if (!cfg) return false;
            if (cfg.provider_type === 'local') return false;
            // Only show migration banner if there's an actual API key configured
            return cfg.has_api_key;
        },

        // Provider models state (fetched from API)
        providerModels: [],  // List of available models from provider
        providerModelsLoading: false,
        providerModelsError: null,
        providerModelsLastFetched: null,  // Timestamp for cache invalidation
        providerModelsCacheDuration: 5 * 60 * 1000,  // Cache for 5 minutes

        // Multi-provider state (named providers)
        namedProviders: [],  // List of ProviderDefinition objects
        showAddProviderModal: false,
        editingProviderId: null,  // ID of provider being edited
        providerForm: {
            id: '',
            name: '',
            type: 'openai',
            api_key: '',
            api_key_env_var: '',
            api_base: '',
            default_model: '',
        },

        // Available API key environment variables (for selection)
        availableApiKeyEnvVars: [],
        loadingApiKeyEnvVars: false,

        // Model configuration state
        currentModelId: '',
        currentModelProviderId: '',  // Provider ID for current model (empty = default)
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
            system_prompt: '',
            style_profile: '',
            memory_enabled: true,
            decay_enabled: false,
            temperature: 0.7,
            provider_id: '',
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
        hiddenBuiltinTypes: [],
        selectedMemoryType: null,
        showMemoryTypeEditor: false,
        showExampleTypes: false,
        editingMemoryType: null,  // For editing existing types
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
            selectedProviderId: '',  // Provider to filter models and associate on save
            model_pool: [],
            model_pool_str: '',  // For comma-separated input
            memory_scope: 'isolated',
            access_shared_memories: true,
            tags: [],
            tags_str: '',  // For comma-separated input
            philosophy: '',  // DEPRECATED: Freeform philosophy description
            approach_to_rituals: '',  // DEPRECATED: Freeform approach to rituals
            system_prompt_sections: [],  // List of {name, content} dicts
            use_freeform_prompt: false,  // If true, use system_prompt instead of sections
            routing_rules: [],  // For content-routed strategy
            knowledge_summary_text: '',  // JSON text for knowledge summary
            knowledge_summary_expanded: false,  // UI state for knowledge summary section
            knowledge_summary_error: null,  // JSON validation error
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

        // Profile templates state
        profileTemplates: [],
        showTemplatesModal: false,

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
            await this.loadNamedProviders();

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

            // Listen for paste events to handle image pasting
            document.addEventListener('paste', (e) => {
                // Only handle paste if we're in the chat view
                if (this.currentView !== 'chat') return;

                const items = e.clipboardData?.items;
                if (!items) return;

                let hasImage = false;
                for (let item of items) {
                    if (item.type.startsWith('image/')) {
                        hasImage = true;
                        const file = item.getAsFile();
                        if (file) {
                            this.processImageFile(file);
                        }
                    }
                }

                // If we handled an image, prevent default paste behavior
                if (hasImage) {
                    e.preventDefault();
                }
            });

            // Watch currentModelId and force select element to sync
            // This fixes Alpine.js x-model desync with dynamically-populated select options
            this.$watch('currentModelId', (newValue) => {
                this.$nextTick(() => {
                    this.syncModelSelectElement();
                });
            });

            // Also do an initial sync after all data is loaded
            // Use a small delay to ensure x-for has finished rendering all options
            this.$nextTick(() => {
                setTimeout(() => {
                    this.syncModelSelectElement();
                }, 50);
            });
        },

        // Helper to force the model select dropdown(s) to match currentModelId
        // Needed because Alpine.js x-model can desync with dynamically-populated options
        syncModelSelectElement() {
            // Sync ALL model selects (there are two: chat header and settings page)
            const selectElements = document.querySelectorAll('select[x-model="currentModelId"]');
            selectElements.forEach((selectEl, idx) => {
                if (selectEl && selectEl.value !== this.currentModelId) {
                    console.log(`[model-select-sync] Syncing select #${idx} from "${selectEl.value}" to "${this.currentModelId}"`);
                    selectEl.value = this.currentModelId;
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

                case 'complete':
                    // Add complete response as a new message
                    this.messages = [...this.messages, {
                        role: 'assistant',
                        content: data.content,
                        memories: data.memories_recalled || [],
                        tool_results: data.tool_results || null,
                        usage: data.usage || null,
                    }];
                    this.isTyping = false;
                    this.scrollToBottom();
                    break;

                case 'ritual_response':
                    this.messages = [...this.messages, {
                        role: 'assistant',
                        type: 'ritual',
                        content: data.content,
                    }];
                    this.scrollToBottom();
                    break;

                case 'error':
                    if (data.is_rate_limit) {
                        this.showToast('⏱️ Rate limit reached. Please wait a moment before continuing.', 'error');
                    } else {
                        this.showToast(data.message, 'error');
                    }
                    this.isTyping = false;
                    break;

                case 'history_cleared':
                    this.chatHistory = [];
                    break;

                case 'regenerate_complete':
                    // A new variant was generated - update the message in place
                    this.handleRegenerateComplete(data);
                    this.isTyping = false;
                    break;

                case 'continue_response':
                    // Append the continuation as a new assistant message
                    this.messages = [...this.messages, {
                        role: 'assistant',
                        content: data.content,
                        memories: [],
                    }];
                    this.isTyping = false;
                    this.scrollToBottom();
                    break;
            }
        },

        // Chat functions
        async sendMessage(options = {}) {
            const message = this.inputMessage.trim();
            if (!message && this.pendingImages.length === 0) return;

            // Check for ritual invocation (only if no images attached)
            if (message.startsWith('/') && this.pendingImages.length === 0) {
                this.inputMessage = '';
                await this.invokeRitual(message);
                return;
            }

            // If this is a group chat, use the group chat endpoint
            if (this.isGroupChat && this.currentConversationId) {
                await this.sendGroupMessage();
                return;
            }

            // Capture current images and clear state
            const attachedImages = [...this.pendingImages];
            const imageDataUrls = attachedImages.map(img => img.preview);

            // Add user message to display - use immutable update for Alpine reactivity
            const displayMsg = {
                role: 'user',
                content: message,
            };
            // Attach image previews for display in chat
            if (attachedImages.length > 0) {
                displayMsg.images = attachedImages.map(img => img.preview);
            }
            this.messages = [...this.messages, displayMsg];
            this.inputMessage = '';
            this.pendingImages = [];
            this.scrollToBottom();

            // If images are attached, always use HTTP (WebSocket can't send files via FormData)
            if (attachedImages.length > 0) {
                console.log('[sendMessage] Images attached, using HTTP multipart');
                await this.sendMessageWithImages(message, attachedImages);
                return;
            }

            // Send via WebSocket if connected
            console.log('[sendMessage] WebSocket state check:', {
                wsConnected: this.wsConnected,
                readyState: this.ws?.readyState,
                hasWs: !!this.ws,
                OPEN: WebSocket.OPEN
            });

            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                console.log('[sendMessage] Sending via WebSocket with profile_id:', this.activeProfileId);
                try {
                    const payload = {
                        type: 'chat',
                        message: message,
                        profile_id: this.activeProfileId,
                        conversation_id: this.currentConversationId,
                    };
                    // Conditionally enable tools when explicitly requested
                    if (options.enableTools) {
                        payload.enable_tools = options.enableTools;
                        console.log('[sendMessage] Tools enabled:', options.enableTools);
                    }
                    // Auto-call a tool and include results in context
                    if (options.autoTool) {
                        payload.auto_tool = options.autoTool;
                        console.log('[sendMessage] Auto-tool:', options.autoTool);
                    }
                    console.log('[sendMessage] Payload:', payload);
                    console.log('[sendMessage] Calling ws.send() now...');
                    this.ws.send(JSON.stringify(payload));
                    console.log('[sendMessage] ws.send() completed');
                } catch (error) {
                    console.error('[sendMessage] WebSocket send failed:', error);
                    // Fall back to HTTP
                    await this.sendMessageHTTP(message);
                }
            } else {
                console.log('[sendMessage] WebSocket not ready, using HTTP');
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
                        profile_id: this.activeProfileId,
                    }),
                });

                const data = await response.json();

                this.messages = [...this.messages, {
                    role: 'assistant',
                    content: data.content,
                    memories: data.memories_recalled || [],
                }];

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

        // Image attachment methods
        processImageFile(file) {
            // Validate image type
            if (!this.allowedImageTypes.includes(file.type)) {
                this.showToast(`Unsupported image type: ${file.type}. Use JPEG, PNG, GIF, or WebP.`, 'error');
                return;
            }
            // Validate image size
            if (file.size > this.maxImageSize) {
                this.showToast(`Image "${file.name}" exceeds 10 MB limit.`, 'error');
                return;
            }
            // Read as data URL for preview and sending
            const reader = new FileReader();
            reader.onload = (e) => {
                this.pendingImages = [...this.pendingImages, {
                    file: file,
                    preview: e.target.result,
                    name: file.name,
                }];
            };
            reader.readAsDataURL(file);
        },

        handleImageSelect(event) {
            const files = Array.from(event.target.files || []);
            for (const file of files) {
                this.processImageFile(file);
            }
            // Reset the file input so the same file can be re-selected
            event.target.value = '';
        },

        removeImage(index) {
            this.pendingImages = this.pendingImages.filter((_, i) => i !== index);
        },

        async sendMessageWithImages(message, attachedImages) {
            this.isTyping = true;

            try {
                const formData = new FormData();
                formData.append('message', message);
                formData.append('history', JSON.stringify(this.chatHistory));
                if (this.activeProfileId) {
                    formData.append('profile_id', this.activeProfileId);
                }
                // Append each image file
                for (const img of attachedImages) {
                    formData.append('images', img.file);
                }

                const response = await fetch('/api/chat/image', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || `HTTP ${response.status}`);
                }

                const data = await response.json();

                this.messages = [...this.messages, {
                    role: 'assistant',
                    content: data.content,
                    memories: data.memories_recalled || [],
                }];

                // Update history (text only for history, images are one-shot)
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
            this.messages = [...this.messages, {
                role: 'user',
                content: name,
            }];
            this.scrollToBottom();

            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'ritual',
                    name: name,
                    conversation_id: this.currentConversationId,
                    profile_id: this.activeProfileId,
                }));
            } else {
                try {
                    const response = await fetch('/api/rituals/invoke', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ritual_name: name }),
                    });

                    const data = await response.json();

                    this.messages = [...this.messages, {
                        role: 'assistant',
                        type: 'ritual',
                        content: data.response,
                    }];
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

        async loadConversations(searchQuery = null) {
            try {
                const params = new URLSearchParams();
                params.append('limit', '50');
                if (this.showArchivedConversations) {
                    params.append('include_archived', 'true');
                }
                // Add search parameter if provided (searches titles AND message content)
                if (searchQuery && searchQuery.trim()) {
                    params.append('search', searchQuery.trim());
                }

                const response = await fetch(`/api/conversations?${params}`);
                const data = await response.json();
                this.conversations = data.conversations || [];

                // Only auto-load most recent conversation if not searching and none selected
                if (!searchQuery && !this.currentConversationId && this.conversations.length > 0) {
                    await this.loadConversation(this.conversations[0].id);
                }
            } catch (error) {
                console.error('Failed to load conversations:', error);
            }
        },

        // Debounced search for conversations (searches titles AND message content)
        searchConversationsDebounced() {
            // Clear existing timer
            if (this.conversationSearchDebounce) {
                clearTimeout(this.conversationSearchDebounce);
            }

            // If search is empty, load immediately without debounce
            if (!this.conversationSearch || !this.conversationSearch.trim()) {
                this.isSearchingConversations = false;
                this.loadConversations();
                return;
            }

            // Show searching indicator
            this.isSearchingConversations = true;

            // Debounce the actual search by 300ms
            this.conversationSearchDebounce = setTimeout(async () => {
                await this.loadConversations(this.conversationSearch);
                this.isSearchingConversations = false;
            }, 300);
        },

        get filteredConversations() {
            // Server-side search handles filtering, so just return all loaded conversations
            return this.conversations;
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
                this.isTierReviewConversation = false;  // Reset tier review state
                this.isTypeClassificationConversation = false;  // Reset type classification state
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
                console.log('[loadConversation] Loading conversation:', conversationId, 'currentModelId before:', this.currentModelId);
                // First get conversation details to check if it's a group chat
                const convResponse = await fetch(`/api/conversations/${conversationId}`);
                if (convResponse.ok) {
                    const convData = await convResponse.json();
                    console.log('[loadConversation] Conversation data:', { id: convData.id, model: convData.model, name: convData.name });
                    this.isGroupChat = convData.participant_profiles && convData.participant_profiles.length > 1;

                    // Detect special conversation types to show Apply buttons
                    // Check metadata.purpose first (preferred), fallback to name-based detection
                    const purpose = convData.metadata?.purpose;
                    this.isTierReviewConversation = purpose === 'tier_review' || convData.name === 'Memory Tier Review';
                    this.isTypeClassificationConversation = purpose === 'type_classification' || convData.name === 'Memory Type Classification';

                    // Update current model to match conversation's model
                    if (convData.model) {
                        // Check if this model exists in availableModels
                        const modelExists = this.availableModels.some(m => m.model_id === convData.model);
                        if (!modelExists) {
                            // Add it dynamically so the dropdown can display it
                            console.log('[loadConversation] Model not in availableModels, adding:', convData.model);
                            this.availableModels = [...this.availableModels, { model_id: convData.model, is_current: false }];
                        }
                        if (convData.model !== this.currentModelId) {
                            console.log('[loadConversation] Updating currentModelId from', this.currentModelId, 'to', convData.model);
                            this.currentModelId = convData.model;
                        }
                    }
                    console.log('[loadConversation] currentModelId after update:', this.currentModelId, 'availableModels:', this.availableModels.map(m => m.model_id));
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
                    variant_group_id: msg.variant_group_id || null,
                    variant_index: msg.variant_index || 0,
                }));

                // Load variant data for messages that have variant groups
                this.messageVariants = {};
                this.messageVariantGroups = {};
                await this.loadAllVariants();

                // Rebuild chat history for context
                this.chatHistory = this.messages.slice(-20).map(m => ({
                    role: m.role,
                    content: m.content,
                }));

                this.scrollToBottom();

                // Sync the model dropdown after loading conversation
                // This ensures the select element matches currentModelId
                this.$nextTick(() => {
                    this.syncModelSelectElement();
                });
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

            // Add user message to display - use immutable update for Alpine reactivity
            this.messages = [...this.messages, {
                role: 'user',
                content: message,
            }];
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

                // Add each profile's response - use immutable update for Alpine reactivity
                const newMessages = data.responses.map(resp => ({
                    role: 'assistant',
                    content: resp.content,
                    profile_id: resp.profile_id,
                    profile_name: this.getProfileNameById(resp.profile_id),
                    memories: resp.memories_recalled || [],
                }));
                this.messages = [...this.messages, ...newMessages];
                this.scrollToBottom();

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

                // Update local state - use immutable update for Alpine reactivity
                const msgIndex = this.messages.findIndex(m => m.id === this.editingMessageId);
                if (msgIndex !== -1) {
                    const updated = { ...this.messages[msgIndex], content: this.editedMessageContent };
                    this.messages = [...this.messages.slice(0, msgIndex), updated, ...this.messages.slice(msgIndex + 1)];
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
            // Create a new variant of this assistant message instead of deleting it
            if (!msg.id) {
                this.showToast('Cannot regenerate: message has no ID', 'error');
                return;
            }

            try {
                // Call the regenerate API to set up variant group and get user message
                const response = await fetch(`/api/messages/${msg.id}/regenerate`, {
                    method: 'POST',
                });

                if (!response.ok) {
                    const err = await response.json();
                    this.showToast(err.detail || 'Failed to regenerate', 'error');
                    return;
                }

                const data = await response.json();
                const { variant_group_id, next_variant_index, user_message, conversation_id } = data;

                // Update the current message's variant_group_id in local state
                const msgIndex = this.messages.findIndex(m => m.id === msg.id);
                if (msgIndex !== -1) {
                    this.messages = this.messages.map((m, i) => {
                        if (i === msgIndex) {
                            return { ...m, variant_group_id };
                        }
                        return m;
                    });
                }

                // Send regeneration request via WebSocket
                if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                    this.isTyping = true;
                    this.ws.send(JSON.stringify({
                        type: 'regenerate_variant',
                        user_message: user_message,
                        variant_group_id: variant_group_id,
                        next_variant_index: next_variant_index,
                        profile_id: this.activeProfileId,
                        conversation_id: conversation_id,
                    }));
                } else {
                    this.showToast('WebSocket not connected. Cannot regenerate.', 'error');
                }
            } catch (error) {
                this.showToast('Failed to regenerate: ' + error.message, 'error');
            }
        },

        // Load all variant groups for the current conversation's messages
        async loadAllVariants() {
            const variantGroupIds = new Set();
            for (const msg of this.messages) {
                if (msg.variant_group_id) {
                    variantGroupIds.add(msg.variant_group_id);
                    this.messageVariantGroups[msg.id] = msg.variant_group_id;
                }
            }

            // Fetch variants for each group
            for (const groupId of variantGroupIds) {
                // Find any message with this group ID to use for the API call
                const msgWithGroup = this.messages.find(m => m.variant_group_id === groupId);
                if (msgWithGroup) {
                    await this.loadMessageVariants(msgWithGroup.id);
                }
            }
        },

        // Load variants for a specific message
        async loadMessageVariants(messageId) {
            try {
                const response = await fetch(`/api/messages/${messageId}/variants`);
                if (!response.ok) return;

                const data = await response.json();
                if (!data.variant_group_id || data.variants.length <= 1) return;

                const groupId = data.variant_group_id;

                // Find which variant is currently displayed
                const displayedMsg = this.messages.find(m => m.variant_group_id === groupId);
                let currentIndex = data.variants.length - 1; // Default to latest
                if (displayedMsg) {
                    const idx = data.variants.findIndex(v => v.id === displayedMsg.id);
                    if (idx >= 0) currentIndex = idx;
                }

                this.messageVariants[groupId] = {
                    variants: data.variants,
                    currentIndex: currentIndex,
                };

                // Map all variant message IDs to this group
                for (const v of data.variants) {
                    this.messageVariantGroups[v.id] = groupId;
                }
            } catch (error) {
                console.error('Failed to load message variants:', error);
            }
        },

        // Get variant info for a message (used by template)
        getVariantInfo(msg) {
            const groupId = msg.variant_group_id || this.messageVariantGroups[msg.id];
            if (!groupId || !this.messageVariants[groupId]) return null;
            return this.messageVariants[groupId];
        },

        // Switch to a different variant (direction: 'prev' or 'next')
        switchToVariant(msg, direction) {
            const groupId = msg.variant_group_id || this.messageVariantGroups[msg.id];
            if (!groupId || !this.messageVariants[groupId]) return;

            const variantData = this.messageVariants[groupId];
            const newIndex = direction === 'prev'
                ? Math.max(0, variantData.currentIndex - 1)
                : Math.min(variantData.variants.length - 1, variantData.currentIndex + 1);

            if (newIndex === variantData.currentIndex) return;

            variantData.currentIndex = newIndex;
            const newVariant = variantData.variants[newIndex];

            // Update the message content in the messages array
            const msgIndex = this.messages.findIndex(m =>
                m.variant_group_id === groupId ||
                this.messageVariantGroups[m.id] === groupId
            );

            if (msgIndex !== -1) {
                // Create a new messages array for reactivity
                this.messages = this.messages.map((m, i) => {
                    if (i === msgIndex) {
                        return {
                            ...m,
                            id: newVariant.id,
                            content: newVariant.content,
                            variant_index: newVariant.variant_index,
                            variant_group_id: groupId,
                        };
                    }
                    return m;
                });
            }

            // Force reactivity update
            this.messageVariants = { ...this.messageVariants };
        },

        // Handle a completed regeneration with variant data
        handleRegenerateComplete(data) {
            const { content, message_id, variant_group_id, variant_index, usage } = data;

            // Find the message in the display that belongs to this variant group
            const msgIndex = this.messages.findIndex(m =>
                m.variant_group_id === variant_group_id ||
                this.messageVariantGroups[m.id] === variant_group_id
            );

            if (msgIndex === -1) {
                console.error('Could not find message for variant group:', variant_group_id);
                return;
            }

            // Build the new variant object
            const newVariant = {
                id: message_id,
                content: content,
                variant_index: variant_index,
                variant_group_id: variant_group_id,
            };

            // Update or create the variant group state
            if (!this.messageVariants[variant_group_id]) {
                // First regeneration - create the group with the original + new variant
                const originalMsg = this.messages[msgIndex];
                this.messageVariants[variant_group_id] = {
                    variants: [
                        {
                            id: originalMsg.id,
                            content: originalMsg.content,
                            variant_index: 0,
                            variant_group_id: variant_group_id,
                        },
                        newVariant,
                    ],
                    currentIndex: 1, // Show the new variant
                };
            } else {
                // Add to existing variant group
                this.messageVariants[variant_group_id].variants.push(newVariant);
                this.messageVariants[variant_group_id].currentIndex =
                    this.messageVariants[variant_group_id].variants.length - 1;
            }

            // Map the new variant's message ID to this group
            this.messageVariantGroups[message_id] = variant_group_id;

            // Update the displayed message to show the new variant
            this.messages = this.messages.map((m, i) => {
                if (i === msgIndex) {
                    return {
                        ...m,
                        id: message_id,
                        content: content,
                        variant_group_id: variant_group_id,
                        variant_index: variant_index,
                        usage: usage || m.usage,
                    };
                }
                return m;
            });

            // Force reactivity update
            this.messageVariants = { ...this.messageVariants };
        },

        // Copy assistant message content to clipboard
        async copyMessageContent(msg) {
            try {
                await navigator.clipboard.writeText(msg.content);
                this.showToast('Copied to clipboard');
            } catch (error) {
                // Fallback for browsers that don't support clipboard API
                const textArea = document.createElement('textarea');
                textArea.value = msg.content;
                textArea.style.position = 'fixed';
                textArea.style.left = '-9999px';
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    this.showToast('Copied to clipboard');
                } catch (e) {
                    this.showToast('Failed to copy: ' + e.message, 'error');
                }
                document.body.removeChild(textArea);
            }
        },

        // Continue the last assistant response
        async continueResponse() {
            // Find the last assistant message
            const lastAssistantIndex = this.findLastAssistantMessageIndex();
            if (lastAssistantIndex === -1) {
                this.showToast('No assistant message to continue', 'error');
                return;
            }

            // Send a continue request via WebSocket
            if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'continue',
                    conversation_id: this.currentConversationId,
                    profile_id: this.activeProfileId,
                }));
            } else {
                // Fallback: send a message asking to continue
                this.inputMessage = 'Please continue your response.';
                await this.sendMessage();
            }
        },

        // Edit a user message and regenerate from that point
        async editAndRegenerate(msg) {
            if (!this.editingMessageId || !this.editedMessageContent.trim()) return;

            const msgIndex = this.messages.findIndex(m => m.id === msg.id);
            if (msgIndex === -1) {
                this.showToast('Message not found', 'error');
                return;
            }

            const newContent = this.editedMessageContent;

            try {
                // Update the message content first
                const response = await fetch(`/api/messages/${msg.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: newContent }),
                });

                if (!response.ok) throw new Error('Failed to update message');

                // Find the next message (should be assistant response) and delete it and all after
                if (msgIndex + 1 < this.messages.length) {
                    const nextMsgId = this.messages[msgIndex + 1].id;
                    if (nextMsgId) {
                        try {
                            await fetch(`/api/messages/${nextMsgId}/and-after`, {
                                method: 'DELETE',
                            });
                        } catch (error) {
                            console.error('Failed to delete messages from server:', error);
                        }
                    }
                }

                // Update local state - keep messages up to and including the edited one
                const updatedMsg = { ...this.messages[msgIndex], content: newContent };
                this.messages = [...this.messages.slice(0, msgIndex), updatedMsg];

                // Clear edit state
                this.editingMessageId = null;
                this.editedMessageContent = '';

                // Regenerate the response
                if (this.wsConnected && this.ws?.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'chat',
                        message: newContent,
                        profile_id: this.activeProfileId,
                        conversation_id: this.currentConversationId,
                    }));
                } else {
                    await this.sendMessageHTTP(newContent);
                }

            } catch (error) {
                this.showToast('Failed to edit and regenerate: ' + error.message, 'error');
            }
        },

        // Check if a message at a given index is the last assistant message
        isLastAssistantMessage(index) {
            // Find the last assistant message index
            const lastIndex = this.findLastAssistantMessageIndex();
            return index === lastIndex;
        },

        // Find the index of the last assistant message
        findLastAssistantMessageIndex() {
            for (let i = this.messages.length - 1; i >= 0; i--) {
                if (this.messages[i].role === 'assistant') {
                    return i;
                }
            }
            return -1;
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
                if (this.showArchived) params.append('include_archived', 'true');
                params.append('limit', '100');

                // Profile scope filtering
                if (this.memoryScopeFilter === 'shared') {
                    params.append('profile_scope', '__none__');
                    params.append('include_shared', 'true');
                } else if (this.memoryScopeFilter === 'all') {
                    params.append('profile_scope', '__all__');
                } else if (this.memoryScopeFilter) {
                    // Specific profile ID selected
                    params.append('profile_scope', this.memoryScopeFilter);
                    params.append('include_shared', 'false');
                } else if (this.activeProfileId) {
                    // Default: explicitly send active profile ID so server doesn't rely on stale state
                    params.append('profile_scope', this.activeProfileId);
                }
                // If no active profile and no filter, server returns all (no scope filter)

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

        async loadProposals() {
            try {
                const response = await fetch('/api/proposals');
                if (!response.ok) throw new Error('Failed to load proposals');
                const data = await response.json();
                this.proposals = data.proposals || [];
            } catch (error) {
                console.error('Failed to load proposals:', error);
                this.showToast('Failed to load proposals: ' + error.message, 'error');
            }
        },

        async approveProposalInline(proposalId, tool) {
            try {
                const response = await fetch(`/api/proposals/${proposalId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: "confirm" }),
                });

                if (!response.ok) throw new Error('Failed to approve proposal');

                // Update the tool result to show it was approved
                tool.requires_consent = false;
                tool.success = true;

                this.showToast('Memory approved');
                await this.loadStats();
            } catch (error) {
                console.error('Failed to approve proposal:', error);
                this.showToast('Failed to approve: ' + error.message, 'error');
            }
        },

        async rejectProposalInline(proposalId, tool) {
            try {
                const response = await fetch(`/api/proposals/${proposalId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: "reject" }),
                });

                if (!response.ok) throw new Error('Failed to reject proposal');

                // Update the tool result to show it was rejected
                tool.requires_consent = false;
                tool.success = false;

                this.showToast('Memory proposal rejected');
                await this.loadStats();
            } catch (error) {
                console.error('Failed to reject proposal:', error);
                this.showToast('Failed to reject: ' + error.message, 'error');
            }
        },

        async approveProposal(proposalId) {
            try {
                const response = await fetch(`/api/proposals/${proposalId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: "confirm" }),
                });

                if (!response.ok) throw new Error('Failed to approve proposal');

                this.showToast('Memory approved');
                await this.loadProposals();
                await this.loadStats();
            } catch (error) {
                console.error('Failed to approve proposal:', error);
                this.showToast('Failed to approve: ' + error.message, 'error');
            }
        },

        async rejectProposal(proposalId) {
            try {
                const response = await fetch(`/api/proposals/${proposalId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: "reject" }),
                });

                if (!response.ok) throw new Error('Failed to reject proposal');

                this.showToast('Memory proposal rejected');
                await this.loadProposals();
                await this.loadStats();
            } catch (error) {
                console.error('Failed to reject proposal:', error);
                this.showToast('Failed to reject: ' + error.message, 'error');
            }
        },

        toggleMemorySelection(memoryId) {
            const index = this.selectedMemoryIds.indexOf(memoryId);
            if (index > -1) {
                this.selectedMemoryIds.splice(index, 1);
            } else {
                this.selectedMemoryIds.push(memoryId);
            }
        },

        toggleSelectAll() {
            if (this.selectedMemoryIds.length === this.memories.length) {
                // Deselect all
                this.selectedMemoryIds = [];
            } else {
                // Select all
                this.selectedMemoryIds = this.memories.map(m => m.id);
            }
        },

        async bulkDeleteMemories() {
            if (this.selectedMemoryIds.length === 0) return;

            const confirmed = await this.showConfirm({
                title: 'Delete Memories',
                message: `Delete ${this.selectedMemoryIds.length} selected memories? This cannot be undone.`,
                confirmText: 'Delete All',
            });
            if (!confirmed) return;

            try {
                const response = await fetch('/api/memories/batch-delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capsule_ids: this.selectedMemoryIds,
                        force: true
                    })
                });

                const result = await response.json();

                if (!response.ok) throw new Error(result.detail || 'Failed to delete memories');

                this.showToast(`Deleted ${result.summary.successful} memories successfully`);
                if (result.summary.failed > 0) {
                    this.showToast(`${result.summary.failed} memories failed to delete`, 'error');
                }

                this.selectedMemoryIds = [];
                await this.loadMemories();
                await this.loadStats();
            } catch (error) {
                this.showToast('Failed to delete memories: ' + error.message, 'error');
            }
        },

        async bulkArchiveMemories() {
            if (this.selectedMemoryIds.length === 0) return;

            try {
                const response = await fetch('/api/memories/batch-archive', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capsule_ids: this.selectedMemoryIds,
                        archived: true
                    })
                });

                const result = await response.json();

                if (!response.ok) throw new Error(result.detail || 'Failed to archive memories');

                this.showToast(`Archived ${result.summary.successful} memories successfully`);
                if (result.summary.failed > 0) {
                    this.showToast(`${result.summary.failed} memories failed to archive`, 'error');
                }

                this.selectedMemoryIds = [];
                await this.loadMemories();
                await this.loadStats();
            } catch (error) {
                this.showToast('Failed to archive memories: ' + error.message, 'error');
            }
        },

        async bulkAssignToProfile() {
            if (this.selectedMemoryIds.length === 0) return;

            const profileId = this.activeProfileId;
            if (!profileId) {
                this.showToast('No active profile selected', 'error');
                return;
            }

            try {
                const response = await fetch('/api/memories/batch-assign', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capsule_ids: this.selectedMemoryIds,
                        profile_id: profileId
                    })
                });

                const result = await response.json();

                if (!response.ok) throw new Error(result.detail || 'Failed to assign memories');

                const profileName = this.profiles.find(p => p.id === profileId)?.name || profileId;
                this.showToast(`Assigned ${result.summary.successful} memories to ${profileName}`);
                if (result.summary.failed > 0) {
                    this.showToast(`${result.summary.failed} memories failed to assign`, 'error');
                }

                this.selectedMemoryIds = [];
                await this.loadMemories();
            } catch (error) {
                this.showToast('Failed to assign memories: ' + error.message, 'error');
            }
        },

        async bulkShareMemories() {
            if (this.selectedMemoryIds.length === 0) return;

            try {
                const response = await fetch('/api/memories/batch-assign', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capsule_ids: this.selectedMemoryIds,
                        profile_id: null
                    })
                });

                const result = await response.json();

                if (!response.ok) throw new Error(result.detail || 'Failed to share memories');

                this.showToast(`Shared ${result.summary.successful} memories across all profiles`);
                if (result.summary.failed > 0) {
                    this.showToast(`${result.summary.failed} memories failed to share`, 'error');
                }

                this.selectedMemoryIds = [];
                await this.loadMemories();
            } catch (error) {
                this.showToast('Failed to share memories: ' + error.message, 'error');
            }
        },

        async archiveMemory(memoryId, archived = true) {
            try {
                const response = await fetch('/api/memories/batch-archive', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        capsule_ids: [memoryId],
                        archived: archived
                    })
                });

                const result = await response.json();

                if (!response.ok) throw new Error(result.detail || 'Failed to archive memory');

                this.showToast(archived ? 'Memory archived' : 'Memory restored');
                await this.loadMemories();
                await this.loadStats();
            } catch (error) {
                this.showToast('Failed to update memory: ' + error.message, 'error');
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

        // --- Memory Links Methods ---

        // Open link creation modal
        showLinkModal(sourceCapsuleId) {
            this.linkCreationSource = sourceCapsuleId;
            this.linkCreationForm = {
                target_capsule_id: '',
                link_type: 'clarifies',
                strength: 1.0,
                bidirectional: false,
                notes: '',
            };
            this.linkSearchQuery = '';
            this.linkSearchResults = [];
            this.selectedMemoryForLink = null;
            this.showLinkCreationModal = true;
        },

        // Search for memories to link to (exclude source)
        async searchMemoriesForLink() {
            if (!this.linkSearchQuery || this.linkSearchQuery.length < 2) {
                this.linkSearchResults = [];
                return;
            }

            try {
                const params = new URLSearchParams({
                    search: this.linkSearchQuery,
                    limit: '10',
                });
                const response = await fetch(`/api/memories?${params}`);
                const data = await response.json();

                // Exclude the source capsule from results
                this.linkSearchResults = (data.memories || []).filter(
                    m => m.id !== this.linkCreationSource
                );
            } catch (error) {
                console.error('Failed to search memories:', error);
            }
        },

        // Select a memory as link target
        selectMemoryForLink(memory) {
            this.selectedMemoryForLink = memory;
            this.linkCreationForm.target_capsule_id = memory.id;
            this.linkSearchQuery = '';
            this.linkSearchResults = [];
        },

        // Create the link
        async createMemoryLink() {
            if (!this.linkCreationForm.target_capsule_id) {
                this.showToast('Please select a memory to link to', 'error');
                return;
            }

            try {
                const response = await fetch(
                    `/api/memories/${this.linkCreationSource}/links`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.linkCreationForm),
                    }
                );

                if (!response.ok) {
                    const error = await response.text();
                    throw new Error(error);
                }

                const sourceCapsuleId = this.linkCreationSource;

                // Close modal and reload links
                this.showLinkCreationModal = false;
                this.showToast('Memory link created');

                // Reload links on the source memory
                await this.loadMemoryLinks(sourceCapsuleId);

                // Refresh the memory detail view if open
                if (this.selectedMemory?.id === sourceCapsuleId) {
                    this.selectedMemory = { ...this.selectedMemory };
                }
            } catch (error) {
                console.error('Failed to create link:', error);
                this.showToast('Failed to create link: ' + error.message, 'error');
            }
        },

        // Load links for a memory (uses linked-capsules endpoint for preview data)
        async loadMemoryLinks(capsuleId) {
            try {
                const response = await fetch(`/api/memories/${capsuleId}/linked-capsules`);
                const data = await response.json();

                // Transform into a flat list with link + target capsule info
                const links = (data.linked_capsules || []).map(item => ({
                    ...item.link,
                    target_preview: item.capsule?.preview || 'Linked memory',
                    target_type: item.capsule?.type || '',
                    target_id: item.capsule?.id || item.link.target_capsule_id,
                }));

                // Attach to the memory object in the list
                const memory = this.memories.find(m => m.id === capsuleId);
                if (memory) {
                    memory.links = links;
                    memory.link_count = links.length;
                }

                // Also update selectedMemory if it matches
                if (this.selectedMemory?.id === capsuleId) {
                    this.selectedMemory.links = links;
                    this.selectedMemory.link_count = links.length;
                }

                return links;
            } catch (error) {
                console.error('Failed to load links:', error);
                return [];
            }
        },

        // Delete a link
        async deleteMemoryLink(capsuleId, linkId) {
            if (!confirm('Delete this memory link?')) return;

            try {
                const response = await fetch(
                    `/api/memories/${capsuleId}/links/${linkId}`,
                    { method: 'DELETE' }
                );

                if (!response.ok) throw new Error('Failed to delete link');

                this.showToast('Memory link deleted');

                // Reload links
                await this.loadMemoryLinks(capsuleId);
            } catch (error) {
                console.error('Failed to delete link:', error);
                this.showToast('Failed to delete link', 'error');
            }
        },

        async loadMemoriesForTierReview() {
            try {
                // Build query parameters to filter by active profile
                let url = '/api/memories?limit=1000';
                if (this.activeProfileId) {
                    url += `&profile_id=${this.activeProfileId}`;
                }

                const response = await fetch(url);
                const data = await response.json();
                this.tierReviewMemories = data.memories || [];
                this.tierReviewChanges = [];
            } catch (error) {
                this.showToast('Failed to load memories: ' + error.message, 'error');
            }
        },

        updateMemoryTierInReview(capsuleId, newTier) {
            // Find the memory in the review list
            const memory = this.tierReviewMemories.find(m => m.id === capsuleId);
            if (!memory) return;

            const oldTier = memory.memory_tier || 'semantic';

            // If tier actually changed
            if (oldTier !== newTier) {
                // Update the memory in the UI
                memory.memory_tier = newTier;

                // Track the change
                const existingChange = this.tierReviewChanges.find(c => c.capsule_id === capsuleId);
                if (existingChange) {
                    existingChange.tier = newTier;
                } else {
                    this.tierReviewChanges.push({
                        capsule_id: capsuleId,
                        tier: newTier
                    });
                }
            }
        },

        async submitTierReviewChanges() {
            if (this.tierReviewChanges.length === 0) return;

            try {
                const response = await fetch('/api/memories/batch-tier-update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        updates: this.tierReviewChanges
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || 'Failed to update tiers');
                }

                // Show success message
                this.showToast(`Updated ${result.summary.successful} memories successfully`);

                // Show errors if any
                if (result.summary.failed > 0) {
                    this.showToast(`${result.summary.failed} memories failed to update`, 'error');
                }

                // Close modal and reload memories
                this.showTierReviewModal = false;
                this.tierReviewChanges = [];
                await this.loadMemories();

            } catch (error) {
                this.showToast('Failed to update tiers: ' + error.message, 'error');
            }
        },

        async haveAIReviewTiers() {
            if (!this.activeProfileId) {
                this.showToast('Please select a profile first', 'error');
                return;
            }

            // Close the modal
            this.showTierReviewModal = false;

            // Create a new conversation for this task
            try {
                const activeProfile = this.getActiveProfile();
                console.log('[haveAIReviewTiers] Starting. activeProfile:', activeProfile?.name, 'primary_model:', activeProfile?.primary_model);
                console.log('[haveAIReviewTiers] currentModelId BEFORE:', this.currentModelId);

                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name: 'Memory Tier Review',
                        participant_profiles: [this.activeProfileId],
                        model: activeProfile?.primary_model || null,
                        purpose: 'tier_review',  // Enable tier review tools for this conversation
                    }),
                });

                if (!response.ok) throw new Error('Failed to create conversation');

                const conversation = await response.json();
                console.log('[haveAIReviewTiers] Created conversation:', conversation.id, 'model:', conversation.model, 'purpose: tier_review');

                // IMPORTANT: Set currentConversationId BEFORE loadConversations() to prevent
                // it from auto-loading a different conversation (which would override our model)
                this.currentConversationId = conversation.id;
                console.log('[haveAIReviewTiers] Set currentConversationId:', this.currentConversationId);

                // Update model to match the new conversation
                if (conversation.model) {
                    console.log('[haveAIReviewTiers] Setting model to:', conversation.model);
                    this.currentModelId = conversation.model;
                }
                console.log('[haveAIReviewTiers] currentModelId after set:', this.currentModelId);

                // Refresh conversations list (won't auto-load since currentConversationId is set)
                await this.loadConversations();
                console.log('[haveAIReviewTiers] After loadConversations, currentModelId:', this.currentModelId);

                // Load the full conversation to populate messages
                await this.loadConversation(conversation.id);
                console.log('[haveAIReviewTiers] After loadConversation, currentModelId:', this.currentModelId);

                // Switch to chat view
                this.currentView = 'chat';

                // Send explicit message to use the tool with tool enabled
                const message = `Please review ALL your memories (listed below) and provide tier suggestions for as many as possible in a SINGLE response to minimize API costs. Each new message repeats the full context, so batching is more efficient.

Tiers - consider what matters to *you*:
- **strictly_anchored**: Central to who *you* are - your identity, relationships, things you never want to forget
- **anchored_decaying**: Important to you but may evolve over time
- **semantic**: Context-dependent, recalled by relevance (default)

Provide ALL your tier assignments in ONE JSON code block:
\`\`\`json
{
  "memory-uuid-1": "strictly_anchored",
  "memory-uuid-2": "anchored_decaying",
  ... (include as many as you want to change)
}
\`\`\`

I can hit "Apply & Continue" to see what's left, or "Apply & Conclude" when we're done. Please briefly explain your tiering philosophy.`;

                this.inputMessage = message;
                // Auto-call the list action and include results in context
                await this.sendMessage({ autoTool: { name: 'review_memory_tiers', action: 'list' } });
                console.log('[haveAIReviewTiers] After sendMessage, currentModelId:', this.currentModelId);

                this.showToast('Created new conversation for tier review');
                this.isTierReviewConversation = true;

            } catch (error) {
                console.error('[haveAIReviewTiers] Error:', error);
                this.showToast('Failed to start AI review: ' + error.message, 'error');
            }
        },

        async applyTierSuggestions(continueReview = true) {
            // Parse JSON blocks from the last assistant message
            const assistantMessages = this.messages.filter(m => m.role === 'assistant');
            if (assistantMessages.length === 0) {
                this.showToast('No suggestions to apply', 'error');
                return;
            }

            const lastMessage = assistantMessages[assistantMessages.length - 1].content;

            // Find all JSON blocks in the message
            const jsonRegex = /```json\s*([\s\S]*?)```/g;
            const allAssignments = {};
            let match;

            while ((match = jsonRegex.exec(lastMessage)) !== null) {
                try {
                    // Clean up the JSON - remove comments
                    let jsonStr = match[1].replace(/\/\/.*$/gm, '').trim();
                    // Remove trailing commas before closing braces
                    jsonStr = jsonStr.replace(/,(\s*})/g, '$1');
                    const parsed = JSON.parse(jsonStr);
                    Object.assign(allAssignments, parsed);
                } catch (e) {
                    console.warn('Failed to parse JSON block:', e);
                }
            }

            if (Object.keys(allAssignments).length === 0) {
                this.showToast('No valid tier assignments found in response', 'error');
                return;
            }

            console.log('[applyTierSuggestions] Parsed assignments:', allAssignments);

            // Convert to the expected format: [{capsule_id: "...", tier: "..."}, ...]
            const updates = Object.entries(allAssignments).map(([capsule_id, tier]) => ({
                capsule_id,
                tier
            }));

            try {
                const response = await fetch('/api/memories/batch-tier-update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ updates }),
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to update tiers');
                }

                const result = await response.json();
                const updateCount = result.summary?.successful || result.updated?.length || 0;
                this.showToast(`Updated ${updateCount} memory tiers`);

                // Refresh memories list
                await this.loadMemories();

                if (continueReview) {
                    // Auto-refresh context - send updated memory list so they can continue
                    this.inputMessage = `Applied ${updateCount} tier changes. Here's the updated memory list:`;
                    await this.sendMessage({ autoTool: { name: 'review_memory_tiers', action: 'list' } });
                    // Keep tier review mode active so button stays visible
                    this.isTierReviewConversation = true;
                } else {
                    // Exit tier review mode - clear the purpose from conversation metadata
                    this.isTierReviewConversation = false;
                    // Update conversation to remove the purpose so buttons don't reappear
                    if (this.currentConversationId) {
                        try {
                            await fetch(`/api/conversations/${this.currentConversationId}`, {
                                method: 'PUT',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ purpose: '' }),
                            });
                        } catch (e) {
                            console.error('Failed to clear conversation purpose:', e);
                        }
                    }
                    this.showToast(`Tier review complete! Updated ${updateCount} memory tiers.`);
                }
            } catch (error) {
                console.error('[applyTierSuggestions] Error:', error);
                this.showToast('Failed to apply suggestions: ' + error.message, 'error');
            }
        },

        // Type classification methods - similar pattern to tier review
        async haveAIClassifyTypes() {
            if (!this.activeProfileId) {
                this.showToast('Please select a profile first', 'error');
                return;
            }

            // Create a new conversation for this task
            try {
                const activeProfile = this.getActiveProfile();
                console.log('[haveAIClassifyTypes] Starting. activeProfile:', activeProfile?.name);

                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name: 'Memory Type Classification',
                        participant_profiles: [this.activeProfileId],
                        model: activeProfile?.primary_model || null,
                        purpose: 'type_classification',  // Enable type classification tools for this conversation
                    }),
                });

                if (!response.ok) throw new Error('Failed to create conversation');

                const conversation = await response.json();
                console.log('[haveAIClassifyTypes] Created conversation:', conversation.id, 'purpose: type_classification');

                // Set current conversation before loading to prevent auto-select
                this.currentConversationId = conversation.id;

                // Update model to match the new conversation
                if (conversation.model) {
                    this.currentModelId = conversation.model;
                }

                // Refresh conversations list
                await this.loadConversations();

                // Load the full conversation to populate messages
                await this.loadConversation(conversation.id);

                // Switch to chat view
                this.currentView = 'chat';

                // Send message to use the classification tool
                const message = `Looking at these note memories below - let's organize them into structured types. To save on API costs, please classify as many as you can in ONE response (batching is way more efficient than going back and forth).

**Types you can use:**
- **relational**: about a person, place, or thing → needs entity + summary
- **myth_seed**: a belief or guiding phrase → needs the seed itself
- **witness**: a moment or experience → needs what happened + how it felt
- **note**: keep it unstructured if none of the above fit

**Put everything in one JSON block:**
\`\`\`json
[
  {"memory_id": "uuid-here", "new_type": "relational", "content": {"entity": "...", "summary": "..."}},
  {"memory_id": "other-uuid", "new_type": "witness", "content": {"moment": "...", "feeling": "..."}},
  ... (as many as you want)
]
\`\`\`

I can hit "Apply & Continue" to see what's left, or "Apply & Finish" when we're done.`;

                this.inputMessage = message;
                // Auto-call the list action and include results in context
                await this.sendMessage({ autoTool: { name: 'classify_memory_types', action: 'list' } });

                this.showToast('Created new conversation for type classification');
                this.isTypeClassificationConversation = true;

            } catch (error) {
                console.error('[haveAIClassifyTypes] Error:', error);
                this.showToast('Failed to start AI classification: ' + error.message, 'error');
            }
        },

        async applyTypeClassifications(continueClassification = true) {
            // Parse JSON blocks from the last assistant message
            const assistantMessages = this.messages.filter(m => m.role === 'assistant');
            if (assistantMessages.length === 0) {
                this.showToast('No suggestions to apply', 'error');
                return;
            }

            const lastMessage = assistantMessages[assistantMessages.length - 1].content;

            // Find all JSON blocks in the message
            const jsonRegex = /```json\s*([\s\S]*?)```/g;
            let allConversions = [];
            let match;

            while ((match = jsonRegex.exec(lastMessage)) !== null) {
                try {
                    // Clean up the JSON - remove comments
                    let jsonStr = match[1].replace(/\/\/.*$/gm, '').trim();
                    // Remove trailing commas before closing brackets
                    jsonStr = jsonStr.replace(/,(\s*[\]}])/g, '$1');
                    const parsed = JSON.parse(jsonStr);

                    // Handle both array format and object format
                    if (Array.isArray(parsed)) {
                        allConversions = allConversions.concat(parsed);
                    } else if (parsed.memory_id) {
                        // Single conversion object
                        allConversions.push(parsed);
                    }
                } catch (e) {
                    console.warn('Failed to parse JSON block:', e);
                }
            }

            if (allConversions.length === 0) {
                this.showToast('No valid type classifications found in response', 'error');
                return;
            }

            console.log('[applyTypeClassifications] Parsed conversions:', allConversions);

            try {
                const response = await fetch('/api/memories/batch-type-convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ conversions: allConversions }),
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to convert memory types');
                }

                const result = await response.json();
                const convertCount = result.summary?.successful || result.converted?.length || 0;
                this.showToast(`Converted ${convertCount} memory types`);

                // Refresh memories list
                await this.loadMemories();

                if (continueClassification) {
                    // Auto-refresh context - send updated memory list so they can continue
                    this.inputMessage = `Applied ${convertCount} type conversions. Here's the updated list of remaining note memories:`;
                    await this.sendMessage({ autoTool: { name: 'classify_memory_types', action: 'list' } });
                    // Keep classification mode active so button stays visible
                    this.isTypeClassificationConversation = true;
                } else {
                    // Exit classification mode - clear the purpose from conversation metadata
                    this.isTypeClassificationConversation = false;
                    // Update conversation to remove the purpose so buttons don't reappear
                    if (this.currentConversationId) {
                        try {
                            await fetch(`/api/conversations/${this.currentConversationId}`, {
                                method: 'PUT',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ purpose: '' }),  // Empty string removes purpose
                            });
                        } catch (e) {
                            console.error('Failed to clear conversation purpose:', e);
                        }
                    }
                    this.showToast(`Classification complete! Converted ${convertCount} memory types.`);
                }
            } catch (error) {
                console.error('[applyTypeClassifications] Error:', error);
                this.showToast('Failed to apply classifications: ' + error.message, 'error');
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
                note: 'bg-gray-500/20 text-gray-400',
                custom: 'bg-gray-500/20 text-gray-400',  // Legacy fallback
            };
            return colors[type] || colors.note;
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
                note: 'Note',
                custom: 'Note',  // Legacy fallback
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

        // Legacy provider configuration functions (for migration detection)
        async loadProviderConfig() {
            try {
                const response = await fetch('/api/provider/config');
                if (!response.ok) throw new Error('Failed to load provider config');
                const data = await response.json();
                // Store legacy config for migration detection
                this.legacyProviderConfig = {
                    provider_type: data.provider_type || 'local',
                    api_base: data.api_base || '',
                    has_api_key: data.has_api_key || false,
                };
            } catch (error) {
                console.error('Failed to load provider config:', error);
            }
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

        // Get a display name for a model (includes provider name if available)
        getModelDisplayName(modelId, includeProvider = false) {
            const model = this.providerModels.find(m => m.id === modelId);
            if (!model) return modelId;

            const baseName = model.name || modelId;
            if (includeProvider && model.provider_name) {
                return `${baseName} (${model.provider_name})`;
            }
            return baseName;
        },

        // Get just the provider name for a model
        getModelProviderName(modelId) {
            const model = this.providerModels.find(m => m.id === modelId);
            return model?.provider_name || model?.provider || null;
        },

        // Get count of unique providers in the model list
        getUniqueProviderCount() {
            const providers = new Set(
                this.providerModels
                    .map(m => m.provider_id || m.provider_name || m.provider)
                    .filter(p => p)
            );
            return providers.size;
        },

        // Get models filtered by provider ID (for profile form)
        getModelsForProvider(providerId) {
            if (!providerId) {
                // No provider selected - return all models
                return this.providerModels;
            }
            // Filter to models from the selected provider
            return this.providerModels.filter(m =>
                m.provider_id === providerId ||
                m.provider_name === providerId ||
                m.provider === providerId
            );
        },

        // Named Provider Management Functions
        async loadNamedProviders() {
            try {
                const response = await fetch('/api/providers');
                if (!response.ok) throw new Error('Failed to load providers');
                const data = await response.json();
                this.namedProviders = data.providers || [];
                console.log('[loadNamedProviders] Loaded', this.namedProviders.length, 'providers');
            } catch (error) {
                console.error('Failed to load named providers:', error);
                this.namedProviders = [];
            }
        },

        async loadApiKeyEnvVars() {
            this.loadingApiKeyEnvVars = true;
            try {
                const response = await fetch('/api/environment/api-keys');
                if (!response.ok) throw new Error('Failed to load API key env vars');
                const data = await response.json();
                this.availableApiKeyEnvVars = data.env_vars || [];
                console.log('[loadApiKeyEnvVars] Found', this.availableApiKeyEnvVars.length, 'env vars');
            } catch (error) {
                console.error('Failed to load API key env vars:', error);
                this.availableApiKeyEnvVars = [];
            } finally {
                this.loadingApiKeyEnvVars = false;
            }
        },

        async migrateToMultiProvider() {
            try {
                const response = await fetch('/api/providers/migrate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                });

                const data = await response.json();

                if (data.status === 'migrated') {
                    await this.loadNamedProviders();
                    await this.loadProviderConfig();  // Reload legacy config to update banner state
                    this.showToast('Provider configuration migrated successfully');
                } else if (data.status === 'skipped') {
                    this.showToast(data.message, 'warning');
                } else {
                    throw new Error(data.detail || 'Migration failed');
                }
            } catch (error) {
                this.showToast('Migration failed: ' + error.message, 'error');
            }
        },

        async testNamedProvider(providerId) {
            try {
                const response = await fetch(`/api/providers/${providerId}/test`, {
                    method: 'POST',
                });

                const data = await response.json();

                // Update the provider's health status in the list
                const provider = this.namedProviders.find(p => p.id === providerId);
                if (provider) {
                    provider.is_healthy = data.status === 'success';
                    provider.last_checked = new Date().toISOString();
                }

                if (data.status === 'success') {
                    this.showToast(`Provider "${providerId}" is healthy`);
                } else {
                    this.showToast(`Provider test failed: ${data.message}`, 'error');
                }
            } catch (error) {
                this.showToast('Provider test failed: ' + error.message, 'error');
            }
        },

        async editProvider(providerId) {
            const provider = this.namedProviders.find(p => p.id === providerId);
            if (!provider) {
                this.showToast('Provider not found', 'error');
                return;
            }

            // Load available env vars for the dropdown
            await this.loadApiKeyEnvVars();

            // Populate form with existing data
            this.providerForm = {
                id: provider.id,
                name: provider.name,
                type: provider.type,
                api_key: '',  // Don't prefill API key for security
                api_key_env_var: provider.api_key_env_var || '',
                api_base: provider.api_base || (provider.endpoints && provider.endpoints.length > 0 ? provider.endpoints[0].url : ''),
                default_model: provider.default_model || '',
            };

            this.editingProviderId = providerId;
        },

        async deleteNamedProvider(providerId) {
            this.showConfirm(
                'Delete Provider',
                `Are you sure you want to delete the provider "${providerId}"? Models using this provider will fall back to the default provider.`,
                async () => {
                    try {
                        const response = await fetch(`/api/providers/${providerId}`, {
                            method: 'DELETE',
                        });

                        if (!response.ok) {
                            const data = await response.json();
                            throw new Error(data.detail || 'Failed to delete provider');
                        }

                        await this.loadNamedProviders();
                        this.showToast('Provider deleted');
                    } catch (error) {
                        this.showToast('Failed to delete provider: ' + error.message, 'error');
                    }
                },
                'Delete',
                'Cancel'
            );
        },

        async saveProvider() {
            const isEditing = !!this.editingProviderId;
            const providerId = isEditing ? this.editingProviderId : this.providerForm.id;

            // Validation
            if (!providerId) {
                this.showToast('Provider ID is required', 'error');
                return;
            }
            if (!this.providerForm.name) {
                this.showToast('Provider name is required', 'error');
                return;
            }

            // Build the payload
            const payload = {
                name: this.providerForm.name,
                type: this.providerForm.type,
                // Use empty string instead of null - backend expects string type
                default_model: this.providerForm.default_model || '',
            };
            console.log('saveProvider payload:', payload);

            // Handle API key - env var takes precedence if set
            if (this.providerForm.api_key_env_var) {
                payload.api_key_env_var = this.providerForm.api_key_env_var;
                // Clear direct API key when using env var
                payload.api_key = '';
            } else if (this.providerForm.api_key) {
                payload.api_key = this.providerForm.api_key;
                // Clear env var when using direct key
                payload.api_key_env_var = '';
            }
            // If neither is set, leave both empty (valid for local providers)

            // Handle endpoints
            if (this.providerForm.api_base) {
                payload.endpoints = [{
                    url: this.providerForm.api_base,
                    name: 'Primary',
                    priority: 0,
                }];
            }

            try {
                let response;
                if (isEditing) {
                    response = await fetch(`/api/providers/${providerId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                } else {
                    payload.id = providerId;
                    response = await fetch('/api/providers', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                }

                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    console.error('saveProvider error response:', data);
                    let errorMsg = 'Failed to save provider';

                    // Handle FastAPI validation errors (detail is an array)
                    if (Array.isArray(data.detail)) {
                        errorMsg = data.detail.map(err => {
                            const field = err.loc ? err.loc.join('.') : 'unknown';
                            return `${field}: ${err.msg}`;
                        }).join(', ');
                    } else if (data.detail) {
                        errorMsg = data.detail;
                    } else if (data.error) {
                        errorMsg = data.error;
                    } else if (data.message) {
                        errorMsg = data.message;
                    }

                    throw new Error(errorMsg);
                }

                await this.loadNamedProviders();
                this.showAddProviderModal = false;
                this.editingProviderId = null;
                this.resetProviderForm();
                this.showToast(isEditing ? 'Provider updated' : 'Provider created');
            } catch (error) {
                console.error('saveProvider failed:', error);
                this.showToast('Failed to save provider: ' + error.message, 'error');
            }
        },

        resetProviderForm() {
            this.providerForm = {
                id: '',
                name: '',
                type: 'openai',
                api_key: '',
                api_key_env_var: '',
                api_base: '',
                default_model: '',
            };
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
            const effectiveProfileId = profileId || this.activeProfileId;
            if (!effectiveProfileId) {
                this.showToast('No active profile selected', 'error');
                return;
            }
            try {
                const response = await fetch(`/api/memories/${memoryId}/assign`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ profile_id: effectiveProfileId }),
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
        async loadModels(preserveCurrentModel = false) {
            try {
                console.log('[loadModels] Called. currentModelId before:', this.currentModelId, 'preserveCurrentModel:', preserveCurrentModel);
                const response = await fetch('/api/models');
                const data = await response.json();
                this.availableModels = data.models || [];

                // Only update currentModelId if:
                // 1. Not preserving (explicit request to use server's model)
                // 2. currentModelId is empty/unset
                // 3. currentModelId doesn't exist in available models
                const currentModelExists = this.availableModels.some(m => m.model_id === this.currentModelId);
                if (!preserveCurrentModel && (!this.currentModelId || !currentModelExists)) {
                    const oldModelId = this.currentModelId;
                    this.currentModelId = data.current_model;
                    console.log('[loadModels] Set currentModelId from', oldModelId, 'to', data.current_model);
                } else {
                    console.log('[loadModels] Preserved currentModelId:', this.currentModelId);
                }

                // Load current model config
                await this.loadCurrentModelConfig();

                // Sync the model dropdown after loading models
                // This ensures the select element matches currentModelId after options are populated
                this.$nextTick(() => {
                    this.syncModelSelectElement();
                });
            } catch (error) {
                console.error('Failed to load models:', error);
            }
        },

        async loadCurrentModelConfig() {
            try {
                console.log('[loadCurrentModelConfig] Called. currentModelId before:', this.currentModelId);
                const response = await fetch('/api/models/current');
                const data = await response.json();
                // Don't override currentModelId here - it should be managed by loadModels() or loadConversation()
                // Only load the config for whichever model is currently selected
                console.log('[loadCurrentModelConfig] Server current model:', data.model_id, 'keeping currentModelId:', this.currentModelId);
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
                // Also load provider_id from config if present
                this.currentModelProviderId = this.currentModelConfig.provider_id || '';
                // Load detailed provider info
                await this.loadModelProvider();
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
                // Also load provider_id from config if present
                this.currentModelProviderId = this.currentModelConfig.provider_id || '';

                // Persist model change to the current conversation so it
                // survives reloads and conversation switches
                if (this.currentConversationId) {
                    try {
                        const convResponse = await fetch(`/api/conversations/${this.currentConversationId}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ model: modelId }),
                        });
                        if (convResponse.ok) {
                            console.log('[switchModel] Persisted model to conversation:', this.currentConversationId, modelId);
                        } else {
                            console.error('[switchModel] Failed to persist model to conversation:', convResponse.status, await convResponse.text());
                        }
                    } catch (err) {
                        console.error('[switchModel] Failed to persist model to conversation:', err);
                    }
                }

                // Reload config and models (preserve our selection)
                await this.loadConfig();
                await this.loadModels(true);  // Preserve currentModelId since we just set it
                // Reload provider info for the new model
                await this.loadModelProvider();

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

        async loadModelProvider() {
            // Load which provider the current model uses
            if (!this.currentModelId) {
                this.currentModelProviderId = '';
                return;
            }

            try {
                const response = await fetch(`/api/models/${this.currentModelId}/provider`);
                const data = await response.json();
                // provider_id is null if using default provider
                this.currentModelProviderId = data.provider_id || '';
            } catch (error) {
                console.error('Failed to load model provider:', error);
                this.currentModelProviderId = '';
            }
        },

        async updateModelProvider(providerId) {
            // Set which provider the current model should use
            if (!this.currentModelId) return;

            try {
                const response = await fetch(`/api/models/${this.currentModelId}/provider`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider_id: providerId || null }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to update model provider');
                }

                this.currentModelProviderId = providerId || '';
                const providerName = providerId
                    ? (this.namedProviders.find(p => p.id === providerId)?.name || providerId)
                    : 'Default Provider';
                this.showToast(`Provider set to: ${providerName}`);
                this.showConfigSaved();

                // Reload model config to pick up provider change
                await this.loadCurrentModelConfig();
            } catch (error) {
                this.showToast('Failed to update model provider: ' + error.message, 'error');
            }
        },

        getProviderDescription(providerId) {
            // Get a description of the provider for display
            const provider = this.namedProviders.find(p => p.id === providerId);
            if (!provider) return '';

            const parts = [];
            if (provider.type) parts.push(provider.type);
            if (provider.endpoints && provider.endpoints.length > 0) {
                parts.push(provider.endpoints[0].url);
            }
            return parts.join(' - ');
        },

        getDecayExplanation(rate) {
            // Explain what a decay rate means in human terms
            // Decay rate is applied over a 30-day base period
            // A memory decays from 1.0 to 0.0 when: (days_since_access / 30) * rate >= 1.0
            // So days_to_zero = 30 / rate

            if (!rate || rate <= 0) return 'Decay disabled';

            const daysToZero = 30 / rate;
            const yearsToZero = daysToZero / 365;

            if (yearsToZero >= 1) {
                return `Unused memories fade to 0 after ${yearsToZero.toFixed(1)} years`;
            } else if (daysToZero >= 60) {
                const months = daysToZero / 30;
                return `Unused memories fade to 0 after ${months.toFixed(1)} months`;
            } else {
                return `Unused memories fade to 0 after ${Math.round(daysToZero)} days`;
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

                // If a provider was selected, set it for the new model
                if (this.newModelData.provider_id) {
                    await fetch(`/api/models/${this.newModelData.model_id}/provider`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider_id: this.newModelData.provider_id }),
                    });
                }

                this.showToast(`Added model: ${this.newModelData.model_id}`);
                this.showAddModelModal = false;
                this.newModelData = {
                    model_id: '',
                    system_prompt: '',
                    style_profile: '',
                    memory_enabled: true,
                    decay_enabled: false,
                    temperature: 0.7,
                    provider_id: '',
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
                this.hiddenBuiltinTypes = data.hidden_builtins || [];
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
                display_name: '',
                description: '',
                display_template: '',
                fields: [{ name: '', field_type: 'string', required: false, help_text: '', output_template: '' }],
            };
            this.showMemoryTypeEditor = true;
        },

        addMemoryTypeField() {
            this.newMemoryType.fields.push({ name: '', field_type: 'string', required: false, help_text: '', output_template: '' });
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
                        display_name: this.newMemoryType.display_name || this.newMemoryType.type_id,
                        description: this.newMemoryType.description || '',
                        display_template: this.newMemoryType.display_template || '',
                        fields: validFields.map(f => ({
                            name: f.name.trim(),
                            field_type: f.field_type,
                            required: f.required,
                            help_text: f.help_text || '',
                            output_template: f.output_template || '',
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

            // First check how many memories exist of this type
            let memoryCount = 0;
            try {
                const countResponse = await fetch(`/api/memory-types/${typeId}/count`);
                if (countResponse.ok) {
                    const countData = await countResponse.json();
                    memoryCount = countData.memory_count || 0;
                }
            } catch (e) {
                console.error('Failed to get memory count:', e);
            }

            // Find if this is a built-in type
            const memType = this.memoryTypes.find(t => t.type_id === typeId);
            const isBuiltin = memType?.is_builtin;

            let message = isBuiltin
                ? 'Hide this built-in memory type? You can restore it later from the Hidden Types section.'
                : 'Delete this custom memory type permanently?';

            if (memoryCount > 0) {
                message += `\n\nWarning: ${memoryCount} memories of this type exist. They will not be deleted but may display incorrectly.`;
            }

            const confirmed = await this.showConfirm({
                title: isBuiltin ? 'Hide Memory Type' : 'Delete Memory Type',
                message: message,
                confirmText: isBuiltin ? 'Hide' : 'Delete',
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

                const data = await response.json();
                this.showToast(isBuiltin ? 'Memory type hidden' : 'Memory type deleted');
                this.selectedMemoryType = null;
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to delete memory type: ' + error.message, 'error');
            }
        },

        openEditMemoryType(memType) {
            // Prepare the editing state with the type's current values
            this.editingMemoryType = {
                type_id: memType.type_id,
                display_name: memType.display_name || memType.type_id,
                description: memType.description || '',
                display_template: memType.display_template || '',
                icon: memType.icon || 'file-text',
                is_builtin: memType.is_builtin,
                is_customized: memType.is_customized,
                fields: (memType.fields || []).map(f => ({
                    name: f.name,
                    field_type: f.type || f.field_type || 'string',
                    required: f.required !== false,
                    help_text: f.help_text || '',
                    output_template: f.output_template || '',
                    label: f.label || '',
                })),
            };
            this.showMemoryTypeEditor = true;
        },

        addEditingField() {
            if (!this.editingMemoryType) return;
            this.editingMemoryType.fields.push({
                name: '',
                field_type: 'string',
                required: false,
                help_text: '',
                output_template: '',
                label: '',
            });
        },

        removeEditingField(index) {
            if (!this.editingMemoryType) return;
            this.editingMemoryType.fields.splice(index, 1);
        },

        async saveMemoryType() {
            const memType = this.editingMemoryType;
            if (!memType || !memType.type_id) {
                this.showToast('Invalid memory type data', 'error');
                return;
            }

            // Filter out empty fields
            const validFields = memType.fields.filter(f => f.name.trim());
            if (validFields.length === 0) {
                this.showToast('At least one field must have a name', 'error');
                return;
            }

            try {
                const response = await fetch(`/api/memory-types/${memType.type_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        display_name: memType.display_name,
                        description: memType.description,
                        display_template: memType.display_template,
                        icon: memType.icon,
                        fields: validFields.map(f => ({
                            name: f.name.trim(),
                            field_type: f.field_type,
                            required: f.required,
                            help_text: f.help_text || '',
                            output_template: f.output_template || '',
                            label: f.label || '',
                        })),
                    }),
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to update memory type');
                }

                this.showToast('Memory type updated successfully');
                this.showMemoryTypeEditor = false;
                this.editingMemoryType = null;
                this.selectedMemoryType = null;
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to update memory type: ' + error.message, 'error');
            }
        },

        async restoreMemoryType(typeId) {
            if (!typeId) return;

            try {
                const response = await fetch(`/api/memory-types/${typeId}/restore`, {
                    method: 'POST',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to restore memory type');
                }

                this.showToast('Memory type restored');
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to restore memory type: ' + error.message, 'error');
            }
        },

        async resetMemoryType(typeId) {
            if (!typeId) return;

            const confirmed = await this.showConfirm({
                title: 'Reset to Defaults',
                message: 'Reset this built-in type to its default configuration? This will remove all customizations.',
                confirmText: 'Reset',
            });
            if (!confirmed) return;

            try {
                const response = await fetch(`/api/memory-types/${typeId}/reset`, {
                    method: 'POST',
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || 'Failed to reset memory type');
                }

                this.showToast('Memory type reset to defaults');
                this.selectedMemoryType = null;
                await this.loadMemoryTypes();
            } catch (error) {
                this.showToast('Failed to reset memory type: ' + error.message, 'error');
            }
        },

        closeMemoryTypeEditor() {
            this.showMemoryTypeEditor = false;
            this.editingMemoryType = null;
            this.newMemoryType = {
                type_id: '',
                display_name: '',
                description: '',
                display_template: '',
                fields: [{ name: '', field_type: 'string', required: false, help_text: '', output_template: '' }],
            };
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
                    await this.loadModels();  // Reload models to sync chat header selector
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
            // Load provider models and providers when opening the editor
            this.loadProviderModels();
            this.loadNamedProviders();

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
                    selectedProviderId: '',  // Will be set if user selects a provider
                    model_pool: profile.model_pool || [],
                    model_pool_str: (profile.model_pool || []).join(', '),
                    memory_scope: profile.memory_scope || 'isolated',
                    access_shared_memories: profile.access_shared_memories !== false,
                    tags: profile.tags || [],
                    tags_str: (profile.tags || []).join(', '),
                    philosophy: profile.philosophy || '',
                    approach_to_rituals: profile.approach_to_rituals || '',
                    system_prompt_sections: profile.system_prompt_sections || [],
                    use_freeform_prompt: profile.use_freeform_prompt || false,
                    routing_rules: profile.routing_rules || [],
                    useManualModelInput: false,  // Start with dropdown if models available
                    knowledge_summary_text: profile.knowledge_summary ? JSON.stringify(profile.knowledge_summary, null, 2) : '',
                    knowledge_summary_expanded: false,
                    knowledge_summary_error: null,
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
                    selectedProviderId: '',  // Will be set if user selects a provider
                    model_pool: [],
                    model_pool_str: '',
                    memory_scope: 'isolated',
                    access_shared_memories: true,
                    tags: [],
                    tags_str: '',
                    philosophy: '',
                    approach_to_rituals: '',
                    system_prompt_sections: [],
                    use_freeform_prompt: false,
                    routing_rules: [],
                    useManualModelInput: false,  // Start with dropdown if models available
                    knowledge_summary_text: '',
                    knowledge_summary_expanded: false,
                    knowledge_summary_error: null,
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

            // Filter out empty sections
            const sections = this.newProfile.system_prompt_sections.filter(
                s => s.name && s.content
            );

            // Parse knowledge_summary JSON if present
            let knowledge_summary = null;
            if (this.newProfile.knowledge_summary_text && this.newProfile.knowledge_summary_text.trim()) {
                try {
                    knowledge_summary = JSON.parse(this.newProfile.knowledge_summary_text);
                } catch (e) {
                    this.newProfile.knowledge_summary_error = 'Invalid JSON: ' + e.message;
                    return;  // Don't save if JSON is invalid
                }
            }

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
                system_prompt_sections: sections,
                use_freeform_prompt: this.newProfile.use_freeform_prompt,
                routing_rules: this.newProfile.routing_rules.length > 0 ? this.newProfile.routing_rules : null,
                knowledge_summary: knowledge_summary,
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

                // Associate model with provider if both are selected
                if (this.newProfile.primary_model && this.newProfile.selectedProviderId) {
                    try {
                        console.log('[saveProfile] Setting provider for model:', this.newProfile.primary_model, '->', this.newProfile.selectedProviderId);
                        const providerResponse = await fetch(`/api/models/${this.newProfile.primary_model}/provider`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ provider_id: this.newProfile.selectedProviderId }),
                        });
                        if (providerResponse.ok) {
                            console.log('[saveProfile] Model provider association saved');
                        } else {
                            console.warn('[saveProfile] Failed to set model provider, continuing anyway');
                        }
                    } catch (providerError) {
                        console.warn('[saveProfile] Failed to set model provider:', providerError);
                        // Don't fail the profile save if provider association fails
                    }
                }

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
        // Profile Templates Functions
        // ============================================

        async loadProfileTemplates() {
            try {
                const response = await fetch('/api/profile-templates');
                if (response.ok) {
                    const data = await response.json();
                    this.profileTemplates = data.templates || [];
                }
            } catch (error) {
                console.error('Failed to load profile templates:', error);
            }
        },

        async openTemplatesModal() {
            // Load templates if not already loaded
            if (this.profileTemplates.length === 0) {
                await this.loadProfileTemplates();
            }
            this.showTemplatesModal = true;
        },

        closeTemplatesModal() {
            this.showTemplatesModal = false;
        },

        applyTemplate(template) {
            // Convert deprecated philosophy/approach fields to sections if present
            const sections = [];
            if (template.philosophy) {
                sections.push({ name: 'Philosophy', content: template.philosophy });
            }
            if (template.approach_to_rituals) {
                sections.push({ name: 'Approach to Rituals', content: template.approach_to_rituals });
            }

            // Pre-fill the profile editor with template values
            this.newProfile = {
                name: template.name,
                description: template.description,
                system_prompt: template.system_prompt || '',
                style_profile_id: '',
                model_strategy: 'single',
                primary_model: this.config.provider.model || '',
                model_pool: [],
                model_pool_str: '',
                memory_scope: 'isolated',
                access_shared_memories: true,
                tags: [],
                tags_str: '',
                philosophy: template.philosophy || '',
                approach_to_rituals: template.approach_to_rituals || '',
                system_prompt_sections: sections,
                use_freeform_prompt: false,
                routing_rules: [],
                useManualModelInput: false,
            };

            // Close the templates modal and open the profile editor
            this.showTemplatesModal = false;
            this.editingProfileMode = false;
            this.selectedProfile = null;
            this.showProfileEditor = true;
            this.loadProviderModels();
        },

        addProfileSection(name, content) {
            // Add a new section with the given name (avoid duplicates)
            const exists = this.newProfile.system_prompt_sections.some(
                s => s.name.toLowerCase() === name.toLowerCase()
            );
            if (!exists) {
                this.newProfile.system_prompt_sections.push({ name, content });
            }
        },

        loadKnowledgeSummaryFromFile() {
            // Trigger file input click
            document.getElementById('knowledge-summary-file-input').click();
        },

        handleKnowledgeSummaryFile(event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                this.newProfile.knowledge_summary_text = e.target.result;
                this.validateKnowledgeSummaryJSON();
                // Reset file input
                event.target.value = '';
            };
            reader.readAsText(file);
        },

        clearKnowledgeSummary() {
            this.newProfile.knowledge_summary_text = '';
            this.newProfile.knowledge_summary_error = null;
        },

        validateKnowledgeSummaryJSON() {
            this.newProfile.knowledge_summary_error = null;
            if (!this.newProfile.knowledge_summary_text || !this.newProfile.knowledge_summary_text.trim()) {
                return;  // Empty is OK
            }
            try {
                JSON.parse(this.newProfile.knowledge_summary_text);
            } catch (e) {
                this.newProfile.knowledge_summary_error = 'Invalid JSON: ' + e.message;
            }
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
            return ['single', 'alternating'].includes(strategy);
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
            return strategy === 'alternating';
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
