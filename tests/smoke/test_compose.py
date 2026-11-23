import json
import os
from html.parser import HTMLParser
from urllib.request import urlopen

import pytest


class DashboardAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.urls.append(attrs.get("href", ""))
        if tag == "script" and "src" in attrs:
            self.urls.append(attrs["src"])


@pytest.mark.skipif(
    not os.getenv("STUDENTTRACK_SMOKE_URL"),
    reason="Set STUDENTTRACK_SMOKE_URL to the running Compose backend",
)
def test_compose_backend_can_reach_postgres():
    base_url = os.environ["STUDENTTRACK_SMOKE_URL"].rstrip("/")

    with urlopen(f"{base_url}/health", timeout=5) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "ok"}


@pytest.mark.skipif(
    not os.getenv("STUDENTTRACK_SMOKE_URL"),
    reason="Set STUDENTTRACK_SMOKE_URL to the running Compose backend",
)
def test_compose_serves_dashboard_assets_and_api_documentation():
    base_url = os.environ["STUDENTTRACK_SMOKE_URL"].rstrip("/")

    with urlopen(f"{base_url}/", timeout=5) as response:
        assert response.headers.get_content_type() == "text/html"
        html = response.read().decode()
    assert "StudentTrack" in html
    assets = DashboardAssets()
    assets.feed(html)
    local_assets = [url for url in assets.urls if url.startswith("/static/")]
    assert any(url.endswith(".css") for url in local_assets)
    assert any(url.endswith((".js", ".mjs")) for url in local_assets)
    for url in local_assets:
        with urlopen(f"{base_url}{url}", timeout=5) as response:
            assert response.status == 200

    with urlopen(f"{base_url}/openapi.json", timeout=5) as response:
        paths = json.load(response)["paths"]
    assert "/api/statistics" in paths
    assert "/api/scholarship/forecast" in paths
