import pytest

from app.services.normalize import InvalidIndicator, classify_indicator


def test_domain_normalisation():
    kind, value = classify_indicator("Portal.Example.TEST.")
    assert kind == "domain"
    assert value == "portal.example.test"


def test_url_strips_fragment_and_rejects_credentials():
    kind, value = classify_indicator("HTTPS://Shop.Example.TEST/path?q=1#frag")
    assert kind == "url"
    assert value == "https://shop.example.test/path?q=1"
    with pytest.raises(InvalidIndicator):
        classify_indicator("https://user:pass@shop.example.test/")


def test_rejects_private_ip_and_bad_scheme():
    with pytest.raises(InvalidIndicator):
        classify_indicator("127.0.0.1")
    with pytest.raises(InvalidIndicator):
        classify_indicator("169.254.169.254")
    with pytest.raises(InvalidIndicator):
        classify_indicator("http://metadata.google.internal/computeMetadata")
    with pytest.raises(InvalidIndicator):
        classify_indicator("ftp://files.example.test/a")


def test_email_and_username_are_rejected_and_a_name_is_accepted():
    with pytest.raises(InvalidIndicator):
        classify_indicator("Analyst@Example.TEST")
    with pytest.raises(InvalidIndicator):
        classify_indicator("Kit_Author")
    with pytest.raises(InvalidIndicator):
        classify_indicator("@Kit_Author")
    kind, value = classify_indicator("https://github.com/Kit_Author")
    assert (kind, value) == ("url", "https://github.com/Kit_Author")
    kind, value = classify_indicator("Jane Doe")
    assert (kind, value) == ("name", "jane doe")


def test_documentation_ip_and_fingerprint_are_accepted():
    kind, value = classify_indicator("198.51.100.10")
    assert (kind, value) == ("ip", "198.51.100.10")
    fingerprint = "ab" * 32
    kind, value = classify_indicator(fingerprint.upper())
    assert kind == "certificate"
    assert value == fingerprint
