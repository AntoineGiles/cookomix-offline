import re
import shutil
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from config import (
    ALLOWED_HOSTS,
    CANONICAL_HOST,
    RECIPES_DIR,
    UPSTREAM_TIMEOUT,
    MAX_DOWNLOAD_SIZE
)

from database import add_recipe, recipe_exists


def normalize_url(url):
    parts = urlsplit(url.strip())

    if parts.scheme not in ("http", "https"):
        raise ValueError("Invalid URL scheme")

    host = (parts.hostname or "").lower()

    if host not in ALLOWED_HOSTS:
        raise ValueError("Only Cookomix URLs are supported")

    if parts.username or parts.password:
        raise ValueError("URL credentials are not allowed")

    if parts.port not in (None, 80, 443):
        raise ValueError("Custom ports are not allowed")

    return urlunsplit((
        "https",
        CANONICAL_HOST,
        parts.path or "/",
        parts.query,
        ""
    ))


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:100] or "recipe"


def download_html(url):
    response = requests.get(
        url,
        timeout=UPSTREAM_TIMEOUT,
        allow_redirects=False,
        headers={"User-Agent": "CookomixOffline/1.0"},
        stream=True
    )

    if response.is_redirect:
        response.close()
        raise ValueError("Recipe URL redirected; import its final URL instead")

    response.raise_for_status()

    content = bytearray()

    for chunk in response.iter_content(65536):
        content.extend(chunk)

        if len(content) > MAX_DOWNLOAD_SIZE:
            response.close()
            raise ValueError("Recipe HTML is too large")

    response.close()

    return bytes(content)


def import_recipe(url):
    url = normalize_url(url)

    if recipe_exists(url):
        raise ValueError("Recipe already exists")

    html = download_html(url)

    soup = BeautifulSoup(html, "html.parser")

    title = (
        soup.title.get_text(strip=True)
        if soup.title else "Cookomix recipe"
    )

    slug = slugify(
        urlsplit(url).path.rstrip("/").split("/")[-1]
    )

    directory = RECIPES_DIR / slug

    if directory.exists():
        raise ValueError("Recipe directory already exists")

    directory.mkdir(parents=True)

    try:
        (directory / "index.html").write_bytes(html)

        add_recipe(
            url,
            title,
            slug,
            directory
        )

    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    return {
        "title": title,
        "slug": slug
    }
