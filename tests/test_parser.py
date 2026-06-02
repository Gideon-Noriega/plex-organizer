"""Tests for filename parsing utilities."""

import pytest
from plex_organizer.parser import (
    extract_movie_info,
    extract_tv_info,
    is_video_file,
    is_subtitle_file,
    is_extras,
    clean_title,
)


class TestExtractMovieInfo:
    """Tests for movie filename parsing."""

    def test_simple_movie_with_year(self):
        info = extract_movie_info("The Matrix 1999.mkv")
        assert info.title == "The Matrix"
        assert info.year == "1999"

    def test_movie_with_dots_and_quality(self):
        info = extract_movie_info(
            "The.Pursuit.of.Happyness.2006.1080p.BluRay.x265.mkv"
        )
        assert info.title == "The Pursuit of Happyness"
        assert info.year == "2006"

    def test_movie_with_release_group(self):
        info = extract_movie_info(
            "Predator Badlands 2025 1080p WEB-DL HEVC x265 5.1 BONE.mkv"
        )
        assert info.title == "Predator Badlands"
        assert info.year == "2025"

    def test_movie_with_brackets(self):
        info = extract_movie_info(
            "[YTS.MX] Avatar 2009 1080p BluRay.mkv"
        )
        assert "Avatar" in info.title
        assert info.year == "2009"

    def test_movie_no_year(self):
        info = extract_movie_info("Some Random Movie.mkv")
        assert info.title == "Some Random Movie"
        assert info.year is None

    def test_title_override(self):
        overrides = {
            "Tom Clancys Jack Ryan Ghost War": "Jack Ryan Ghost War"
        }
        info = extract_movie_info(
            "Tom.Clancys.Jack.Ryan.Ghost.War.2025.1080p.WEB.mkv",
            title_overrides=overrides,
        )
        assert info.title == "Jack Ryan Ghost War"

    def test_movie_with_year_in_parens(self):
        info = extract_movie_info("The Big Short (2015).mkv")
        assert info.title == "The Big Short"
        assert info.year == "2015"


class TestExtractTVInfo:
    """Tests for TV show filename parsing."""

    def test_standard_sxxexx(self):
        info = extract_tv_info("Breaking.Bad.S01E01.720p.mkv")
        assert info.show_name == "Breaking Bad"
        assert info.season == 1
        assert info.episode == 1

    def test_season_folder(self):
        info = extract_tv_info(
            "Abbott Elementary (2021) Season 2 S02 (1080p AMZN WEB-DL x265 HEVC 10bit EAC3 5.1 Silence)"
        )
        assert "Abbott Elementary" in info.show_name
        assert info.season == 2

    def test_show_with_year(self):
        info = extract_tv_info("Mr.and.Mrs.Smith.2024.S01E05.mkv")
        assert info.year == "2024"
        assert info.season == 1
        assert info.episode == 5


class TestHelperFunctions:
    """Tests for helper utility functions."""

    def test_is_video_file(self):
        assert is_video_file("movie.mkv") is True
        assert is_video_file("movie.mp4") is True
        assert is_video_file("movie.avi") is True
        assert is_video_file("movie.srt") is False
        assert is_video_file("movie.txt") is False

    def test_is_subtitle_file(self):
        assert is_subtitle_file("movie.srt") is True
        assert is_subtitle_file("movie.sub") is True
        assert is_subtitle_file("movie.ass") is True
        assert is_subtitle_file("movie.mkv") is False

    def test_is_extras(self):
        assert is_extras("Behind the Scenes.mkv") is True
        assert is_extras("Movie.Featurette.mkv") is True
        assert is_extras("Sample.mkv") is True
        assert is_extras("The.Matrix.1999.mkv") is False

    def test_clean_title(self):
        assert clean_title("The.Matrix.1080p.BluRay") == "The Matrix"
        assert clean_title("Movie_Name-2024") == "Movie Name"
        assert clean_title("[YTS.MX] Movie Name") == "Movie Name"
