import pytest

from app.services.embeddings import cosine_similarity_vectors, embed_text, retrieve_by_embedding


def test_embed_text_returns_normalized_vector():
    vec = embed_text("refund policy for customers")
    assert len(vec) > 0
    assert all(isinstance(v, float) for v in vec)


def test_cosine_similarity_identical_vectors():
    vec = embed_text("hello world")
    assert cosine_similarity_vectors(vec, vec) == pytest.approx(1.0, abs=0.01)


def test_cosine_similarity_rejects_dimension_mismatch():
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        cosine_similarity_vectors([1.0, 0.0], [1.0, 0.0, 0.0])


def test_retrieve_by_embedding_ranks_relevant_doc():
    docs = [
        {"id": "1", "text": "company refund policy and receipt requirements"},
        {"id": "2", "text": "tomato gardening in spring season"},
    ]
    for doc in docs:
        doc["embedding"] = embed_text(doc["text"])
    hits = retrieve_by_embedding("refund policy receipt", docs, top_k=1)
    assert hits[0]["id"] == "1"


@pytest.mark.asyncio
async def test_discord_integration_posts():
    from unittest.mock import AsyncMock, patch

    from app.services.integrations import run_discord_integration

    with patch("app.services.integrations.safe_http_request", new_callable=AsyncMock) as mock_request:
        response = AsyncMock()
        response.status_code = 204
        response.text = ""
        mock_request.return_value = response

        out = await run_discord_integration(
            "https://discord.com/api/webhooks/test",
            "Ping {{input.user}}",
            {"input": {"user": "Ada"}, "steps": {}, "last_output": "", "memory": {}},
            "",
        )
        assert out == "Discord 204"
        mock_request.assert_awaited_once()