import ipaddress
import socket
import threading

import requests

from urllib.parse import urlsplit, urljoin

from flask import Response, abort, request, send_file

from config import (
    ALLOWED_HOSTS,
    ONLINE_MODE,
    UPSTREAM_TIMEOUT,
    MAX_DOWNLOAD_SIZE
)

from cache import get_cached, save_cached


_locks = {}
_locks_guard = threading.Lock()


def resource_lock(url):
    with _locks_guard:
        if url not in _locks:
            _locks[url] = threading.Lock()

        return _locks[url]


def validate_url(url):
    parts = urlsplit(url)

    if parts.scheme != "https":
        abort(403)

    host = (parts.hostname or "").lower()

    if host not in ALLOWED_HOSTS:
        abort(403)

    if parts.username or parts.password:
        abort(403)

    if parts.port not in (None, 443):
        abort(403)

    try:
        addresses = socket.getaddrinfo(host, 443)

        for result in addresses:
            ip = ipaddress.ip_address(result[4][0])

            if not ip.is_global:
                abort(403)

    except socket.gaierror:
        abort(502)

    return url


def modify_cookomix_js(content):
    try:
        
        js = content.decode("utf-8")

        js = js.replace(
            'noAds()}',
            '}'
        )

        return js.encode("utf-8")

    except (UnicodeDecodeError, AttributeError):
        
        print(f"BIG ERROR SA MERE")
        return content


def fetch_resource(url):
    print(f"[FETCH] {url}")
    validate_url(url)

    cached = get_cached(url)

    if cached:
        return send_file(
            cached[0],
            mimetype=cached[1],
            conditional=True
        )

    if not ONLINE_MODE:
        abort(404)

    with resource_lock(url):

        cached = get_cached(url)

        if cached:
            return send_file(
                cached[0],
                mimetype=cached[1],
                conditional=True
            )

        current = url

        for _ in range(5):

            validate_url(current)

            try:
                response = requests.get(
                    current,
                    timeout=UPSTREAM_TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 CookomixOffline/1.0",
                        "Accept": request.headers.get("Accept", "*/*")
                    }
                )
            except requests.RequestException:
                abort(502)

            if response.is_redirect:
                location = response.headers.get("Location")
                response.close()

                if not location:
                    abort(502)

                current = urljoin(current, location)
                continue

            if response.status_code != 200:
                status = response.status_code
                response.close()
                abort(status)

            content = bytearray()

            try:
                for chunk in response.iter_content(65536):
                    content.extend(chunk)

                    if len(content) > MAX_DOWNLOAD_SIZE:
                        abort(413)
            finally:
                response.close()

            if (
                urlsplit(current).path.endswith(".js")
                and ("cook_recipes.js" in urlsplit(current).path
                or "cook.js" in urlsplit(current).path)
                ):
                content = modify_cookomix_js(content)

            content_type = response.headers.get(
                "Content-Type",
                "application/octet-stream"
            )

            save_cached(
                current,
                bytes(content),
                content_type
            )

            # Cache under the original URL too, in case of redirects.
            if current != url:
                save_cached(
                    url,
                    bytes(content),
                    content_type
                )



            return Response(
                bytes(content),
                status=200,
                content_type=content_type,
                headers={"Cache-Control": "no-cache"}
            )

        abort(502)
