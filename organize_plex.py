"""
Organize Plex media files into proper Plex naming convention with genre folders.

Movies: /plex/movies/{Genre}/{Movie Name} ({Year})/{Movie Name} ({Year}).ext
TV:     /plex/tv/{Show Name} ({Year})/Season {XX}/episodes...
"""
import os
import re
import shutil

MOVIES_DIR = "/plex/movies"
TV_DIR = "/plex/tv"
DRY_RUN = False

# Title overrides (messy name -> clean title)
TITLE_OVERRIDES = {
    "A Marvel Television Special Presentation The Punisher One Last Kill": "The Punisher One Last Kill",
    "Avatar The Legend of Aang The Last Airbender": "Avatar The Last Airbender",
    "Good Luck Have Fun Dont Die": "Good Luck Have Fun Don't Die",
    "Tom Clancys Jack Ryan Ghost War": "Jack Ryan Ghost War",
}

# Genre mapping
GENRE_MAP = {
    "Action": [
        "Punisher", "Mortal Kombat", "Predator Badlands", "Shadow Force", "War Machine",
        "Caught Stealing", "Hostile Takeover", "Kill Code", "The Huntsman", "Wardriver",
        "The Killers Game", "Shadow Strays", "Jack Ryan", "Suicide Squad",
        "Deep Cover", "Pretty Lethal", "Brothers Under Fire", "Crime 101", "No Ordinary Heist",
        "F1 The Movie"
    ],
    "Comedy": [
        "Balls Up", "Good Luck Have Fun", "Trading Places", "Youre Cordially Invited",
        "Ladies First", "Roommates", "The Family Plan", "Mike Nick", "Bookworm",
        "Hunting Season"
    ],
    "Drama": [
        "The Pursuit of Happyness", "Wolf of Wall Street", "Big Short", "Normal",
        "Novocaine", "The Drama", "Rental Family", "One Mile", "Shelter", "Send Help",
        "My Dead Friend Zoe", "Primate", "Whistle", "Tow", "The Good Boy",
        "How to Make a Killing", "Uncontained", "Cold Storage", "The Pickup",
        "Marty Supreme", "The Shadows Edge"
    ],
    "Sci-Fi": [
        "Avatar", "Jurassic World", "Project Hail Mary", "Red One",
        "Three Thousand Years", "Legend of Hei"
    ],
    "International": [
        "Angkinin", "Sex Trip", "Stepdaddy", "Sulutan", "Solo Mio"
    ],
    "Adventure": [
        "The Meg"
    ],
}

# TV Show name overrides
TV_OVERRIDES = {
    "Jujutsu Kaisen (Season 2) [1080p][HEVC x265 10bit][Dual-Audio][Multi-Subs]": ("Jujutsu Kaisen", "2020", "Season 02"),
    "The.Copenhagen.Test.S01.1080p.WEB-DL-[Feranki1980]": ("The Copenhagen Test", "2025", "Season 01"),
    "Teacup.S01.COMPLETE.1080p.PCOK.WEB-DL.DDP5.1.H.264-FLUX[TGx]": ("Teacup", "2024", "Season 01"),
    "Mr.and.Mrs.Smith.2024.S01.COMPLETE.1080p.AMZN.WEB.H264-MIXED[TGx]": ("Mr and Mrs Smith", "2024", "Season 01"),
    "Prisoner 2026 S01 1080p WEB-DL HEVC x265 5.1 BONE": ("Prisoner", "2026", "Season 01"),
}

# Abbott Elementary season mapping
ABBOTT_SEASONS = {
    "Abbott Elementary (2021) Season 1 S01 (1080p HMAX WEB-DL x265 HEVC 10bit AC3 5.1 Silence)": "Season 01",
    "Abbott Elementary (2021) Season 2 S02 (1080p AMZN WEB-DL x265 HEVC 10bit EAC3 5.1 Silence)": "Season 02",
    "Abbott Elementary (2021) S03 (1080p AMZN WEB-DL x265 10bit EAC3 5.1 Silence)": "Season 03",
    "Abbott Elementary (2021) S04 (1080p AMZN WEB-DL x265 10bit EAC3 5.1 Silence)": "Season 04",
}

# The Rookie season mapping
ROOKIE_SEASONS = {
    "The Rookie": "keep",  # base folder, keep as is
    "The Rookie (2018) Season 7 S07 (1080p AMZN WEB-DL x265 HEVC 10bit DDP 5.1 Vyndros)": "Season 07",
    "The Rookie (2018) Season 8 S08": "Season 08",
}


def extract_movie_info(filename):
    """Extract movie name and year from messy filename."""
    name = filename

    # Remove common file extensions
    name = re.sub(r'\.(mkv|mp4|avi|m4v)$', '', name, flags=re.IGNORECASE)

    # Try to find year pattern (avoid matching years inside release group names)
    year_match = re.search(r'[\.\s\(]*((?:19|20)\d{2})[\.\s\)\]\-]', name)
    year = year_match.group(1) if year_match else None

    # Get title (everything before the year)
    if year:
        title_part = name[:year_match.start()]
    else:
        title_part = name

    # Clean up title
    title = title_part
    title = re.sub(r'[\.\-_]', ' ', title)
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'(?i)\b(1080p|2160p|4K|WEB|WEBRip|WEB-DL|BluRay|HDRip|HEVC|x265|x264|H264|H265|AAC|DDP|DD|AC3|EAC3|5\.1|10bit|10Bit|AMZN|HMAX|PCOK|ATVP|PMNTP|BONE|NeoNoir|Rapta|GalaxyRG|TGx|YTS\.\w+|PSA|LAMA|RGB|DKS2|LEAK|Ghost|SAMPA|Silence|Vyndros|Eng|ESub|Tagalog|DUAL-AUDIO|IND-ENG|iNTERNAL|DCPRIP)\b', '', title)
    title = re.sub(r'\s+', ' ', title).strip()

    # Apply title overrides
    for messy, clean in TITLE_OVERRIDES.items():
        if messy.lower() in title.lower() or title.lower() in messy.lower():
            title = clean
            break

    return title, year


def get_genre(title):
    """Get genre for a movie based on title keywords."""
    for genre, keywords in GENRE_MAP.items():
        for keyword in keywords:
            if keyword.lower() in title.lower():
                return genre
    return "Other"


def organize_movies():
    """Organize movies into genre/proper naming structure."""
    print("=== Organizing Movies ===\n")

    entries = os.listdir(MOVIES_DIR)
    moves = []

    for entry in sorted(entries):
        full_path = os.path.join(MOVIES_DIR, entry)

        # Skip if already in a genre folder
        if os.path.isdir(full_path) and entry in ["Action", "Comedy", "Drama", "Sci-Fi", "Thriller", "International", "Adventure", "Other"]:
            continue

        title, year = extract_movie_info(entry)

        if not title:
            print(f"  SKIP (no title): {entry}")
            continue

        # Determine if it's a file or directory
        if os.path.isdir(full_path):
            video_files = []
            for root, dirs, files in os.walk(full_path):
                for f in files:
                    if f.lower().endswith(('.mkv', '.mp4', '.avi', '.m4v')):
                        video_files.append(os.path.join(root, f))
            if not video_files:
                print(f"  SKIP (no video): {entry}")
                continue
            source = video_files[0]
            ext = os.path.splitext(source)[1]
        else:
            source = full_path
            ext = os.path.splitext(entry)[1]

        # Build new path
        genre = get_genre(title)
        if year:
            folder_name = f"{title} ({year})"
            file_name = f"{title} ({year}){ext}"
        else:
            folder_name = title
            file_name = f"{title}{ext}"

        new_dir = os.path.join(MOVIES_DIR, genre, folder_name)
        new_path = os.path.join(new_dir, file_name)

        moves.append((source, new_path, entry, full_path))
        print(f"  {entry}")
        print(f"    -> {genre}/{folder_name}/{file_name}")
        print()

    print(f"\nTotal: {len(moves)} movies to organize")

    if not DRY_RUN:
        print(f"\nExecuting {len(moves)} moves...")
        for source, dest, original, orig_full in moves:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(source, dest)
            # Clean up empty original directory
            if os.path.isdir(orig_full) and orig_full != os.path.dirname(dest):
                try:
                    shutil.rmtree(orig_full)
                except:
                    pass
        # Clean up any remaining empty files/dirs at root level
        for entry in os.listdir(MOVIES_DIR):
            full = os.path.join(MOVIES_DIR, entry)
            if os.path.isdir(full) and entry not in ["Action", "Comedy", "Drama", "Sci-Fi", "Thriller", "International", "Adventure", "Other"]:
                if not os.listdir(full):
                    os.rmdir(full)
        print("Movies organized!")
    else:
        print(f"\n[DRY RUN] Would execute {len(moves)} moves")


def organize_tv():
    """Organize TV shows into proper Plex naming."""
    print("\n=== Organizing TV Shows ===\n")

    entries = os.listdir(TV_DIR)

    # Phase 1: Handle Abbott Elementary (merge seasons into one show folder)
    abbott_dir = os.path.join(TV_DIR, "Abbott Elementary (2021)")
    os.makedirs(abbott_dir, exist_ok=True) if not DRY_RUN else None

    for entry, season in ABBOTT_SEASONS.items():
        source = os.path.join(TV_DIR, entry)
        if os.path.exists(source):
            dest = os.path.join(abbott_dir, season)
            print(f"  {entry}")
            print(f"    -> Abbott Elementary (2021)/{season}/")
            if not DRY_RUN:
                if os.path.exists(dest):
                    # Merge
                    for item in os.listdir(source):
                        shutil.move(os.path.join(source, item), os.path.join(dest, item))
                    shutil.rmtree(source)
                else:
                    shutil.move(source, dest)
            print()

    # Phase 2: Handle The Rookie (merge seasons)
    rookie_dir = os.path.join(TV_DIR, "The Rookie (2018)")
    os.makedirs(rookie_dir, exist_ok=True) if not DRY_RUN else None

    for entry, season in ROOKIE_SEASONS.items():
        if season == "keep":
            # Move contents of base "The Rookie" into the year-named folder
            source = os.path.join(TV_DIR, entry)
            if os.path.exists(source) and source != rookie_dir:
                print(f"  {entry} -> The Rookie (2018)/")
                if not DRY_RUN:
                    for item in os.listdir(source):
                        shutil.move(os.path.join(source, item), os.path.join(rookie_dir, item))
                    shutil.rmtree(source)
                print()
            continue

        source = os.path.join(TV_DIR, entry)
        if os.path.exists(source):
            dest = os.path.join(rookie_dir, season)
            print(f"  {entry}")
            print(f"    -> The Rookie (2018)/{season}/")
            if not DRY_RUN:
                shutil.move(source, dest)
            print()

    # Phase 3: Handle override shows
    for entry, (name, year, season) in TV_OVERRIDES.items():
        source = os.path.join(TV_DIR, entry)
        if os.path.exists(source):
            show_dir = os.path.join(TV_DIR, f"{name} ({year})")
            dest = os.path.join(show_dir, season)
            print(f"  {entry}")
            print(f"    -> {name} ({year})/{season}/")
            if not DRY_RUN:
                os.makedirs(show_dir, exist_ok=True)
                shutil.move(source, dest)
            print()

    # Phase 4: Handle remaining shows (just clean names)
    remaining_renames = {
        "Pluribus (2025) S01 (1080p ATVP WEB-DL x265 10bit EAC3 Atmos 5.1 Ghost)": "Pluribus (2025)",
        "Rooster": "Rooster",
        "Teacup": "Teacup (2024)",
        "Widows bay": "Widows Bay",
        "gachiakuta": "Gachiakuta",
        "solo leveling": "Solo Leveling",
        "Malcolm in the Middle (2025) {tvdb-457779}": "Malcolm in the Middle (2025)",
    }

    for old_name, new_name in remaining_renames.items():
        source = os.path.join(TV_DIR, old_name)
        dest = os.path.join(TV_DIR, new_name)
        if os.path.exists(source) and old_name != new_name:
            print(f"  {old_name}")
            print(f"    -> {new_name}")
            if not DRY_RUN:
                if os.path.exists(dest):
                    for item in os.listdir(source):
                        shutil.move(os.path.join(source, item), os.path.join(dest, item))
                    shutil.rmtree(source)
                else:
                    shutil.move(source, dest)
            print()

    if DRY_RUN:
        print("\n[DRY RUN] No changes made")
    else:
        print("\nTV shows organized!")


if __name__ == "__main__":
    import sys
    if "--dry-run" in sys.argv:
        DRY_RUN = True
        print("=== DRY RUN MODE ===\n")

    organize_movies()
    organize_tv()
