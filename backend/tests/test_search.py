import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.search import run_search, search_duckduckgo


def test_run_search_duckduckgo():
    with patch("app.services.search.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = "DDG results"
        result = asyncio.run(run_search("duckduckgo", "test query"))
        mock_thread.assert_awaited_once()
        assert result == "DDG results"


@pytest.mark.asyncio
async def test_run_search_exa_without_key(monkeypatch):
    monkeypatch.setattr("app.services.search.settings.exa_api_key", "")
    result = await run_search("exa", "test")
    assert "EXA_API_KEY" in result


@patch("app.services.search.DDGS")
def test_search_duckduckgo_formats_results(mock_ddgs):
    instance = MagicMock()
    instance.__enter__.return_value = instance
    instance.text.return_value = [
        {"title": "A", "body": "Body", "href": "https://example.com"},
    ]
    mock_ddgs.return_value = instance

    result = search_duckduckgo("hello")
    assert "A" in result
    assert "https://example.com" in result