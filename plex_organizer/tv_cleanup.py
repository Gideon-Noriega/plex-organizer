"""TV show cleanup utilities: flatten nested episodes and normalize naming."""

import os
import re
import shutil
from typing import Optional

from .parser import is_video_file, get_extension, NOISE_PATTERNS


def flatten_episodes(tv_dir: str, dry_run: bool = False) -> list[dict]:
    """
    Move video files from nested subdirectories up to their Season folder.

    Plex expects: Show (Year)/Season XX/episode.mkv
    This fixes:   Show (Year)/Season XX/Some.Folder/episode.mkv

    Returns list of moves performed.
    """
    moves = []

    for show in sorted(os.listdir(tv_dir)):
        show_path = os.path.join(tv_dir, show)
        if not os.path.isdir(show_path):
            continue

        for season in sorted(os.listdir(show_path)):
            season_path = os.path.join(show_path, season)
            if not os.path.isdir(season_path) or not season.lower().startswith("season"):
                continue

            for entry in os.listdir(season_path):
                entry_path = os.path.join(season_path, entry)
                if not os.path.isdir(entry_path):
                    continue

                for root, dirs, files in os.walk(entry_path):
                    for f in files:
                        if is_video_file(f):
                            src = os.path.join(root, f)
                            dst = os.path.join(season_path, f)
                            moves.append({"source": src, "destination": dst})
                            if not dry_run:
                                if not os.path.exists(dst):
                                    shutil.move(src, dst)

                # Remove the now-empty directory tree
                if not dry_run:
                    shutil.rmtree(entry_path, ignore_errors=True)

    return moves


def normalize_episode_names(tv_dir: str, dry_run: bool = False) -> list[dict]:
    """
    Rename TV episodes to Plex-preferred format: Show - SXXEXX - Title.ext

    Handles common messy formats:
    - Show.S01E01.Title.1080p.WEB-DL.x265-Group.mkv
    - Show S01E01 Title 1080p CR WEB-DL.mkv
    - show.s01e01.1080p.web.h264-group.mkv

    Returns list of renames performed.
    """
    renames = []

    for show in sorted(os.listdir(tv_dir)):
        show_path = os.path.join(tv_dir, show)
        if not os.path.isdir(show_path):
            continue

        # Extract show name from folder (remove year)
        show_name = re.sub(r"\s*\(\d{4}\)\s*$", "", show).strip()

        for season in sorted(os.listdir(show_path)):
            season_path = os.path.join(show_path, season)
            if not os.path.isdir(season_path) or not season.lower().startswith("season"):
                continue

            for filename in sorted(os.listdir(season_path)):
                filepath = os.path.join(season_path, filename)
                if not os.path.isfile(filepath) or not is_video_file(filename):
                    continue

                # Check if already in good format: Show - SXXEXX - Title.ext
                if re.match(r"^.+ - S\d{2}E\d{2,3} - .+\.\w+$", filename):
                    continue

                new_name = _build_episode_name(show_name, filename)
                if new_name and new_name != filename:
                    dst = os.path.join(season_path, new_name)
                    if not os.path.exists(dst):
                        renames.append({"source": filepath, "destination": dst, "old_name": filename, "new_name": new_name})
                        if not dry_run:
                            shutil.move(filepath, dst)

    return renames


def _build_episode_name(show_name: str, filename: str) -> Optional[str]:
    """Build a normalized episode filename from a messy one."""
    ext = get_extension(filename)
    name = filename

    # Remove extension
    name_no_ext = re.sub(r"\.\w+$", "", name)

    # Extract SXXEXX
    se_match = re.search(r"[Ss](\d{1,2})[.\s]?[Ee](\d{1,3})", name_no_ext)
    if not se_match:
        return None

    season = int(se_match.group(1))
    episode = int(se_match.group(2))

    # Extract episode title (text between SXXEXX and noise)
    after_se = name_no_ext[se_match.end():]

    # Replace dots/underscores with spaces
    after_se = re.sub(r"[\.\-_]", " ", after_se).strip()

    # Remove noise patterns
    for pattern in NOISE_PATTERNS:
        after_se = re.sub(pattern, "", after_se)

    # Remove bracketed content
    after_se = re.sub(r"\[.*?\]", "", after_se)
    after_se = re.sub(r"\(.*?\)", "", after_se)

    # Remove common release group patterns and leftover codec/format noise
    after_se = re.sub(r"(?i)\b(WEB[\-\s]?DL|DL)\b", "", after_se)
    after_se = re.sub(r"(?i)\b(DDP?\s?\d[\.\s]\d)\b", "", after_se)
    after_se = re.sub(r"(?i)\b(DD\s?\d[\.\s]\d)\b", "", after_se)
    after_se = re.sub(r"(?i)\b\d[\.\s]\d\b", "", after_se)
    after_se = re.sub(r"(?i)\b(H[\.\s]?264|H[\.\s]?265)\b", "", after_se)
    after_se = re.sub(r"(?i)\b(playWEB|STRiKES|Kitsune|GRACE|ELiTE|MeGusta|skyanime|SuccessfulCrab|NeoNoir|Slurpuff|FLUX|Vyndros|kawaii)\b", "", after_se)
    after_se = re.sub(r"(?i)\b(DUBBED|v\d+)\b", "", after_se)
    after_se = re.sub(r"(?i)\bEZTVx?\.to\b", "", after_se)
    after_se = re.sub(r"(?i)\b(AAC\d[\.\s]\d)\b", "", after_se)
    after_se = re.sub(r"(?i)\b(FantasticSwingingMarkhorOfPiety)\b", "", after_se)

    # Remove trailing/leading dashes and whitespace
    after_se = re.sub(r"[\s\-]+$", "", after_se)
    after_se = re.sub(r"^[\s\-]+", "", after_se)

    # Clean up whitespace
    title = re.sub(r"\s+", " ", after_se).strip()

    # Remove trailing dashes or single-word leftovers that look like group names
    title = re.sub(r"\s*-\s*$", "", title).strip()

    if not title:
        title = f"Episode {episode}"

    return f"{show_name} - S{season:02d}E{episode:02d} - {title}{ext}"
