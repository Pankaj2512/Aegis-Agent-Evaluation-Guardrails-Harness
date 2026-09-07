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

import re
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


def compute_grounding_ratio(answer: str, context: str, min_word_len: int = 2) -> float:
    """Calculate the deterministic lexical grounding ratio of an answer against context.

    Extracts word tokens of length >= min_word_len from the answer and computes
    what fraction appear in the retrieved context. Pure function — does not require
    external API calls or LLM tokens.

    Returns a float between 0.0 and 1.0 (rounded to 4 decimals).
    """
    if not answer or not answer.strip():
        return 0.0
    if not context or not context.strip():
        return 0.0

    answer_tokens = [
        t for t in re.findall(r"\b\w+\b", answer.lower())
        if len(t) >= min_word_len
    ]
    if not answer_tokens:
        return 0.0

    context_tokens = set(
        t for t in re.findall(r"\b\w+\b", context.lower())
        if len(t) >= min_word_len
    )
    if not context_tokens:
        return 0.0

    matched = sum(1 for t in answer_tokens if t in context_tokens)
    return round(matched / len(answer_tokens), 4)


def assess_hallucination_risk(
    faithfulness: float | None = None,
    grounding_ratio: float | None = None,
) -> dict[str, Any]:
    """Assess hallucination risk combining semantic faithfulness (1-5) and lexical grounding (0-1).

    Produces a risk level ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'), confidence tier, and explanatory flags.
    """
    flags: list[str] = []

    if faithfulness is None and grounding_ratio is None:
        return {
            "risk_level": "UNKNOWN",
            "faithfulness": None,
            "grounding_ratio": None,
            "confidence": "LOW",
            "flags": ["insufficient_data"],
        }

    confidence = "HIGH" if (faithfulness is not None and grounding_ratio is not None) else "MEDIUM"

    if grounding_ratio is not None:
        if grounding_ratio >= 0.75:
            flags.append("strong_lexical_grounding")
        elif grounding_ratio < 0.35:
            flags.append("low_lexical_overlap")

    if faithfulness is not None:
        if faithfulness >= 4.0:
            flags.append("high_semantic_faithfulness")
        elif faithfulness <= 2.0:
            flags.append("low_semantic_faithfulness")

    if faithfulness is not None and grounding_ratio is not None:
        normalized_faith = (faithfulness - 1.0) / 4.0
        combined_score = 0.65 * normalized_faith + 0.35 * grounding_ratio
        if combined_score >= 0.70:
            risk_level = "LOW"
        elif combined_score >= 0.40:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
            flags.append("unsupported_claims_likely")
    elif faithfulness is not None:
        if faithfulness >= 4.0:
            risk_level = "LOW"
        elif faithfulness >= 3.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
            flags.append("unsupported_claims_likely")
    else:
        if grounding_ratio >= 0.70:
            risk_level = "LOW"
        elif grounding_ratio >= 0.35:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
            flags.append("unsupported_claims_likely")

    return {
        "risk_level": risk_level,
        "faithfulness": faithfulness,
        "grounding_ratio": grounding_ratio,
        "confidence": confidence,
        "flags": flags,
    }


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
    """Score a RAG triple. Returns per-dimension scores + aggregate, deterministic
    grounding ratio, and hallucination risk assessment (never raises)."""
    grounding = compute_grounding_ratio(answer, context)

    if not settings.google_api_key:
        risk = assess_hallucination_risk(faithfulness=None, grounding_ratio=grounding)
        return {
            "skipped": True,
            "message": "RAG scoring needs GOOGLE_API_KEY configured.",
            "rag_aggregate": None,
            "grounding_ratio": grounding,
            "hallucination_risk": risk,
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
        data["grounding_ratio"] = grounding
        data["hallucination_risk"] = assess_hallucination_risk(
            faithfulness=float(scores.faithfulness),
            grounding_ratio=grounding,
        )
        return data
    except Exception as exc:  # noqa: BLE001
        risk = assess_hallucination_risk(faithfulness=None, grounding_ratio=grounding)
        return {
            "error": str(exc),
            "rag_aggregate": None,
            "grounding_ratio": grounding,
            "hallucination_risk": risk,
        }

