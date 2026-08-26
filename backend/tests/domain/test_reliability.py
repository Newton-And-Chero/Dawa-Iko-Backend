from app.domain.services.reliability import compute_reliability_score


def test_perfect_answer_rate_and_confidence_scores_one() -> None:
    assert compute_reliability_score(answer_rate=1.0, avg_result_confidence=1.0) == 1.0


def test_falls_back_to_answer_rate_when_no_confidence_data() -> None:
    assert compute_reliability_score(answer_rate=0.8, avg_result_confidence=None) == 0.8


def test_weights_answer_rate_more_heavily_than_confidence() -> None:
    high_answer_rate = compute_reliability_score(answer_rate=1.0, avg_result_confidence=0.0)
    high_confidence = compute_reliability_score(answer_rate=0.0, avg_result_confidence=1.0)
    assert high_answer_rate > high_confidence
    assert high_answer_rate == 0.65
    assert high_confidence == 0.35
