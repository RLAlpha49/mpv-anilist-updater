"""
mpv-anilist-updater: Auto-update AniList based on MPV file watching.

Parses anime filenames, finds AniList entries, and updates progress/status.
"""

# Configuration options for anilistUpdater (set in anilistUpdater.conf):
#   DIRECTORIES: List or comma/semicolon-separated string. The directories the script will work on. Leaving it empty will make it work on every video you watch with mpv. Example: DIRECTORIES = ["D:/Torrents", "D:/Anime"]
#   UPDATE_PERCENTAGE: Integer (0-100). The percentage of the video you need to watch before it updates AniList automatically. Default is 85 (usually before the ED of a usual episode duration).
#   SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE: Boolean. If true, when watching episode 1 of a completed anime, set it to rewatching and update progress.
#   UPDATE_PROGRESS_WHEN_REWATCHING: Boolean. If true, allow updating progress for anime set to rewatching. This is for if you want to set anime to rewatching manually, but still update progress automatically.
#   SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT: Boolean. If true, set to COMPLETED after last episode if status was CURRENT.
#   SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING: Boolean. If true, set to COMPLETED after last episode if status was REPEATING (rewatching).
#   ADD_ENTRY_IF_MISSING: Boolean. If true, automatically add anime to your list when an update is triggered (i.e., when you've watched enough of the episode). Default is False.

import json
import sys
from pathlib import Path

# Add the parent directory to sys.path to enable absolute imports from the python package
script_dir = Path(__file__).resolve().parent
parent_dir = script_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from python.updater import AniListUpdater  # noqa: E402


def main() -> None:
    """Main entry point for the script."""
    try:
        # Reconfigure to utf-8
        if sys.stdout.encoding != "utf-8":
            try:
                sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
                sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
            except Exception as e_reconfigure:
                print(f"Couldn't reconfigure stdout/stderr to UTF-8: {e_reconfigure}", file=sys.stderr)

        # Parse options from argv[3] if present
        options = {
            "SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE": False,
            "UPDATE_PROGRESS_WHEN_REWATCHING": True,
            "SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT": False,
            "SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING": True,
            "ADD_ENTRY_IF_MISSING": False,
        }
        if len(sys.argv) > 3:
            user_options = json.loads(sys.argv[3])
            options.update(user_options)

        # Pass options to AniListUpdater
        updater = AniListUpdater(options, sys.argv[2])
        updater.handle_filename(sys.argv[1])

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
