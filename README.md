# Plex Media Organizer

Script to organize Plex media files into proper naming convention with genre folders.

## Structure

### Movies
```
/plex/movies/{Genre}/{Movie Name} ({Year})/{Movie Name} ({Year}).ext
```

Genres: Action, Adventure, Comedy, Drama, International, Other, Sci-Fi

### TV Shows
```
/plex/tv/{Show Name} ({Year})/Season {XX}/episodes...
```

## Usage

```bash
# Preview changes (no files moved)
sudo python3 ~/projects/plex-organizer/organize_plex.py --dry-run

# Execute for real
sudo python3 ~/projects/plex-organizer/organize_plex.py
```

Note: Must run with sudo because /plex/ is owned by nobody:nogroup (NFS/SMB mount).

## What the script does

1. **Movies:** Extracts title + year from messy filenames, removes release group tags (BONE, NeoNoir, Rapta, YTS, etc.), assigns genre, creates proper folder structure
2. **TV Shows:** Merges multi-season folders (Abbott Elementary, The Rookie), fixes naming, adds Season folders for single-season shows

## Post-run manual fixes

After running the script, check for:
- Apostrophes in titles (e.g., "Youre" -> "You're")
- Years without parentheses (e.g., "Movie 2019" -> "Movie (2019)")
- Title overrides that didn't catch (check TITLE_OVERRIDES in script)
- Genre mismatches (check GENRE_MAP in script)
- Nested season folders (e.g., show had "Season 1" subfolder already)

## Adding new movies/shows

When adding new movies, either:
1. Drop them in the correct genre folder with proper naming: `/plex/movies/Action/Movie Name (2026)/Movie Name (2026).mkv`
2. Or drop them in `/plex/movies/` root and re-run the script (update GENRE_MAP first)

For TV shows:
1. Create folder: `/plex/tv/Show Name (Year)/Season XX/`
2. Drop episodes inside with proper naming

## Plex settings

After reorganizing, restart Plex to trigger rescan:
```bash
sudo systemctl restart plexmediaserver
```

Or trigger a manual scan in Plex UI: Settings > Libraries > Scan Library Files

## File ownership

```
/plex/ owned by nobody:nogroup (NFS/SMB mount)
Plex service runs as user: plex
Server: 192.168.100.43
Plex version: 1.43.0.10492
```

## Current inventory (as of 2026-06-02)

| Category | Count | Size |
|----------|-------|------|
| Movies (Action) | 20 | - |
| Movies (Drama) | 21 | - |
| Movies (Comedy) | 10 | - |
| Movies (Sci-Fi) | 8 | - |
| Movies (International) | 5 | - |
| Movies (Adventure) | 1 | - |
| Movies (Other) | 1 | - |
| **Total Movies** | **66** | **126 GB** |
| TV Shows | 13 | 228 GB |
| Music | - | 957 MB |
| **Total Media** | - | **~560 GB** |

Disk: 1.4 TB volume, 406 GB free
