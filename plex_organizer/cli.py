"""Command-line interface for plex-organizer."""

import argparse
import os
import subprocess
import sys

from . import __version__
from .config import Config, load_config
from .organizer import PlexOrganizer, undo_moves
from .tv_cleanup import flatten_episodes, normalize_episode_names
from .cleanup import cleanup_junk
from .plex import refresh_library, empty_trash


SERVICE_TEMPLATE = """[Unit]
Description=Plex Organizer - Organize media into Plex naming conventions
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory={work_dir}
ExecStart={venv_bin}/plex-organizer --movies {movies_dir} --tv {tv_dir} --config {config_path} --yes
"""

TIMER_TEMPLATE = """[Unit]
Description=Run Plex Organizer {frequency_desc}

[Timer]
OnCalendar={on_calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""


def setup_schedule():
    """Interactive setup for scheduling plex-organizer via systemd timer."""
    if os.geteuid() != 0:
        print("Error: --schedule requires root privileges. Run with sudo.")
        sys.exit(1)

    print("=" * 50)
    print("  Plex Organizer - Schedule Setup")
    print("=" * 50)
    print()

    # Frequency
    print("How often should the organizer run?")
    print("  1) Daily")
    print("  2) Every 12 hours")
    print("  3) Every 6 hours")
    print("  4) Weekly (Sunday)")
    print()
    freq = input("Choose [1-4] (default: 1): ").strip() or "1"

    # Time
    print()
    print("What time should it run? (24-hour format, UTC)")
    print("  Examples: 22:00 (10pm UTC = 1am EAT)")
    print("            06:00 (6am UTC = 9am EAT)")
    print("            00:00 (midnight UTC = 3am EAT)")
    print()
    time_input = input("Time [HH:MM] (default: 22:00): ").strip() or "22:00"

    # Validate time format
    try:
        parts = time_input.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
        time_str = f"{hour:02d}:{minute:02d}:00"
    except (ValueError, IndexError):
        print(f"Error: Invalid time format '{time_input}'. Use HH:MM (e.g., 22:00)")
        sys.exit(1)

    # Build OnCalendar string
    if freq == "1":
        on_calendar = f"*-*-* {time_str}"
        frequency_desc = f"daily at {time_input} UTC"
    elif freq == "2":
        h2 = (hour + 12) % 24
        on_calendar = f"*-*-* {hour:02d},{h2:02d}:{minute:02d}:00"
        frequency_desc = f"every 12 hours at :{minute:02d} UTC"
    elif freq == "3":
        hours = ",".join(f"{(hour + i * 6) % 24:02d}" for i in range(4))
        on_calendar = f"*-*-* {hours}:{minute:02d}:00"
        frequency_desc = f"every 6 hours starting at {time_input} UTC"
    elif freq == "4":
        on_calendar = f"Sun *-*-* {time_str}"
        frequency_desc = f"weekly on Sundays at {time_input} UTC"
    else:
        print(f"Error: Invalid choice '{freq}'")
        sys.exit(1)

    # Directories
    print()
    movies_dir = input("Movies directory (default: /plex/movies): ").strip() or "/plex/movies"
    tv_dir = input("TV shows directory (default: /plex/tv): ").strip() or "/plex/tv"

    # Detect paths
    work_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_bin = os.path.dirname(sys.executable)
    config_path = os.path.join(work_dir, "config.yaml")

    # Summary
    print()
    print("-" * 50)
    print(f"  Schedule:    {frequency_desc}")
    print(f"  Movies dir:  {movies_dir}")
    print(f"  TV dir:      {tv_dir}")
    print(f"  Config:      {config_path}")
    print(f"  OnCalendar:  {on_calendar}")
    print("-" * 50)
    print()

    confirm = input("Install this schedule? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        sys.exit(0)

    # Write service file
    service_content = SERVICE_TEMPLATE.format(
        work_dir=work_dir,
        venv_bin=venv_bin,
        movies_dir=movies_dir,
        tv_dir=tv_dir,
        config_path=config_path,
    )
    with open("/etc/systemd/system/plex-organizer.service", "w") as f:
        f.write(service_content)

    # Write timer file
    timer_content = TIMER_TEMPLATE.format(
        frequency_desc=frequency_desc,
        on_calendar=on_calendar,
    )
    with open("/etc/systemd/system/plex-organizer.timer", "w") as f:
        f.write(timer_content)

    # Enable and start
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "plex-organizer.timer"], check=True)
    subprocess.run(["systemctl", "start", "plex-organizer.timer"], check=True)

    print()
    print("Schedule installed successfully!")
    print(f"  Timer: plex-organizer.timer ({frequency_desc})")
    print()
    print("Useful commands:")
    print("  systemctl status plex-organizer.timer    # Check next run time")
    print("  journalctl -u plex-organizer.service -e  # View last run logs")
    print("  sudo systemctl stop plex-organizer.timer # Stop the schedule")
    print("  sudo plex-organizer --schedule           # Reconfigure schedule")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="plex-organizer",
        description="Organize media files into Plex naming conventions with genre folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Organize movies with TMDb genre detection
  plex-organizer --movies /plex/movies --tmdb-api-key YOUR_KEY

  # Organize TV shows
  plex-organizer --tv /plex/tv

  # Dry run (preview without moving)
  plex-organizer --movies /plex/movies --dry-run

  # Use a config file
  plex-organizer --config config.yaml

  # Fix nested episode folders (flatten to Season dir)
  plex-organizer --flatten --tv /plex/tv

  # Normalize episode filenames to Plex format
  plex-organizer --normalize --tv /plex/tv

  # Set up automatic scheduling
  sudo plex-organizer --schedule

  # Undo the last batch of moves
  plex-organizer --undo

  # Skip confirmation prompt
  plex-organizer --movies /plex/movies --yes
""",
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--movies",
        metavar="DIR",
        help="Path to movies directory to organize",
    )
    parser.add_argument(
        "--tv",
        metavar="DIR",
        help="Path to TV shows directory to organize",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without moving any files",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and execute immediately",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to YAML config file (default: ./config.yaml)",
    )
    parser.add_argument(
        "--tmdb-api-key",
        metavar="KEY",
        help="TMDb API key for genre auto-detection (or set TMDB_API_KEY env var)",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the last batch of moves from moves.json",
    )
    parser.add_argument(
        "--log-file",
        metavar="FILE",
        default="moves.json",
        help="Path to moves log file (default: ./moves.json)",
    )
    parser.add_argument(
        "--flatten",
        action="store_true",
        help="Flatten nested episode folders (move video files up to Season directory)",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize episode filenames to Plex format (Show - SXXEXX - Title.ext)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove junk files (.nfo, torrent ads, screenshots, empty dirs)",
    )
    parser.add_argument(
        "--refresh-plex",
        action="store_true",
        help="Trigger Plex library scan after organizing",
    )
    parser.add_argument(
        "--plex-token",
        metavar="TOKEN",
        help="Plex auth token (or set PLEX_TOKEN env var; auto-detected from Preferences.xml)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Interactive setup for automatic scheduling (requires sudo)",
    )

    args = parser.parse_args()

    # Handle schedule setup
    if args.schedule:
        setup_schedule()
        sys.exit(0)

    # Handle flatten
    if args.flatten:
        tv_dir = args.tv
        if not tv_dir:
            config = load_config(args.config)
            tv_dir = config.tv_dir
        if not tv_dir:
            parser.error("--flatten requires --tv or tv_dir in config")
        print(f"Flattening nested episodes in: {tv_dir}")
        moves = flatten_episodes(tv_dir, dry_run=args.dry_run)
        if moves:
            for m in moves:
                tag = "[DRY RUN] " if args.dry_run else ""
                print(f"  {tag}{os.path.basename(m['source'])} -> {os.path.dirname(m['destination'])}/")
            print(f"\n{'Would flatten' if args.dry_run else 'Flattened'} {len(moves)} files.")
        else:
            print("  No nested episodes found. All clean.")
        sys.exit(0)

    # Handle normalize
    if args.normalize:
        tv_dir = args.tv
        if not tv_dir:
            config = load_config(args.config)
            tv_dir = config.tv_dir
        if not tv_dir:
            parser.error("--normalize requires --tv or tv_dir in config")
        print(f"Normalizing episode names in: {tv_dir}")
        renames = normalize_episode_names(tv_dir, dry_run=args.dry_run)
        if renames:
            for r in renames:
                tag = "[DRY RUN] " if args.dry_run else ""
                print(f"  {tag}{r['old_name']}")
                print(f"    -> {r['new_name']}")
                print()
            print(f"{'Would rename' if args.dry_run else 'Renamed'} {len(renames)} files.")
        else:
            print("  All episodes already in proper format.")
        sys.exit(0)

    # Handle cleanup
    if args.cleanup:
        dirs_to_clean = []
        if args.movies:
            dirs_to_clean.append(args.movies)
        if args.tv:
            dirs_to_clean.append(args.tv)
        if not dirs_to_clean:
            config = load_config(args.config)
            if config.movies_dir:
                dirs_to_clean.append(config.movies_dir)
            if config.tv_dir:
                dirs_to_clean.append(config.tv_dir)
        if not dirs_to_clean:
            parser.error("--cleanup requires --movies or --tv (or set in config)")
        for d in dirs_to_clean:
            print(f"Cleaning junk in: {d}")
            result = cleanup_junk(d, dry_run=args.dry_run)
            tag = "[DRY RUN] " if args.dry_run else ""
            if result["files"]:
                for f in result["files"][:20]:
                    print(f"  {tag}Removed: {os.path.basename(f)}")
                if len(result["files"]) > 20:
                    print(f"  ... and {len(result['files']) - 20} more files")
            if result["dirs"]:
                for d_path in result["dirs"][:10]:
                    print(f"  {tag}Removed dir: {d_path}")
                if len(result["dirs"]) > 10:
                    print(f"  ... and {len(result['dirs']) - 10} more dirs")
            if not result["files"] and not result["dirs"]:
                print("  Already clean.")
            else:
                print(f"  {'Would remove' if args.dry_run else 'Removed'} {len(result['files'])} files, {len(result['dirs'])} directories")
        sys.exit(0)

    # Handle undo
    if args.undo:
        count = undo_moves(args.log_file)
        if count > 0:
            print(f"\nSuccessfully undone {count} moves.")
        sys.exit(0)

    # Must specify at least --movies or --tv
    if not args.movies and not args.tv:
        parser.error("At least one of --movies or --tv is required (or use --undo)")

    # Load config
    config = load_config(args.config)

    # CLI args override config file
    if args.movies:
        config.movies_dir = args.movies
    if args.tv:
        config.tv_dir = args.tv

    # TMDb API key: CLI > env var > config file
    tmdb_key = args.tmdb_api_key or os.environ.get("TMDB_API_KEY") or config.tmdb_api_key
    if tmdb_key:
        config.tmdb_api_key = tmdb_key

    # Create organizer
    organizer = PlexOrganizer(config)

    # Plan moves
    total_moves = []

    if config.movies_dir:
        print(f"Scanning movies: {config.movies_dir}")
        movie_moves = organizer.plan_movies(config.movies_dir)
        total_moves.extend(movie_moves)
        print(f"  Found {len(movie_moves)} movie moves")

    if config.tv_dir:
        # Flatten nested episodes first
        flat_moves = flatten_episodes(config.tv_dir, dry_run=args.dry_run)
        if flat_moves:
            print(f"\nFlattened {len(flat_moves)} nested episodes")

        # Normalize episode names
        norm_renames = normalize_episode_names(config.tv_dir, dry_run=args.dry_run)
        if norm_renames:
            print(f"Normalized {len(norm_renames)} episode filenames")

        print(f"\nScanning TV shows: {config.tv_dir}")
        tv_moves = organizer.plan_tv(config.tv_dir)
        total_moves.extend(tv_moves)
        print(f"  Found {len(tv_moves)} TV show moves")

    if not total_moves:
        print("\nNothing to organize. All files appear to be in the right place.")
        sys.exit(0)

    # Show preview
    organizer.moves = total_moves
    print(f"\n{organizer.preview()}")

    if args.dry_run:
        print("[DRY RUN] No files were moved.")
        sys.exit(0)

    # Confirm unless --yes
    if not args.yes:
        try:
            response = input(f"\nProceed with {len(total_moves)} moves? [y/N] ")
            if response.lower() not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

    # Execute
    count = organizer.execute(args.log_file)
    print(f"\nDone! Moved {count} files.")
    print(f"Move log saved to: {args.log_file}")
    print("Use --undo to reverse these changes.")

    # Cleanup junk after organizing
    dirs_to_clean = []
    if config.movies_dir:
        dirs_to_clean.append(config.movies_dir)
    if config.tv_dir:
        dirs_to_clean.append(config.tv_dir)
    for d in dirs_to_clean:
        result = cleanup_junk(d)
        if result["files"] or result["dirs"]:
            print(f"Cleaned {len(result['files'])} junk files, {len(result['dirs'])} empty dirs from {d}")

    # Refresh Plex
    if args.refresh_plex or os.environ.get("PLEX_TOKEN"):
        token = args.plex_token or os.environ.get("PLEX_TOKEN")
        print("\nRefreshing Plex libraries...")
        if empty_trash("1", token=token):
            print("  Emptied trash")
        if empty_trash("2", token=token):
            print("  Emptied trash (Films)")
        if refresh_library(token=token):
            print("  Library scan triggered")
        else:
            print("  Could not trigger Plex refresh")


if __name__ == "__main__":
    main()
