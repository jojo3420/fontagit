"""50종 법적 감사 파일럿의 핵심 안전 계약."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fontagit_pipeline.audit_runner import (
    FontTarget,
    run_legal_audit,
    select_pilot,
    write_dry_run_artifacts,
)
from fontagit_pipeline.audit_store import InMemoryAuditStore


def _targets() -> list[FontTarget]:
    required = [
        FontTarget(
            font_id=uuid4(),
            slug="흰꼬리수리",
            name_ko="흰꼬리수리",
            source_tier="B",
            provider="noonnu",
            provider_record_id="613",
            reference_url="https://noonnu.cc/font_page/613",
        ),
        FontTarget(
            font_id=uuid4(),
            slug="횡성한우체",
            name_ko="횡성한우체",
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


def test_pilot_is_deterministic_and_contains_reported_fonts() -> None:
    """신고된 두 폰트는 같은 입력의 50종 표본에 반드시 포함된다."""
    targets = _targets()

    selected = select_pilot(targets, size=50)

    assert len(selected) == 50
    assert {"흰꼬리수리", "횡성한우체"} <= {target.name_ko for target in selected}
    assert selected == select_pilot(targets, size=50)


def test_same_snapshot_and_finding_are_idempotent_until_applied() -> None:
    """같은 근거는 중복 저장하지 않되 applied finding은 새 검수 건으로 남긴다."""
    store = InMemoryAuditStore()
    target = _targets()[0]

    first = run_legal_audit([target], store, registry={"version": 1, "entries": []}, rules={})
    second = run_legal_audit([target], store, registry={"version": 1, "entries": []}, rules={})

    assert first.snapshot_ids == second.snapshot_ids
    assert store.finding_count == 1

    store.mark_applied(first.finding_ids[0])
    third = run_legal_audit([target], store, registry={"version": 1, "entries": []}, rules={})

    assert third.snapshot_ids == first.snapshot_ids
    assert third.finding_ids != first.finding_ids
    assert store.finding_count == 2


def test_dry_run_writes_artifacts_without_calling_store(tmp_path: Path) -> None:
    """dry-run은 자격증명이나 DB 저장 없이 원자적 산출물과 SHA만 남긴다."""
    store = InMemoryAuditStore(fail_on_write=True)
    report = run_legal_audit(
        _targets()[:1], store, registry={"version": 1, "entries": []}, rules={}, dry_run=True
    )

    digest = write_dry_run_artifacts(report, tmp_path / "pilot")

    assert (tmp_path / "pilot.json").exists()
    assert (tmp_path / "pilot.md").exists()
    assert (tmp_path / "pilot.json.sha256").read_text(encoding="ascii") == f"{digest}\n"
    assert store.write_calls == 0
