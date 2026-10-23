"""The web UI: the page, the upload, a whole run and the guards, all against the fake server."""

import time
import zipfile
from io import BytesIO

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from doc2pages.web.app import STEPS, allowed_host_names, create_app  # noqa: E402


def wait(client, seconds: float = 60.0) -> dict:
    """The status of the one run once it is no longer going."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        status = client.get("/api/status").json()
        if status["state"] in ("done", "error"):
            return status
        time.sleep(0.05)
    raise AssertionError("The run did not finish in time.")


def settings_of(server) -> dict:
    return {"base_url": server.base_url, "model": "your-model"}


@pytest.fixture
def client():
    with TestClient(create_app(allowed_hosts={"testserver", "localhost", "127.0.0.1"})) as c:
        yield c


def test_the_page_and_its_files_are_served(client):
    answer = client.get("/")
    assert answer.status_code == 200
    assert "doc2pages" in answer.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_the_info_names_the_formats_and_the_limits(client):
    info = client.get("/api/info").json()
    assert ".pdf" in info["extensions"]
    assert info["languages"] == ["de", "en"]
    assert info["max_files"] >= 1
    # Without a model in the environment the page has to ask for one.
    assert info["configured"] is False


def test_the_info_passes_on_what_the_environment_sets(monkeypatch, server):
    monkeypatch.setenv("DOC2PAGES_BASE_URL", server.base_url)
    monkeypatch.setenv("DOC2PAGES_MODEL", "your-model")
    monkeypatch.setenv("DOC2PAGES_IMAGES", "1")
    monkeypatch.setenv("DOC2PAGES_TRANSLATE_TO", "en")
    with TestClient(create_app()) as client:
        info = client.get("/api/info").json()
    assert info["configured"] is True
    assert info["model"] == "your-model"
    assert info["images"] is True
    assert info["translate_to"] == "en"


def test_an_unsupported_file_is_refused(client):
    answer = client.post("/api/upload", files={"files": ("picture.jpg", b"x", "image/jpeg")})
    assert answer.status_code == 400
    assert "not supported" in answer.json()["detail"]


def test_upload_lists_the_files_and_clear_empties_the_list(client, material):
    answer = client.post("/api/upload",
                         files={"files": (material.name, material.read_bytes(), "text/plain")})
    assert answer.status_code == 200
    assert answer.json()["files"] == [material.name]
    # A reloaded page finds the files again through the info.
    assert client.get("/api/info").json()["files"] == [material.name]
    assert client.post("/api/clear").json()["files"] == []
    assert client.get("/api/info").json()["files"] == []


def test_without_material_a_run_is_refused(client, server):
    answer = client.post("/api/create", json=settings_of(server))
    assert answer.status_code == 400
    assert "Upload material first" in answer.json()["detail"]


def test_without_a_model_the_run_says_which_setting_is_missing(client, material):
    client.post("/api/upload",
                files={"files": (material.name, material.read_bytes(), "text/plain")})
    answer = client.post("/api/create", json={})
    assert answer.status_code == 400
    assert "--base-url" in answer.json()["detail"]


def test_a_whole_run_gives_a_page_its_pictures_and_a_zip(client, server, material):
    client.post("/api/upload",
                files={"files": (material.name, material.read_bytes(), "text/plain")})
    started = client.post("/api/create", json=settings_of(server))
    assert started.status_code == 200
    assert started.json()["state"] == "running"

    status = wait(client)
    assert status["state"] == "done", status["error"]
    assert len(status["pages"]) == 1
    assert status["pages"][0]["title"] == "Lineare Regression"

    page = client.get("/api/page/0")
    assert page.status_code == 200
    assert "<html" in page.text.lower()
    assert "Lineare Regression" in page.text

    missing = client.get("/api/page/7")
    assert missing.status_code == 404

    bundle = client.get("/api/download")
    assert bundle.status_code == 200
    assert bundle.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(bundle.content)) as zipped:
        names = zipped.namelist()
    assert "index.html" in names
    assert any(n.endswith("page.md") for n in names)


def test_translation_gives_a_second_page(client, server, material):
    client.post("/api/upload",
                files={"files": (material.name, material.read_bytes(), "text/plain")})
    client.post("/api/create", json={**settings_of(server), "translate_to": "en"})
    status = wait(client)
    assert status["state"] == "done", status["error"]
    assert len(status["pages"]) == 2
    assert {p["language"] for p in status["pages"]} == {"de", "en"}


def test_the_title_picture_is_drawn_and_served_next_to_the_page(client, server, material):
    client.post("/api/upload",
                files={"files": (material.name, material.read_bytes(), "text/plain")})
    client.post("/api/create", json={**settings_of(server), "images": True})
    status = wait(client)
    assert status["state"] == "done", status["error"]
    assert server.images
    bundle = client.get("/api/download")
    names = zipfile.ZipFile(BytesIO(bundle.content)).namelist()
    picture = next(n for n in names if n.endswith(".webp"))
    assert client.get(f"/api/page/0/{picture.split('/')[-1]}").status_code == 200


def test_the_checkbox_can_switch_the_pictures_off_again(monkeypatch, server, material):
    monkeypatch.setenv("DOC2PAGES_BASE_URL", server.base_url)
    monkeypatch.setenv("DOC2PAGES_MODEL", "your-model")
    monkeypatch.setenv("DOC2PAGES_IMAGES", "1")
    with TestClient(create_app()) as client:
        client.post("/api/upload",
                    files={"files": (material.name, material.read_bytes(), "text/plain")})
        client.post("/api/create", json={"images": False})
        status = wait(client)
    assert status["state"] == "done", status["error"]
    assert not server.images


def test_a_broken_model_server_ends_in_an_error_the_page_can_show(client, server, material):
    server.status = 500
    client.post("/api/upload",
                files={"files": (material.name, material.read_bytes(), "text/plain")})
    client.post("/api/create", json=settings_of(server))
    status = wait(client)
    assert status["state"] == "error"
    assert status["error"]


def test_an_unknown_host_is_refused(material):
    with TestClient(create_app(allowed_hosts={"localhost"})) as client:
        answer = client.get("/", headers={"host": "evil.example"})
    assert answer.status_code == 400
    assert "Unknown host" in answer.text


def test_another_origin_is_refused(client):
    answer = client.get("/", headers={"origin": "http://evil.example"})
    assert answer.status_code == 403
    assert "Cross-origin" in answer.text


def test_the_own_origin_is_allowed(client):
    assert client.get("/", headers={"origin": "http://testserver"}).status_code == 200


def test_a_too_large_upload_is_refused_before_it_is_read(monkeypatch, server):
    monkeypatch.setenv("DOC2PAGES_BASE_URL", server.base_url)
    monkeypatch.setenv("DOC2PAGES_MODEL", "your-model")
    monkeypatch.setenv("DOC2PAGES_MAX_FILES", "1")
    monkeypatch.setenv("DOC2PAGES_MAX_FILE_MB", "0.001")
    with TestClient(create_app()) as client:
        answer = client.post("/api/upload",
                             files={"files": ("big.txt", b"x" * (3 * 1024 * 1024), "text/plain")})
    assert answer.status_code == 413


def test_a_second_browser_sees_the_run_that_is_going_and_its_result(server, material):
    """A reload or a second tab is a second client against the same server.

    The run lives on the server, not in the page, so the second client has to find the
    uploaded files, the step of the run that is going and the finished page.
    """
    app = create_app(allowed_hosts={"testserver", "localhost", "127.0.0.1"})
    # Every model answer waits a moment, so the run is still going when the second client asks.
    server.delay = 0.3
    with TestClient(app) as first:
        second = TestClient(app)
        first.post("/api/upload",
                   files={"files": (material.name, material.read_bytes(), "text/plain")})
        started = first.post("/api/create", json=settings_of(server))
        assert started.json()["state"] == "running"

        # The second client knows nothing of the first one and still finds everything.
        info = second.get("/api/info").json()
        assert info["files"] == [material.name]
        status = second.get("/api/status").json()
        assert status["state"] == "running"
        assert status["step"] in STEPS

        # A second run while the first is going is refused, from either client.
        assert second.post("/api/create", json=settings_of(server)).status_code == 409
        assert second.post("/api/upload", files={
            "files": (material.name, material.read_bytes(), "text/plain")}).status_code == 409

        done = wait(second)
        assert done["state"] == "done", done["error"]
        assert second.get("/api/page/0").status_code == 200
        assert first.get("/api/status").json()["state"] == "done"


def test_the_host_check_stays_on_when_the_server_listens_on_every_interface():
    """A container publishes a port, the browser still sends a loopback name."""
    from doc2pages.web.app import allowed_host_names

    names = allowed_host_names("0.0.0.0")
    assert names is not None
    assert set(names) >= {"localhost", "127.0.0.1", "::1"}
    # The address it was started with counts too, and a port is never part of a name.
    assert "example.org" in allowed_host_names("example.org:8000")
    # Named hosts replace the default set, "*" switches the check off.
    assert allowed_host_names("0.0.0.0", ["pages.example.org"]) == ["pages.example.org"]
    assert allowed_host_names("0.0.0.0", ["*"]) is None


def test_a_container_refuses_a_foreign_host_name(material):
    app = create_app(allowed_hosts=allowed_host_names("0.0.0.0"))
    with TestClient(app, base_url="http://127.0.0.1") as local:
        assert local.get("/api/info").status_code == 200
    with TestClient(app, base_url="http://pages.example.org") as outside:
        answer = outside.get("/api/info")
    assert answer.status_code == 400
    assert "Unknown host" in answer.text
