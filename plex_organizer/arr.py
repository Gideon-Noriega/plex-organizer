"""Tell Sonarr and Radarr where files went after this tool renames them.

Both *arrs have renaming turned off (`renameEpisodes` and `renameMovies` are
false), so they import a release under its original name and this tool renames
and relocates it afterwards. Nothing tells the *arr, so its database goes on
pointing at a path that no longer exists.

That is not cosmetic. An *arr that has lost track of a file cannot upgrade or
replace it, so the next grab for the same episode or movie lands BESIDE the
existing copy instead of over it. That is where duplicate media comes from. When
this module was written, on 2026-08-29, thirty tracked files were in that state
and `The Gentleman Thief (2026)` held both a .mp4 and a .mkv of the same film
that Radarr could see neither of.

The drift arrives in two layers, and both are repaired here:

  * the show or movie FOLDER was renamed -- Sonarr held `/data/tv/The Dark`
    while the disk had `The Dark (2026)`. The record is repointed with
    `moveFiles=false`, which updates the database without touching the disk.
  * the FILENAME was normalised inside a folder that is still correct. A rescan
    of that one folder is enough.

Reconciling against the *arr's own records, rather than against this tool's move
log, is deliberate: `flatten_episodes` and `normalize_episode_names` rename files
without going through `PlexOrganizer.execute`, so they never appear in
moves.json. Comparing the database to the disk catches every path equally, and
clears drift that accumulated before this module existed.

Configure with environment variables; no credentials are read from config.yaml:

    SONARR_URL, SONARR_API_KEY
    RADARR_URL, RADARR_API_KEY

A missing API key simply disables that half of the sync.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

_API_ERRORS = (urllib.error.URLError, urllib.error.HTTPError, OSError)

# The *arrs see the media tree through a single /plex => /data bind mount, so
# host <-> container is one prefix swap. Keep this in step with media-stack; if
# the mounts are ever split, hardlinking breaks and so does this.
HOST_ROOT = "/plex"
CONTAINER_ROOT = "/data"


def to_container(path):
    """Host path (/plex/...) -> the path an *arr uses (/data/...), or None."""
    if path == HOST_ROOT:
        return CONTAINER_ROOT
    if path.startswith(HOST_ROOT + "/"):
        return CONTAINER_ROOT + path[len(HOST_ROOT):]
    return None


def to_host(path):
    """Path as an *arr reports it (/data/...) -> host path (/plex/...), or None.

    None means the path lies outside the bind mount, so it does not exist in
    the container at all. Passing it through unchanged instead would compare
    container paths against host paths and quietly match nothing.
    """
    if path == CONTAINER_ROOT:
        return HOST_ROOT
    if path.startswith(CONTAINER_ROOT + "/"):
        return HOST_ROOT + path[len(CONTAINER_ROOT):]
    return None


class ArrClient:
    """Minimal Sonarr/Radarr API v3 client."""

    def __init__(self, name, url, api_key):
        self.name = name
        self.url = url.rstrip("/")
        self.key = api_key

    def _req(self, method, path, body=None, **params):
        query = "?" + urllib.parse.urlencode(params) if params else ""
        req = urllib.request.Request(
            f"{self.url}/api/v3/{path.lstrip('/')}{query}",
            method=method,
            headers={"X-Api-Key": self.key, "Content-Type": "application/json"},
            data=json.dumps(body).encode() if body is not None else None,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else None

    def get(self, path, **params):
        return self._req("GET", path, None, **params)

    def put(self, path, body, **params):
        return self._req("PUT", path, body, **params)

    def post(self, path, body, **params):
        return self._req("POST", path, body, **params)


def clients_from_env(env=None):
    """Build the configured clients. An absent API key disables that half."""
    env = os.environ if env is None else env
    clients = {}
    for name, default_port in (("sonarr", 8989), ("radarr", 7878)):
        key = env.get(f"{name.upper()}_API_KEY")
        if not key:
            continue
        url = env.get(f"{name.upper()}_URL", f"http://localhost:{default_port}")
        clients[name] = ArrClient(name, url, key)
    return clients


def norm(name):
    """Fold a folder name for comparison: lowercase alphanumerics only."""
    return "".join(c for c in name.lower() if c.isalnum())


def candidate_dirs(root, depth):
    """Directories under root, down to `depth` levels.

    Movies need depth 2 because this tool files them under a genre folder;
    shows sit directly beneath the TV root, so depth 1 is enough.
    """
    found, level = [], [root]
    for _ in range(depth):
        nxt = []
        for base in level:
            try:
                entries = sorted(os.listdir(base))
            except OSError:
                continue
            for entry in entries:
                path = os.path.join(base, entry)
                if os.path.isdir(path):
                    found.append(path)
                    nxt.append(path)
        level = nxt
    return found


def relocated_folder(record, root, depth):
    """Find where a record's folder went after this tool renamed it.

    Matches on the record's own title and year rather than inferring from the
    old path, and only commits when exactly ONE candidate matches. Ambiguity is
    handed to a human rather than settled by a tie-break: plan_cleanup.py
    already demonstrated that a tie-break which is merely deterministic is not
    necessarily a safe one.

    Returns (folder or None, list of matching folders).
    """
    title = record.get("title") or ""
    if not title:
        return None, []
    year = record.get("year")

    wanted = {norm(title)}
    if year:
        wanted.add(norm(f"{title} ({year})"))

    matches = [d for d in candidate_dirs(root, depth)
               if norm(os.path.basename(d)) in wanted]
    return (matches[0] if len(matches) == 1 else None), matches


def has_files(name, record):
    """Whether the *arr believes this record has any file at all.

    Used to tell real drift from a title that is merely monitored and not yet
    downloaded: an *arr creates the folder on import, so no folder and no file
    is the normal state for something on the wanted list, not a fault.
    """
    if name == "radarr":
        return bool(record.get("hasFile"))
    stats = record.get("statistics") or {}
    return bool(stats.get("episodeFileCount"))


def tracked_files(client, name, record):
    """The file paths an *arr currently associates with one record."""
    if name == "radarr":
        mfile = record.get("movieFile")
        return [mfile["path"]] if mfile and mfile.get("path") else []
    try:
        files = client.get("episodefile", seriesId=record["id"]) or []
    except _API_ERRORS:
        return []
    return [f["path"] for f in files if f.get("path")]


def wait_command(client, command_id, timeout=300, interval=3):
    """Block until a queued *arr command finishes.

    Returns (status, exception_text). Status is the *arr's own terminal status,
    or "timeout" if it never reached one, or "unknown" if the command could not
    be polled at all.
    """
    if not command_id:
        return "unknown", "no command id returned"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            body = client.get(f"command/{command_id}") or {}
        except _API_ERRORS as exc:
            return "unknown", str(exc)
        status = body.get("status", "")
        if status in ("completed", "failed", "aborted"):
            return status, body.get("exception") or ""
    return "timeout", ""


# (name, resource, rescan command, id field, depth below the library root)
_TARGETS = (
    ("radarr", "movie", "RescanMovie", "movieId", 2),
    ("sonarr", "series", "RescanSeries", "seriesId", 1),
)


def sync(movies_dir=None, tv_dir=None, clients=None, dry_run=False,
         verbose=True):
    """Reconcile every *arr record against what is actually on disk.

    A record whose folder cannot be located unambiguously is reported and left
    alone. A tracked path can also be missing because the file was genuinely
    deleted, and that must never be repointed at a lookalike.

    Args:
        movies_dir: movie library root on the host, e.g. /plex/movies.
        tv_dir: TV library root on the host, e.g. /plex/tv.
        clients: mapping of name -> ArrClient; built from the environment when
            omitted.
        dry_run: report what would be sent without sending it.
        verbose: print a line per action.

    Returns:
        dict with counts: missing, repointed, rescanned, and a list of errors.
    """
    result = {"missing": 0, "repointed": 0, "rescanned": 0, "errors": []}
    clients = clients_from_env() if clients is None else clients
    if not clients:
        if verbose:
            print("arr sync: no SONARR_API_KEY or RADARR_API_KEY set, skipping")
        return result

    roots = {"radarr": movies_dir, "sonarr": tv_dir}

    for name, resource, command, id_field, depth in _TARGETS:
        client = clients.get(name)
        root = roots.get(name)
        if client is None or not root:
            continue
        root = os.path.normpath(root)

        try:
            records = client.get(resource) or []
        except _API_ERRORS as exc:
            result["errors"].append(f"{name}: could not read library ({exc})")
            continue

        pending = []
        for record in records:
            record_id = record["id"]
            folder = to_host(record.get("path") or "")
            if folder is None:
                result["errors"].append(
                    f"{name} {resource} {record_id}: path "
                    f"{record.get('path')!r} is outside the bind mount")
                continue

            needs_rescan = False

            if not os.path.isdir(folder):
                # Layer one: the folder itself was renamed or moved.
                new_folder, matches = relocated_folder(record, root, depth)
                if new_folder is None:
                    if not matches and not has_files(name, record):
                        # Monitored but never downloaded. No folder is correct.
                        continue
                    result["missing"] += 1
                    detail = (
                        f"nothing under {root} matches "
                        f"{record.get('title')!r}" if not matches else
                        f"{len(matches)} folders match "
                        f"{record.get('title')!r} "
                        # Show the path relative to the root: the basenames are
                        # identical, it is the genre folder that differs.
                        f"({', '.join(os.path.relpath(m, root) for m in matches)})")
                    result["errors"].append(
                        f"{name} {resource} {record_id}: {folder} is gone and "
                        f"{detail}; left alone")
                    continue
                result["missing"] += 1
                if dry_run:
                    if verbose:
                        print(f"  would repoint {name} {resource} {record_id}: "
                              f"{folder} -> {new_folder}")
                else:
                    try:
                        full = client.get(f"{resource}/{record_id}")
                        full["path"] = to_container(new_folder)
                        # moveFiles=false: the file is already where we want it.
                        client.put(f"{resource}/{record_id}", full,
                                   moveFiles="false")
                    except _API_ERRORS as exc:
                        result["errors"].append(
                            f"{name} {resource} {record_id}: repoint failed "
                            f"({exc})")
                        continue
                    if verbose:
                        print(f"  repointed {name} {resource} {record_id}: "
                              f"{folder} -> {new_folder}")
                result["repointed"] += 1
                needs_rescan = True
            else:
                # Layer two: the folder is right but filenames may have changed.
                for path in tracked_files(client, name, record):
                    host = to_host(path)
                    if host is None or not os.path.exists(host):
                        result["missing"] += 1
                        needs_rescan = True

            if not needs_rescan:
                continue
            if dry_run:
                if verbose:
                    print(f"  would {command} {name} {resource} {record_id}")
                result["rescanned"] += 1
                continue
            pending.append(record_id)

        # Rescans run only once every repoint for this *arr has landed. A rescan
        # queued in the same breath as its own PUT races the refresh that the PUT
        # itself triggers, and loses: it scans the path the record used to have,
        # finds nothing, and leaves the stale filenames in the database. Waiting
        # for each command also turns a silent no-op into a reported failure.
        for record_id in pending:
            try:
                queued = client.post("command", {"name": command,
                                                 id_field: record_id}) or {}
            except _API_ERRORS as exc:
                result["errors"].append(
                    f"{name} {resource} {record_id}: could not queue {command} "
                    f"({exc})")
                continue
            status, detail = wait_command(client, queued.get("id"))
            if status == "completed":
                result["rescanned"] += 1
                if verbose:
                    print(f"  {command} completed for {name} {resource} "
                          f"{record_id}")
                continue
            result["errors"].append(
                f"{name} {resource} {record_id}: {command} {status}"
                + (f" ({detail[:120]})" if detail else ""))

    if verbose:
        print(f"arr sync: {result['missing']} stale paths, "
              f"{result['repointed']} repointed, "
              f"{result['rescanned']} rescans queued")
        for err in result["errors"]:
            print(f"  needs a look: {err}")

    return result
