"""
Legacy wrapper for mpv-anilist-updater.

This file is kept for backward compatibility. The main logic has been moved to python/main.py.
"""

# For backward compatibility with existing MPV Lua scripts
from python.main import main

if __name__ == "__main__":
    main()
