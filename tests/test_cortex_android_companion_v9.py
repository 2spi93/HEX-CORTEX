"""Static security and source integrity checks for standalone Android companion V9.

These tests are intentionally not a hardware camera test: Android permission,
video drivers, Quick Share, PWA install, HTTPS and touch behavior require a
real smartphone browser, which CI does not control.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "docs" / "companion"


class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.scripts = []
        self.forms = []
        self.meta = {}
        self.links = []
        self.videos = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if "id" in props:
            self.ids.add(props["id"])
        if tag == "script":
            self.scripts.append(props)
        if tag == "form":
            self.forms.append(props)
        if tag == "link":
            self.links.append(props)
        if tag == "video":
            self.videos.append(props)
        if tag == "meta":
            self.meta[props.get("http-equiv", "")] = props.get("content", "")


def _read(name: str) -> str:
    return (APP / name).read_text(encoding="utf-8")


def test_mobile_static_shell_is_relative_and_does_not_embed_external_scripts():
    page = _read("index.html")
    parser = _Ids()
    parser.feed(page)
    assert "<html lang=\"fr\">" in page
    assert not parser.forms
    assert len(parser.scripts) == 1
    assert parser.scripts[0]["src"] == "app.js"
    assert not any(x.startswith("http") for x in (
        [d.get("href", "") for d in parser.links]
        + [d.get("src", "") for d in parser.scripts]
    ))
    policy = parser.meta["Content-Security-Policy"]
    assert "default-src 'none'" in policy
    assert "script-src 'self'" in policy
    assert "connect-src 'self'" in policy
    assert "object-src" not in page
    assert len(parser.videos) == 1
    assert parser.videos[0].get("playsinline") is None
    assert "capture=\"environment\"" in page
    assert "Aucun accès au PC, drone ou robot" in page


def test_controls_are_wired_and_uploads_require_explicit_share():
    html = _Ids()
    html.feed(_read("index.html"))
    js = _read("app.js")
    assert {
        "camera-start", "camera-snap", "camera-stop", "camera-feed",
        "photo-choose", "camera-fallback", "photo", "object-name",
        "selection-clear", "export-photo", "export-box", "share",
        "selection-state", "export-state", "connection", "camera-state",
    } <= html.ids
    wired = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", js))
    assert wired and wired <= html.ids
    assert "getUserMedia" in js
    assert "createImageBitmap" in js
    assert "bbox_xyxy" in js
    assert "navigator.share" in js
    assert "navigator.mediaDevices" in js
    assert "video.srcObject = null" in js
    assert "track.stop()" in js
    assert "window.addEventListener('pagehide', stopCamera)" in js
    assert "image_sha256" in js
    assert "source_capture" not in js or "model" not in js
    assert "segmentation_performed: false" in js
    assert "remote_device_control_performed: false" in js
    # This application exports / shares selected files. It has no upload API.
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "WebSocket" not in js
    assert "sendBeacon" not in js
    assert "localStorage" not in js


def test_mobile_app_manifest_and_cache_do_not_persist_any_images():
    manifest = json.loads(_read("manifest.webmanifest"))
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "./"
    assert manifest["start_url"] == "./"
    assert manifest["lang"] == "fr"
    sw = _read("sw.js")
    assert "hex-mobile-companion-" in sw
    assert "req.method !== 'GET'" in sw
    assert "url.origin !== self.location.origin" in sw
    assert "'./app.js'" in sw
    assert "photo.jpg" not in sw
    assert "image/jpeg" not in sw
    assert "POST" not in sw


def test_mobile_source_js_compiles_when_node_installed():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not available")
    for name in ("app.js", "sw.js"):
        result = subprocess.run(
            [node, "--check", str(APP / name)], capture_output=True,
            text=True, check=False, timeout=8,
        )
        assert result.returncode == 0, f"{name}: {result.stderr}"


def test_files_are_small_and_self_contained():
    expected = {
        "index.html", "app.js", "style.css", "sw.js",
        "manifest.webmanifest", "icon.svg",
    }
    assert {p.name for p in APP.iterdir() if p.is_file()} == expected
    assert sum((APP / name).stat().st_size for name in expected) < 75_000
    assert "http:" not in _read("app.js")
    assert "https:" not in _read("app.js")
