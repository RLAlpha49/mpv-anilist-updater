"""Data classes for anime information and file data."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SeasonEpisodeInfo:
    """Season and episode info for absolute numbering."""

    season_id: Optional[int]
    season_title: Optional[str]
    progress: Optional[int]
    episodes: Optional[int]
    relative_episode: Optional[int]


@dataclass
class AnimeInfo:
    """Anime information including progress and status."""

    anime_id: Optional[int]
    anime_name: Optional[str]
    current_progress: Optional[int]
    total_episodes: Optional[int]
    file_progress: Optional[int]
    current_status: Optional[str]

    # Can not specify the type further. Causes some of the the variables type checking to be unhappy.
    def __iter__(self) -> Iterator[Any]:  # fmt: off
        """Allow tuple unpacking of AnimeInfo."""
        return iter((self.anime_id, self.anime_name, self.current_progress, self.total_episodes, self.file_progress, self.current_status))  # fmt: off


@dataclass
class FileInfo:
    """Parsed filename information."""

    name: str
    episode: int
    year: str
