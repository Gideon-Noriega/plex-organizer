"""Core organizer logic for moving media files into Plex naming conventions."""

import os
import re
import shutil
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .parser import (
    extract_movie_info,
    extract_tv_info,
    is_video_file,
    is_subtitle_file,
    is_extras,
    get_extension,
)
from .config import Config, get_genre_from_map
from .tmdb import TMDbClient


@dataclass
class MoveOperation:
    """A planned file move operation."""

    source: str
    destination: str
    is_subtitle: bool = False


class PlexOrganizer:
    """Main organizer class that plans and executes file moves."""

    def __init__(self, config: Config):
        self.config = config
        self.tmdb: Optional[TMDbClient] = None
        self.moves: list[MoveOperation] = []
        self.move_log: list[dict] = []

        if config.tmdb_api_key:
            self.tmdb = TMDbClient(config.tmdb_api_key)

    def get_genre(self, title: str, year: Optional[str] = None) -> str:
        """
        Determine genre for a movie title.

        Priority:
        1. Config-based genre map (manual overrides)
        2. TMDb API lookup
        3. Fallback to "Other"
        """
        # Check config genre map first
        if self.config.genre_map:
            genre = get_genre_from_map(title, self.config.genre_map)
            if genre:
                return genre

        # Try TMDb
        if self.tmdb:
            genre = self.tmdb.get_movie_genre(title, year)
            if genre:
                return genre

        return "Other"

    def plan_movies(self, movies_dir: str) -> list[MoveOperation]:
        """
        Plan movie organization moves.

        Scans the movies directory and plans moves into:
        {movies_dir}/{Genre}/{Title} ({Year})/{Title} ({Year}).ext

        Returns list of planned MoveOperation objects.
        """
        self.moves = []

        if not os.path.isdir(movies_dir):
            print(f"Error: Movies directory does not exist: {movies_dir}")
            return self.moves

        entries = sorted(os.listdir(movies_dir))

        for entry in entries:
            full_path = os.path.join(movies_dir, entry)

            # Skip genre folders (already organized)
            if os.path.isdir(full_path) and entry in self.config.genre_folders:
                continue

            # Skip hidden files
            if entry.startswith("."):
                continue

            # Skip extras/featurettes
            if is_extras(entry):
                continue

            # Parse movie info
            info = extract_movie_info(entry, self.config.title_overrides)

            if not info.title:
                continue

            # Find video files
            if os.path.isdir(full_path):
                video_files = []
                subtitle_files = []
                for root, dirs, files in os.walk(full_path):
                    for f in files:
                        filepath = os.path.join(root, f)
                        if is_extras(f):
                            continue
                        if is_video_file(f):
                            video_files.append(filepath)
                        elif is_subtitle_file(f):
                            subtitle_files.append(filepath)

                if not video_files:
                    continue

                # Use the first (or largest) video file
                video_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
                source = video_files[0]
                ext = get_extension(source)
            else:
                if not is_video_file(entry):
                    continue
                source = full_path
                ext = get_extension(entry)
                # Find associated subtitle files
                subtitle_files = self._find_associated_subtitles(
                    movies_dir, entry
                )

            # Build destination path
            genre = self.get_genre(info.title, info.year)
            if info.year:
                folder_name = f"{info.title} ({info.year})"
            else:
                folder_name = info.title

            file_name = f"{folder_name}{ext}"
            dest_dir = os.path.join(movies_dir, genre, folder_name)
            dest_path = os.path.join(dest_dir, file_name)

            # Skip if already in the right place
            if os.path.abspath(source) == os.path.abspath(dest_path):
                continue

            self.moves.append(
                MoveOperation(source=source, destination=dest_path)
            )

            # Plan subtitle moves
            for sub_file in subtitle_files:
                sub_ext = get_extension(sub_file)
                sub_basename = os.path.basename(sub_file)
                # Try to preserve language tag from subtitle filename
                # e.g., Movie.Name.2024.eng.srt -> Movie Name (2024).eng.srt
                lang_match = _extract_lang_tag(sub_basename)
                if lang_match:
                    sub_dest_name = f"{folder_name}.{lang_match}{sub_ext}"
                else:
                    sub_dest_name = f"{folder_name}{sub_ext}"
                sub_dest = os.path.join(dest_dir, sub_dest_name)
                self.moves.append(
                    MoveOperation(
                        source=sub_file, destination=sub_dest, is_subtitle=True
                    )
                )

        return self.moves

    def plan_tv(self, tv_dir: str) -> list[MoveOperation]:
        """
        Plan TV show organization moves.

        Scans the TV directory and plans moves into:
        {tv_dir}/{Show Name} ({Year})/Season {XX}/{episode files}

        Returns list of planned MoveOperation objects.
        """
        self.moves = []

        if not os.path.isdir(tv_dir):
            print(f"Error: TV directory does not exist: {tv_dir}")
            return self.moves

        entries = sorted(os.listdir(tv_dir))

        for entry in entries:
            full_path = os.path.join(tv_dir, entry)

            # Skip hidden files
            if entry.startswith("."):
                continue

            # Check if this entry has a TV override
            if entry in self.config.tv_overrides:
                override = self.config.tv_overrides[entry]
                if isinstance(override, dict):
                    show_name = override.get("name", entry)
                    year = override.get("year")
                    season = override.get("season")
                elif isinstance(override, (list, tuple)) and len(override) >= 3:
                    show_name, year, season = override[0], override[1], override[2]
                else:
                    continue

                if year:
                    show_dir = os.path.join(tv_dir, f"{show_name} ({year})")
                else:
                    show_dir = os.path.join(tv_dir, show_name)

                if season:
                    dest = os.path.join(show_dir, season)
                else:
                    dest = show_dir

                if os.path.isdir(full_path):
                    # Move entire folder contents
                    for root, dirs, files in os.walk(full_path):
                        for f in files:
                            src = os.path.join(root, f)
                            rel = os.path.relpath(src, full_path)
                            dst = os.path.join(dest, rel)
                            self.moves.append(MoveOperation(source=src, destination=dst))
                continue

            # Auto-detect from directory/file names
            if os.path.isdir(full_path):
                info = extract_tv_info(entry)
                if not info.show_name:
                    continue

                # Determine year (from parse or TMDb)
                year = info.year
                if not year and self.tmdb:
                    year = self.tmdb.get_tv_year(info.show_name)

                if year:
                    show_folder = f"{info.show_name} ({year})"
                else:
                    show_folder = info.show_name

                show_dir = os.path.join(tv_dir, show_folder)

                # If the entry is already properly named, skip
                if os.path.abspath(full_path) == os.path.abspath(show_dir):
                    continue

                # Determine season
                if info.season is not None:
                    season_folder = f"Season {info.season:02d}"
                    dest_base = os.path.join(show_dir, season_folder)
                else:
                    dest_base = show_dir

                # Move all files
                for root, dirs, files in os.walk(full_path):
                    for f in files:
                        src = os.path.join(root, f)
                        rel = os.path.relpath(src, full_path)
                        dst = os.path.join(dest_base, rel)
                        self.moves.append(MoveOperation(source=src, destination=dst))

        return self.moves

    def preview(self) -> str:
        """Generate a human-readable preview of planned moves."""
        if not self.moves:
            return "No moves planned."

        lines = []
        lines.append(f"Planned moves: {len(self.moves)}")
        lines.append("=" * 60)

        for i, move in enumerate(self.moves, 1):
            tag = " [subtitle]" if move.is_subtitle else ""
            lines.append(f"  {i}. {os.path.basename(move.source)}{tag}")
            lines.append(f"     -> {move.destination}")
            lines.append("")

        return "\n".join(lines)

    def execute(self, moves_log_path: str = "moves.json") -> int:
        """
        Execute all planned moves and save a log for undo.

        Args:
            moves_log_path: Path to save the moves log JSON.

        Returns:
            Number of files moved.
        """
        if not self.moves:
            return 0

        executed = []
        errors = []

        for move in self.moves:
            try:
                os.makedirs(os.path.dirname(move.destination), exist_ok=True)

                # Don't overwrite existing files
                if os.path.exists(move.destination):
                    errors.append(
                        f"Skipped (exists): {move.destination}"
                    )
                    continue

                shutil.move(move.source, move.destination)
                executed.append(
                    {
                        "source": move.source,
                        "destination": move.destination,
                        "is_subtitle": move.is_subtitle,
                    }
                )
            except Exception as e:
                errors.append(f"Error moving {move.source}: {e}")

        # Clean up empty directories left behind
        self._cleanup_empty_dirs(executed)

        # Save move log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "moves": executed,
            "errors": errors,
        }

        # Append to existing log if present
        existing_log = []
        if os.path.exists(moves_log_path):
            try:
                with open(moves_log_path, "r") as f:
                    existing_log = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing_log = []

        existing_log.append(log_entry)

        with open(moves_log_path, "w") as f:
            json.dump(existing_log, f, indent=2)

        self.move_log = executed

        if errors:
            print(f"\nWarnings/Errors ({len(errors)}):")
            for err in errors:
                print(f"  - {err}")

        return len(executed)

    def _find_associated_subtitles(
        self, directory: str, video_filename: str
    ) -> list[str]:
        """Find subtitle files associated with a video file."""
        base = os.path.splitext(video_filename)[0]
        subtitles = []

        for f in os.listdir(directory):
            if is_subtitle_file(f) and f.startswith(base):
                subtitles.append(os.path.join(directory, f))

        return subtitles

    def _cleanup_empty_dirs(self, executed: list[dict]) -> None:
        """Remove empty directories left after moves."""
        dirs_to_check = set()
        for move in executed:
            parent = os.path.dirname(move["source"])
            dirs_to_check.add(parent)

        for d in dirs_to_check:
            try:
                while d and os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
                    d = os.path.dirname(d)
            except OSError:
                pass


def undo_moves(moves_log_path: str = "moves.json") -> int:
    """
    Undo the last batch of moves from the log file.

    Args:
        moves_log_path: Path to the moves log JSON.

    Returns:
        Number of files moved back.
    """
    if not os.path.exists(moves_log_path):
        print(f"No moves log found at: {moves_log_path}")
        return 0

    with open(moves_log_path, "r") as f:
        log = json.load(f)

    if not log:
        print("Moves log is empty, nothing to undo.")
        return 0

    # Undo the last batch
    last_batch = log.pop()
    moves = last_batch.get("moves", [])

    if not moves:
        print("Last batch has no moves to undo.")
        return 0

    print(f"Undoing {len(moves)} moves from {last_batch['timestamp']}...")

    undone = 0
    for move in reversed(moves):
        src = move["destination"]  # Current location
        dst = move["source"]  # Original location

        if not os.path.exists(src):
            print(f"  Warning: {src} no longer exists, skipping")
            continue

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            undone += 1
        except Exception as e:
            print(f"  Error undoing {src}: {e}")

    # Clean up empty directories created by the original move
    dirs_to_check = set()
    for move in moves:
        parent = os.path.dirname(move["destination"])
        dirs_to_check.add(parent)

    for d in dirs_to_check:
        try:
            while d and os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
        except OSError:
            pass

    # Save updated log (with last batch removed)
    with open(moves_log_path, "w") as f:
        json.dump(log, f, indent=2)

    print(f"Undone: {undone}/{len(moves)} moves reversed.")
    return undone


def _extract_lang_tag(filename: str) -> Optional[str]:
    """Extract language tag from a subtitle filename (e.g., 'eng' from 'Movie.eng.srt')."""
    match = re.search(
        r"\.(eng|en|spa|es|fre|fr|ger|de|ita|it|por|pt|jpn|ja|kor|ko|chi|zh|ara|ar|hin|hi|rus|ru|swe|sv|nor|no|dan|da|fin|fi|dut|nl|pol|pl|tur|tr|heb|he|tha|th|vie|vi|ind|id|mal|ms|fil|tl|forced)\.",
        filename,
        re.IGNORECASE,
    )
    return match.group(1).lower() if match else None
