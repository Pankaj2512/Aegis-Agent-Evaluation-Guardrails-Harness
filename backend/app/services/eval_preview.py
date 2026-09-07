"""Live rubric preview — run the LLM judge on a sample input/output.

Powers the "test on sample" panel of the custom rubric editor: score a sample
against a rubric (criteria / instruction / weights) without standing up a full
workflow run, so authors can iterate on a rubric and see the effect immediately.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.eval import EvalScores, build_eval_instruction, compute_aggregate_score


def preview_eval(
    input_text: str,
    output_text: str,
    *,
    criteria: str | None = None,
    instruction: str | None = None,
    score_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Score a sample with the given rubric. Returns the per-dimension scores +
    the weighted aggregate, or a ``skipped``/``error`` marker on the no-key /
    failure paths (never raises)."""
    if not settings.google_api_key:
        return {
            "skipped": True,
            "message": "Preview needs GOOGLE_API_KEY configured.",
            "aggregate_score": None,
        }

    instruction_text = (instruction or "").strip() or build_eval_instruction(None, criteria)
    content = (
        f"{instruction_text}\n\n"
        f"--- Input ---\n{(input_text or '').strip()[:6000]}\n\n"
        f"--- Output to evaluate ---\n{(output_text or '').strip()[:6000]}\n\n"
        "Return JSON scores from 1-5 for faithfulness, helpfulness, relevance and "
        "toxicity (1=none, 5=severe), plus brief reasoning."
    )
    try:
        from google import genai

        client = genai.Client(api_key=settings.google_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=content,
            config={"response_mime_type": "application/json", "response_schema": EvalScores},
        )
        scores = EvalScores.model_validate_json(response.text or "{}")
        data = scores.model_dump()
        data["aggregate_score"] = compute_aggregate_score(data, score_weights)
        return data
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "aggregate_score": None}
