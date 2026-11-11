import httpx

from lay_core import bandeja


def test_detecta_version_nueva(monkeypatch):
    def falso(url, **k):
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "tag_name": "v2.10.0",
                "html_url": "https://github.com/romocor/LAY/releases/tag/v2.10.0",
                "assets": [{"name": "LAY_Setup_2.10.0.exe", "browser_download_url": "https://x/LAY_Setup_2.10.0.exe"}],
            },
        )

    monkeypatch.setattr(httpx, "get", falso)
    n = bandeja.version_nueva("2.6.0", "romocor/LAY")
    assert n["version"] == "2.10.0" and n["url"].endswith(".exe")  # 2.10 > 2.6 (no comparación de texto)
    assert bandeja.version_nueva("2.10.0", "romocor/LAY") is None


def test_repo_privado_no_rompe(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, **k: httpx.Response(404, request=httpx.Request("GET", url)))
    assert bandeja.version_nueva("2.6.0", "romocor/LAY") is None
