import hashlib
from pathlib import Path
from urllib.parse import urlsplit

from config import CACHE_DIR
from database import connect


def cache_path(url):
    parts = urlsplit(url)

    relative = Path(parts.netloc) / parts.path.lstrip("/")

    if not parts.path or parts.path.endswith("/"):
        relative = relative / "index"

    if parts.query:
        suffix = hashlib.sha256(
            parts.query.encode()
        ).hexdigest()[:16]

        relative = relative.with_name(
            relative.name + "_" + suffix
        )

    destination = (CACHE_DIR / relative).resolve()

    if CACHE_DIR.resolve() not in destination.parents:
        raise ValueError("Invalid cache path")

    return destination


def get_cached(url):
    with connect() as db:
        row = db.execute("""
            SELECT file_path, content_type
            FROM resources
            WHERE url = ?
        """, (url,)).fetchone()

    if row and Path(row["file_path"]).is_file():
        return Path(row["file_path"]), row["content_type"]

    return None


def save_cached(url, content, content_type):
    destination = cache_path(url)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_name(
        destination.name + ".tmp"
    )

    temporary.write_bytes(content)
    temporary.replace(destination)

    with connect() as db:
        db.execute("""
            INSERT OR REPLACE INTO resources
            (url, file_path, content_type, size, cached_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            url,
            str(destination),
            content_type,
            len(content)
        ))

    return destination
