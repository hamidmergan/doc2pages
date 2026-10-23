"""The one GET behind an image URL, with every HTTP library this package may find.

A server that answers with a redirect or with an error must look the same whichever
library is installed, else a picture arrives in the dev environment and an error page
arrives in the container.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from doc2pages import client

PICTURE = b"not-a-real-picture"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "/picture.webp")
            self.end_headers()
            return
        if self.path == "/picture.webp":
            self.send_response(200)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Content-Length", str(len(PICTURE)))
            self.end_headers()
            self.wfile.write(PICTURE)
            return
        body = b"<html>not found</html>"
        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def host():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def _libraries():
    """Every way _fetch can take on this machine, the standard library included."""
    ways = [("urllib", None)]
    for name in client._HTTP_LIBRARIES:
        try:
            ways.append((name, __import__(name)))
        except ImportError:
            continue
    return ways


@pytest.mark.parametrize("name,library", _libraries(), ids=lambda v: getattr(v, "__name__", v))
def test_every_http_library_follows_a_redirect_and_raises_on_an_error(monkeypatch, host,
                                                                      name, library):
    monkeypatch.setattr(client, "_http_library", lambda: library)
    assert client._fetch(f"{host}/picture.webp", 10.0) == PICTURE
    # A picture behind a redirect is what S3 and most content networks hand out.
    assert client._fetch(f"{host}/moved", 10.0) == PICTURE
    # An error page must never reach the picture reader as if it were a picture.
    with pytest.raises(Exception) as e:
        client._fetch(f"{host}/nothing", 10.0)
    assert "404" in str(e.value)


def test_the_library_the_package_installs_is_the_one_that_is_tried_first():
    assert client._HTTP_LIBRARIES[0] == "httpx2"
    assert client._http_library() is not None
