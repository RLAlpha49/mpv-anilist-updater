"""Filename parsing and GuessIt logic."""

import os
import re

from guessit import guessit  # type: ignore

from .data_classes import FileInfo


class FilenameParser:
    """Handles filename parsing and GuessIt operations."""

    OPTIONS: str = "--excludes country --excludes language --type episode"

    def fix_filename(self, path_parts: list[str]) -> list[str]:
        """
        Apply hardcoded fixes to filename/folder structure for better detection.

        Args:
            path_parts (list[str]): Path components.

        Returns:
            list[str]: Modified path components.
        """
        # Simply easier for fixing the filename if we have what it is detecting.
        guess = guessit(path_parts[-1], self.OPTIONS)

        path_parts[-1] = os.path.splitext(path_parts[-1])[0]
        pattern = r'[\\\/:!\*\?"<>\|\._-]'

        title_depth = -1

        # Fix from folders if the everything is not in the filename
        if "title" not in guess:
            for depth in range(2, min(4, len(path_parts))):
                folder_guess = guessit(path_parts[-depth], self.OPTIONS)
                if "title" in folder_guess:
                    guess["title"] = folder_guess["title"]
                    title_depth = -depth
                    break

        if "title" not in guess:
            print(f"Couldn't find title in filename '{path_parts[-1]}'! Guess result: {guess}")
            return path_parts

        # Only clean up titles for some series
        cleanup_titles = ["Ranma", "Chi", "Bleach", "Link Click"]
        if any(title in guess["title"] for title in cleanup_titles):
            path_parts[title_depth] = re.sub(pattern, " ", path_parts[title_depth])
            path_parts[title_depth] = " ".join(path_parts[title_depth].split())

        if guess["title"] == "Centimeters per Second" and guess.get("episode", 0) == 5:
            path_parts[title_depth] = path_parts[title_depth].replace(" 5 ", " Five ")
            # For some reason AniList has this film in 3 parts.
            path_parts[title_depth] = path_parts[title_depth].replace("per Second", "per Second 3")

        # Remove 'v2', 'v3'... from the title since it fucks up with episode detection
        match = re.search(r"(E\d+)v\d", path_parts[title_depth])
        if match:
            episode = match.group(1)
            path_parts[title_depth] = path_parts[title_depth].replace(match.group(0), episode)

        return path_parts

    def parse_filename(self, filepath: str) -> FileInfo:
        """
        Parse filename/folder structure to extract anime info.

        Args:
            filepath (str): Path to video file.

        Returns:
            FileInfo: Parsed info with name, episode, year.
        """
        path_parts = self.fix_filename(filepath.replace("\\", "/").split("/"))
        filename = path_parts[-1]
        name, season, part, year = "", "", "", ""
        remaining: list[int] = []
        episode = 1
        # First, try to guess from the filename
        guess = guessit(filename, self.OPTIONS)
        print(f"File name guess: {filename} -> {dict(guess)}")

        # Episode guess from the title.
        # Usually, releases are formated [Release Group] Title - S01EX

        # If the episode index is 0, that would mean that the episode is before the title in the filename
        # Which is a horrible way of formatting it, so assume its wrong

        # If its 1, then the title is probably 0, so its okay. (Unless season is 0)
        # Really? What is the format "S1E1 - {title}"? That's almost psycopathic.

        # If its >2, theres probably a Release Group and Title / Season / Part, so its good

        episode = guess.get("episode", None)
        season = guess.get("season", "")
        part = str(guess.get("part", ""))
        year = str(guess.get("year", ""))

        # Quick fixes assuming season before episode
        # 'episode_title': '02' in 'S2 02'
        if guess.get("episode_title", "").isdigit() and "episode" not in guess:
            print(f"Detected episode in episode_title. Episode: {int(guess.get('episode_title'))}")
            episode = int(guess.get("episode_title"))

        # 'episode': [86, 13] (EIGHTY-SIX), [1, 2, 3] (RANMA) lol.
        if isinstance(episode, list):
            print(f"Detected multiple episodes: {episode}. Picking last one.")
            remaining = episode[:-1]
            episode = episode[-1]

        # 'season': [2, 3] in "S2 03"
        if isinstance(season, list):
            print(f"Detected multiple seasons: {season}. Picking first one as season.")
            # If episode wasn't detected or is default, try to extract from season list
            if episode is None and len(season) > 1:
                print("Episode not detected. Picking last position of the season list.")
                episode = season[-1]

            season = season[0]

        # Ensure episode is never None
        episode = episode or 1

        season = str(season)

        keys = list(guess.keys())
        episode_index = keys.index("episode") if "episode" in guess else 1
        season_index = keys.index("season") if "season" in guess else -1
        title_in_filename = "title" in guess and (episode_index > 0 and (season_index > 0 or season_index == -1))

        # If the title is not in the filename or episode index is 0, try the folder name
        # If the episode index > 0 and season index > 0, its safe to assume that the title is in the file name

        if title_in_filename:
            name = guess["title"]
        else:
            # If it isnt in the name of the file, try to guess using the name of the folder it is stored in

            # Depth=2 folders
            for depth in [2, 3]:
                folder_guess = guessit(path_parts[-depth], self.OPTIONS) if len(path_parts) > depth - 1 else None
                if folder_guess:
                    print(
                        f"{depth - 1}{'st' if depth - 1 == 1 else 'nd'} Folder guess:\n{path_parts[-depth]} -> {dict(folder_guess)}"
                    )

                    name = str(folder_guess.get("title", ""))
                    season = season or str(folder_guess.get("season", ""))
                    part = part or str(folder_guess.get("part", ""))
                    year = year or str(folder_guess.get("year", ""))

                    # If we got the name, its probable we already got season and part from the way folders are usually structured
                    if not name:
                        break

        # Haven't tested enough but seems to work fine
        if remaining:
            # If there are remaining episodes, append them to the name
            name += " " + " ".join(str(ep) for ep in remaining)

        # Add season and part if there are
        if season and (int(season) > 1 or part):
            name += f" Season {season}"

        if part:
            name += f" Part {part}"

        print("Guessed name: " + name)
        return FileInfo(name, episode, year)
