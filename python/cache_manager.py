"""Cache operations and file management."""

import hashlib
import json
import os
import time
from typing import Any, Optional

from .data_classes import AnimeInfo


class CacheManager:
    """Handles cache operations and file management."""

    CACHE_REFRESH_RATE: int = 24 * 60 * 60

    def __init__(self, cache_path: str) -> None:
        """Initialize cache manager with path."""
        self.cache_path = cache_path
        self._cache: Optional[dict[str, Any]] = None

    def cache_to_file(self, path: str, guessed_name: str, absolute_progress: int, result: AnimeInfo) -> None:
        """
        Store/update cache entry for anime information.

        Args:
            path (str): File path.
            guessed_name (str): Guessed anime name.
            absolute_progress (int): Absolute episode number.
            result (AnimeInfo): Anime information to cache.
        """
        try:
            dir_hash = self.hash_path(os.path.dirname(path))
            cache = self.load_cache()

            anime_id, _, current_progress, total_episodes, relative_progress, current_status = result

            now = time.time()

            cache[dir_hash] = {
                "guessed_name": guessed_name,
                "anime_id": anime_id,
                "current_progress": current_progress,
                "relative_progress": f"{absolute_progress}->{relative_progress}",
                "total_episodes": total_episodes,
                "current_status": current_status,
                "ttl": now + self.CACHE_REFRESH_RATE,
            }

            self.save_cache(cache)
        except Exception as e:
            print(f"Error trying to cache {result}: {e}")

    def hash_path(self, path: str) -> str:
        """
        Generate SHA256 hash of normalized path.

        Normalizes the path on all platforms to ensure consistent hashing,
        especially on Windows where case sensitivity can vary.

        Args:
            path (str): Path to hash.

        Returns:
            str: Hashed path.
        """
        normalized_path = os.path.normcase(os.path.normpath(path))
        normalized_path = normalized_path.replace(os.sep, "/")
        return hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()

    def check_and_clean_cache(self, path: str, guessed_name: str) -> Optional[dict[str, Any]]:
        """
        Get valid cache entry and clean expired entries.

        Args:
            path (str): Path to media file.
            guessed_name (str): Guessed anime name.

        Returns:
            Optional[dict[str, Any]]: Cache entry or None if not found/valid.
        """
        try:
            cache = self.load_cache()
            now = time.time()
            keys_to_delete = []
            for k, v in cache.items():
                if v.get("ttl", 0) < now:
                    keys_to_delete.append(k)

            changed = len(keys_to_delete) > 0
            for k in keys_to_delete:
                cache.pop(k, None)

            if changed:
                self.save_cache(cache)

            dir_hash = self.hash_path(os.path.dirname(path))
            entry = cache.get(dir_hash)

            if entry and entry.get("guessed_name") == guessed_name:
                return entry

            return None
        except Exception as e:
            print(f"Error trying to read cache file: {e}")
            return None

    def load_cache(self) -> dict[str, Any]:
        """
        Load cache from JSON file with lazy loading.

        Returns:
            dict[str, Any]: Cache data or empty dict if file doesn't exist.
        """
        if self._cache is None:
            try:
                if not os.path.exists(self.cache_path):
                    self._cache = {}
                else:
                    with open(self.cache_path, encoding="utf-8") as f:
                        self._cache = json.load(f)
            except Exception:
                self._cache = {}
        # At this point, self._cache is guaranteed to be a dict
        assert self._cache is not None
        return self._cache

    def save_cache(self, cache: dict[str, Any]) -> None:
        """
        Save cache dictionary to JSON file.

        Args:
            cache (dict[str, Any]): Cache data to save.
        """
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            # Keep local cache in sync
            self._cache = cache
        except Exception as e:
            print(f"Failed saving cache.json: {e}")
