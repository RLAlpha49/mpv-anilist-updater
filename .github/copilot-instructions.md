# Copilot Instructions for mpv-anilist-updater

## Project Architecture

This is an MPV media player script that automatically updates AniList anime progress. The architecture consists of:

- **`main.lua`**: MPV interface layer that handles events, keybinds, and configuration
- **`anilistUpdater.py`**: Core logic for filename parsing, AniList API communication, and progress updates
- **Configuration**: `anilistUpdater.conf` auto-generated in MPV's script-opts directory

### Data Flow
1. MPV loads video → Lua script captures file path and playback events
2. Lua calls Python script with file path and action (`update`/`launch`)
3. Python parses filename using GuessIt → queries AniList API → updates progress
4. Results cached locally for 24 hours to reduce API calls

## Coding Standards
- Add typing annotations to all functions and classes, including return types.
- Add descriptive docstrings to all functions and classes (PEP 257 convention). Update existing docstrings if needed.
- Keep all existing comments in files.
- Use Ruff for code style consistency.

## Key Components

### Filename Parsing Strategy
- Primary: Parse episode/season from filename using GuessIt library
- Fallback: Extract anime title from parent folder if filename parsing fails
- Absolute numbering: Map episode numbers to seasons using AniList episode counts
- Year detection: Handle remakes by specifying year in filename/folder

### AniList Integration
- **Authentication**: Bearer token stored in `anilistToken.txt`
- **GraphQL API**: Two main operations - anime search and progress update
- **Caching**: Directory-based hashing in `cache.json` with 24-hour TTL
- **Status Logic**: Only updates anime with status "watching", "planning", or "rewatching"

### Configuration System
Config file searched in priority order:
1. `script-opts/anilistUpdater.conf` (preferred)
2. `scripts/anilistUpdater.conf` (script directory)
3. MPV config directory

## Development Patterns

### Error Handling
- Non-blocking: Failures don't interrupt video playback
- Graceful degradation: Missing token/API errors shown as OSD messages
- Legacy cleanup: Auto-removes old cache formats and user_id from token file

### MPV Integration Patterns
- **Timer control**: Stop/resume based on pause state and directory filters
- **Event handling**: `file-loaded` resets episode detection state
- **OSD messaging**: User feedback without interrupting playback
- **Subprocess calls**: Async Python execution with callback handling

## API Integration Notes

### Rate Limiting
- Cache prevents repeated API calls for same directory
- 24-hour TTL balances freshness vs API usage
- Failed requests don't invalidate cache

### GraphQL Queries
- Search includes year filtering and onList status
- Update mutation only requires mediaId, progress, and status
- Media format filtering (TV shows >21 minutes) for accurate season detection

## Code Analysis & Improvement Guidelines

### Pre-Change Investigation
Before implementing any changes, AI agents should:
- **Context Analysis**: Read surrounding code to understand the full implementation context
- **Logic Review**: Examine existing algorithms for potential optimizations or simplifications
- **Error Scenarios**: Identify edge cases and potential failure points in current and proposed code
- **Dependency Impact**: Check how changes affect the Lua ↔ Python communication layer

### Code Quality Checks
- **Redundancy Detection**: Look for unnecessary code patterns or duplicate logic
- **Performance Opportunities**: Identify inefficient API calls, file I/O, or parsing operations
- **Error Handling Gaps**: Ensure proper exception handling for network failures, file access, and parsing errors
- **Cross-Platform Compatibility**: Verify changes work on Windows, Linux, and macOS

### Bug Prevention Patterns
- **Input Validation**: Check for edge cases in data being processed or parameters being passed
- **State Management**: Investigate potential race conditions or state inconsistencies around modified code
- **Error Propagation**: Ensure failures are handled gracefully and don't cascade to unrelated functionality
- **Boundary Conditions**: Test limits, null values, empty collections, and extreme inputs
- **Integration Points**: Verify changes don't break communication between components or external services
