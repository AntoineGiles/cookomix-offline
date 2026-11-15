import sqlite3
from config import DB_PATH


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                slug TEXT NOT NULL,
                directory TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                url TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                content_type TEXT,
                size INTEGER DEFAULT 0,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def get_recipes():
    with connect() as db:
        return db.execute("""
            SELECT * FROM recipes
            ORDER BY created_at DESC
        """).fetchall()


def get_recipe(recipe_id):
    with connect() as db:
        return db.execute(
            "SELECT * FROM recipes WHERE id = ?",
            (recipe_id,)
        ).fetchone()


def add_recipe(url, title, slug, directory):
    with connect() as db:
        db.execute("""
            INSERT INTO recipes (url, title, slug, directory)
            VALUES (?, ?, ?, ?)
        """, (url, title, slug, str(directory)))


def recipe_exists(url):
    with connect() as db:
        return db.execute(
            "SELECT id FROM recipes WHERE url = ?",
            (url,)
        ).fetchone() is not None
