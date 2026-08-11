"""Contract tests for the scheduled quality loop and governance documents."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_hourly_workflow_is_scheduled_and_read_only() -> None:
    workflow = (ROOT / ".github/workflows/hourly-product-loop.yml").read_text()
    assert 'cron: "17 * * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "COPILOT_GITHUB_TOKEN" not in workflow
    assert "NVIDIA_NIM_API_KEY" in workflow


def test_hourly_sentinel_has_no_personal_data_contract() -> None:
    script = (ROOT / "scripts/hourly_product_loop.py").read_text()
    assert "REQUIRED_FILES" in script
    assert "capture_output=True" in script
    assert "ensure_ascii=False" in script
    assert "birth" not in script.lower()


def test_public_docstring_audit_is_part_of_the_sentinel() -> None:
    audit = (ROOT / "scripts/docstring_audit.py").read_text()
    sentinel = (ROOT / "scripts/hourly_product_loop.py").read_text()
    assert "ast.get_docstring" in audit
    assert "public-docstrings" in sentinel


def test_commercial_quality_documents_are_traced() -> None:
    traceability = (ROOT / "docs/TRACEABILITY.md").read_text()
    for document in ("PRD", "TRD", "threat model", "testing", "operations"):
        assert document in traceability
    assert "ADR-0002" in traceability
    assert "ADR-0003" in traceability
