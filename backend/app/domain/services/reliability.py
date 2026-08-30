_ANSWER_RATE_WEIGHT = 0.65
_CONFIDENCE_WEIGHT = 0.35


def compute_reliability_score(*, answer_rate: float, avg_result_confidence: float | None) -> float:
    if avg_result_confidence is None:
        return round(answer_rate, 4)
    score = _ANSWER_RATE_WEIGHT * answer_rate + _CONFIDENCE_WEIGHT * avg_result_confidence
    return round(score, 4)
