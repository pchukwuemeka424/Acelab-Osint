from urllib.parse import unquote

import pytest

from app.connectors.profiles import (
    WEB_SEARCH_UNAVAILABLE,
    collect_name_websites,
    load_platforms,
    profile_url,
    search_result_urls,
)
from app.security.ssrf import UnsafeURL, fetch_profile


class _Page:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.content = body
        self.text = body.decode()


def test_vendored_blindeye_list_includes_github_and_reddit():
    platforms = load_platforms()
    names = {item["name"] for item in platforms}
    assert "GitHub" in names
    assert "Reddit" in names
    github = next(item for item in platforms if item["name"] == "GitHub")
    reddit = next(item for item in platforms if item["name"] == "Reddit")
    assert profile_url(github["url"], "kit_author") == "https://github.com/kit_author"
    assert profile_url(reddit["url"], "kit_author") == "https://www.reddit.com/user/kit_author"


def test_name_websites_keep_pages_that_contain_the_name():
    html = (
        b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fshop.example.test%2Fabout">'
        b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.gmail.com%2F">'
        b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fnoise.example.test%2F">'
    )

    def fetch(url: str) -> _Page:
        if "duckduckgo.com" in url:
            return _Page(200, html)
        if url.startswith("https://shop.example.test"):
            return _Page(200, b"About Jane Doe")
        return _Page(200, b"user profile placeholder " + b"x" * 600)

    result = collect_name_websites("jane doe", fetch=fetch)
    assert [entity.display_value for entity in result.entities] == ["shop.example.test"]
    assert result.entities[0].metadata["category"] == "website"
    assert result.entities[0].metadata["group"] == "social"
    assert result.entities[0].metadata["url"] == "https://shop.example.test/about"
    assert "gmail.com" not in search_result_urls(html.decode())


def test_name_website_search_retries_when_duckduckgo_blocks_the_lookup():
    challenge = b"Unfortunately, bots use DuckDuckGo too."
    html = (
        b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fshop.example.test%2Fabout">'
        b"About Jane Doe"
    )
    calls = []

    def fetch(url: str) -> _Page:
        calls.append(url)
        if "r.jina.ai" in url:
            return _Page(200, html)
        if "duckduckgo.com" in url:
            return _Page(202, challenge)
        return _Page(200, b"placeholder without the name")

    result = collect_name_websites("jane doe", fetch=fetch)
    assert any("r.jina.ai" in url for url in calls)
    assert [entity.display_value for entity in result.entities] == ["shop.example.test"]
    assert result.entities[0].metadata["group"] == "social"
    assert result.limitations == []


def test_a_blocked_website_search_is_not_reported_as_an_empty_result():
    def fetch(url: str) -> _Page:
        return _Page(202, b"Unfortunately, bots use DuckDuckGo too.")

    result = collect_name_websites("jane doe", fetch=fetch)
    assert result.entities == []
    assert result.limitations == [WEB_SEARCH_UNAVAILABLE]


def test_category_search_keeps_a_snippet_hit_and_drops_pages_without_the_name():
    def fetch(url: str) -> _Page:
        decoded = unquote(url)
        if "site:linkedin.com" in decoded:
            return _Page(
                200,
                b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fanalyst">'
                b"About Jane Doe",
            )
        if "site:onlyfans.com" in decoded:
            return _Page(
                200,
                b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fonlyfans.com%2Fanalyst">profile',
            )
        if "site:x.com" in decoded or "duckduckgo.com" in url:
            return _Page(200, b"No results")
        if "linkedin.com" in url:
            return _Page(200, b"live page without the name")
        return _Page(200, b"no name")

    result = collect_name_websites("jane doe", fetch=fetch)
    assert [entity.display_value for entity in result.entities] == ["linkedin.com"]
    assert result.entities[0].metadata["group"] == "jobs"
    assert result.entities[0].metadata["category"] == "website"


def test_general_website_search_stops_after_thirty_candidates():
    searches = []
    pages = []

    def fetch(url: str) -> _Page:
        decoded = unquote(url)
        if "site:" in decoded:
            return _Page(200, b"No results")
        if "duckduckgo.com" in url:
            searches.append(url)
            offset = int(url.rsplit("&s=", 1)[1]) if "&s=" in url else 0
            links = [
                f'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fsite{index}.example.test%2F">'
                for index in range(offset, offset + 10)
            ]
            return _Page(200, "".join(links).encode())
        pages.append(url)
        return _Page(200, b"no name")

    result = collect_name_websites("jane doe", fetch=fetch)
    assert result.entities == []
    assert result.limitations == ["No public page contained this name."]
    assert len(pages) == 30
    assert [url for url in searches if "&s=30" in url] == []


def test_name_search_keeps_pages_that_contain_the_text():
    name_html = (
        b'<a href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fstudio.example.test%2F">'
        b"About Jane Doe"
    )

    def fetch(url: str) -> _Page:
        decoded = unquote(url)
        if "jane doe" in decoded.lower() or "Jane Doe" in decoded:
            return _Page(200, name_html)
        return _Page(200, b"unrelated page")

    person = collect_name_websites("jane doe", fetch=fetch)
    assert [entity.display_value for entity in person.entities] == ["studio.example.test"]
    assert person.relationships[0].reason.endswith("jane doe.")


def test_profile_fetch_refuses_a_private_address():
    def resolver(host, port):
        return [(None, None, None, None, ("127.0.0.1", port))]

    with pytest.raises(UnsafeURL):
        fetch_profile("https://github.com/kit_author", resolver=resolver)
    with pytest.raises(UnsafeURL):
        fetch_profile("http://github.com/kit_author", resolver=resolver)
