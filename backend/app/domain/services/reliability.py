"""Facility reliability scoring formula — PROJECT.md 2.8's "answer rate,
historical report accuracy" combined into one `Facility.reliability_score`.

Weighted 65/35 toward call answer rate over report confidence: a facility
CALL-E can actually reach is more useful to future sweep planning than one
that occasionally gives an ambiguous stock answer, but a pattern of
low-confidence/"unknown" extractions (Sprint 03's confidence score) still
pulls the score down rather than being ignored.
"""

_ANSWER_RATE_WEIGHT = 0.65
_CONFIDENCE_WEIGHT = 0.35


def compute_reliability_score(*, answer_rate: float, avg_result_confidence: float | None) -> float:
    """`avg_result_confidence` is `None` when the facility has never produced
    an `AvailabilityResult` (e.g. every call was a `no_answer`) — in that
    case the score is answer rate alone, since there's no report-confidence
    signal to blend in."""
    if avg_result_confidence is None:
        return round(answer_rate, 4)
    score = _ANSWER_RATE_WEIGHT * answer_rate + _CONFIDENCE_WEIGHT * avg_result_confidence
    return round(score, 4)
