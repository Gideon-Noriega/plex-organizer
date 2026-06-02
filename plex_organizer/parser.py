"""Filename parsing utilities for extracting movie/TV metadata from messy filenames."""

import re
from dataclasses import dataclass
from typing import Optional


# Common release group tags and quality markers to strip
NOISE_PATTERNS = [
    r"(?i)\b(1080p|2160p|4K|720p|480p)\b",
    r"(?i)\b(WEB|WEBRip|WEB-DL|BluRay|BRRip|HDRip|DVDRip|HDTV|PDTV)\b",
    r"(?i)\b(HEVC|x265|x264|H\.?264|H\.?265|AV1|VP9|10bit|10Bit|8bit)\b",
    r"(?i)\b(AAC|DDP|DD|AC3|EAC3|FLAC|DTS|Atmos|TrueHD|5\.1|7\.1|2\.0)\b",
    r"(?i)\b(AMZN|HMAX|PCOK|ATVP|PMNTP|NF|DSNP|HBO|STAN)\b",
    r"(?i)\b(BONE|NeoNoir|Rapta|GalaxyRG|TGx|YTS\.\w+|PSA|LAMA|RGB)\b",
    r"(?i)\b(DKS2|LEAK|Ghost|SAMPA|Silence|Vyndros|FLUX|MIXED|Feranki\d*)\b",
    r"(?i)\b(Eng|ESub|Tagalog|DUAL[\-\.]?AUDIO|IND[\-\.]?ENG|iNTERNAL)\b",
    r"(?i)\b(DCPRIP|PROPER|REPACK|EXTENDED|UNRATED|DIRECTORS\.?CUT)\b",
    r"(?i)\b(Multi[\-\.]?Subs?|Dual[\-\.]?Audio)\b",
    r"(?i)\b(COMPLETE)\b",
    r"(?i)\{tvdb-\d+\}",
]

# Video file extensions
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".flv", ".mov", ".ts"}

# Subtitle extensions
SUBTITLE_EXTENSIONS = {".srt", ".sub", ".ass", ".ssa", ".vtt", ".idx"}

# Extras/featurettes indicators
EXTRAS_INDICATORS = [
    r"(?i)\b(featurette|behind.the.scenes|deleted.scenes?|gag.reel"
    r"|trailer|interview|extra|bonus|sample)\b",
]


@dataclass
class MovieInfo:
    """Parsed movie information."""

    title: str
    year: Optional[str]
    original_path: str


@dataclass
class TVInfo:
    """Parsed TV show information."""

    show_name: str
    year: Optional[str]
    season: Optional[int]
    episode: Optional[int]
    original_path: str


def is_video_file(filename: str) -> bool:
    """Check if a file is a video file."""
    ext = get_extension(filename)
    return ext in VIDEO_EXTENSIONS


def is_subtitle_file(filename: str) -> bool:
    """Check if a file is a subtitle file."""
    ext = get_extension(filename)
    return ext in SUBTITLE_EXTENSIONS


def get_extension(filename: str) -> str:
    """Get lowercase file extension."""
    match = re.search(r"(\.[^.]+)$", filename)
    return match.group(1).lower() if match else ""


def is_extras(filename: str) -> bool:
    """Check if a file appears to be extras/featurettes/sample."""
    for pattern in EXTRAS_INDICATORS:
        if re.search(pattern, filename):
            return True
    return False


def clean_title(title: str) -> str:
    """Clean a title string by removing noise patterns and normalizing spacing."""
    # Replace dots, dashes, underscores with spaces
    cleaned = re.sub(r"[\.\-_]", " ", title)

    # Remove bracketed content
    cleaned = re.sub(r"\[.*?\]", "", cleaned)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)

    # Remove noise patterns
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def extract_movie_info(
    filename: str, title_overrides: Optional[dict] = None
) -> MovieInfo:
    """
    Extract movie name and year from a messy filename.

    Args:
        filename: The filename or directory name to parse.
        title_overrides: Optional dict of {messy_name: clean_title} overrides.

    Returns:
        MovieInfo with parsed title and year.
    """
    name = filename
    overrides = title_overrides or {}

    # Remove common file extensions
    name = re.sub(
        r"\.(mkv|mp4|avi|m4v|wmv|flv|mov|ts)$", "", name, flags=re.IGNORECASE
    )

    # Try to find year pattern
    year_match = re.search(r"[\.\s\(\[]*((?:19|20)\d{2})[\.\s\)\]\-]", name)
    year = year_match.group(1) if year_match else None

    # Get title (everything before the year)
    if year:
        title_part = name[: year_match.start()]
    else:
        title_part = name

    title = clean_title(title_part)

    # Apply title overrides
    for messy, clean in overrides.items():
        if messy.lower() in title.lower() or title.lower() in messy.lower():
            title = clean
            break

    return MovieInfo(title=title, year=year, original_path=filename)


def extract_tv_info(filename: str) -> TVInfo:
    """
    Extract TV show name, year, season, and episode from a filename.

    Args:
        filename: The filename to parse.

    Returns:
        TVInfo with parsed show metadata.
    """
    name = filename

    # Remove extension
    name_no_ext = re.sub(
        r"\.(mkv|mp4|avi|m4v|wmv|flv|mov|ts|srt|sub|ass)$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    # Extract season/episode patterns
    # S01E01, S01.E01, s01e01
    se_match = re.search(r"[Ss](\d{1,2})[.\s]?[Ee](\d{1,3})", name_no_ext)
    # Season 01, season 1
    season_match = re.search(r"(?i)season\s*(\d{1,2})", name_no_ext)
    # S01 (just season, no episode)
    s_only_match = re.search(r"[Ss](\d{1,2})(?![Ee\d])", name_no_ext)

    season = None
    episode = None

    if se_match:
        season = int(se_match.group(1))
        episode = int(se_match.group(2))
    elif season_match:
        season = int(season_match.group(1))
    elif s_only_match:
        season = int(s_only_match.group(1))

    # Extract year
    year_match = re.search(r"[\(\s]*((?:19|20)\d{2})[\)\s\-\.]", name_no_ext)
    year = year_match.group(1) if year_match else None

    # Get show name (everything before season/episode/year indicator)
    show_part = name_no_ext
    if se_match:
        show_part = name_no_ext[: se_match.start()]
    elif season_match:
        show_part = name_no_ext[: season_match.start()]
    elif s_only_match:
        show_part = name_no_ext[: s_only_match.start()]
    elif year_match:
        show_part = name_no_ext[: year_match.start()]

    show_name = clean_title(show_part)

    return TVInfo(
        show_name=show_name,
        year=year,
        season=season,
        episode=episode,
        original_path=filename,
    )
