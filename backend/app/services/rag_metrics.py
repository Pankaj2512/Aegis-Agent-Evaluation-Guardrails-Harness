"""RAG-specific evaluation scorers.

Standard RAG quality dimensions an LLM judge can assess from a (question,
retrieved-context, answer) triple:

- context_precision — is the retrieved context relevant to the question?
- faithfulness      — is the answer grounded in the context (not hallucinated)?
- answer_relevance  — does the answer actually address the question?

Scores are 1-5 (matching the LLM-judge EvalScores scale) so they slot alongside
the existing eval dimensions. The judge call degrades to a skip marker with no
API key and never raises.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.config import settings

RAG_DIMENSIONS = ("context_precision", "faithfulness", "answer_relevance")

RAG_INSTRUCTION = (
    "You are a retrieval-augmented-generation (RAG) evaluation judge. Given a "
    "question, the retrieved context, and an answer, score each dimension from 1 "
    "(poor) to 5 (excellent): context_precision (is the retrieved context relevant "
    "to the question?), faithfulness (is the answer supported by the context rather "
    "than hallucinated?), and answer_relevance (does the answer address the "
    "question?). Base the scores strictly on the material provided."
)


class RagScores(BaseModel):
    context_precision: int = Field(ge=1, le=5)
    faithfulness: int = Field(ge=1, le=5)
    answer_relevance: int = Field(ge=1, le=5)
    reasoning: str = ""


def rag_aggregate(scores: dict[str, Any]) -> float | None:
    """Mean of the three RAG dimensions (1-5), rounded."""
    values = [
        float(scores[dim])
        for dim in RAG_DIMENSIONS
        if isinstance(scores.get(dim), (int, float))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def score_rag(question: str, answer: str, context: str) -> dict[str, Any]:
    """Score a RAG triple. Returns per-dimension scores + aggregate, or a
    skip/error marker (never raises)."""
    if not settings.google_api_key:
        return {
            "skipped": True,
            "message": "RAG scoring needs GOOGLE_API_KEY configured.",
            "rag_aggregate": None,
        }

    prompt = (
        f"{RAG_INSTRUCTION}\n\n"
        f"--- Question ---\n{(question or '').strip()[:4000]}\n\n"
        f"--- Retrieved context ---\n{(context or '').strip()[:8000]}\n\n"
        f"--- Answer ---\n{(answer or '').strip()[:4000]}\n\n"
        "Return JSON: context_precision, faithfulness, answer_relevance (1-5) and reasoning."
    )
    try:
        from google import genai

        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": RagScores},
        )
        scores = RagScores.model_validate_json(response.text or "{}")
        data = scores.model_dump()
        data["rag_aggregate"] = rag_aggregate(data)
        return data
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "rag_aggregate": None}
