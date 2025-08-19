# TODO

Legend: ☐ not completed | ☑ completed

## Pull Request Batches

1. ☑ Cache
	- PR Title: Cache: structured cache file, LRU eviction & debounced updates
	- Branch Name: cache
	- PR Description: Introduce robust caching (structured separate cache.json with hash→{guessed_name, anime_id, last_progress, ttl}, LRU eviction), minimize disk/token I/O by removing cache lines from token file, and debounce noisy playback events to improve stability & performance.
	- ☑ Structured cache file (move cache lines from anilistToken.txt to cache.json; hash→{guessed_name, anime_id, last_progress, ttl})
	- ☑ Cache enhancements: LRU / max size eviction
	- ☑ Single token read + in-memory; redact token in debug
	- ☑ Debounce rapid percent-pos events

2. Types, Exceptions & Hotkeys
	- PR Title: Typing, exceptions & hotkeys refactor
	- Branch Name: types-hotkeys
	- PR Description: This adds proper typing throughout the codebase using dataclasses and TypedDicts to replace tuple returns, introduces a unified exception hierarchy, and centralizes GraphQL queries. It also adds immediate user control through multi-action hotkeys for force updating progress, reloading configuration at runtime, and clearing cache for the current show.
	- ☐ Introduce dataclasses / TypedDicts; replace tuple returns
	- ☐ Centralize GraphQL queries
	- ☐ Custom exception hierarchy (ParseError, MatchAmbiguousError, NotInListError, ApiError)
	- ☐ Multi-action hotkeys (Force update, Reload config, Clear cache for current show)
	- ☐ Implement runtime config reload & targeted cache clear

3. Config & Safety Enhancements
	- PR Title: Config expansion (auto-add, env token, trigger modes, dry-run)
	- Branch Name: config-safety
	- PR Description: This expands configuration options with auto-add entries for missing anime, environment variable token override (ANILIST_TOKEN), configurable trigger modes (threshold vs EOF), and dry-run mode. It also improves token security with separate storage and proper permissions handling to prevent unintended writes.
	- ☐ Add-entry-if-missing option
	- ☐ Environment variable token override (ANILIST_TOKEN)
	- ☐ Separate token storage / permissions handling
	- ☐ Configurable trigger mode (threshold vs EOF)
	- ☐ Dry-run / NO_WRITE_MODE flag

4. Parsing & Media-Type Coverage
	- PR Title: Parser improvements (specials, gap detection, heuristics)
	- Branch Name: parsing-media-types
	- PR Description: This enhances filename parsing to properly classify and handle specials, OVAs, and movies (detecting them and skipping updates appropriately). It also adds episode gap detection warnings to catch suspicious numbering and improves absolute numbering heuristics with better ambiguous match handling for safer progress updates.
	- ☐ Support specials / OVA / movies (detect + handle/skip)
	- ☐ Episode gap detection warning
	- ☐ Improve absolute numbering heuristic & ambiguous match handling

5. UX & MPV Integration
	- PR Title: Overlay feedback & MPV script enhancements
	- Branch Name: ux-mpv-integration
	- PR Description: This improves user feedback by showing overlay status previews on file load (title, planned episode, absolute numbering flag), distinguishing auto vs manual updates in messages, and adding completion warnings. It also strengthens MPV integration reliability by reattaching observers on each file-loaded event and exposes script-message hooks for external automation.
	- ☐ Overlay status preview on load (title + planned episode + abs numbering flag)
	- ☐ Distinguish auto vs manual updates in messages
	- ☐ "Will mark COMPLETED after this episode" pre-threshold message
	- ☐ Reuse OSD message IDs to avoid flicker
	- ☐ Add configuration options for overlay and message behavior
	- ☐ Reattach observer on each file-loaded
	- ☐ mpv script-message interface (e.g. `script-message anilist-update-now`)
	- ☐ Wire manual trigger path

6. Batch / Library CLI Mode
	- PR Title: CLI batch dry-run & unmapped report
	- Branch Name: batch-cli-mode
	- PR Description: This adds CLI tooling to dry-run parse entire directory trees and generate reports of unmapped or ambiguous files. This allows users to proactively identify and fix naming issues before they cause problems during actual playback.
	- ☐ Directory tree dry-run parse
	- ☐ Report unmapped / ambiguous files

7. Networking & Backend Abstraction
	- PR Title: Resilient networking & backend strategy abstraction
	- Branch Name: networking-backend
	- PR Description: This introduces resilient networking with automatic retry using exponential backoff and clear separation of transient vs logic failures. It also defines a backend strategy interface and isolates the AniList implementation, laying groundwork for optional MAL/Kitsu support without requiring core rewrites.
	- ☐ Automatic retry with exponential backoff
	- ☐ Network vs logic error classification (uses custom exceptions)
	- ☐ Optional async/non-blocking external browser open
	- ☐ Strategy interface (AniList now; MAL/Kitsu placeholders)
	- ☐ Adapter wiring (no full feature parity yet)

8. Logging & Documentation
	- PR Title: Session logging & comprehensive documentation
	- Branch Name: logging-docs
	- PR Description: This provides structured watch session logging in CSV/JSON formats including timestamps and manual/auto attribution flags to aid in debugging and analytics. It also adds comprehensive documentation including an architecture/flow diagram, troubleshooting guide, and complete configuration reference table to reduce onboarding time and support overhead.
	- ☐ Watch session log (CSV/JSON) incl. timestamps & auto/manual flag
	- ☐ Flow diagram
	- ☐ Troubleshooting section
	- ☐ Config reference table & README updates

Deferred / Future Epics
	- ☐ Local web or TUI config editor
	- ☐ Advanced multi-backend sync / reconciliation
	- ☐ Rich ambiguity resolution (interactive selection)
