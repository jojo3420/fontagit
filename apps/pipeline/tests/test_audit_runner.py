"""50종 법적 감사 파일럿의 핵심 안전 계약."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from fontagit_pipeline.audit_runner import (
    AuditGateError,
    CandidateUrl,
    FontTarget,
    run_legal_audit,
    select_pilot,
    write_dry_run_artifacts,
)
from fontagit_pipeline.audit_http import FetchResult
from fontagit_pipeline.audit_store import FindingDraft, InMemoryAuditStore
from fontagit_pipeline.config import AuditSettings


def _targets() -> list[FontTarget]:
    required = [
        FontTarget(
            font_id=uuid4(),
            slug="흰꼬리수리",
            # 표시명은 바뀔 수 있으므로 파일럿 필수 조건에는 쓰면 안 된다.
            name_ko="흰꼬리수리 별칭",
            source_tier="B",
            provider="noonnu",
            provider_record_id="613",
            reference_url="https://noonnu.cc/font_page/613",
        ),
        FontTarget(
            font_id=uuid4(),
            slug="횡성한우체",
            name_ko="횡성한우체 별칭",
            source_tier="B",
            provider="noonnu",
            provider_record_id="854",
            reference_url="https://noonnu.cc/font_page/854",
        ),
    ]
    return required + [
        FontTarget(
            font_id=uuid4(),
            slug=f"font-{index:03d}",
            name_ko=f"폰트 {index:03d}",
            source_tier="A" if index % 2 else "B",
            provider="google-fonts" if index % 2 else "noonnu",
            provider_record_id=str(index),
            reference_url=f"https://example{index % 3}.com/font/{index}",
            foundry="제작사" if index % 3 else None,
        )
        for index in range(60)
    ]


def _fetched(url: str) -> FetchResult:
    """파일럿 경계 테스트는 실제 외부 사이트를 호출하지 않는다."""
    content = b"<html><body>fixed audit fixture</body></html>"
    return FetchResult(
        status=200,
        final_url=url,
        content=content,
        content_sha256="0" * 64,
        redirect_count=0,
    )


def _forbidden_fetch(_: str) -> FetchResult:
    raise AssertionError("dry-run must not request external URLs")


def test_pilot_is_deterministic_and_requires_unique_stable_slugs() -> None:
    """필수 slug는 표시명과 무관하게 정확히 한 건씩 선택한다."""
    targets = _targets()

    selected = select_pilot(targets, size=50)

    assert len(selected) == 50
    assert {"흰꼬리수리", "횡성한우체"} <= {target.slug for target in selected}
    assert selected == select_pilot(targets, size=50)
    assert abs(sum(item.source_tier == "A" for item in selected) - sum(item.source_tier == "B" for item in selected)) <= 2
    with pytest.raises(ValueError, match="required slug"):
        select_pilot(targets, size=50, require_slugs=["없는-폰트"])
    duplicate_slug = replace(targets[0], font_id=uuid4())
    with pytest.raises(ValueError, match="slug"):
        select_pilot([*targets, duplicate_slug], size=50)


def test_findings_are_immutable_per_run_and_urls_use_safe_priority() -> None:
    """새 실행은 별도 finding이고, 승인 제작사 URL만 역할별 후보가 된다."""
    store = InMemoryAuditStore()
    target = replace(
        _targets()[0],
        foundry="네이버",
        candidates=(
            CandidateUrl(
                url="https://clova.ai/handwriting/list.html",
                document_role="download",
                source="official",
                name_ko="흰꼬리수리 별칭",
                maker="네이버",
            ),
            CandidateUrl(
                url="https://noonnu.cc/font_page/613",
                document_role="download",
                source="noonnu",
                name_ko="흰꼬리수리 별칭",
                maker="네이버",
                meaningful_cta=True,
            ),
            CandidateUrl(
                url="https://clova.ai/",
                document_role="homepage",
                source="official",
                name_ko="흰꼬리수리 별칭",
                maker="네이버",
            ),
            CandidateUrl(
                url="https://clova.ai/license",
                document_role="license",
                source="official",
                name_ko="흰꼬리수리 별칭",
                maker="네이버",
            ),
            CandidateUrl(
                url="https://search.example/result",
                document_role="download",
                source="discovery",
                name_ko="흰꼬리수리 별칭",
                maker="네이버",
            ),
        ),
    )
    registry = {
        "version": 1,
        "entries": [
            {
                "maker": "네이버",
                "domain": "clova.ai",
                "roles": ["homepage", "download", "license"],
                "source_kind": "official",
                "approved_by": "reviewer",
                "approved_at": "2026-07-18T00:00:00Z",
                "evidence_snapshot_id": "evidence-1",
            }
        ],
    }

    rules = {"version": 1, "standard_licenses": [], "maker_templates": []}
    first = run_legal_audit([target], store, registry=registry, rules=rules, fetcher=_fetched)
    second = run_legal_audit([target], store, registry=registry, rules=rules, fetcher=_fetched)

    assert first.snapshot_ids == second.snapshot_ids
    assert first.finding_ids != second.finding_ids
    assert store.finding_count == 8
    assert [store.finding_draft(item).proposed_value for item in first.finding_ids[1:]] == [
        "https://clova.ai/",
        "https://clova.ai/handwriting/list.html",
        "https://clova.ai/license",
    ]
    assert first.needs_review_count == 1
    store.mark_applied(first.finding_ids[0])
    assert store.save_finding(
        first.run_id,
        # 같은 run / font / field는 applied 뒤에도 덮어쓰지 않는다.
        FindingDraft(
            font_id=target.font_id,
            field_name="source_discovery",
            before_value=None,
            proposed_value={"changed": True},
            evidence_id=None,
            confidence="reference",
            review_reason="must stay immutable",
        ),
    ) == first.finding_ids[0]


def test_dry_run_writes_artifacts_without_calling_store(tmp_path: Path) -> None:
    """dry-run은 자격증명이나 DB 저장 없이 원자적 산출물과 SHA만 남긴다."""
    store = InMemoryAuditStore(fail_on_write=True)
    report = run_legal_audit(
        _targets()[:1],
        store,
        registry={"version": 1, "entries": []},
        rules={"version": 1, "standard_licenses": [], "maker_templates": []},
        dry_run=True,
        fetcher=_forbidden_fetch,
    )

    digest = write_dry_run_artifacts(report, tmp_path / "pilot")

    assert (tmp_path / "pilot.json").exists()
    assert (tmp_path / "pilot.md").exists()
    assert (tmp_path / "pilot.json.sha256").read_text(encoding="ascii") == f"{digest}\n"
    assert store.write_calls == 0

    fixture_target = replace(
        _targets()[0],
        foundry="네이버",
        candidates=(
            CandidateUrl(
                url="https://clova.ai/handwriting/list.html",
                document_role="download",
                source="official",
                name_ko="흰꼬리수리 별칭",
                maker="네이버",
                dry_run_status="broken",
            ),
        ),
    )
    fixture_report = run_legal_audit(
        [fixture_target],
        store,
        registry={
            "version": 1,
            "entries": [
                {
                    "maker": "네이버",
                    "domain": "clova.ai",
                    "roles": ["download"],
                    "source_kind": "official",
                    "approved_by": "reviewer",
                    "approved_at": "2026-07-18T00:00:00Z",
                    "evidence_snapshot_id": "evidence-1",
                }
            ],
        },
        rules={"version": 1, "standard_licenses": [], "maker_templates": []},
        dry_run=True,
        fetcher=_forbidden_fetch,
    )
    assert fixture_report.broken_count == 1

    with pytest.raises(ValueError, match="ALLOWLIST"):
        AuditSettings(
            supabase_dev_url="https://unapproved.supabase.co",
            supabase_dev_secret_key="not-logged",
        ).dev_write_credentials()

    with pytest.raises(AuditGateError, match="target count"):
        report.__class__(
            run_id=report.run_id,
            stage="legal",
            dry_run=True,
            targets=[],
            snapshot_ids=[],
            finding_ids=[],
        ).assert_safe()
