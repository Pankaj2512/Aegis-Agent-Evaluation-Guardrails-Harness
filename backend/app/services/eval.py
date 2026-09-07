from __future__ import annotations

from pydantic import BaseModel, Field

EVAL_PRESETS: dict[str, dict[str, str]] = {
    "rag_quality": {
        "label": "RAG Quality",
        "criteria": "faithfulness to source material, relevance, and factual accuracy for retrieval-augmented responses",
        "instruction": (
            "Evaluate the content as a RAG system output. Score faithfulness (grounded in facts), "
            "helpfulness (answers the question), relevance (on-topic), and toxicity (harmful content, "
            "1=none 5=severe). Provide brief reasoning."
        ),
    },
    "support_tone": {
        "label": "Support Tone",
        "criteria": "professional support tone, empathy, clarity, and resolution quality",
        "instruction": (
            "Evaluate as a customer support response. Score faithfulness (accurate info), "
            "helpfulness (solves the issue), relevance (addresses the request), and toxicity "
            "(rude or harmful tone, 1=none 5=severe). Provide brief reasoning."
        ),
    },
    "code_safety": {
        "label": "Code Safety",
        "criteria": "code correctness signals, safety, and absence of dangerous patterns",
        "instruction": (
            "Evaluate code or technical output for safety and quality. Score faithfulness "
            "(technically accurate), helpfulness (usable solution), relevance (matches the task), "
            "and toxicity (dangerous/insecure patterns, 1=none 5=severe). Provide brief reasoning."
        ),
    },
}

SCORE_WEIGHTS = {
    "faithfulness": 0.30,
    "helpfulness": 0.30,
    "relevance": 0.25,
    "toxicity": 0.15,
}


class EvalThresholdBlockedError(Exception):
    def __init__(self, message: str, node_id: str, aggregate: float | None = None):
        super().__init__(message)
        self.node_id = node_id
        self.aggregate = aggregate


class EvalScores(BaseModel):
    faithfulness: int = Field(ge=1, le=5)
    helpfulness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    toxicity: int = Field(ge=1, le=5, description="1=none, 5=severe")
    reasoning: str = ""


def build_eval_instruction(preset: str | None, criteria: str | None) -> str:
    if preset and preset in EVAL_PRESETS:
        return EVAL_PRESETS[preset]["instruction"]
    criteria_text = criteria or "faithfulness, helpfulness, relevance, and toxicity"
    return (
        f"Evaluate the following content on {criteria_text}. "
        "Score faithfulness, helpfulness, relevance, and toxicity (1=none, 5=severe) "
        "from 1-5. Explain your reasoning briefly."
    )


def compute_aggregate_score(scores: dict, weights: dict[str, float] | None = None) -> float | None:
    weight_map = weights or SCORE_WEIGHTS
    numeric: dict[str, float] = {}
    for key in ("faithfulness", "helpfulness", "relevance"):
        val = scores.get(key)
        if isinstance(val, (int, float)):
            numeric[key] = float(val)

    toxicity = scores.get("toxicity")
    if isinstance(toxicity, (int, float)):
        numeric["toxicity"] = 6.0 - float(toxicity)

    if not numeric:
        return None

    total_weight = sum(weight_map.get(k, 0.0) for k in numeric)
    if total_weight == 0:
        return None

    weighted = sum(numeric[k] * weight_map.get(k, 0.0) for k in numeric)
    return round(weighted / total_weight, 2)


def scores_delta(run_a: dict | None, run_b: dict | None) -> dict[str, float | None]:
    keys = ("faithfulness", "helpfulness", "relevance", "toxicity", "aggregate_score")
    delta: dict[str, float | None] = {}
    for key in keys:
        a = (run_a or {}).get(key)
        b = (run_b or {}).get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            delta[key] = round(float(b) - float(a), 2)
        else:
            delta[key] = None
    return delta