import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

RECIPES_DIR = DATA_DIR / "recipes"
CACHE_DIR = DATA_DIR / "resources"
DB_PATH = DATA_DIR / "cookomix.db"

ALLOWED_HOSTS = {
    "cookomix.com",
    "www.cookomix.com",
}

CANONICAL_HOST = "www.cookomix.com"

UPSTREAM_TIMEOUT = 30
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024

# False: never fetch uncached resources.
# True: fetch resources on demand.
ONLINE_MODE = True

SECRET_KEY = os.environ.get(
    "FLASK_SECRET_KEY",
    "replace-this-with-a-random-secret"
)

for directory in (DATA_DIR, RECIPES_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
