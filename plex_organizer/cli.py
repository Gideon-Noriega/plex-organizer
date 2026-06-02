"""Command-line interface for plex-organizer."""

import argparse
import os
import sys

from . import __version__
from .config import Config, load_config
from .organizer import PlexOrganizer, undo_moves


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

    args = parser.parse_args()

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
        print(f"\nScanning TV shows: {config.tv_dir}")
        tv_moves = organizer.plan_tv(config.tv_dir)
        total_moves.extend(tv_moves)
        print(f"  Found {len(tv_moves)} TV show moves")

    if not total_moves:
        print("\nNothing to organize. All files appear to be in the right place.")
        sys.exit(0)

    # Show preview
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


if __name__ == "__main__":
    main()
