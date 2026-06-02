"""TMDb API integration for genre lookup."""

import urllib.request
import urllib.parse
import json
from typing import Optional


TMDB_BASE_URL = "https://api.themoviedb.org/3"

# TMDb genre ID to name mapping (pre-populated for offline fallback)
GENRE_ID_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western",
}


class TMDbClient:
    """Client for TMDb API genre lookups."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_movie(self, title: str, year: Optional[str] = None) -> Optional[dict]:
        """
        Search TMDb for a movie by title and optional year.

        Returns the first matching result or None.
        """
        params = {
            "api_key": self.api_key,
            "query": title,
            "include_adult": "false",
        }
        if year:
            params["year"] = year

        url = f"{TMDB_BASE_URL}/search/movie?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                if data.get("results"):
                    return data["results"][0]
        except Exception:
            return None

        return None

    def search_tv(self, title: str, year: Optional[str] = None) -> Optional[dict]:
        """
        Search TMDb for a TV show by title and optional year.

        Returns the first matching result or None.
        """
        params = {
            "api_key": self.api_key,
            "query": title,
            "include_adult": "false",
        }
        if year:
            params["first_air_date_year"] = year

        url = f"{TMDB_BASE_URL}/search/tv?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                if data.get("results"):
                    return data["results"][0]
        except Exception:
            return None

        return None

    def get_movie_genre(self, title: str, year: Optional[str] = None) -> Optional[str]:
        """
        Look up the primary genre for a movie.

        Returns the genre name string or None if not found.
        """
        result = self.search_movie(title, year)
        if not result:
            return None

        genre_ids = result.get("genre_ids", [])
        if not genre_ids:
            return None

        # Return the first (primary) genre
        primary_id = genre_ids[0]
        return GENRE_ID_MAP.get(primary_id)

    def get_tv_year(self, title: str) -> Optional[str]:
        """Look up the first air date year for a TV show."""
        result = self.search_tv(title)
        if not result:
            return None

        first_air = result.get("first_air_date", "")
        if first_air and len(first_air) >= 4:
            return first_air[:4]
        return None
