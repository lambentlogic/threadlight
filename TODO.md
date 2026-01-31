# Threadlight TODO

## Immediate Bugs to Fix

### API Configuration Issues
- [ ] API key visibility toggle shows asterisks instead of actual key value
- [ ] Support multiple API endpoint URLs per provider (not just one base_url)
- [ ] Populate model dropdown from provider's available models (call list models API)
- [ ] Model selector in profile creation should show models from configured provider

### UI Polish Needed
- [ ] Model Strategy dropdown needs better organization:
  - [ ] Default to "Single" (just one model)
  - [ ] Put "Alternating", "Weighted", "Routed" behind "Advanced" accordion
  - [ ] Add clear descriptions/tooltips for each strategy
  - [ ] "Routed" should only show if routing rules exist

### Default Content Cleanup
- [ ] Remove Fable as default style profile (too specific, not general)
- [ ] Rename myth_seed memory type to something more universal
  - Suggestion: "identity_phrase" or "core_belief"
- [ ] Review if ritual should be a default memory type (removed from UI but still in code?)
- [ ] Consider which memory types should be defaults:
  - Keep: relational (universal), witness (broadly useful)
  - Remove/make optional: myth_seed (spiritual), ritual (command-based)

## Feature Ideas Discussed

### Memory System
- [ ] Add ability to create custom memory types via UI
- [ ] Memory type templates users can choose from
- [ ] Import/export memory types between profiles

### Profile Management
- [ ] Inline style editing in profile creation (not separate step)
- [ ] Style templates dropdown: Professional, Casual, Creative, etc.
- [ ] Profile templates: "Work Assistant", "Creative Companion", "Technical Helper"
- [ ] Profile export/import for sharing between users

### Multi-Profile Features
- [ ] Group chat backend implementation (frontend UI exists)
  - Format messages with [Profile Name:] tags for other profiles
  - API endpoint to handle multi-profile responses
- [ ] Profile-switching within conversation (not just at conversation start)
- [ ] Profile comparison view (see how different profiles would respond)

### Embedding & Search
- [ ] Model comparison UI (show stats for different embedding models)
- [ ] Embedding migration tool (re-embed with new model)
- [ ] Search quality feedback (thumbs up/down on search results)
- [ ] Hybrid search (semantic + keyword)

### Settings & Configuration
- [ ] Provider health check indicator (show connection status)
- [ ] Cost tracking per provider (if applicable)
- [ ] Usage statistics dashboard
- [ ] Backup/restore for entire database
- [ ] Export settings as shareable config

### Import/Export
- [ ] Better import UX with progress indicators
- [ ] Preview import before committing
- [ ] Selective import (choose which conversations/memories)
- [ ] Export individual conversations
- [ ] Export profile with its memories

### Alloying / Model Strategy
- [ ] Visual flow diagram showing how strategies work
- [ ] Model performance comparison (speed, quality)
- [ ] A/B testing: compare responses from different models
- [ ] Smart model selection based on message characteristics

### UI/UX Improvements
- [ ] Responsive design (mobile-friendly)
- [ ] Dark mode support
- [ ] Keyboard shortcuts
- [ ] Command palette (Cmd+K for quick actions)
- [ ] Empty states for all views
- [ ] Loading states with skeletons
- [ ] Better error messages with recovery suggestions
- [ ] Onboarding tour for new users

### Documentation
- [ ] Update README with all new features
- [ ] Add screenshots/GIFs to README
- [ ] API documentation improvements
- [ ] Video walkthrough
- [ ] Contributing guide updates

## Known Issues

### Backend
- [ ] Embedding manager initialization requires config reload (not hot-swappable)
- [ ] Profile scoping edge cases in stats queries
- [ ] Large conversation history performance (42k+ messages)

### Frontend
- [ ] Console highlight.js warnings (fixed but verify)
- [ ] Progress bar SSE connection handling on error
- [ ] Modal z-index conflicts (rare)

## Architecture Improvements

### Performance
- [ ] Lazy load conversations (pagination)
- [ ] Virtual scrolling for long message lists
- [ ] Database query optimization for large datasets
- [ ] Caching layer for frequent queries

### Testing
- [ ] E2E tests for critical flows
- [ ] Visual regression testing
- [ ] Performance benchmarks
- [ ] Integration tests for API endpoints

### Code Quality
- [ ] Type hints completion (Python)
- [ ] Frontend TypeScript migration (currently vanilla JS)
- [ ] Consolidate duplicate code
- [ ] Extract reusable UI components

## Future Vision

### Advanced Features
- [ ] Voice input/output support
- [ ] Image handling in conversations
- [ ] Code execution environment (sandbox)
- [ ] Plugin system for extensibility
- [ ] Webhook support for integrations
- [ ] API rate limiting and quotas

### Collaboration
- [ ] Multi-user support (optional)
- [ ] Shared profiles/conversations
- [ ] Team workspace features
- [ ] Role-based permissions

### AI Enhancements
- [ ] Automatic memory creation from conversations
- [ ] Smart memory suggestions
- [ ] Conversation summarization
- [ ] Topic extraction and tagging
- [ ] Sentiment analysis

## Migration Path for Existing Users

- [ ] Document breaking changes
- [ ] Provide migration scripts
- [ ] Backwards compatibility layer where possible
- [ ] Deprecation warnings in UI/logs

---

## Priority Levels

**P0 (Critical):** Bugs that break core functionality
**P1 (High):** Features that significantly improve UX
**P2 (Medium):** Nice-to-have improvements
**P3 (Low):** Future vision items

## Next Steps

1. Fix API key visibility bug
2. Clean up default content (Fable, myth_seed)
3. Improve Model Strategy UI organization
4. Add model selection from provider's available models
5. Implement group chat backend
