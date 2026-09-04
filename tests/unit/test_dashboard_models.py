import pytest
from pydantic import ValidationError

from ai_qa_engineering.dashboard_models import (
    ReportVerificationDocument,
    ReportWorkspaceSubmission,
    ReviewSubmission,
)
from tests.dashboard_support import report_workspace_submission


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


@pytest.mark.unit
def test_report_workspace_requires_every_score_category_and_unique_flows() -> None:
    workspace = report_workspace_submission()

    assert len(workspace.assessments) == 6
    with pytest.raises(ValidationError, match="each score category"):
        ReportWorkspaceSubmission.model_validate(
            workspace.model_dump() | {"assessments": workspace.assessments[:-1]}
        )
    with pytest.raises(ValidationError, match="Critical flow IDs must be unique"):
        ReportWorkspaceSubmission.model_validate(
            workspace.model_dump()
            | {"critical_flows": workspace.critical_flows + workspace.critical_flows}
        )


@pytest.mark.unit
def test_verified_report_record_requires_visual_review_details() -> None:
    with pytest.raises(ValidationError, match="visual review timestamp and rationale"):
        ReportVerificationDocument.model_validate(
            {
                "audit_id": "audit-1",
                "input_digest": "a" * 64,
                "generated_at": "2026-09-04T12:00:00Z",
                "status": "verified",
                "score": 100,
                "recommendation": "READY TO LAUNCH",
                "html_path": "report.html",
                "pdf_path": "report.pdf",
                "page_images": ["page-1.png"],
                "page_count": 1,
                "automated_checks": [{"name": "PDF structure", "passed": True, "detail": "Valid."}],
            }
        )
