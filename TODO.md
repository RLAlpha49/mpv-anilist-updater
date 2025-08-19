# TODO

Legend: ☐ not completed | ☑ completed

## Pull Request Batches

1. Cache
	- PR Title: Cache: structured cache file, LRU eviction & debounced updates
	- Branch Name: cache
	- PR Description: Introduce robust caching (structured separate cache.json with hash→{guessed_name, anime_id, last_progress, ttl}, LRU eviction), minimize disk/token I/O by removing cache lines from token file, and debounce noisy playback events to improve stability & performance.
	- ☑ Structured cache file (move cache lines from anilistToken.txt to cache.json; hash→{guessed_name, anime_id, last_progress, ttl})
	- ☑ Cache enhancements: LRU / max size eviction
	- ☑ Single token read + in-memory; redact token in debug
	- ☑ Debounce rapid percent-pos events

2. Foundational Refactor & Types
	- PR Title: Refactor core into modules + typing & exceptions
	- Branch Name: refactor-types
	- PR Description: Split file into modules, add typing/dataclasses and unified exceptions, and centralize GraphQL queries to reduce complexity.
	- ☐ Split `anilistUpdater.py` into modules (api_client, parser, cache, updater, cli)
	- ☐ Introduce dataclasses / TypedDicts; replace tuple returns
	- ☐ Centralize GraphQL queries
	- ☐ Custom exception hierarchy (ParseError, MatchAmbiguousError, NotInListError, ApiError)

3. Core Interaction & Hotkeys
	- PR Title: Hotkeys & runtime control (force update, reload, cache clear)
	- Branch Name: hotkeys-runtime-control
	- PR Description: Provide immediate user control (force update, runtime reload, per-show cache clear) establishing a responsive interaction layer for later UX enhancements.
	- ☐ Multi-action hotkeys (Force update, Reload config, Clear cache for current show)
	- ☐ Implement runtime config reload & targeted cache clear

4. Config & Safety Enhancements
	- PR Title: Config expansion (auto-add, env token, trigger modes, dry-run)
	- Branch Name: config-safety
	- PR Description: Expand and harden configuration surface (auto-add entries, env token override, secure storage, trigger mode selection, dry-run) improving flexibility without risking unintended writes.
	- ☐ Add-entry-if-missing option
	- ☐ Environment variable token override (ANILIST_TOKEN)
	- ☐ Separate token storage / permissions handling
	- ☐ Configurable trigger mode (threshold vs EOF)
	- ☐ Dry-run / NO_WRITE_MODE flag

5. Parsing & Media-Type Coverage
	- PR Title: Parser improvements (specials, gap detection, heuristics)
	- Branch Name: parsing-media-types
	- PR Description: Enhance filename/media parsing to properly classify specials/movies, detect suspicious episode gaps, and refine absolute-number heuristics & ambiguity handling for safer progress updates.
	- ☐ Support specials / OVA / movies (detect + handle/skip)
	- ☐ Episode gap detection warning
	- ☐ Improve absolute numbering heuristic & ambiguous match handling

6. UX / Overlay & Feedback
	- PR Title: Overlay & feedback messaging upgrades
	- Branch Name: ux-overlay-feedback
	- PR Description: Surface clear, timely playback metadata and differentiate auto vs manual operations; reduce OSD flicker and improve user confidence before updates occur.
	- ☐ Overlay status preview on load (title + planned episode + abs numbering flag)
	- ☐ Distinguish auto vs manual updates in messages
	- ☐ "Will mark COMPLETED after this episode" pre-threshold message
	- ☐ Reuse OSD message IDs to avoid flicker

7. Lua Script Extensions
	- PR Title: MPV Lua integration enhancements & script messages
	- Branch Name: lua-extensions
	- PR Description: Strengthen MPV integration reliability and expose script-message hooks enabling external automation and scripting beyond hotkeys.
	- ☐ Reattach observer on each file-loaded
	- ☐ mpv script-message interface (e.g. `script-message anilist-update-now`)
	- ☐ Wire manual trigger path

8. Batch / Library CLI Mode
	- PR Title: CLI batch dry-run & unmapped report
	- Branch Name: batch-cli-mode
	- PR Description: Add CLI tooling to dry-run parse libraries and enumerate unmapped or ambiguous files so users can fix naming issues proactively.
	- ☐ Directory tree dry-run parse
	- ☐ Report unmapped / ambiguous files

9. Retry & Error Classification
	- PR Title: Resilient networking (retry & error classification)
	- Branch Name: retry-error-handling
	- PR Description: Introduce resilient networking via exponential backoff and clear separation of transient vs logic failures; avoid blocking UI when opening external resources.
	- ☐ Automatic retry with exponential backoff
	- ☐ Network vs logic error classification (uses custom exceptions)
	- ☐ Optional async/non-blocking external browser open

10. Backend Abstraction
	- PR Title: Backend strategy abstraction (AniList isolation)
	- Branch Name: backend-abstraction
	- PR Description: Define backend strategy interface and isolate AniList implementation, laying groundwork for optional MAL/Kitsu support without core rewrites.
	- ☐ Strategy interface (AniList now; MAL/Kitsu placeholders)
	- ☐ Adapter wiring (no full feature parity yet)

11. Session Logging & Export
	- PR Title: Session logging (CSV/JSON) w/ timestamps & mode flag
	- Branch Name: session-logging
	- PR Description: Provide structured watch session logging (CSV/JSON) including timestamps and manual/auto attribution to aid debugging, analytics, and user history.
	- ☐ Watch session log (CSV/JSON) incl. timestamps & auto/manual flag

12. Documentation & Diagrams
	- PR Title: Docs & diagrams (architecture, troubleshooting, config ref)
	- Branch Name: docs-diagrams
	- PR Description: Add architecture/flow diagram, troubleshooting guide, and comprehensive config reference to reduce onboarding time and support overhead.
	- ☐ Flow diagram
	- ☐ Troubleshooting section
	- ☐ Config reference table & README updates

Deferred / Future Epics
	- ☐ Local web or TUI config editor
	- ☐ Advanced multi-backend sync / reconciliation
	- ☐ Rich ambiguity resolution (interactive selection)

Notes
	- (Meta) May collapse 2+3 or 6+7 if review bandwidth tight
	- (Meta) Keep PR 2 standalone to reduce rebase churn
	- (Meta) Target ≤ ~600 LOC net diff per PR where practical
