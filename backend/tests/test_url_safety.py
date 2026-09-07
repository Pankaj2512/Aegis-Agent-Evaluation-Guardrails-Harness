import pytest

from app.services.url_safety import validate_http_url


def test_validate_http_url_allows_public_https():
    assert validate_http_url("https://httpbin.org/get") == "https://httpbin.org/get"


def test_validate_http_url_blocks_localhost():
    with pytest.raises(ValueError, match="not allowed"):
        validate_http_url("http://localhost/admin")


def test_validate_http_url_blocks_private_ip_literal():
    with pytest.raises(ValueError, match="blocked"):
        validate_http_url("http://127.0.0.1/secret")


def test_validate_http_url_blocks_metadata_ip():
    with pytest.raises(ValueError, match="blocked"):
        validate_http_url("http://169.254.169.254/latest/meta-data/")


def test_validate_http_url_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="only supports"):
        validate_http_url("file:///etc/passwd")