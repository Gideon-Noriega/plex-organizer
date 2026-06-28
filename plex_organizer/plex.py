"""Plex server integration: library scan triggers and status checks."""

import os
import re
import urllib.request
import urllib.error


def get_plex_token():
    """Try to read the Plex token from the local Preferences.xml."""
    prefs_paths = [
        "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml",
        os.path.expanduser("~/Library/Application Support/Plex Media Server/Preferences.xml"),
    ]
    for path in prefs_paths:
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    content = f.read()
                match = re.search(r'PlexOnlineToken="([^"]+)"', content)
                if match:
                    return match.group(1)
            except PermissionError:
                pass
    return None


def refresh_library(section_id=None, plex_url="http://localhost:32400", token=None):
    """
    Trigger a Plex library scan.

    Args:
        section_id: Library section ID to scan (None = all sections)
        plex_url: Plex server URL
        token: Plex auth token (auto-detected if None)

    Returns:
        True if scan was triggered successfully
    """
    if not token:
        token = os.environ.get("PLEX_TOKEN") or get_plex_token()
    if not token:
        print("  Warning: No Plex token found. Cannot trigger library refresh.")
        print("  Set PLEX_TOKEN env var or ensure Preferences.xml is readable.")
        return False

    try:
        if section_id:
            url = f"{plex_url}/library/sections/{section_id}/refresh?X-Plex-Token={token}"
        else:
            sections = _get_sections(plex_url, token)
            for sid in sections:
                url = f"{plex_url}/library/sections/{sid}/refresh?X-Plex-Token={token}"
                urllib.request.urlopen(url)
            return True

        urllib.request.urlopen(url)
        return True
    except urllib.error.URLError as e:
        print(f"  Warning: Could not reach Plex server: {e}")
        return False


def empty_trash(section_id, plex_url="http://localhost:32400", token=None):
    """Empty trash for a library section."""
    if not token:
        token = os.environ.get("PLEX_TOKEN") or get_plex_token()
    if not token:
        return False

    try:
        url = f"{plex_url}/library/sections/{section_id}/emptyTrash?X-Plex-Token={token}"
        req = urllib.request.Request(url, method="PUT")
        urllib.request.urlopen(req)
        return True
    except urllib.error.URLError:
        return False


def _get_sections(plex_url, token):
    """Get all library section IDs."""
    try:
        url = f"{plex_url}/library/sections?X-Plex-Token={token}"
        response = urllib.request.urlopen(url)
        content = response.read().decode()
        return re.findall(r'key="(\d+)"', content)
    except urllib.error.URLError:
        return []
