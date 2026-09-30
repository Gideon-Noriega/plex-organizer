"""Filenames must survive organizing when an *arr manages the library.

Sonarr and Radarr re-derive a file's quality by re-parsing its name, so the
quality tokens in a release filename (1080p, WEB-DL, BluRay, x265) are the only
record of quality outside the *arr database. Rewriting the name to
"Title (Year).ext" makes the *arr re-grade the file HDTV-1080p, which falls
below the profile cutoff and triggers a re-download that can install a WORSE
release than the one already on disk. See docs/quality-token-loss.md in the
media-stack repo for the incident this guards against.
"""

import os
import tempfile
import unittest

from plex_organizer.config import Config
from plex_organizer.organizer import PlexOrganizer

RELEASE = "Idiots 2026 1080p WEB-DL HEVC x265 5.1 BONE.mkv"


class TestKeepFilenames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.movies = self.tmp.name
        open(os.path.join(self.movies, RELEASE), "w").close()

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, keep):
        config = Config(movies_dir=self.movies, keep_filenames=keep)
        return PlexOrganizer(config).plan_movies(self.movies)

    def test_keep_filenames_preserves_quality_tokens(self):
        moves = self._plan(keep=True)
        self.assertEqual(len(moves), 1)
        self.assertEqual(os.path.basename(moves[0].destination), RELEASE)

    def test_keep_filenames_still_files_into_a_genre_folder(self):
        """The point is to stop renaming, not to stop organizing."""
        moves = self._plan(keep=True)
        parent = os.path.basename(os.path.dirname(moves[0].destination))
        self.assertEqual(parent, "Idiots (2026)")

    def test_default_rewrites_the_name_and_loses_the_tokens(self):
        """Documents the old behaviour that caused the re-downloads."""
        moves = self._plan(keep=False)
        self.assertEqual(os.path.basename(moves[0].destination), "Idiots (2026).mkv")
        self.assertNotIn("1080p", moves[0].destination)


if __name__ == "__main__":
    unittest.main()
