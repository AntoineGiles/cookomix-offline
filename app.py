from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    send_file,
    Response
)

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, urljoin, quote

from bs4 import BeautifulSoup

from config import SECRET_KEY, RECIPES_DIR

from database import (
    init_db,
    get_recipes,
    get_recipe
)

from importer import import_recipe
from cache import get_cached
from proxy import fetch_resource, validate_url


app = Flask(__name__)
app.secret_key = SECRET_KEY

init_db()


def rewrite_html(html, original_url):
    soup = BeautifulSoup(html, "html.parser")

    def rewrite(value):
        if not value:
            return value

        absolute = urljoin(original_url, value)
        parts = urlsplit(absolute)

        if parts.scheme not in ("http", "https"):
            return value

        if parts.hostname not in (
            "cookomix.com",
            "www.cookomix.com"
        ):
            return value

        upstream = urlunsplit((
            "https",
            parts.netloc,
            parts.path,
            parts.query,
            ""
        ))

        cached = get_cached(upstream)

        if cached:
            return "/cached/" + quote(upstream, safe="")

        return "/fetch/" + quote(upstream, safe="")

    # Standard resource attributes.
    for tag in soup.find_all(["img", "script", "iframe", "source", "audio", "video"]):
        for attr in ("src", "poster"):
            if tag.has_attr(attr):
                tag[attr] = rewrite(tag[attr])

    # Stylesheets, icons and preload references.
    for tag in soup.find_all(["link"]):
        if tag.has_attr("href"):
            rel = tag.get("rel", [])

            if any(x in rel for x in [
                "stylesheet", "icon", "preload", "manifest"
            ]):
                tag["href"] = rewrite(tag["href"])

    # Inline CSS.
    import re

    for tag in soup.find_all(style=True):
        tag["style"] = re.sub(
            r"url\(['\"]?(.*?)['\"]?\)",
            lambda m: "url('" + rewrite(m.group(1)) + "')",
            tag["style"]
        )

    # CSS embedded in style tags.
    for style in soup.find_all("style"):
        css = style.string or style.get_text()

        css = re.sub(
            r"url\(['\"]?(.*?)['\"]?\)",
            lambda m: "url('" + rewrite(m.group(1)) + "')",
            css
        )

        style.string = css

    for script in soup.find_all("script"):
        if script.string and "cookomix.com/assets/1496/cook.js" in script.string:
            script.string = script.string.replace(
                "https://www.cookomix.com/assets/1496/cook.js",
                "/fetch/" + quote(
                "https://www.cookomix.com/assets/1496/cook.js",
                safe=""
                )
            )

    return str(soup)


@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "media-src 'self' blob:; "
        "frame-src 'self'; "
        "worker-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'"
    )

    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


@app.get("/")
def index():
    return render_template(
        "index.html",
        recipes=get_recipes()
    )


@app.post("/add")
def add():
    url = request.form.get("url", "").strip()

    try:
        recipe = import_recipe(url)
        flash(f"Imported: {recipe['title']}", "success")

    except Exception as exc:
        flash(str(exc), "error")

    return redirect(url_for("index"))


@app.get("/recipe/<int:recipe_id>")
def recipe(recipe_id):
    item = get_recipe(recipe_id)

    if not item:
        abort(404)

    html_file = Path(item["directory"]) / "index.html"

    if not html_file.is_file():
        abort(404)

    original_html = html_file.read_text(encoding="utf-8")

    rewritten = rewrite_html(
        original_html,
        item["url"]
    )

    return Response(
        rewritten,
        content_type="text/html; charset=utf-8"
    )


@app.route("/<path:path>", methods=["GET", "HEAD"])
def resource_fallback(path):
    if path in ("", "favicon.ico"):
        abort(404)

    # Do not proxy management routes.
    if path in ("add",) or path.startswith(("recipe/", "fetch/", "cached/")):
        abort(404)

    url = "https://www.cookomix.com/" + path

    return fetch_resource(url)


@app.route("/fetch/<path:url>", methods=["GET", "HEAD"])
def fetch(url):
    from urllib.parse import unquote

    return fetch_resource(unquote(url))


@app.route("/cached/<path:url>", methods=["GET", "HEAD"])
def cached(url):
    from urllib.parse import unquote

    url = unquote(url)
    validate_url(url)

    item = get_cached(url)

    if not item:
        abort(404)

    return send_file(
        item[0],
        mimetype=item[1],
        conditional=True
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=False
    )
