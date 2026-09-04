import pytest
from pydantic import ValidationError

from ai_qa_engineering.dashboard_models import ReviewSubmission


@pytest.mark.unit
def test_rejected_review_requires_only_a_rationale() -> None:
    review = ReviewSubmission.model_validate(
        {
            "candidate_id": "AUTO-001",
            "decision": "rejected",
            "rationale": "Expected negative test behavior.",
        }
    )

    assert review.decision.value == "rejected"
    assert review.severity is None


@pytest.mark.unit
def test_confirmed_review_requires_complete_verified_finding_details() -> None:
    with pytest.raises(ValidationError, match="Confirmed findings require"):
        ReviewSubmission.model_validate(
            {
                "candidate_id": "AUTO-001",
                "decision": "confirmed",
                "rationale": "Reproduced manually.",
            }
        )

    review = ReviewSubmission.model_validate(
        {
            "candidate_id": "AUTO-001",
            "decision": "confirmed",
            "rationale": "Reproduced manually.",
            "severity": "Major",
            "category": "core-flows",
            "steps": ["Open checkout", "Submit the order"],
            "expected": "The order completes.",
            "actual": "The request fails.",
            "recommendation": "Repair checkout before launch.",
        }
    )

    assert review.severity is not None
    assert review.severity.value == "Major"
