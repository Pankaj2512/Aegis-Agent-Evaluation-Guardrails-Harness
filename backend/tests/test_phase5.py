import uuid

from app.services.expressions import render_template
from app.services.knowledge_base import retrieve_documents, score_document_bm25, score_document_tfidf
from app.services.persistent_memory import merge_memory_into_context, namespace_to_dict


def test_memory_expression_resolution():
    ctx = {
        "input": {"text": "hi"},
        "steps": {},
        "last_output": "hi",
        "memory": {"users": {"alice": "engineer"}},
    }
    assert render_template("Role: {{memory.users.alice}}", ctx, "") == "Role: engineer"


def test_merge_memory_into_context():
    ctx: dict = {"input": {}, "steps": {}, "last_output": "", "memory": {"session": {"x": "1"}}}
    rows = [
        {"namespace": "session", "key": "y", "value": "2"},
        {"namespace": "prefs", "key": "theme", "value": "dark"},
    ]
    merge_memory_into_context(ctx, rows)
    assert ctx["memory"]["session"]["x"] == "1"
    assert ctx["memory"]["session"]["y"] == "2"
    assert ctx["memory"]["prefs"]["theme"] == "dark"


def test_namespace_to_dict():
    rows = [
        {"namespace": "a", "key": "k1", "value": "v1"},
        {"namespace": "a", "key": "k2", "value": "v2"},
    ]
    assert namespace_to_dict(rows) == {"a": {"k1": "v1", "k2": "v2"}}


def test_tfidf_prefers_relevant_document():
    docs = [
        {"id": "1", "text": "refund policy within thirty days receipt required"},
        {"id": "2", "text": "gardening tips for spring planting tomatoes"},
    ]
    hits = retrieve_documents("refund policy receipt", docs, top_k=1, method="tfidf")
    assert hits[0]["id"] == "1"
    assert score_document_tfidf("refund policy receipt", docs[0]["text"]) >= score_document_tfidf(
        "refund policy receipt", docs[1]["text"]
    )


def test_bm25_prefers_relevant_document():
    docs = [
        {"id": "1", "text": "refund policy within thirty days receipt required"},
        {"id": "2", "text": "gardening tips for spring planting tomatoes"},
    ]
    s1 = score_document_bm25("refund policy receipt", docs[0]["text"])
    s2 = score_document_bm25("refund policy receipt", docs[1]["text"])
    assert s1 > s2
    hits = retrieve_documents("refund policy receipt", docs, top_k=1, method="bm25")
    assert hits[0]["id"] == "1"