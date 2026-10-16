import pytest

from app.security.ssrf import (
    UnsafeURL,
    assert_public_destination,
    assert_public_https,
    assert_safe_url,
    assert_subject_url,
    is_blocked_ip,
    rdap_redirect_url,
    same_host_redirect,
)


def _resolver(address: str):
    def resolve(host, port):
        return [(None, None, None, None, (address, port))]

    return resolve


def test_blocks_unapproved_hosts_and_private_answers():
    with pytest.raises(UnsafeURL):
        assert_safe_url("http://openrouter.ai/api", "openrouter", resolver=_resolver("1.1.1.1"))
    with pytest.raises(UnsafeURL):
        assert_safe_url("https://evil.example/steal", "openrouter", resolver=_resolver("1.1.1.1"))
    with pytest.raises(UnsafeURL):
        assert_safe_url("https://openrouter.ai/api/v1/chat/completions", "openrouter", resolver=_resolver("127.0.0.1"))
    with pytest.raises(UnsafeURL):
        assert_safe_url("https://openrouter.ai/api/v1/chat/completions", "openrouter", resolver=_resolver("169.254.169.254"))


def test_allows_public_openrouter_resolution():
    addresses = assert_safe_url(
        "https://openrouter.ai/api/v1/chat/completions",
        "openrouter",
        resolver=_resolver("1.1.1.1"),
    )
    assert addresses == ["1.1.1.1"]
    assert is_blocked_ip("10.1.1.1")
    assert not is_blocked_ip("1.1.1.1")


def test_rdap_bootstrap_redirect_stays_on_public_https():
    target = rdap_redirect_url("https://rdap.org/domain/example.co.uk", "https://rdap.example/domain/example.co.uk")
    assert target == "https://rdap.example/domain/example.co.uk"
    assert assert_public_https(target, resolver=_resolver("1.1.1.1")) == ["1.1.1.1"]
    with pytest.raises(UnsafeURL):
        rdap_redirect_url("https://crt.sh/?q=example", "https://rdap.example/domain/example")
    with pytest.raises(UnsafeURL):
        rdap_redirect_url("https://rdap.org/domain/example.co.uk", "http://rdap.example/domain/example.co.uk")
    with pytest.raises(UnsafeURL):
        assert_public_https("https://rdap.example/domain/example.co.uk", resolver=_resolver("127.0.0.1"))


def test_subject_page_rejects_private_addresses_and_other_hosts():
    with pytest.raises(UnsafeURL):
        assert_subject_url("https://example.com/", "example.com", resolver=_resolver("127.0.0.1"))
    with pytest.raises(UnsafeURL):
        assert_subject_url("https://other.example/", "example.com", resolver=_resolver("1.1.1.1"))
    with pytest.raises(UnsafeURL):
        same_host_redirect("https://example.com/", "https://evil.example/a", "example.com")
    assert same_host_redirect("https://example.com/a", "/b", "example.com") == "https://example.com/b"
    assert assert_subject_url("https://example.com/", "example.com", resolver=_resolver("1.1.1.1")) == "example.com"


def test_recorded_image_host_must_be_public():
    assert assert_public_destination("https://cdn.example/logo.png", resolver=_resolver("1.1.1.1")) == "cdn.example"
    with pytest.raises(UnsafeURL):
        assert_public_destination("https://cdn.example/logo.png", resolver=_resolver("10.0.0.8"))
    with pytest.raises(UnsafeURL):
        assert_public_destination("http://169.254.169.254/latest", resolver=_resolver("169.254.169.254"))
    with pytest.raises(UnsafeURL):
        assert_public_destination("file:///etc/passwd", resolver=_resolver("1.1.1.1"))
