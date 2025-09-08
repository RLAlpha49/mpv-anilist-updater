"""Main AniListUpdater class."""

import os
import webbrowser
from typing import Any, Optional

from .api_client import APIClient
from .auth_manager import AuthManager
from .cache_manager import CacheManager
from .data_classes import AnimeInfo, SeasonEpisodeInfo
from .filename_parser import FilenameParser
from .queries import AniListQueries


def osd_message(msg: str) -> None:
    """Display an on-screen display (OSD) message."""
    print(f"OSD:{msg}")


class AniListUpdater:
    """AniList authentication, file parsing, API requests, and progress updates."""

    TOKEN_PATH: str = os.path.join(os.path.dirname(__file__), "..", "anilistToken.txt")
    CACHE_PATH: str = os.path.join(os.path.dirname(__file__), "..", "cache.json")

    def __init__(self, options: dict[str, Any], action: str) -> None:
        """
        Initialize AniListUpdater with configuration and action.

        Args:
            options (dict[str, Any]): Configuration options.
            action (str): Action to perform ('update' or 'launch').
        """
        self.auth_manager = AuthManager(self.TOKEN_PATH)
        self.cache_manager = CacheManager(self.CACHE_PATH)
        self.api_client = APIClient()
        self.filename_parser = FilenameParser()

        self.access_token: Optional[str] = self.auth_manager.load_access_token()
        self.options: dict[str, Any] = options
        self.ACTION: str = action

    @staticmethod
    def season_order(season: Optional[str]) -> int:
        """
        Get numeric order for season sorting.

        Args:
            season (Optional[str]): Season name (WINTER, SPRING, SUMMER, FALL).

        Returns:
            int: Order value.
        """
        return {"WINTER": 1, "SPRING": 2, "SUMMER": 3, "FALL": 4}.get(season, 5)  # type: ignore

    def find_season_and_episode(self, seasons: list[dict[str, Any]], absolute_episode: int) -> SeasonEpisodeInfo:
        """
        Find correct season and relative episode for absolute episode number.

        Args:
            seasons (list[dict[str, Any]]): Season dicts.
            absolute_episode (int): Absolute episode number.

        Returns:
            SeasonEpisodeInfo: Season and episode information.
        """
        accumulated_episodes = 0
        for season in seasons:
            season_episodes = season.get("episodes", 12) if season.get("episodes") else 12

            if accumulated_episodes + season_episodes >= absolute_episode:
                return SeasonEpisodeInfo(
                    season.get("id"),
                    season.get("title", {}).get("romaji"),
                    season.get("mediaListEntry", {}).get("progress") if season.get("mediaListEntry") else None,
                    episodes=season.get("episodes"),
                    relative_episode=absolute_episode - accumulated_episodes,
                )
            accumulated_episodes += season_episodes
        return SeasonEpisodeInfo(None, None, None, None, None)

    def handle_filename(self, filename: str) -> None:
        """
        Handle file processing: parse, check cache, update AniList.

        Args:
            filename (str): Path to video file.
        """
        file_info = self.filename_parser.parse_filename(filename)
        cache_entry = self.cache_manager.check_and_clean_cache(filename, file_info.name)

        # If launching and cache has anime_id, we can skip search and open directly.
        if self.ACTION == "launch" and cache_entry and cache_entry.get("anime_id"):
            anime_id = cache_entry["anime_id"]
            print(f'Opening AniList (cached) for guessed "{file_info.name}": https://anilist.co/anime/{anime_id}')
            osd_message(f'Opening AniList for "{file_info.name}"')
            webbrowser.open_new_tab(f"https://anilist.co/anime/{anime_id}")
            return

        # Use cached data if available, otherwise fetch fresh info
        if cache_entry:
            print(f'Using cached data for "{file_info.name}"')

            left, right = cache_entry.get("relative_progress", "0->0").split("->")
            # For example, if 19->7, that means that 19 absolute is equivalent to 7 relative to this season
            # File episode 20: 18 - 19 + 7 = 8 relative to this season
            offset = int(left) - int(right)

            relative_episode = file_info.episode - offset

            if 1 <= relative_episode <= (cache_entry.get("total_episodes") or 0):
                # Reconstruct result from cache
                result = AnimeInfo(
                    cache_entry["anime_id"],
                    cache_entry["guessed_name"],
                    cache_entry["current_progress"],
                    cache_entry["total_episodes"],
                    relative_episode,
                    cache_entry["current_status"],
                )
            else:
                result = self.get_anime_info_and_progress(file_info.name, file_info.episode, file_info.year)

        else:
            result = self.get_anime_info_and_progress(file_info.name, file_info.episode, file_info.year)

        result = self.update_episode_count(result)

        if result and result.current_progress is not None:
            # Update cache with latest data
            self.cache_manager.cache_to_file(filename, file_info.name, file_info.episode, result)
        return

    def filter_valid_seasons(self, seasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter and sort valid TV seasons for absolute numbering.

        Args:
            seasons (list[dict[str, Any]]): Season dicts from AniList API.

        Returns:
            list[dict[str, Any]]: Filtered and sorted seasons.
        """
        # Filter only to those whose format is TV and duration > 21 OR those who have no duration and are releasing.
        # This is due to newly added anime having duration as null
        seasons = [
            season
            for season in seasons
            if (
                (season["duration"] is None and season["status"] == "RELEASING")
                or (season["duration"] is not None and season["duration"] > 21)
            )
            and season["format"] == "TV"
        ]
        # One of the problems with this filter is needing the format to be 'TV'
        # But if accepted any format, it would also include many ONA's which arent included in absolute numbering.

        # Sort them based on release date
        seasons = sorted(
            seasons,
            key=lambda x: (
                x["seasonYear"] or float("inf"),
                self.season_order(x["season"]),
            ),
        )
        return seasons

    def get_anime_info_and_progress(self, name: str, file_progress: int, year: str) -> AnimeInfo:
        """
        Query AniList for anime info and user progress.

        Args:
            name (str): Anime title.
            file_progress (int): Episode number from file.
            year (str): Year string (may be empty).

        Returns:
            AnimeInfo: Complete anime information.

        Raises:
            Exception: If the update fails.
        """
        # Only those that are in the user's list
        query = AniListQueries.SEARCH_ANIME
        variables = {"search": name, "year": year or 1, "page": 1, "onList": True}

        response = self.api_client.make_api_request(query, variables, self.access_token)

        if not response or "data" not in response:
            return AnimeInfo(None, None, None, None, None, None)

        seasons = response["data"]["Page"]["media"]

        # No results from the API request
        if not seasons:
            # For launch action or ADD_ENTRY_IF_MISSING, search all anime (not just user's list)
            if self.ACTION == "launch" or self.options.get("ADD_ENTRY_IF_MISSING", False):
                print(f"Anime '{name}' not found in your list. Searching all anime...")
                variables["onList"] = False
                response = self.api_client.make_api_request(query, variables, self.access_token)

                if not response or "data" not in response:
                    return AnimeInfo(None, None, None, None, None, None)

                seasons = response["data"]["Page"]["media"]
                if not seasons:
                    raise Exception(f"Couldn't find an anime from this title! ({name})")

                # If this is an ADD_ENTRY_IF_MISSING request, prepare anime data for potential addition
                if self.ACTION != "launch" and self.options.get("ADD_ENTRY_IF_MISSING", False):
                    anime_to_add = seasons[0]
                    anime_id = anime_to_add["id"]
                    anime_title = anime_to_add["title"]["romaji"]

                    # Return AnimeInfo with None progress to indicate it needs to be added to list
                    # The addition will happen in update_episode_count when update is actually triggered
                    return AnimeInfo(anime_id, anime_title, None, anime_to_add["episodes"], file_progress, None)
            else:
                raise Exception(f"Couldn't find an anime from this title! ({name}). Is it in your list?")

        # This is the first element, which is the same as Media(search: $search)
        entry = seasons[0]["mediaListEntry"]
        anime_data = AnimeInfo(
            seasons[0]["id"],
            seasons[0]["title"]["romaji"],
            entry["progress"] if entry is not None else None,
            seasons[0]["episodes"],
            file_progress,
            entry["status"] if entry is not None else None,
        )

        # If the episode in the file name is larger than the total amount of episodes
        # Then they are using absolute numbering format for episodes
        # Try to guess season and episode.
        if seasons[0]["episodes"] is not None and file_progress > seasons[0]["episodes"]:
            seasons = self.filter_valid_seasons(seasons)
            print("Related shows:", ", ".join(season["title"]["romaji"] for season in seasons))
            season_episode_info = self.find_season_and_episode(seasons, file_progress)
            print(season_episode_info)
            found_season = next(
                (season for season in seasons if season["id"] == season_episode_info.season_id), None
            )
            found_entry = (
                found_season["mediaListEntry"] if found_season and found_season["mediaListEntry"] else None
            )
            anime_data = AnimeInfo(
                season_episode_info.season_id,
                season_episode_info.season_title,
                season_episode_info.progress,
                season_episode_info.episodes,
                season_episode_info.relative_episode,
                found_entry["status"] if found_entry else None,
            )
            print(f"Final guessed anime: {found_season}")
            print(
                f"Absolute episode {file_progress} corresponds to Anime: {anime_data.anime_name}, Episode: {anime_data.file_progress}"
            )
        else:
            print(f"Final guessed anime: {seasons[0]}")
        return anime_data

    def update_episode_count(self, result: AnimeInfo) -> AnimeInfo:
        """
        Update episode count and/or status on AniList per user settings.

        Args:
            result (AnimeInfo): Anime information.

        Returns:
            AnimeInfo: Updated anime information.

        Raises:
            Exception: If the update fails.
        """
        if result is None:
            raise Exception("Parameter in update_episode_count is null.")

        anime_id, anime_name, current_progress, total_episodes, file_progress, current_status = result

        if anime_id is None:
            raise Exception("Couldn't find that anime! Make sure it is on your list and the title is correct.")

        # Only launch anilist
        if self.ACTION == "launch":
            osd_message(f'Opening AniList for "{anime_name}"')
            print(f'Opening AniList for "{anime_name}": https://anilist.co/anime/{anime_id}')
            webbrowser.open_new_tab(f"https://anilist.co/anime/{anime_id}")
            return result

        # Handle adding anime to list if it's not already there (ADD_ENTRY_IF_MISSING feature)
        if current_progress is None and current_status is None:
            # This indicates anime was found in search but is not in user's list
            if self.options.get("ADD_ENTRY_IF_MISSING", False):
                print(f'Adding "{anime_name}" to your list since you\'re watching it...')

                # Since user is actively watching this anime, always set to CURRENT
                initial_status = "CURRENT"

                # Add to list
                if self.add_anime_to_list(anime_id, anime_name, initial_status, file_progress):
                    osd_message(f'Added "{anime_name}" to your list with progress: {file_progress}')
                    print(f'Successfully added "{anime_name}" to your list with progress: {file_progress}')
                    # Return updated result
                    return AnimeInfo(
                        anime_id, anime_name, file_progress, total_episodes, file_progress, initial_status
                    )
                raise Exception(f"Failed to add '{anime_name}' to your list.")
            raise Exception("Failed to get current episode count. Is it on your list?")

        # Handle completed -> rewatching on first episode
        if (
            current_status == "COMPLETED"
            and file_progress == 1
            and self.options["SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE"]
        ):
            # Needs to update in 2 steps, since AniList
            # doesn't allow setting progress while changing the status from completed to rewatching.
            # If you try, it will just reset the progress to 0.
            print(
                "Setting status to REPEATING (rewatching) and updating progress for first episode of completed anime."
            )

            # Step 1: Set to REPEATING, progress=0
            query = AniListQueries.SAVE_MEDIA_LIST_ENTRY

            variables = {"mediaId": anime_id, "progress": 0, "status": "REPEATING"}
            response = self.api_client.make_api_request(query, variables, self.access_token)

            # Step 2: Set progress to 1
            variables = {"mediaId": anime_id, "progress": 1}
            response = self.api_client.make_api_request(query, variables, self.access_token)

            if response and "data" in response:
                updated_progress = response["data"]["SaveMediaListEntry"]["progress"]
                osd_message(f'Updated "{anime_name}" to REPEATING with progress: {updated_progress}')
                print(f"Episode count updated successfully! New progress: {updated_progress}")

                return AnimeInfo(anime_id, anime_name, updated_progress, total_episodes, 1, "REPEATING")
            print("Failed to update episode count.")
            raise Exception("Failed to update episode count.")

        # Handle updating progress for rewatching
        if current_status == "REPEATING" and self.options["UPDATE_PROGRESS_WHEN_REWATCHING"]:
            print("Updating progress for anime set to REPEATING (rewatching).")
            status_to_set = "REPEATING"

        # Only update if status is CURRENT or PLANNING
        elif current_status in {"CURRENT", "PLANNING"}:
            # If its lower than the current progress, dont update.
            if file_progress and current_progress is not None and file_progress <= current_progress:
                raise Exception(f"Episode was not new. Not updating ({file_progress} <= {current_progress})")

            status_to_set = "CURRENT"

        else:
            raise Exception(f"Anime is not in a modifiable state (status: {current_status}). Not updating.")

        # Set to COMPLETED if last episode and the option is enabled
        if file_progress == total_episodes and (
            (current_status == "CURRENT" and self.options["SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT"])
            or (current_status == "REPEATING" and self.options["SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING"])
        ):
            status_to_set = "COMPLETED"

        query = AniListQueries.SAVE_MEDIA_LIST_ENTRY

        variables = {"mediaId": anime_id, "progress": file_progress}
        if status_to_set:
            variables["status"] = status_to_set

        response = self.api_client.make_api_request(query, variables, self.access_token)
        if response and "data" in response:
            updated_progress = response["data"]["SaveMediaListEntry"]["progress"]
            osd_message(f'Updated "{anime_name}" to: {updated_progress}')
            print(f"Episode count updated successfully! New progress: {updated_progress}")
            updated_status = response["data"]["SaveMediaListEntry"]["status"]

            return AnimeInfo(anime_id, anime_name, updated_progress, total_episodes, file_progress, updated_status)
        print("Failed to update episode count.")
        raise Exception("Failed to update episode count.")

    def add_anime_to_list(
        self, anime_id: int, anime_name: str, initial_status: str = "PLANNING", initial_progress: int = 0
    ) -> bool:
        """
        Add an anime to the user's AniList.

        Args:
            anime_id (int): AniList anime ID.
            anime_name (str): Anime title for logging.
            initial_status (str): Initial status to set (default: 'PLANNING').
            initial_progress (int): Initial progress to set (default: 0).

        Returns:
            bool: True if successfully added, False otherwise.
        """
        try:
            query = AniListQueries.SAVE_MEDIA_LIST_ENTRY
            variables = {"mediaId": anime_id, "status": initial_status, "progress": initial_progress}

            response = self.api_client.make_api_request(query, variables, self.access_token)

            if response and "data" in response and response["data"]["SaveMediaListEntry"]:
                return True
            print(f'Failed to add "{anime_name}" to your list.')
            return False
        except Exception as e:
            print(f'Error adding "{anime_name}" to list: {e}')
            return False
