"""
mpv-anilist-updater: Automatically updates your AniList based on the file you just watched in MPV.

This script parses anime filenames, determines the correct AniList entry, and updates your progress
or status accordingly.

Supported actions:
- update: Normal update with caching
- launch: Open AniList page for the anime
"""

# Configuration options for anilistUpdater (set in anilistUpdater.conf):
#
# DIRECTORIES: List or comma/semicolon-separated string. The directories the script will work on. Leaving it empty will make it work on every video you watch with mpv. Example: DIRECTORIES = ["D:/Torrents", "D:/Anime"]
#
# UPDATE_PERCENTAGE: Integer (0-100). The percentage of the video you need to watch before it updates AniList automatically. Default is 85 (usually before the ED of a usual episode duration).
#
# SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE: Boolean. If true, when watching episode 1 of a completed anime, set it to rewatching and update progress.
#
# UPDATE_PROGRESS_WHEN_REWATCHING: Boolean. If true, allow updating progress for anime set to rewatching. This is for if you want to set anime to rewatching manually, but still update progress automatically.
#
# SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT: Boolean. If true, set to COMPLETED after last episode if status was CURRENT.
#
# SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING: Boolean. If true, set to COMPLETED after last episode if status was REPEATING (rewatching).

import sys
import os
import webbrowser
import time
import hashlib
import re
import json
import requests
from dataclasses import dataclass
from typing import Optional, TypedDict, Any
from guessit import guessit


# Custom exception hierarchy for AniList updater
class AniListUpdaterError(Exception):
    """Base exception class for all AniList updater related errors."""
    pass


class ParseError(AniListUpdaterError):
    """Raised when filename parsing fails or produces invalid results."""

    def __init__(self, message: str, filename: Optional[str] = None, guess_result: Optional[dict] = None):
        self.filename = filename
        self.guess_result = guess_result
        super().__init__(message)


class MatchAmbiguousError(AniListUpdaterError):
    """Raised when multiple potential anime matches are found and disambiguation is needed."""

    def __init__(self, message: str, search_term: str, matches: Optional[list] = None):
        self.search_term = search_term
        self.matches = matches or []
        super().__init__(message)


class NotInListError(AniListUpdaterError):
    """Raised when the anime is not found in the user's AniList."""

    def __init__(self, message: str, anime_name: str, in_list_search: bool = True):
        self.anime_name = anime_name
        self.in_list_search = in_list_search
        super().__init__(message)


class ApiError(AniListUpdaterError):
    """Raised when AniList API requests fail or return unexpected responses."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None, query: Optional[str] = None, variables: Optional[dict] = None):
        self.status_code = status_code
        self.response_text = response_text
        self.query = query
        self.variables = variables
        super().__init__(message)


@dataclass
class TokenInfo:
    """Container for AniList authentication information."""
    user_id: Optional[int]
    access_token: Optional[str]


@dataclass
class FileInfo:
    """Container for parsed filename information."""
    name: str
    episode: int
    year: str


@dataclass
class AnimeInfo:
    """Container for anime information from AniList API."""
    anime_id: Optional[int]
    anime_name: Optional[str]
    current_progress: Optional[int]
    total_episodes: Optional[int]
    file_progress: int
    current_status: Optional[str]


@dataclass
class SeasonEpisodeInfo:
    """Container for season and episode information for absolute numbering."""
    season_id: Optional[int]
    season_title: Optional[str]
    progress: Optional[int]
    episodes: Optional[int]
    relative_episode: Optional[int]


class CacheEntry(TypedDict):
    """Type definition for cache entry structure."""
    guessed_name: str
    anime_id: Optional[int]
    current_progress: Optional[int]
    total_episodes: Optional[int]
    current_status: Optional[str]
    ttl: float


class GraphQLQueries:
    """Centralized GraphQL queries for AniList API."""

    # Query to get the authenticated user's ID
    GET_VIEWER_ID = '''
        query {
            Viewer {
                id
            }
        }
    '''

    # Query to search for anime with optional filters
    # Variables: search (String), year (FuzzyDateInt), page (Int), onList (Boolean)
    SEARCH_ANIME = '''
        query($search: String, $year: FuzzyDateInt, $page: Int, $onList: Boolean) {
            Page(page: $page) {
                media (search: $search, type: ANIME, startDate_greater: $year, onList: $onList) {
                    id
                    title { romaji }
                    season
                    seasonYear
                    episodes
                    duration
                    format
                    status
                    mediaListEntry {
                        status
                        progress
                        media {
                            episodes
                        }
                    }
                }
            }
        }
    '''

    # Mutation to update user's anime list entry (progress and/or status)
    # Variables: mediaId (Int), progress (Int), status (MediaListStatus)
    UPDATE_MEDIA_LIST_ENTRY = '''
        mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
            SaveMediaListEntry (mediaId: $mediaId, progress: $progress, status: $status) {
                status
                id
                progress
            }
        }
    '''

class AniListUpdater:
    """
    Handles AniList authentication, file parsing, API requests, and updating anime progress/status.
    """
    ANILIST_API_URL = 'https://graphql.anilist.co'
    TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'anilistToken.txt')
    CACHE_PATH = os.path.join(os.path.dirname(__file__), 'cache.json')
    OPTIONS = "--excludes country --excludes language --type episode"
    CACHE_REFRESH_RATE =  24 * 60 * 60

    # Load token
    def __init__(self, options, action):
        """
        Initializes the AniListUpdater, loading the access token.
        """
        token_info = self.load_access_token()
        self.access_token = token_info.access_token
        self.options = options
        self.ACTION = action
        self._cache = None

    # Load token from anilistToken.txt
    def load_access_token(self) -> TokenInfo:
        """
        Loads access token in a single file read.
        Token file formats supported:
          - token_only
          - user_id:token (legacy - user_id will be removed)
          (legacy cache lines with ';;' are also cleaned up if found)
        Returns:
            TokenInfo: Container with access_token (user_id always None since it's not used)
        """
        try:
            if not os.path.exists(self.TOKEN_PATH):
                return TokenInfo(user_id=None, access_token=None)
            with open(self.TOKEN_PATH, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            if not lines:
                return TokenInfo(user_id=None, access_token=None)

            # Check for legacy formats and clean them up if found
            has_legacy_cache = any(';;' in ln for ln in lines)
            has_legacy_user_id = ':' in lines[0] and lines[0].split(':', 1)[0].isdigit()

            if has_legacy_cache or has_legacy_user_id:
                self._cleanup_legacy_formats(lines, has_legacy_user_id)

            header = lines[0].strip()
            token = None
            if ':' in header:
                left, right = header.split(':', 1)
                if left.isdigit():
                    # Legacy user_id:token format
                    token = right.strip()
                else:
                    token = header.strip()
            else:
                token = header.strip()
            if token == '':
                token = None
            return TokenInfo(user_id=None, access_token=token)
        except Exception as e:
            print(f'Error reading access token: {e}')
            return TokenInfo(user_id=None, access_token=None)


    # Load user id from file, if not then make api request and save it.
    def get_user_id(self):
        """
        Loads the AniList user ID from the token file, or fetches and caches it if not present.
        Returns:
            int or None: The user ID, or None if not found.
        """
        if getattr(self, 'user_id', None) is not None:
            return self.user_id
        if not self.access_token:
            return None

        try:
            response = self.make_api_request(GraphQLQueries.GET_VIEWER_ID, None, self.access_token)
            if response and 'data' in response:
                self.user_id = response['data']['Viewer']['id']
                self.save_user_id(self.user_id)
                return self.user_id
        except ApiError as e:
            print(f'Failed to get user ID: {e}')
            return None
        return None

    def _cleanup_legacy_formats(self, lines, has_legacy_user_id):
        """
        Removes legacy cache entries and user_id from token file using already-read lines.
        Args:
            lines (list): The lines already read from the token file.
            has_legacy_user_id (bool): Whether the first line has user_id:token format.
        """
        try:
            header = lines[0] if lines else ''

            # Extract just the token if it's in user_id:token format
            if has_legacy_user_id and ':' in header:
                token = header.split(':', 1)[1].strip()
            else:
                token = header.strip()

            # Rewrite token file with just the token, removing user_id and cache lines
            with open(self.TOKEN_PATH, 'w', encoding='utf-8') as f:
                f.write(token + ('\n' if token else ''))

            if has_legacy_user_id:
                print('Cleaned up legacy user_id from token file.')
            if any(';;' in ln for ln in lines):
                print('Cleaned up legacy cache entries from token file.')
        except Exception as e:
            print(f'Legacy format cleanup failed: {e}')


    def cache_to_file(self, path: str, guessed_name: str, result: Optional[AnimeInfo]) -> None:
        """
        Stores/updates a structured cache entry in cache.json.
        Cache schema: hash -> { guessed_name, anime_id, current_progress, total_episodes, current_status, ttl }
        ttl is an absolute epoch time (expiry moment).
        Args:
            path: The file path.
            guessed_name: The guessed anime name.
            result: The AnimeInfo to cache.
        """
        try:
            dir_hash = self.hash_path(os.path.dirname(path))
            cache = self.load_cache()
            if result is not None:
                now = time.time()
                cache_entry: CacheEntry = {
                    'guessed_name': guessed_name,
                    'anime_id': result.anime_id,
                    'current_progress': result.current_progress,
                    'total_episodes': result.total_episodes,
                    'current_status': result.current_status,
                    'ttl': now + self.CACHE_REFRESH_RATE
                }
                cache[dir_hash] = cache_entry
                self.save_cache(cache)
        except Exception as e:
            print(f'Error trying to cache {result}: {e}')

    def hash_path(self, path):
        """
        Returns a SHA256 hash of the given path.
        Args:
            path (str): The path to hash.
        Returns:
            str: The hashed path.
        """
        return hashlib.sha256(path.encode('utf-8')).hexdigest()

    def check_and_clean_cache(self, path: str, guessed_name: str) -> Optional[CacheEntry]:
        """
        Returns structured cache entry if valid. Cleans expired entries.
        Args:
            path: The path to the media file.
            guessed_name: The guessed name of the anime.
        Returns:
            CacheEntry or None: Valid cache entry or None if not found/expired.
        """
        try:
            cache = self.load_cache()
            now = time.time()
            changed = False
            # Purge expired
            for k, v in list(cache.items()):
                if v.get('ttl', 0) < now:
                    cache.pop(k, None)
                    changed = True
            if changed:
                self.save_cache(cache)

            dir_hash = self.hash_path(os.path.dirname(path))
            entry = cache.get(dir_hash)
            if entry and entry.get('guessed_name') == guessed_name and entry.get('ttl', 0) >= now:
                return entry
            return None
        except Exception as e:
            print(f'Error trying to read cache file: {e}')
            return None


    def load_cache(self):
        """
        Loads the cache from the CACHE_PATH JSON file with lazy loading.
        Returns the cached data if already loaded, otherwise loads from file.
        Returns an empty dictionary if the file does not exist or an error occurs.
        """
        if self._cache is None:
            try:
                if not os.path.exists(self.CACHE_PATH):
                    self._cache = {}
                else:
                    with open(self.CACHE_PATH, 'r', encoding='utf-8') as f:
                        self._cache = json.load(f)
            except Exception:
                self._cache = {}
        return self._cache

    def save_cache(self, cache):
        """
        Saves the cache dictionary to the CACHE_PATH JSON file and updates the local cache.
        Args:
            cache (dict): The cache data to save.
        """
        try:
            with open(self.CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            # Keep local cache in sync
            self._cache = cache
        except Exception as e:
            print(f'Failed saving cache.json: {e}')

    # Function to make an api request to AniList's api
    def make_api_request(self, query, variables=None, access_token=None):
        """
        Makes a POST request to the AniList GraphQL API.
        Args:
            query (str): The GraphQL query string.
            variables (dict, optional): Variables for the query.
            access_token (str, optional): AniList access token.
        Returns:
            dict or None: The API response as a dict, or None on error.
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'

        response = requests.post(self.ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers, timeout=10)
        # print(f"Made an API Query with: Query: {query}\nVariables: {variables} ")
        if response.status_code == 200:
            return response.json()

        error_msg = f'API request failed: {response.status_code} - {response.text}'
        raise ApiError(error_msg, status_code=response.status_code, response_text=response.text, query=query, variables=variables)

    @staticmethod
    def season_order(season):
        """
        Returns a numeric order for seasons for sorting.
        Args:
            season (str): The season name (WINTER, SPRING, SUMMER, FALL).
        Returns:
            int: The order value.
        """
        return {'WINTER': 1, 'SPRING': 2, 'SUMMER': 3, 'FALL': 4}.get(season, 5)

    def filter_valid_seasons(self, seasons):
        """
        Filters and sorts valid TV seasons for absolute numbering logic.
        Args:
            seasons (list): List of season dicts from AniList API.
        Returns:
            list: Filtered and sorted list of seasons.
        """
        # Filter only to those whose format is TV and duration > 21 OR those who have no duration and are releasing.
        # This is due to newly added anime having duration as null
        seasons = [
                    season for season in seasons
                if ((season['duration'] is None and season['status'] == 'RELEASING') or
                   (season['duration'] is not None and season['duration'] > 21)) and season['format'] == 'TV'
                ]
                # One of the problems with this filter is needing the format to be 'TV'
                # But if accepted any format, it would also include many ONA's which arent included in absolute numbering.

                # Sort them based on release date
        seasons = sorted(seasons, key=lambda x: (x['seasonYear'] if x['seasonYear'] else float("inf"), self.season_order(x['season'] if x['season'] else float("inf"))))
        return seasons

    # Finds the season and episode of an anime with absolute numbering
    def find_season_and_episode(self, seasons: list, absolute_episode: int) -> SeasonEpisodeInfo:
        """
        Finds the correct season and relative episode for an absolute episode number.
        Args:
            seasons: List of season dicts.
            absolute_episode: The absolute episode number.
        Returns:
            SeasonEpisodeInfo: Container with season information and relative episode.
        """
        accumulated_episodes = 0
        for season in seasons:
            season_episodes = season.get('episodes', 12) if season.get('episodes') else 12

            if accumulated_episodes + season_episodes >= absolute_episode:
                return SeasonEpisodeInfo(
                    season_id=season.get('id'),
                    season_title=season.get('title', {}).get('romaji'),
                    progress=season.get('mediaListEntry', {}).get('progress') if season.get('mediaListEntry') else None,
                    episodes=season.get('episodes'),
                    relative_episode=absolute_episode - accumulated_episodes
                )
            accumulated_episodes += season_episodes
        return SeasonEpisodeInfo(
            season_id=None,
            season_title=None,
            progress=None,
            episodes=None,
            relative_episode=None
        )

    def handle_filename(self, filename: str) -> None:
        """
        Main entry point for handling a file: parses, checks cache, updates AniList, and manages cache.
        Args:
            filename: The path to the video file.
        """
        try:
            file_info = self.parse_filename(filename)
        except ParseError:
            # Re-raise ParseError to be handled by main()
            raise

        cache_entry = self.check_and_clean_cache(filename, file_info.name)

        # If launching and cache has anime_id, we can skip search and open directly.
        if self.ACTION == 'launch' and cache_entry and cache_entry.get('anime_id'):
            anime_id = cache_entry['anime_id']
            print(f'Opening AniList (cached) for guessed "{file_info.name}": https://anilist.co/anime/{anime_id}')
            webbrowser.open_new_tab(f'https://anilist.co/anime/{anime_id}')
            return

        # Use cached data if available, otherwise fetch fresh info
        if cache_entry:
            # Reconstruct AnimeInfo from cache
            result = AnimeInfo(
                anime_id=cache_entry['anime_id'],
                anime_name=cache_entry['guessed_name'],
                current_progress=cache_entry['current_progress'],
                total_episodes=cache_entry['total_episodes'],
                file_progress=file_info.episode,
                current_status=cache_entry['current_status']
            )
            print(f'Using cached data for "{file_info.name}"')
        else:
            result = self.get_anime_info_and_progress(file_info.name, file_info.episode, file_info.year)

        updated_result = self.update_episode_count(result)

        if updated_result and updated_result.current_progress is not None:
            # Update cache with latest data
            self.cache_to_file(filename, file_info.name, updated_result)
        return

    # Hardcoded exceptions to fix detection
    # Easier than just renaming my files 1 by 1 on Qbit
    # Every exception I find will be added here
    def fix_filename(self, path_parts):
        """
        Applies hardcoded exceptions and fixes to the filename and folder structure for better title detection.
        Args:
            path_parts (list): List of path components.
        Returns:
            list: Modified path components.
        """
        guess = guessit(path_parts[-1], self.OPTIONS) # Simply easier for fixing the filename if we have what it is detecting.

        path_parts[-1] = os.path.splitext(path_parts[-1])[0]
        pattern = r'[\\\/:!\*\?"<>\|\._-]'

        title_depth = -1

        # Fix from folders if the everything is not in the filename
        if 'title' not in guess:
            # Depth=2
            for depth in range(2, min(4, len(path_parts))):
                folder_guess = guessit(path_parts[-depth], self.OPTIONS)
                if 'title' in folder_guess:
                    guess['title'] = folder_guess['title']
                    title_depth = -depth
                    break

        if 'title' not in guess:
            raise ParseError(f"Couldn't find title in filename '{path_parts[-1]}'! Guess result: {guess}", filename=path_parts[-1], guess_result=dict(guess))

        # Only clean up titles for some series
        cleanup_titles = ['Ranma', 'Chi', 'Bleach', 'Link Click']
        if any(title in guess['title'] for title in cleanup_titles):
            path_parts[title_depth] = re.sub(pattern, ' ', path_parts[title_depth])
            path_parts[title_depth] = " ".join(path_parts[title_depth].split())

        if 'Centimeters per Second' == guess['title'] and 5 == guess.get('episode', 0):
            path_parts[title_depth] = path_parts[title_depth].replace(' 5 ', ' Five ')
            # For some reason AniList has this film in 3 parts.
            path_parts[title_depth] = path_parts[title_depth].replace('per Second', 'per Second 3')

        # Remove 'v2', 'v3'... from the title since it fucks up with episode detection
        match = re.search(r'(E\d+)v\d', path_parts[title_depth])
        if match:
            episode = match.group(1)
            path_parts[title_depth] = path_parts[title_depth].replace(match.group(0), episode)

        return path_parts

    # Parse the file name using guessit
    def parse_filename(self, filepath: str) -> FileInfo:
        """
        Parses the filename and folder structure to extract anime title, episode, season, and year.
        Args:
            filepath: The path to the video file.
        Returns:
            FileInfo: Parsed info with name, episode, and year.
        """
        path_parts = self.fix_filename(filepath.replace('\\', '/').split('/'))
        filename = path_parts[-1]
        name, season, part, year = '', '', '', ''
        remaining: list[int] = []
        episode = 1
        # First, try to guess from the filename
        guess = guessit(filename, self.OPTIONS)
        print(f'File name guess: {filename} -> {dict(guess)}')

        # Episode guess from the title.
        # Usually, releases are formated [Release Group] Title - S01EX

        # If the episode index is 0, that would mean that the episode is before the title in the filename
        # Which is a horrible way of formatting it, so assume its wrong

        # If its 1, then the title is probably 0, so its okay. (Unless season is 0)
        # Really? What is the format "S1E1 - {title}"? That's almost psycopathic.

        # If its >2, theres probably a Release Group and Title / Season / Part, so its good

        episode = guess.get('episode', None)
        season = guess.get('season', '')
        part = str(guess.get('part', ''))
        year = str(guess.get('year', ''))

        # Quick fixes assuming season before episode
        # 'episode_title': '02' in 'S2 02'
        if guess.get('episode_title', '').isdigit() and episode is None:
            print(f'Detected episode in episode_title. Episode: {int(guess.get("episode_title"))}')
            episode = int(guess.get('episode_title'))

        # 'episode': [86, 13] (EIGHTY-SIX), [1, 2, 3] (RANMA) lol.
        if isinstance(episode, list):
            print(f'Detected multiple episodes: {episode}. Picking last one.')
            remaining = episode[:-1]
            episode = episode[-1]

        # 'season': [2, 3] in "S2 03"
        if isinstance(season, list):
            print(f'Detected multiple seasons: {season}. Picking first one as season.')
            if episode is None:
                print('Episode still not detected. Picking last position of the season list.')
                episode = season[-1]

            season = season[0]

        episode = episode or 1
        season = str(season)

        keys = list(guess.keys())
        episode_index = keys.index('episode') if 'episode' in guess else 1
        season_index = keys.index('season') if 'season' in guess else -1
        title_in_filename = 'title' in guess and (episode_index > 0 and (season_index > 0 or season_index == -1))

        # If the title is not in the filename or episode index is 0, try the folder name
        # If the episode index > 0 and season index > 0, its safe to assume that the title is in the file name

        if title_in_filename:
            name = guess['title']
        else:
            # If it isnt in the name of the file, try to guess using the name of the folder it is stored in

            # Depth=2 folders
            for depth in [2, 3]:
                if len(path_parts) > depth-1:
                    folder_guess = guessit(path_parts[-depth], self.OPTIONS)
                    if folder_guess:
                        print(f'{depth-1}{"st" if depth-1==1 else "nd"} Folder guess:\n{path_parts[-depth]} -> {dict(folder_guess)}')

                        name = str(folder_guess.get('title', ''))
                        season = season or str(folder_guess.get('season', ''))
                        part = part or str(folder_guess.get('part', ''))
                        year = year or str(folder_guess.get('year', ''))

                        # If we got the name, its probable we already got season and part from the way folders are usually structured
                        if name != '':
                            break

        # Haven't tested enough but seems to work fine
        if remaining:
            # If there are remaining episodes, append them to the name
            name += ' ' + ' '.join(str(ep) for ep in remaining)

        # Add season and part if there are
        if season and (int(season) > 1 or part):
            name += f" Season {season}"

        if part:
            name += f" Part {part}"

        print('Guessed name: ' + name)
        return FileInfo(
            name=name,
            episode=episode,
            year=year
        )

    def get_anime_info_and_progress(self, name: str, file_progress: int, year: str) -> AnimeInfo:
        """
        Queries AniList for anime info and user progress for a given title and year.
        Args:
            name: Anime title.
            file_progress: Episode number from the file.
            year: Year string (may be empty).
        Returns:
            AnimeInfo: Container with anime information and progress.
        """

        # Only those that are in the user's list
        variables = {'search': name, 'year': year or 1, 'page': 1, 'onList': True}

        try:
            response = self.make_api_request(GraphQLQueries.SEARCH_ANIME, variables, self.access_token)
        except ApiError:
            return AnimeInfo(
                anime_id=None,
                anime_name=None,
                current_progress=None,
                total_episodes=None,
                file_progress=file_progress,
                current_status=None
            )

        if not response or 'data' not in response:
            return AnimeInfo(
                anime_id=None,
                anime_name=None,
                current_progress=None,
                total_episodes=None,
                file_progress=file_progress,
                current_status=None
            )

        seasons = response['data']['Page']['media']

        # No results from the API request
        if not seasons:
            # Before erroring, if its a "launch" request we can search even if its not in the user list
            if self.ACTION == 'launch':
                variables['onList'] = False
                try:
                    response = self.make_api_request(GraphQLQueries.SEARCH_ANIME, variables, self.access_token)
                except ApiError:
                    return AnimeInfo(
                        anime_id=None,
                        anime_name=None,
                        current_progress=None,
                        total_episodes=None,
                        file_progress=file_progress,
                        current_status=None
                    )

                if not response or 'data' not in response:
                    return AnimeInfo(
                        anime_id=None,
                        anime_name=None,
                        current_progress=None,
                        total_episodes=None,
                        file_progress=file_progress,
                        current_status=None
                    )

                seasons = response['data']['Page']['media']
                # If its still empty
                if not seasons:
                    raise NotInListError(f"Couldn't find an anime from this title! ({name})", anime_name=name, in_list_search=False)
            else:
                raise NotInListError(f"Couldn't find an anime from this title! ({name}). Is it in your list?", anime_name=name, in_list_search=True)

        # This is the first element, which is the same as Media(search: $search)
        entry = seasons[0]['mediaListEntry']
        anime_data = AnimeInfo(
            anime_id=seasons[0]['id'],
            anime_name=seasons[0]['title']['romaji'],
            current_progress=entry['progress'] if entry is not None else None,
            total_episodes=seasons[0]['episodes'],
            file_progress=file_progress,
            current_status=entry['status'] if entry is not None else None
        )

        # If the episode in the file name is larger than the total amount of episodes
        # Then they are using absolute numbering format for episodes
        # Try to guess season and episode.
        if seasons[0]['episodes'] is not None and file_progress > seasons[0]['episodes']:
            seasons = self.filter_valid_seasons(seasons)
            print('Related shows:', ", ".join(season["title"]["romaji"] for season in seasons))
            season_info = self.find_season_and_episode(seasons, file_progress)
            print(season_info)
            found_season = next((season for season in seasons if season['id'] == season_info.season_id), None)
            found_entry = found_season['mediaListEntry'] if found_season and found_season['mediaListEntry'] else None
            anime_data = AnimeInfo(
                anime_id=season_info.season_id,
                anime_name=season_info.season_title,
                current_progress=season_info.progress,
                total_episodes=season_info.episodes,
                file_progress=season_info.relative_episode or file_progress,
                current_status=found_entry['status'] if found_entry else None
            )
            print(f"Final guessed anime: {found_season}")
            print(f'Absolute episode {file_progress} corresponds to Anime: {anime_data.anime_name}, Episode: {anime_data.file_progress}')
        else:
            print(f"Final guessed anime: {seasons[0]}")
        return anime_data

    # Update the anime based on file progress
    def update_episode_count(self, result: Optional[AnimeInfo]) -> Optional[AnimeInfo]:
        """
        Updates the episode count and/or status for an anime entry on AniList, according to user settings.
        Args:
            result: AnimeInfo container with anime information.
        Returns:
            AnimeInfo or None: Updated anime info, or None on failure.
        """
        if result is None:
            raise ValueError('Parameter in update_episode_count is null.')

        anime_id = result.anime_id
        anime_name = result.anime_name
        current_progress = result.current_progress
        total_episodes = result.total_episodes
        file_progress = result.file_progress
        current_status = result.current_status

        if anime_id is None:
            raise NotInListError('Couldn\'t find that anime! Make sure it is on your list and the title is correct.', anime_name=anime_name or "Unknown")

        # Only launch anilist
        if self.ACTION == 'launch':
            print(f'Opening AniList for "{anime_name}": https://anilist.co/anime/{anime_id}')
            webbrowser.open_new_tab(f'https://anilist.co/anime/{anime_id}')
            return result

        if current_progress is None:
            raise NotInListError('Failed to get current episode count. Is it on your list?', anime_name=anime_name or "Unknown")

        # Handle completed -> rewatching on first episode
        if (current_status == 'COMPLETED' and file_progress == 1 and self.options['SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE']):

            # Needs to update in 2 steps, since AniList
            # doesn't allow setting progress while changing the status from completed to rewatching.
            # If you try, it will just reset the progress to 0.
            print('Setting status to REPEATING (rewatching) and updating progress for first episode of completed anime.')

            # Step 1: Set to REPEATING, progress=0
            variables = {'mediaId': anime_id, 'progress': 0, 'status': 'REPEATING'}
            try:
                response = self.make_api_request(GraphQLQueries.UPDATE_MEDIA_LIST_ENTRY, variables, self.access_token)

                # Step 2: Set progress to 1
                variables = {'mediaId': anime_id, 'progress': 1}
                response = self.make_api_request(GraphQLQueries.UPDATE_MEDIA_LIST_ENTRY, variables, self.access_token)

                if response and 'data' in response:
                    updated_progress = response['data']['SaveMediaListEntry']['progress']
                    print(f'Episode count updated successfully! New progress: {updated_progress}')

                    return AnimeInfo(
                        anime_id=anime_id,
                        anime_name=anime_name,
                        current_progress=updated_progress,
                        total_episodes=total_episodes,
                        file_progress=1,
                        current_status='REPEATING'
                    )
            except ApiError as e:
                print(f'Failed to update episode count: {e}')
                return None

            return None

        # Handle updating progress for rewatching
        if (current_status == 'REPEATING' and self.options['UPDATE_PROGRESS_WHEN_REWATCHING']):
            print('Updating progress for anime set to REPEATING (rewatching).')
            status_to_set = 'REPEATING'

        # Only update if status is CURRENT or PLANNING
        elif current_status in ['CURRENT', 'PLANNING']:

            # If its lower than the current progress, dont update.
            if file_progress <= current_progress:
                raise ValueError(f'Episode was not new. Not updating ({file_progress} <= {current_progress})')

            status_to_set = 'CURRENT'

        else:
            raise ValueError(f'Anime is not in a modifiable state (status: {current_status}). Not updating.')

        # Set to COMPLETED if last episode and the option is enabled
        if file_progress == total_episodes:
            if (current_status == 'CURRENT' and self.options['SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT']) or (current_status == 'REPEATING' and self.options['SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING']):
                status_to_set = "COMPLETED"

        variables_dict: dict[str, Any] = {'mediaId': anime_id, 'progress': file_progress}
        if status_to_set:
            variables_dict['status'] = status_to_set

        try:
            response = self.make_api_request(GraphQLQueries.UPDATE_MEDIA_LIST_ENTRY, variables_dict, self.access_token)
            if response and 'data' in response:
                updated_progress = response['data']['SaveMediaListEntry']['progress']
                print(f'Episode count updated successfully! New progress: {updated_progress}')
                updated_status = response['data']['SaveMediaListEntry']['status']

                return AnimeInfo(
                    anime_id=anime_id,
                    anime_name=anime_name,
                    current_progress=updated_progress,
                    total_episodes=total_episodes,
                    file_progress=file_progress,
                    current_status=updated_status
                )
        except ApiError as e:
            print(f'Failed to update episode count: {e}')
            return None
        print('Failed to update episode count.')
        return None

def main():
    """
    Main entry point for the script. Handles encoding and runs the updater.
    """
    try:
        # Reconfigure to utf-8
        if sys.stdout.encoding != 'utf-8':
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception as e_reconfigure:
                print(f"Couldn\'t reconfigure stdout/stderr to UTF-8: {e_reconfigure}", file=sys.stderr)

        # Parse options from argv[3] if present
        options = {
            "SET_COMPLETED_TO_REWATCHING_ON_FIRST_EPISODE": False,
            "UPDATE_PROGRESS_WHEN_REWATCHING": True,
            "SET_TO_COMPLETED_AFTER_LAST_EPISODE_CURRENT": False,
            "SET_TO_COMPLETED_AFTER_LAST_EPISODE_REWATCHING": True
        }
        if len(sys.argv) > 3:
            user_options = json.loads(sys.argv[3])
            options.update(user_options)

        # Pass options to AniListUpdater
        updater = AniListUpdater(options, sys.argv[2])
        updater.handle_filename(sys.argv[1])

    except ParseError as e:
        print(f'PARSE ERROR: {e}')
        if e.filename:
            print(f'Problematic filename: {e.filename}')
        if e.guess_result:
            print(f'Guess result: {e.guess_result}')
        sys.exit(1)
    except NotInListError as e:
        print(f'NOT IN LIST ERROR: {e}')
        print(f'Anime: {e.anime_name}')
        if e.in_list_search:
            print('Suggestion: Add the anime to your AniList or check the title spelling.')
        else:
            print('Suggestion: The anime was not found even in general search.')
        sys.exit(1)
    except MatchAmbiguousError as e:
        print(f'AMBIGUOUS MATCH ERROR: {e}')
        print(f'Search term: {e.search_term}')
        if e.matches:
            print(f'Potential matches: {e.matches}')
        sys.exit(1)
    except ApiError as e:
        print(f'API ERROR: {e}')
        if e.status_code:
            print(f'Status code: {e.status_code}')
        if e.response_text:
            print(f'Response: {e.response_text}')
        sys.exit(1)
    except AniListUpdaterError as e:
        print(f'ANILIST UPDATER ERROR: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'UNEXPECTED ERROR: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
