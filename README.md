# Plex Organizer

A CLI tool to automatically organize messy media files into proper [Plex naming conventions](https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/) with genre-based folder structure.

## Features

- **Movie organization** — Parse titles/years from messy filenames, auto-detect genres via TMDb, organize into `{Genre}/{Title} ({Year})/` structure
- **TV show organization** — Organize into `{Show} ({Year})/Season {XX}/` structure with proper naming
- **Flatten nested episodes** — Fix episodes buried in subdirectories (common with torrent downloads)
- **Normalize episode names** — Rename to Plex format: `Show - SXXEXX - Title.ext` (strips release groups, codec tags, torrent site names)
- **Junk cleanup** — Remove .nfo, torrent site ads (.txt), screenshots, .parts files, and empty directories
- **Plex integration** — Trigger library scan and empty trash after organizing
- **Sonarr/Radarr sync** — Repoint the *arrs at the files this tool renamed, so they stop re-downloading media that is already on disk
- **`--keep-filenames`** — Organize without renaming. Required on an *arr-managed library: the quality tokens in a release filename are the only record of quality outside the *arr database
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

## Sonarr / Radarr sync

This tool renames and relocates files that Sonarr and Radarr imported. Both have
their own renaming turned off (`renameEpisodes` and `renameMovies` are false), so
each import arrives under its release name and is reorganised afterwards.
Nothing tells the *arr, and its database goes on pointing at a path that no
longer exists.

That is not cosmetic. **An *arr that has lost track of a file cannot upgrade or
replace it, so the next grab for the same episode or movie lands beside the
existing copy instead of over it.** That is where duplicate media comes from. On
2026-08-29 the libraries here held 30 such stale paths, Radarr could see files
for only 3 of its 30 movies, and `The Gentleman Thief (2026)` had both a `.mp4`
and a `.mkv` of the same film that Radarr was tracking neither of.

The sync reconciles each *arr's records against what is actually on disk and
repairs two layers of drift:

| Drift | Example | Repair |
| --- | --- | --- |
| The show or movie **folder** was renamed | Sonarr held `/data/tv/The Dark`, disk had `The Dark (2026)` | `PUT` the record with `moveFiles=false`, then rescan |
| The **filename** was normalised inside a folder that is still correct | `Rick and Morty S09E03 ... AMZN WEB-DL.mkv` → `Rick and Morty - S09E03 - Rick Fu Hustle.mkv` | rescan that folder |

`moveFiles=false` matters: the file is already where it should be, so the record
is updated without touching the disk. A rescan afterwards re-matches the
renamed files.

### Usage

It runs automatically after organizing whenever API keys are present:

```bash
export SONARR_URL=http://localhost:8989   # optional, this is the default
export SONARR_API_KEY=...
export RADARR_URL=http://localhost:7878   # optional, this is the default
export RADARR_API_KEY=...

plex-organizer --movies /plex/movies --tv /plex/tv --yes
```

A missing API key silently disables that half of the sync. To be explicit:

```bash
plex-organizer ... --arr-sync      # force it on
plex-organizer ... --no-arr-sync   # skip it even with keys configured
```

`--dry-run` reports what it would send without sending anything.

The API keys can be read out of the container configs:

```bash
sudo grep -oP '(?<=<ApiKey>)[^<]+' ~/sonarr/config/config.xml
sudo grep -oP '(?<=<ApiKey>)[^<]+' ~/radarr/config/config.xml
```

### What it refuses to do

A record whose folder cannot be located **unambiguously** is reported and left
alone. Ambiguity is handed to a human rather than settled by a tie-break, for two
reasons: a tracked path can also be missing because the file was genuinely
deleted, which must never be repointed at a lookalike; and a tie-break that is
merely deterministic is not necessarily a safe one.

In practice the ambiguous cases are titles that exist in two genre folders at
once, usually `Other/` plus the real genre — the tool filed them under `Other/`
before the TMDb genre lookup succeeded, then filed the next copy correctly:

```
radarr movie 5: /plex/movies/Toy Story 5 (2026) is gone and 2 folders match
'Toy Story 5' (Animation/Toy Story 5 (2026), Other/Toy Story 5 (2026)); left alone
```

Resolve those by deleting the copy you do not want, then re-running.

Titles that are merely monitored and not yet downloaded are **not** drift — an
*arr creates the folder on import, so no folder and no file is the normal state
for something on the wanted list. Those are skipped silently.

### Why rescans run in a second pass

Rescans are issued only after every repoint for that *arr has landed. A rescan
queued in the same breath as its own `PUT` races the refresh that the `PUT`
itself triggers, and loses: it scans the path the record used to have, finds
nothing, and leaves the stale filenames in the database. The failure is silent —
the command reports `completed`. Each rescan is therefore polled to completion,
which also turns a silent no-op into a reported error.

### Why it reconciles against the *arr, not against `moves.json`

`flatten_episodes` and `normalize_episode_names` rename files without going
through `PlexOrganizer.execute`, so they never appear in the move log. Comparing
the database to the disk catches every path equally, and clears drift that
accumulated before this feature existed.

## `--keep-filenames`: the rename is itself the bug

The sync above repairs drift after the fact. It cannot repair everything, and on
2026-09-30 it turned out that **renaming an *arr-managed file is destructive in a
way no amount of syncing can undo.**

Sonarr and Radarr store no durable record of a file's quality. They **re-derive
it by re-parsing the filename** on every scan, so the quality/source tokens in a
release name are the only copy of that information outside the *arr database —
and `NOISE_PATTERNS` in `parser.py` strips exactly those tokens:

```
The Whisper Man (2026) 1080p BRRip 5.1 x264 -YTS.mkv   ->   The Whisper Man (2026).mkv
```

With no source token left the parser falls back to `HDTV-1080p`. That is below
the `HD-1080p` profile cutoff (`Bluray-1080p`) on an `upgradeAllowed=True`
profile, so Radarr believes it is holding a bad file and goes shopping. It
replaced a genuine Bluray with a WEBRip and logged `reason=Upgrade`.

`--arr-sync` does not help and never did: it correctly repoints the path and
queues a rescan, but **a rescan restores the pointer, not the grade** — the grade
came from the name that was just destroyed. Radarr `movieFileDeleted
reason=MissingFromDisk` totals 22 before the day `arr.py` landed and 22 after.

So on an *arr-managed library, do not rename:

```bash
plex-organizer --movies /plex/movies --tv /plex/tv --keep-filenames --yes
```

`--keep-filenames` (or `keep_filenames: true` in `config.yaml`) suppresses both
rename sites — `normalize_episode_names` for TV and the `Title (Year).ext`
rebuild in `plan_movies` for films — while keeping everything the *arrs cannot
do: genre foldering, flattening nested episode folders, junk cleanup, and the
Plex refresh. Files still move into the right folders; only their names are left
as imported.

```
default           Idiots 2026 1080p WEB-DL HEVC x265 5.1 BONE.mkv -> Idiots (2026).mkv
--keep-filenames  Idiots 2026 1080p WEB-DL HEVC x265 5.1 BONE.mkv -> (unchanged)
```

Let the *arrs rename instead. Both already have Plex-convention formats that
include `{Quality Full}`; both simply had renaming turned off, which is the only
reason this tool ever renamed anything. An *arr that renames its own file updates
its database in the same operation, so drift is structurally impossible **and**
the quality token survives.

Full writeup, including the repair list for the 10 movies this mis-graded:
[`media-stack/docs/quality-token-loss.md`](https://github.com/Gideon-Noriega/media-stack/blob/main/docs/quality-token-loss.md).

## Scheduling

`systemd/` holds the units used on the homelab:

```bash
sudo cp systemd/plex-organizer.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plex-organizer.timer
```

The unit reads secrets from `/etc/plex-organizer.env` rather than `Environment=`
lines, because those are readable by any user via `systemctl cat`:

```bash
sudo install -m 600 -o root -g root /dev/null /etc/plex-organizer.env
sudo tee /etc/plex-organizer.env > /dev/null <<'EOF'
TMDB_API_KEY=...
PLEX_TOKEN=...
SONARR_URL=http://localhost:8989
SONARR_API_KEY=...
RADARR_URL=http://localhost:7878
RADARR_API_KEY=...
EOF
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

# Never rename video files, only move them. Set this whenever Sonarr/Radarr
# manage the library -- see the --keep-filenames section above.
keep_filenames: false

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
| `SONARR_API_KEY` | Enables the Sonarr half of `--arr-sync`; absent means skip |
| `SONARR_URL` | Defaults to `http://localhost:8989` |
| `RADARR_API_KEY` | Enables the Radarr half of `--arr-sync`; absent means skip |
| `RADARR_URL` | Defaults to `http://localhost:7878` |

## How It Works

The full pipeline (when run with `--movies` and `--tv`):

1. **Flatten** — Move video files from nested subdirectories up to Season folders
2. **Normalize** — Rename episodes to `Show - SXXEXX - Title.ext`
3. **Organize movies** — Parse title/year, detect genre via TMDb, move to `Genre/Title (Year)/`
4. **Organize TV** — Parse show/season/episode, move to `Show (Year)/Season XX/`
5. **Cleanup** — Remove .nfo, .txt ads, screenshots, empty dirs
6. **Sync Sonarr/Radarr** — Repoint them at the renamed files, so they do not
   re-download what is already on disk (see [Sonarr / Radarr sync](#sonarr--radarr-sync))
7. **Refresh Plex** — Empty trash + trigger library scan

## Plex Integration

The organizer can auto-detect your Plex token from `Preferences.xml` or you can set it via:

```bash
# Environment variable
export PLEX_TOKEN=your_token_here

# Or CLI flag
plex-organizer --movies /plex/movies --refresh-plex --plex-token YOUR_TOKEN
```

## Scheduled Operation

Once set up with `--schedule`, or from the units in `systemd/` (see
[Scheduling](#scheduling)), the organizer runs automatically:

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
