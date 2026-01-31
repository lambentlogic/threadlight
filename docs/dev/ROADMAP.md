# Profile-Based Architecture Implementation Roadmap

## Overview

This roadmap outlines the phased implementation of Threadlight's profile-based architecture. Total estimated time: 5-6 weeks for a complete implementation.

---

## Phase 1: Core Profile Infrastructure (Week 1)

### Goals
- Establish Profile data model
- Create storage layer
- Basic CRUD operations

### Tasks

#### 1.1 Profile Data Model
- [ ] Create `src/threadlight/profiles/__init__.py`
- [ ] Create `src/threadlight/profiles/profile.py`
  - [ ] `Profile` dataclass
  - [ ] `ModelStrategy` enum
  - [ ] `AlloyedConfig` dataclass
  - [ ] `RoutingRule` dataclass
  - [ ] Serialization methods (`to_dict`, `from_dict`)
- [ ] Write unit tests for Profile

#### 1.2 Storage Layer
- [ ] Add profiles table to SQLite schema
- [ ] Update `storage/base.py` with profile interface methods
- [ ] Implement in `storage/sqlite.py`:
  - [ ] `save_profile()`
  - [ ] `get_profile()`
  - [ ] `update_profile()`
  - [ ] `delete_profile()`
  - [ ] `list_profiles()`
- [ ] Write storage unit tests

#### 1.3 Profile Manager
- [ ] Create `src/threadlight/profiles/manager.py`
  - [ ] `ProfileManager` class
  - [ ] CRUD operations
  - [ ] Profile switching
  - [ ] Caching layer
- [ ] Write ProfileManager unit tests

### Deliverables
- Working Profile data model
- Profile persistence in SQLite
- ProfileManager with full CRUD

---

## Phase 2: Memory Integration (Week 2)

### Goals
- Add `profile_scope` to capsules
- Update memory operations for profile scoping
- Migration from `model_scope`

### Tasks

#### 2.1 Schema Changes
- [ ] Add `profile_scope` column to capsules table
- [ ] Create index on `profile_scope`
- [ ] Add `profile_id` column to messages table
- [ ] Add `model_used` column to messages table

#### 2.2 Filter Updates
- [ ] Update `CapsuleFilter` in `storage/base.py`
  - [ ] Add `profile_scope` field
  - [ ] Add `include_shared` field
- [ ] Update `list_capsules()` to support `profile_scope`
- [ ] Update `search_by_cue()` to support `profile_scope`

#### 2.3 Memory Orchestrator
- [ ] Update `MemoryOrchestrator.recall()` for profile scoping
- [ ] Update `MemoryOrchestrator.create()` to include `profile_scope`
- [ ] Add `ProfileMemoryManager` helper class

#### 2.4 Migration
- [ ] Create migration script for `model_scope` -> `profile_scope`
- [ ] Add migration to `_run_migrations()` in SQLite storage
- [ ] Test migration with existing data

### Deliverables
- Profile-scoped memory operations
- Backward-compatible migration
- Updated memory orchestrator

---

## Phase 3: Alloyed Profiles (Week 3)

### Goals
- Implement model selection strategies
- State persistence for alloyed profiles

### Tasks

#### 3.1 Alloyed Engine
- [ ] Create `src/threadlight/profiles/alloyed.py`
- [ ] Implement `AlloyedProfileEngine` class
- [ ] Implement strategies:
  - [ ] `SINGLE` (trivial)
  - [ ] `ALTERNATING`
  - [ ] `RATIO`
  - [ ] `WEIGHTED`
  - [ ] `DYNAMIC`
  - [ ] `ROUND_ROBIN`
- [ ] State persistence callbacks

#### 3.2 Routing Rules
- [ ] Implement routing rule matching:
  - [ ] Keyword matching
  - [ ] Regex matching
  - [ ] Length-based matching
  - [ ] Starts/ends with matching
- [ ] Priority-based rule evaluation

#### 3.3 Testing
- [ ] Unit tests for each strategy
- [ ] State persistence tests
- [ ] Rule matching tests
- [ ] Edge case tests (empty pool, single model, etc.)

### Deliverables
- Complete AlloyedProfileEngine
- All model selection strategies
- Comprehensive test coverage

---

## Phase 4: Threadlight Integration (Week 4)

### Goals
- Integrate profiles with main Threadlight class
- Profile-aware chat flow
- Backward compatibility

### Tasks

#### 4.1 Core Integration
- [ ] Update `Threadlight.__init__()`:
  - [ ] Add `ProfileManager` initialization
  - [ ] Add optional `profile` parameter
  - [ ] Auto-load profile if specified
- [ ] Add `switch_profile()` method
- [ ] Add `_apply_profile()` internal method

#### 4.2 Chat Flow
- [ ] Update `chat()` to use active profile's settings
- [ ] Integrate AlloyedProfileEngine for model selection
- [ ] Update message attribution with profile_id
- [ ] Update context composer for profile context

#### 4.3 Memory Integration
- [ ] Update `recall()` to use profile scope
- [ ] Update `remember()` to include profile scope
- [ ] Handle shared memories properly

#### 4.4 Backward Compatibility
- [ ] Ensure `chat()` works without profiles
- [ ] Ensure memory operations work without profiles
- [ ] Add deprecation warnings where appropriate

#### 4.5 Testing
- [ ] Integration tests for profile switching
- [ ] Integration tests for profile chat
- [ ] Integration tests for memory isolation
- [ ] Backward compatibility tests

### Deliverables
- Profile-aware Threadlight
- Seamless profile switching
- Full backward compatibility

---

## Phase 5: Group Chat (Week 5)

### Goals
- Multi-profile conversation support
- Turn order strategies
- Profile attribution

### Tasks

#### 5.1 Data Model
- [ ] Create `src/threadlight/group_chat/__init__.py`
- [ ] Create `src/threadlight/group_chat/group.py`
  - [ ] `GroupChat` dataclass
  - [ ] `TurnOrderStrategy` enum
  - [ ] `ProfileResponse` dataclass
- [ ] Add group_chats table to storage

#### 5.2 Group Chat Manager
- [ ] Create `GroupChatManager` class
- [ ] Implement CRUD operations
- [ ] Implement `send_message()` flow

#### 5.3 Turn Order Strategies
- [ ] Implement `SEQUENTIAL`
- [ ] Implement `PARALLEL` (async)
- [ ] Implement `ROUND_ROBIN`
- [ ] Implement `ADDRESSED` (@mentions)
- [ ] Implement `VOLUNTEER` (auto-routing)
- [ ] Implement `DEBATE`

#### 5.4 Context Building
- [ ] Group awareness prompt
- [ ] Previous response injection
- [ ] Profile context composition

#### 5.5 Threadlight Integration
- [ ] Add `create_group_chat()` method
- [ ] Add `get_group_chat()` method
- [ ] Add `list_group_chats()` method
- [ ] Add sync wrapper for CLI

#### 5.6 Testing
- [ ] Unit tests for each turn order
- [ ] Integration tests for group chat
- [ ] Concurrency tests for parallel mode

### Deliverables
- Complete group chat functionality
- All turn order strategies
- Full Threadlight integration

---

## Phase 6: Polish & UX (Week 6)

### Goals
- Profile templates
- Export/import
- Documentation
- Examples

### Tasks

#### 6.1 Templates
- [ ] Create `src/threadlight/profiles/templates.py`
- [ ] Built-in templates:
  - [ ] "assistant" (basic helpful)
  - [ ] "creative" (creative writing)
  - [ ] "debug-buddy" (technical)
  - [ ] "fable" (poetic/presence)
- [ ] Template creation API

#### 6.2 Export/Import
- [ ] Implement `export_profile()` in ProfileManager
- [ ] Implement `import_profile()` in ProfileManager
- [ ] JSON export format with versioning
- [ ] Include memories option
- [ ] Include conversations option

#### 6.3 CLI Integration
- [ ] Add profile commands to CLI:
  - [ ] `threadlight profile list`
  - [ ] `threadlight profile create`
  - [ ] `threadlight profile switch`
  - [ ] `threadlight profile export`
  - [ ] `threadlight profile import`
- [ ] Add group chat commands

#### 6.4 Documentation
- [ ] Update README with profile examples
- [ ] Create "Profiles Guide" documentation
- [ ] Create "Group Chat Guide" documentation
- [ ] API reference updates

#### 6.5 Examples
- [ ] Create `examples/profiles.py`
- [ ] Create `examples/alloyed_profiles.py`
- [ ] Create `examples/group_chat.py`
- [ ] Update existing examples for profiles

### Deliverables
- Complete profile template system
- Export/import functionality
- Updated CLI
- Comprehensive documentation
- Example code

---

## Success Metrics

### Phase 1
- [ ] All Profile unit tests pass
- [ ] Profile CRUD operations work

### Phase 2
- [ ] Memory isolation tests pass
- [ ] Migration script works with test data

### Phase 3
- [ ] All strategy tests pass
- [ ] State persists across restarts

### Phase 4
- [ ] Existing tests still pass (backward compat)
- [ ] Profile chat integration tests pass

### Phase 5
- [ ] Group chat with 2+ profiles works
- [ ] All turn order strategies function

### Phase 6
- [ ] Templates can be used to create profiles
- [ ] Export/import roundtrip preserves data
- [ ] Documentation reviewed and complete

---

## Risk Mitigation

### Risk: Breaking Backward Compatibility
**Mitigation**:
- All new profile functionality is additive
- Existing APIs continue to work
- Comprehensive test suite for existing functionality

### Risk: Performance Degradation
**Mitigation**:
- Profile caching in ProfileManager
- Lazy loading of profiles
- Efficient database queries with proper indexing

### Risk: State Inconsistency (Alloyed Profiles)
**Mitigation**:
- Atomic state updates
- State validation on load
- Reset mechanism for corrupted state

### Risk: Group Chat Complexity
**Mitigation**:
- Start with SEQUENTIAL strategy (simplest)
- Add strategies incrementally
- Comprehensive error handling

---

## Dependencies

### External
- None (all dependencies already in project)

### Internal
- Storage backend must support new tables
- Context composer needs profile awareness
- Provider factory for group chat

---

## Future Enhancements (Post-MVP)

1. **Profile Sharing**: Share profiles between users
2. **Profile Marketplace**: Community profile templates
3. **Advanced Routing**: ML-based model selection
4. **Profile Analytics**: Usage statistics per profile
5. **Voice Synthesis**: Per-profile voice settings
6. **Multi-User Groups**: Multiple humans + multiple profiles

---

## Timeline Summary

| Phase | Duration | Key Deliverable |
|-------|----------|-----------------|
| 1. Core Profile | Week 1 | Profile CRUD |
| 2. Memory Integration | Week 2 | Profile-scoped memories |
| 3. Alloyed Profiles | Week 3 | Model selection strategies |
| 4. Threadlight Integration | Week 4 | Profile-aware chat |
| 5. Group Chat | Week 5 | Multi-profile conversations |
| 6. Polish | Week 6 | Templates, docs, examples |

**Total: 6 weeks to complete implementation**
