from types import SimpleNamespace

from app.api.workflows import _extract_run_eval_metrics


def test_extract_run_eval_metrics_flattens_completed_run_scores():
    run = SimpleNamespace(
        metrics_json={
            "eval_aggregate": 4.5,
            "eval_scores": [
                {
                    "node_id": "n3",
                    "faithfulness": 5,
                    "helpfulness": 4,
                    "relevance": 5,
                    "toxicity": 1,
                    "reasoning": "Good",
                }
            ],
        },
        node_results=[],
    )
    scores = _extract_run_eval_metrics(run)
    assert scores is not None
    assert scores["faithfulness"] == 5
    assert scores["aggregate_score"] == 4.5
    assert "scores" not in scores