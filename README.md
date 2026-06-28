# Plex Organizer

A CLI tool to automatically organize messy media files into proper [Plex naming conventions](https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/) with genre-based folder structure.

## Features

- **Movie organization** — Parse titles/years from messy filenames, auto-detect genres via TMDb, organize into `{Genre}/{Title} ({Year})/` structure
- **TV show organization** — Organize into `{Show} ({Year})/Season {XX}/` structure with proper naming
- **Flatten nested episodes** — Fix episodes buried in subdirectories (common with torrent downloads)
- **Normalize episode names** — Rename to Plex format: `Show - SXXEXX - Title.ext` (strips release groups, codec tags, torrent site names)
- **Junk cleanup** — Remove .nfo, torrent site ads (.txt), screenshots, .parts files, and empty directories
- **Plex integration** — Trigger library scan and empty trash after organizing
- **TMDb genre detection** — Auto-assign genres via [TMDb API](https://www.themoviedb.org/documentation/api) (free)
- **Scheduling** — Interactive setup for automatic daily/hourly runs via systemd timer
- **Dry run mode** — Preview all changes before executing
- **Undo support** — Reverse moves via `moves.json` log
- **Subtitle handling** — Move associated .srt/.sub/.ass files alongside videos
- **Config file** — YAML config for custom genre maps, title overrides, TV show overrides

## Installation

```bash
git clone https://github.com/Gideon-Noriega/plex-organizer.git
cd plex-organizer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

```bash
# Preview what would happen (no files moved)
plex-organizer --movies /plex/movies --tv /plex/tv --dry-run

# Organize everything with TMDb genre detection
plex-organizer --movies /plex/movies --tv /plex/tv --tmdb-api-key YOUR_KEY --yes

# Use a config file (recommended)
plex-organizer --movies /plex/movies --tv /plex/tv --config config.yaml --yes
```

## Commands

### Organize (default)

```bash
# Organize movies into genre folders
plex-organizer --movies /plex/movies --tmdb-api-key YOUR_KEY

# Organize TV shows (flatten + normalize + move)
plex-organizer --tv /plex/tv

# Both at once with Plex refresh
plex-organizer --movies /plex/movies --tv /plex/tv --config config.yaml --yes --refresh-plex
```

### Fix TV Episodes

```bash
# Flatten nested episodes (move from subdirs to Season folder)
plex-organizer --flatten --tv /plex/tv

# Normalize episode names to Plex format
plex-organizer --normalize --tv /plex/tv

# Preview first
plex-organizer --normalize --tv /plex/tv --dry-run
```

### Cleanup

```bash
# Remove junk files (.nfo, torrent ads, screenshots, empty dirs)
plex-organizer --cleanup --movies /plex/movies --tv /plex/tv

# Preview what would be removed
plex-organizer --cleanup --tv /plex/tv --dry-run
```

### Schedule

```bash
# Interactive setup for automatic scheduling
sudo plex-organizer --schedule
```

Options:
- Daily, every 12h, every 6h, or weekly
- Choose time (UTC)
- Auto-installs systemd timer

### Undo

```bash
# Reverse the last batch of moves
plex-organizer --undo
```

## Configuration

Copy and edit `config.yaml`:

```yaml
# Media directories
movies_dir: "/plex/movies"
tv_dir: "/plex/tv"

# TMDb API key (or use --tmdb-api-key flag or TMDB_API_KEY env var)
tmdb_api_key: ""

# Manual genre assignments (override TMDb)
genre_map:
  Action:
    - "Punisher"
    - "Predator"
  Comedy:
    - "Trading Places"

# Fix misdetected titles
title_overrides:
  "Some Messy Parsed Title": "Correct Title"

# Fix TV shows with unparseable folder names
tv_overrides:
  "Messy.Show.S01.1080p.WEB-DL":
    name: "Show Name"
    year: "2024"
    season: "Season 01"

# Valid genre folder names (won't be re-organized)
genre_folders:
  - Action
  - Comedy
  - Drama
  # ... etc
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TMDB_API_KEY` | TMDb API key for genre detection |
| `PLEX_TOKEN` | Plex authentication token for library refresh |

## How It Works

The full pipeline (when run with `--movies` and `--tv`):

1. **Flatten** — Move video files from nested subdirectories up to Season folders
2. **Normalize** — Rename episodes to `Show - SXXEXX - Title.ext`
3. **Organize movies** — Parse title/year, detect genre via TMDb, move to `Genre/Title (Year)/`
4. **Organize TV** — Parse show/season/episode, move to `Show (Year)/Season XX/`
5. **Cleanup** — Remove .nfo, .txt ads, screenshots, empty dirs
6. **Refresh Plex** — Empty trash + trigger library scan

## Plex Integration

The organizer can auto-detect your Plex token from `Preferences.xml` or you can set it via:

```bash
# Environment variable
export PLEX_TOKEN=your_token_here

# Or CLI flag
plex-organizer --movies /plex/movies --refresh-plex --plex-token YOUR_TOKEN
```

## Scheduled Operation

Once set up with `--schedule`, the organizer runs automatically. The systemd service:

```bash
# Check status
systemctl status plex-organizer.timer

# View last run
journalctl -u plex-organizer.service -e

# Stop scheduling
sudo systemctl stop plex-organizer.timer

# Reconfigure
sudo plex-organizer --schedule
```

## License

Private project.
