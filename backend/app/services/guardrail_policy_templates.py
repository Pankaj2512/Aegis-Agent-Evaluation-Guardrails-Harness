"""Built-in guardrail policy templates.

One-click starting points a user can adopt into their reusable GuardrailPolicy
library (and then attach to any workflow's guardrail node). Templates are
static reference data — adopting one creates an owned, editable copy; the
template itself is never mutated. Each ``rules_json`` uses the same schema as a
guardrail node's ``rules`` so it validates through the normal guardrail path.
"""

from __future__ import annotations

from typing import Any

POLICY_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "pii-strict",
        "name": "PII shield (strict)",
        "description": "Redact emails, phone numbers, cards, SSNs, IPs, names and "
        "locations from model output before it leaves the workflow.",
        "category": "privacy",
        "rules_json": {
            "guardrail_type": "presidio",
            "mode": "output",
            "detect_pii": True,
            "pii_engine": "presidio",
            "presidio_entities": [
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "CREDIT_CARD",
                "US_SSN",
                "IP_ADDRESS",
                "PERSON",
                "LOCATION",
            ],
            "fail_behavior": "mask",
        },
    },
    {
        "id": "injection-shield",
        "name": "Prompt injection shield",
        "description": "Screen incoming user input for instruction-override and "
        "jailbreak attempts, blocking the run before the agent sees them.",
        "category": "security",
        "rules_json": {
            "guardrail_type": "prompt_injection",
            "mode": "input",
            "fail_behavior": "block",
        },
    },
    {
        "id": "content-moderation",
        "name": "Content moderation",
        "description": "Score output across toxicity, hate, violence, self-harm and "
        "sexual content, blocking anything over a strict threshold.",
        "category": "safety",
        "rules_json": {
            "guardrail_type": "moderation",
            "mode": "output",
            "moderation_threshold": 0.4,
            "fail_behavior": "block",
        },
    },
    {
        "id": "safe-customer",
        "name": "Safe customer support",
        "description": "Warn on toxic or unsafe replies before they reach a customer, "
        "without hard-blocking the conversation.",
        "category": "safety",
        "rules_json": {
            "guardrail_type": "moderation",
            "mode": "output",
            "moderation_threshold": 0.5,
            "fail_behavior": "warn",
        },
    },
    {
        "id": "financial-compliance",
        "name": "Financial compliance",
        "description": "Flag risky financial-advice language (guaranteed returns, "
        "insider tips) so it can be reviewed before delivery.",
        "category": "compliance",
        "rules_json": {
            "guardrail_type": "rules",
            "mode": "output",
            "blocked_keywords": [
                "guaranteed returns",
                "risk-free",
                "insider tip",
                "get rich quick",
                "can't lose",
            ],
            "fail_behavior": "warn",
        },
    },
    {
        "id": "healthcare-phi",
        "name": "Healthcare PHI",
        "description": "Block protected health information — names, SSNs, and contact "
        "details — from appearing in output.",
        "category": "compliance",
        "rules_json": {
            "guardrail_type": "presidio",
            "mode": "output",
            "detect_pii": True,
            "pii_engine": "presidio",
            "presidio_entities": [
                "PERSON",
                "US_SSN",
                "PHONE_NUMBER",
                "EMAIL_ADDRESS",
                "LOCATION",
            ],
            "fail_behavior": "block",
        },
    },
]


def list_policy_templates() -> list[dict[str, Any]]:
    return POLICY_TEMPLATES


def get_policy_template(template_id: str) -> dict[str, Any] | None:
    return next((t for t in POLICY_TEMPLATES if t["id"] == template_id), None)
