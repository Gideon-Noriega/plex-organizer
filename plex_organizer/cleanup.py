"""Post-organization cleanup: remove junk files and empty directories."""

import os
import shutil

JUNK_PATTERNS = [
    ".nfo",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".DS_Store",
    ".parts",
]

JUNK_DIRS = [
    "Screens",
    "Subs",
    "Sample",
    "Extras",
    "Featurettes",
]

JUNK_FILENAME_KEYWORDS = [
    "YTS",
    "YIFY",
    "UIndex",
    "EZTV",
    "Torrent Downloaded",
    "Official site",
    "Proxies",
]


def cleanup_junk(media_dir: str, dry_run: bool = False) -> dict:
    """
    Remove junk files and empty directories from a media directory.

    Removes: .nfo, .txt (torrent site ads), screenshots, .parts files,
    and known junk directories (Screens, Subs without matching video, Sample).

    Returns dict with counts of removed items.
    """
    removed_files = []
    removed_dirs = []

    for root, dirs, files in os.walk(media_dir, topdown=False):
        # Remove junk files
        for f in files:
            filepath = os.path.join(root, f)
            if _is_junk_file(f):
                removed_files.append(filepath)
                if not dry_run:
                    os.remove(filepath)

        # Remove known junk directories
        for d in dirs:
            dirpath = os.path.join(root, d)
            if d in JUNK_DIRS and os.path.isdir(dirpath):
                removed_dirs.append(dirpath)
                if not dry_run:
                    shutil.rmtree(dirpath, ignore_errors=True)

    # Second pass: remove empty directories
    for root, dirs, files in os.walk(media_dir, topdown=False):
        for d in dirs:
            dirpath = os.path.join(root, d)
            if os.path.isdir(dirpath) and not os.listdir(dirpath):
                removed_dirs.append(dirpath)
                if not dry_run:
                    os.rmdir(dirpath)

    return {
        "files": removed_files,
        "dirs": removed_dirs,
    }


VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".flv", ".mov", ".ts"}
SUBTITLE_EXTENSIONS = {".srt", ".sub", ".ass", ".ssa", ".vtt", ".idx"}


def _is_junk_file(filename: str) -> bool:
    """Check if a file is junk (torrent ads, screenshots, nfo, etc.)."""
    lower = filename.lower()
    ext = os.path.splitext(lower)[1]

    # Never remove video or subtitle files
    if ext in VIDEO_EXTENSIONS or ext in SUBTITLE_EXTENSIONS:
        return False

    # Check extension-based junk (but not subtitle files)
    ext = os.path.splitext(lower)[1]
    if ext in (".nfo", ".parts"):
        return True

    # Check for torrent site ad files
    for keyword in JUNK_FILENAME_KEYWORDS:
        if keyword.lower() in lower:
            return True

    # .txt files in media dirs are almost always junk
    if ext == ".txt":
        return True

    # Screenshot images inside episode/movie folders
    if ext in (".jpg", ".jpeg", ".png", ".gif"):
        # Only remove if filename looks like a screenshot (screenXXXX, etc.)
        if "screen" in lower or "sample" in lower:
            return True

    return False
