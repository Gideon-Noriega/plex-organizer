# Plex Organizer

A CLI tool to automatically organize messy media files into proper [Plex naming conventions](https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/) with genre-based folder structure.

## Features

- Parse movie titles and years from messy filenames (strips release group tags, quality markers, etc.)
- Auto-detect genres via [TMDb API](https://www.themoviedb.org/documentation/api) (free)
- YAML config file for custom genre maps, title overrides, and TV show overrides
- Organize movies into `{Genre}/{Title} ({Year})/` structure
- Organize TV into `{Show} ({Year})/Season {XX}/` structure
- Move associated subtitle files (.srt, .sub, .ass) alongside videos
- Skip extras/featurettes/samples automatically
- Dry run mode to preview before executing
- Undo support via `moves.json` log

## Installation

```bash
# Clone and install
git clone https://github.com/gideon/plex-organizer.git
cd plex-organizer
pip install -e .

# Or install dependencies manually
pip install -r requirements.txt
```

## Quick Start

```bash
# Preview what would happen (no files moved)
plex-organizer --movies /plex/movies --dry-run

# Organize movies with TMDb genre detection
plex-organizer --movies /plex/movies --tmdb-api-key YOUR_KEY

# Organize TV shows
plex-organizer --tv /plex/tv

# Both at once
plex-organizer --movies /plex/movies --tv /plex/tv --tmdb-api-key YOUR_KEY

# Use a config file (recommended)
plex-organizer --config config.yaml

# Skip confirmation prompt
plex-organizer --movies /plex/movies --yes

# Undo the last batch of moves
plex-organizer --undo
```

## Configuration

Create a `config.yaml` file (see `config.yaml` for a full example):

```yaml
# Media directories
movies_dir: "/plex/movies"
tv_dir: "/plex/tv"

# TMDb API key (free: https://www.themoviedb.org/settings/api)
tmdb_api_key: "your_api_key_here"

# Manual genre overrides (checked before TMDb)
genre_map:
  Action:
    - "Punisher"
    - "Jack Ryan"
  Sci-Fi:
    - "Avatar"
    - "Jurassic World"

# Fix titles the parser gets wrong
title_overrides:
  "Tom Clancys Jack Ryan Ghost War": "Jack Ryan Ghost War"
  "Good Luck Have Fun Dont Die": "Good Luck Have Fun Don't Die"

# TV shows with messy folder names
tv_overrides:
  "Jujutsu Kaisen (Season 2) [1080p][HEVC x265 10bit][Dual-Audio][Multi-Subs]":
    name: "Jujutsu Kaisen"
    year: "2020"
    season: "Season 02"
```

## TMDb API Key

Get a free API key at https://www.themoviedb.org/settings/api

Set it via (in priority order):
1. `--tmdb-api-key` CLI flag
2. `TMDB_API_KEY` environment variable
3. `tmdb_api_key` in config.yaml

## Output Structure

### Movies

```
/plex/movies/
  Action/
    The Punisher One Last Kill (2025)/
      The Punisher One Last Kill (2025).mkv
      The Punisher One Last Kill (2025).eng.srt
  Drama/
    The Pursuit of Happyness (2006)/
      The Pursuit of Happyness (2006).mkv
  Sci-Fi/
    Avatar (2009)/
      Avatar (2009).mkv
```

### TV Shows

```
/plex/tv/
  Abbott Elementary (2021)/
    Season 01/
      Abbott.Elementary.S01E01.mkv
    Season 02/
      Abbott.Elementary.S02E01.mkv
  The Copenhagen Test (2025)/
    Season 01/
      episode files...
```

## Edge Cases Handled

- **Subtitles**: `.srt`, `.sub`, `.ass`, `.ssa`, `.vtt`, `.idx` files are moved with their video, preserving language tags
- **Multi-file movies**: Folders containing multiple files pick the largest video file
- **Extras/featurettes**: Files with "featurette", "behind the scenes", "deleted scenes", "sample", etc. are skipped
- **Release group tags**: BONE, NeoNoir, YTS, GalaxyRG, TGx, FLUX, etc. are stripped from titles
- **Quality markers**: 1080p, 4K, x265, HEVC, WEB-DL, BluRay, etc. are stripped
- **Existing organization**: Genre folders and already-organized files are not re-processed

## Undo

Every run saves a detailed log to `moves.json`. To reverse the last batch:

```bash
plex-organizer --undo
plex-organizer --undo --log-file /path/to/moves.json
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=plex_organizer
```

## Requirements

- Python 3.9+
- PyYAML (for config file support)
- Internet access (only if using TMDb API for genre detection)

## Notes

- On NFS/SMB mounts (like `/plex/`), you may need to run with `sudo`
- After reorganizing, trigger a Plex library scan: Settings > Libraries > Scan Library Files
- The tool always shows a preview and asks for confirmation before moving files (unless `--yes` is used)
