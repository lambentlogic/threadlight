# Tier Review Implementation & Debug Log
**Session Date**: 2026-01-31
**Context**: Implementing tiered memory system with UI for batch review

## Summary
Implemented tiered memory system (strictly_anchored, anchored_decaying, semantic) with both manual UI and AI-assisted review. Multiple issues with UI model display, logging, and tool execution discovered during implementation.

---

## What's Implemented & Working ✅

### Backend - Tiered Memory System (COMPLETE)
1. **Memory Tier Enum** (`src/threadlight/capsules/base.py` line 38-43)
   - `STRICTLY_ANCHORED`: Core identity, never decays
   - `ANCHORED_DECAYING`: Important but can demote to semantic
   - `SEMANTIC`: Recalled by relevance (default)

2. **Database Schema** (`src/threadlight/storage/sqlite.py`)
   - Added `memory_tier` column (line 62)
   - Migration for existing databases (lines 241-245)
   - Index on tier column
   - Backward compatibility (defaults to 'semantic')

3. **Tiered Recall Logic** (`src/threadlight/memory/orchestrator.py` lines 583-714)
   - Queries strictly_anchored first
   - Then anchored_decaying
   - Fills remaining budget with semantic
   - Respects max_anchored limit (default 10)

4. **Profile Isolation** (WORKING)
   - Tool executor filters by active profile (lines 326-350 & 407-430)
   - Prevents cross-profile memory access
   - Respects `access_shared_memories` setting

5. **Batch Tier Update API** (`src/threadlight/api/server.py`)
   - Endpoint: `POST /api/memories/batch-tier-update`
   - Request: `{updates: [{capsule_id, tier}, ...]}`
   - Returns: `{updated: [], errors: [], summary: {total, successful, failed}}`
   - **VERIFIED WORKING** via curl test

6. **Conversational Tool** (`src/threadlight/tools/`)
   - Tool name: `review_memory_tiers`
   - Actions: 'list' (get all memories) and 'update' (apply tier changes)
   - Implemented by killed agent a096903 (complete implementation exists)
   - Located in `executor.py` lines 303-454
   - Tool definition in `definitions.py`

### Frontend - Manual Tier Review (MOSTLY WORKING)
1. **UI Modal** (`src/threadlight/api/static/index.html` after line 2440)
   - "Review Tiers" button in Memory Browser header
   - Shows all memories with tier dropdowns
   - Tracks changes locally
   - "Apply Manual Changes" button
   - "AI-Assisted Review" button (has issues - see below)

2. **JavaScript State** (`src/threadlight/api/static/js/app.js`)
   - `showTierReviewModal`, `tierReviewMemories`, `tierReviewChanges`
   - `loadMemoriesForTierReview()` - filters by active profile
   - `updateMemoryTierInReview()` - tracks local changes
   - `submitTierReviewChanges()` - calls batch API
   - `haveAIReviewTiers()` - creates conversation and sends tool request (HAS ISSUES)

---

## Critical Issues ❌

### 1. UI Model Display Not Updating
**Problem**: When "Have [Profile] Review" button creates new conversation, model dropdown shows "Hermes-4.3-36B" instead of profile's model (e.g., "chatgpt-4o-latest")

**Evidence**:
- Database shows conversations CORRECTLY created with `model: "chatgpt-4o-latest"`
- Verified via: `sqlite3 threadlight.db "SELECT id, name, model FROM conversations WHERE name LIKE '%Memory%'"`
- UI still displays Hermes
- User reports: "switched models but it switched back to hermes when I tabbed out and back"

**Code Location**: `haveAIReviewTiers()` in app.js (line 1664)
```javascript
// Code exists to update currentModelId but doesn't work:
this.currentModelId = conversation.model || this.currentModelId;
await this.loadConversations();
await this.loadConversation(conversation.id);  // Added to fix, still not working
```

**What's Been Tried**:
- Setting `currentModelId` directly from conversation.model
- Calling `loadConversation()` after creation
- Multiple hard refreshes (Ctrl+Shift+R)
- Suggested incognito mode, cache clear (not confirmed tested)

**Status**: UNRESOLVED - JavaScript changes not taking effect despite being in source file

### 2. Logging Completely Broken
**Problem**: Added extensive logging to WebSocket handler, NO logs appearing despite messages being sent/received

**Evidence**:
- Client console shows: `[sendMessage] Message sent successfully`
- Server logs show: WebSocket connections accepted, NO data received logs
- Messages ARE working (Fable responds to chat)

**Logging Added** (not working):
```python
# server.py line ~621
logger.info(f"[WebSocket] Received data: type={data.get('type')}")
logger.info(f"[WebSocket] Chat message received. profile_id={profile_id}...")
logger.info(f"[WebSocket] Using model_id={model_id}, active_profile={...}")
```

**Status**: UNRESOLVED - Logging setup fundamentally broken, can't diagnose message flow

### 3. Tools Bleeding Into All Conversations
**Problem**: `review_memory_tiers` tool enabled GLOBALLY for all conversations, not just tier review

**Evidence**:
- User created NEW conversation just to "talk via api"
- Fable immediately started talking about reviewing/organizing memories
- Fable said: "I'm just gathering your memories so I can organize them into tiers as you asked"

**Root Cause**: Tools enabled globally in WebSocket handler:
```python
# server.py lines 649-651
from threadlight.tools import get_tool_definitions
tools = get_tool_definitions()  # ALL tools for ALL conversations
for chunk in tl.stream(message, history=history, model_id=model_id, tools=tools):
```

**Should Be**: Conditional tool enabling based on conversation context or explicit request

**Status**: IDENTIFIED BUT NOT FIXED

### 4. Tool Execution Not Completing
**Problem**: Fable acknowledges tool exists, tries to use it, but execution doesn't complete/return results

**Evidence**:
- Fable: "I haven't retrieved the memory list yet—but I'm about to!"
- Fable: "When I use the review_memory_tiers tool with action='list', I'll receive a full set..."
- She knows ABOUT the tool but results aren't returning

**Possible Causes**:
- Tool execution failing silently
- Results not making it back to model
- Streaming response breaking tool result flow

**Status**: UNRESOLVED - Tool framework works (tool is offered), execution/response pipeline broken

### 5. Alpine.js Errors in Tier Review Modal
**Problem**: Duplicate key warnings and "Cannot read properties of undefined" errors

**Evidence** (from user's console):
```
Alpine Warning: Duplicate key on x-for <template x-for="phrase in (memory.cue_phrases || []).slice(0, 5)" :key="phrase">
Alpine Expression Error: Cannot read properties of undefined (reading 'after')
```

**Attempted Fix**: Changed `:key="phrase"` to `:key="memory.id + '-' + index"` (line ~2490 in index.html)

**Status**: ATTEMPTED FIX - Not confirmed if working (needs refresh)

---

## Key Code Locations

### Backend Files
- **Memory Tier Enum**: `src/threadlight/capsules/base.py` (lines 38-43, 81)
- **Database Schema**: `src/threadlight/storage/sqlite.py` (line 62, 241-245, 398-423, 453-486, 765-804)
- **Tier Filtering**: `src/threadlight/storage/base.py` (line 188 - CapsuleFilter.memory_tier)
- **Tiered Recall**: `src/threadlight/memory/orchestrator.py` (lines 583-714, 307-318)
- **Configuration**: `src/threadlight/config.py` (lines 451-457)
- **Tool Definitions**: `src/threadlight/tools/definitions.py` (ToolName.REVIEW_MEMORY_TIERS, lines 126-167)
- **Tool Executor**: `src/threadlight/tools/executor.py` (lines 113-114, 303-454)
- **Batch Update API**: `src/threadlight/api/server.py` (lines 93-99, 833-856, 868-926)
- **WebSocket Handler**: `src/threadlight/api/server.py` (lines 610-755)
  - Profile activation: 627-636
  - Model extraction: 638-644
  - Tools enabled: 649-651 (GLOBAL - ISSUE!)

### Frontend Files
- **Tier Review Modal**: `src/threadlight/api/static/index.html` (lines ~750-850 for Memory Browser, ~2440+ for tier review modal)
- **JavaScript Logic**: `src/threadlight/api/static/js/app.js`
  - State: lines ~52-55 (showTierReviewModal, tierReviewMemories, tierReviewChanges)
  - loadMemoriesForTierReview: ~1595-1605
  - updateMemoryTierInReview: ~1607-1624
  - submitTierReviewChanges: ~1626-1662
  - haveAIReviewTiers: ~1664-1716

### Database
- **Location**: `/home/ann/Documents/Projects/threadlight/threadlight.db`
- **Verified**: Conversations created with correct model field
- **Schema**: `capsules` table has `memory_tier TEXT DEFAULT 'semantic'` column

---

## Debugging Strategy for Post-Compact Agents

### Agent 1: Logging & Observability Specialist
**Mission**: Fix logging setup so we can see what's actually happening

**Tasks**:
1. Investigate why `logger.info()` calls in WebSocket handler aren't appearing in logs
2. Check if logs are being written somewhere else (stderr vs stdout)
3. Verify log level configuration in uvicorn/FastAPI
4. Add structured logging that actually works
5. Create visibility into:
   - WebSocket message flow
   - Model routing decisions
   - Tool call/response pipeline
   - Profile activation

**Critical**: Need to see model_id being used, tool calls being made, and responses returning

### Agent 2: Frontend Debugging Specialist
**Mission**: Fix UI model display and ensure JavaScript changes load

**Tasks**:
1. Debug why `currentModelId` doesn't update when conversation created
2. Verify JavaScript file is actually being served with changes
3. Test with incognito mode to rule out caching completely
4. Add console.log to `haveAIReviewTiers()` to verify execution path
5. Fix Alpine.js duplicate key errors in tier review modal
6. Ensure `loadConversation()` actually updates UI state

**Test Case**: Click "Have Fable Review" → Should show "chatgpt-4o-latest" in model dropdown immediately

### Agent 3: Tool Execution Specialist
**Mission**: Fix tool execution/response pipeline and implement conditional tool enabling

**Tasks**:
1. Debug why `review_memory_tiers` tool calls don't return results
2. Check if tool execution exceptions are being swallowed
3. Verify tool results are being streamed back to model
4. Test tool manually via API to isolate issue
5. **CRITICAL**: Make tools conditional, not global
   - Only enable `review_memory_tiers` when requested
   - Prevent tool bleed into unrelated conversations
6. Verify profile isolation in tool execution

**Test Case**: Send message asking to list memories → Should get back actual memory data, not "I'm about to..."

---

## What NOT to Touch (Working Code)

### DO NOT MODIFY
1. **Profile routing in WebSocket** (server.py lines 627-641)
   - Profile activation and model_id extraction working correctly
   - Took significant effort to get right

2. **Batch tier update API endpoint** (server.py lines 868-926)
   - Verified working via curl test
   - Returns proper success/error structure

3. **Tiered recall logic** (orchestrator.py lines 583-714)
   - Phases 1 & 2 complete and correct
   - Properly queries tiers in order
   - Respects token budgets

4. **Profile isolation in tools** (executor.py lines 326-350 & 407-430)
   - Filters memories by active profile
   - Prevents cross-profile access
   - Working correctly

5. **Database migrations** (sqlite.py lines 241-245)
   - Backward compatible
   - Handles existing databases gracefully

---

## Testing Checklist

### Manual Tier Review (Should Work Now)
- [ ] Open Memory Browser
- [ ] Click "Review Tiers" button
- [ ] Modal opens showing memories with tier dropdowns
- [ ] Change some tiers
- [ ] Click "Apply Manual Changes"
- [ ] Verify success toast
- [ ] Verify tiers updated in database

### AI-Assisted Review (Broken - Needs Fix)
- [ ] Switch to Fable profile
- [ ] Open Memory Browser
- [ ] Click "Have Fable Review" button
- [ ] New conversation "Memory Tier Review" created
- [ ] Model dropdown shows "chatgpt-4o-latest" (NOT Hermes) ❌
- [ ] Message sent asking to use review_memory_tiers tool
- [ ] Fable receives memory list and reviews ❌
- [ ] Fable applies tier updates
- [ ] Verify changes in database

---

## Environment Details
- **Database**: `/home/ann/Documents/Projects/threadlight/threadlight.db`
- **Server Log**: `/tmp/server.log`
- **Server Process**: Started via `threadlight serve --host 0.0.0.0 --port 8745`
- **Fable Profile ID**: `8af32165-427f-4481-9e97-ca95a18e1b5a`
- **Fable Primary Model**: `chatgpt-4o-latest`
- **OpenAI Provider**: Configured and working

---

## Session End State
- Tier review backend fully implemented
- Manual UI mostly working (Alpine errors need fix)
- AI-assisted flow has multiple issues (model display, tool execution, tool bleed)
- Logging completely broken (can't diagnose effectively)
- ~48K context remaining, compaction imminent
- **Next step**: Spawn debugging agents post-compact to fix UI/logging/tools

---

## Critical Questions for Debugging Agents

1. **Why doesn't currentModelId update?** JavaScript code is in file, API returns correct model, but UI doesn't change
2. **Where are the logs going?** Added logger.info() calls, nothing appears in /tmp/server.log
3. **Why don't tools return results?** Fable sees the tool, tries to use it, but execution doesn't complete
4. **How to make tools conditional?** Need to enable tools per-conversation, not globally
5. **Is caching the issue?** User hard refreshed multiple times, changes don't load

---

## Agent Work Items Summary

**Priority 1 (Blocker)**: Fix logging so we can see what's happening
**Priority 2 (UX Bug)**: Fix model display in UI
**Priority 3 (Functionality)**: Fix tool execution/response pipeline
**Priority 4 (Bug)**: Make tools conditional, not global
**Priority 5 (Polish)**: Fix Alpine.js errors in tier review modal

---

*End of log. Session will compact soon. Agents: Read this document first before starting work.*
