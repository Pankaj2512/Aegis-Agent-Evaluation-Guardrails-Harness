from app.services.eval import compute_aggregate_score, scores_delta


def test_compute_aggregate_score():
    scores = {
        "faithfulness": 5,
        "helpfulness": 4,
        "relevance": 4,
        "toxicity": 1,
    }
    result = compute_aggregate_score(scores)
    assert result is not None
    assert 4.0 <= result <= 5.0


def test_scores_delta():
    delta = scores_delta(
        {"faithfulness": 3, "aggregate_score": 3.5},
        {"faithfulness": 5, "aggregate_score": 4.2},
    )
    assert delta["faithfulness"] == 2.0
    assert delta["aggregate_score"] == 0.7