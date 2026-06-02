"""Configuration loading from YAML files."""

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class Config:
    """Application configuration."""

    movies_dir: str = ""
    tv_dir: str = ""
    tmdb_api_key: str = ""
    genre_map: dict = field(default_factory=dict)
    title_overrides: dict = field(default_factory=dict)
    tv_overrides: dict = field(default_factory=dict)
    genre_folders: list = field(
        default_factory=lambda: [
            "Action",
            "Adventure",
            "Animation",
            "Comedy",
            "Crime",
            "Documentary",
            "Drama",
            "Family",
            "Fantasy",
            "History",
            "Horror",
            "International",
            "Music",
            "Mystery",
            "Romance",
            "Sci-Fi",
            "Thriller",
            "War",
            "Western",
            "Other",
        ]
    )


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML config file. If None, uses default config.

    Returns:
        Config object with loaded values.
    """
    config = Config()

    if config_path is None:
        # Try default locations
        candidates = [
            os.path.join(os.getcwd(), "config.yaml"),
            os.path.expanduser("~/.config/plex-organizer/config.yaml"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                config_path = candidate
                break

    if config_path and os.path.exists(config_path):
        if yaml is None:
            raise ImportError(
                "PyYAML is required for config file support. "
                "Install with: pip install pyyaml"
            )

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        config.movies_dir = data.get("movies_dir", config.movies_dir)
        config.tv_dir = data.get("tv_dir", config.tv_dir)
        config.tmdb_api_key = data.get("tmdb_api_key", config.tmdb_api_key)
        config.genre_map = data.get("genre_map", config.genre_map)
        config.title_overrides = data.get("title_overrides", config.title_overrides)
        config.tv_overrides = data.get("tv_overrides", config.tv_overrides)

        if "genre_folders" in data:
            config.genre_folders = data["genre_folders"]

    return config


def get_genre_from_map(title: str, genre_map: dict) -> Optional[str]:
    """
    Look up genre from the config-based genre map.

    The genre_map is structured as: {genre_name: [keyword1, keyword2, ...]}

    Args:
        title: Movie title to look up.
        genre_map: Dict mapping genre names to lists of title keywords.

    Returns:
        Genre string or None if not found.
    """
    title_lower = title.lower()
    for genre, keywords in genre_map.items():
        if isinstance(keywords, list):
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    return genre
    return None
