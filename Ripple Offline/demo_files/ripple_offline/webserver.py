"""A web service built out of Python's own library and nothing else.

The packaged build of Ripple runs on FastAPI and uvicorn. Neither can be
installed on a machine that refuses installs, so this stands in their place.

It is deliberately small. Every route in ``app.py`` is a plain function that
takes what it needs and returns a dictionary, exactly as it does under FastAPI,
so the two versions of the service read almost identically and neither has any
thinking in it. What is here is only the plumbing: match a request to a
function, hand it the body, and turn the answer into JSON.

The shape of every reply is the one the screens already expect:

    a success   the function's dictionary or list, as JSON
    a refusal   {"detail": "one sentence a person can act on"} and a status

Get that wrong and every error on screen becomes the number 500, which tells
nobody anything.
"""
from __future__ import annotations

import json
import re
import socket
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


class HTTPError(Exception):
    """A refusal with a status and a sentence. The same idea as FastAPI's
    HTTPException, so the route bodies do not have to change."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# What a file is served as. Anything not here is sent as bytes, which every
# browser handles; guessing a type is how a font arrives as text and the page
# renders in the wrong one.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

# A path piece written as {name} in a route becomes a value handed to the
# function. Everything else has to match exactly.
_PARAM = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class Router:
    """Which function answers which request."""

    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern, object]] = []
        self._static: tuple[str, Path] | None = None
        self._index: Path | None = None

    def route(self, method: str, path: str):
        pattern = re.compile("^" + _PARAM.sub(r"(?P<\1>[^/]+)", re.escape(path)
                                              .replace(r"\{", "{").replace(r"\}", "}")) + "$")

        def keep(fn):
            self._routes.append((method.upper(), pattern, fn))
            return fn
        return keep

    def get(self, path: str):
        return self.route("GET", path)

    def post(self, path: str):
        return self.route("POST", path)

    def patch(self, path: str):
        return self.route("PATCH", path)

    def mount(self, prefix: str, folder: Path) -> None:
        self._static = (prefix.rstrip("/"), Path(folder))

    def index(self, file: Path) -> None:
        self._index = Path(file)

    def find(self, method: str, path: str):
        """The function for this request, and the values out of its path.

        A path that matches on the address but not the method is told so, rather
        than reported as missing: "405" and "404" send somebody looking in two
        completely different places.
        """
        wrong_method = False
        for m, pattern, fn in self._routes:
            found = pattern.match(path)
            if found is None:
                continue
            if m != method:
                wrong_method = True
                continue
            return fn, found.groupdict()
        if wrong_method:
            raise HTTPError(405, f"{path} does not answer a {method}.")
        return None, {}


# ── reading what the browser sent ──────────────────────────────────────────
def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    size = int(handler.headers.get("Content-Length") or 0)
    return handler.rfile.read(size) if size else b""


def _multipart(raw: bytes, content_type: str) -> tuple[str, bytes]:
    """The one uploaded file out of a form: its name and its bytes.

    Written by hand because the package that normally does this is one more
    install. Only the shape the screen actually sends is handled -- a single
    file field -- and anything else is refused out loud rather than half-read.
    An email that arrives empty extracts nothing, and the screen then shows a
    confident blank form as though the message said nothing at all.
    """
    marker = "boundary="
    if marker not in content_type:
        raise HTTPError(400, "That upload was not a form Ripple could read.")
    boundary = content_type.split(marker, 1)[1].strip().strip('"')
    sep = b"--" + boundary.encode()
    for part in raw.split(sep):
        head, _, body = part.partition(b"\r\n\r\n")
        if b"filename=" not in head:
            continue
        name = ""
        found = re.search(rb'filename="([^"]*)"', head)
        if found:
            name = unquote(found.group(1).decode("utf-8", "replace"))
        # Every part ends with the line break that introduces the next
        # boundary. Left on, it is two stray bytes on the end of the file.
        return name, body[:-2] if body.endswith(b"\r\n") else body
    raise HTTPError(400, "No file was found in that upload.")


def _call(fn, params: dict, query: dict, handler: BaseHTTPRequestHandler):
    """Hand the route function what it asked for, and nothing else."""
    import inspect                                            # noqa: PLC0415
    wanted = inspect.signature(fn).parameters
    args: dict = {}
    for name in wanted:
        if name in params:
            args[name] = params[name]
        elif name == "body":
            raw = _read_body(handler)
            args[name] = json.loads(raw or b"{}")
        elif name == "upload":
            args[name] = _multipart(_read_body(handler),
                                    handler.headers.get("Content-Type") or "")
        elif name in query:
            args[name] = query[name][0]
        else:
            args[name] = ""
    return fn(**args)


def make_handler(router: Router):
    class Handler(BaseHTTPRequestHandler):
        # The default writes a line to the console for every request, which on a
        # scan that polls progress every second buries anything worth reading.
        def log_message(self, *_args) -> None:
            return

        protocol_version = "HTTP/1.1"

        def _send(self, status: int, body: bytes, ctype: str, cache: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError):
                # The page was closed or refreshed mid-request. Ordinary, and
                # not worth a stack trace in a window somebody is working in.
                pass

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"),
                       "application/json", "no-store, must-revalidate")

        def _serve_file(self, file: Path) -> None:
            if not file.is_file():
                self._json(404, {"detail": "Not found."})
                return
            # The page and its script are never cached: during a demo that is
            # the difference between seeing a change and staring at yesterday's
            # page. Fonts are cached -- they never change and they are large.
            cache = ("public, max-age=2592000" if file.suffix == ".woff2"
                     else "no-store, must-revalidate")
            self._send(200, file.read_bytes(),
                       CONTENT_TYPES.get(file.suffix.lower(), "application/octet-stream"),
                       cache)

        def _handle(self, method: str) -> None:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            try:
                if method == "GET" and router._static:
                    prefix, folder = router._static
                    if path.startswith(prefix + "/"):
                        wanted = (folder / path[len(prefix) + 1:]).resolve()
                        # Never serve outside the web folder, whatever the
                        # address asks for. ../../ in a URL is the oldest trick
                        # there is and this server is on somebody's own machine.
                        if folder.resolve() in wanted.parents or wanted == folder.resolve():
                            self._serve_file(wanted)
                        else:
                            self._json(404, {"detail": "Not found."})
                        return
                if method == "GET" and path == "/" and router._index:
                    self._serve_file(router._index)
                    return

                fn, params = router.find(method, path)
                if fn is None:
                    self._json(404, {"detail": f"{path} is not something Ripple answers."})
                    return
                out = _call(fn, params, parse_qs(parsed.query), self)
                self._json(200, out)
            except HTTPError as exc:
                self._json(exc.status_code, {"detail": exc.detail})
            except json.JSONDecodeError:
                self._json(400, {"detail": "That request was not readable JSON."})
            except Exception as exc:                          # noqa: BLE001
                # The message, not just the status. "Something went wrong: 500"
                # on screen tells nobody what to do next, and this window is the
                # whole product.
                traceback.print_exc()
                self._json(500, {"detail": f"{type(exc).__name__}: {exc}"})

        def do_GET(self) -> None:                             # noqa: N802
            self._handle("GET")

        def do_POST(self) -> None:                            # noqa: N802
            self._handle("POST")

        def do_PATCH(self) -> None:                           # noqa: N802
            self._handle("PATCH")

    return Handler


def free_port(first: int = 8000, last: int = 8020) -> int:
    """The first port in the range nothing else is holding.

    Fixing the port is fine until the day something else on the machine already
    has it, and then Ripple stops with a socket error that names no application
    and tells nobody what to close -- on the one machine where nobody can go and
    look.
    """
    for port in range(first, last + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(
        f"Every port from {first} to {last} is already in use on this machine. "
        f"Close whatever is using them and start Ripple again.")


def serve(router: Router, port: int) -> ThreadingHTTPServer:
    """Start answering, on a thread, and hand back the server so it can be
    stopped. Threaded because the screen asks what the scan is doing WHILE the
    scan is running, and a single-threaded server would answer that only once
    the scan it is asking about had finished."""
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(router))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="ripple-web", daemon=True).start()
    return server
