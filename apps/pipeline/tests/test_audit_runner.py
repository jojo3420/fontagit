"""50종 법적 감사 파일럿의 핵심 안전 계약."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from fontagit_pipeline.audit_runner import (
    AuditGateError,
    CandidateUrl,
    FontTarget,
    AuditInputError,
    ScheduledObservation,
    _fetched_snapshot,
    _finding_id,
    load_bootstrap_targets,
    build_scheduled_artifact,
    import_observations,
    read_regular_file_once,
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
    draft_one = FindingDraft(
        font_id=target.font_id,
        field_name="source_discovery",
        before_value=None,
        proposed_value={"first": True},
        evidence_id=None,
        confidence="reference",
        review_reason="same dry-run key",
    )
    draft_two = replace(draft_one, proposed_value={"second": True})
    assert _finding_id(first.run_id, draft_one) == _finding_id(first.run_id, draft_two)
    store.mark_applied(first.finding_ids[0])
    repeat_key = store.save_finding(
        first.run_id,
        FindingDraft(
            font_id=target.font_id,
            field_name="source_discovery",
            before_value=None,
            proposed_value={"changed": True},
            evidence_id=None,
            confidence="reference",
            review_reason="same key",
        ),
    )
    assert repeat_key == first.finding_ids[0]
    observation = {
        "font_id": str(target.font_id),
        "snapshot_id": str(first.snapshot_ids[0]),
        "normalized_url": "https://clova.ai/shared",
    }
    observation_store = InMemoryAuditStore()
    first_observation = observation_store.save_observation(first.run_id, observation)
    second_observation = observation_store.save_observation(
        first.run_id, {**observation, "snapshot_id": str(first.snapshot_ids[-1])}
    )
    assert first_observation == second_observation
    assert observation_store.observation_count == 1
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

    fixture = Path(__file__).parent / "fixtures" / "audit" / "noonnu-white-tailed-eagle.html"
    reference_html = fixture.read_bytes()

    def noonnu_fetch(url: str) -> FetchResult:
        content = reference_html if url.endswith("/613") else b"<html><body>cta</body></html>"
        return FetchResult(200, url, content, "1" * 64, 0)

    noonnu_target = replace(
        _targets()[0], name_ko="흰꼬리수리", foundry=None, candidates=()
    )
    noonnu_store = InMemoryAuditStore()
    noonnu_report = run_legal_audit(
        [noonnu_target], noonnu_store, registry={"version": 1, "entries": []}, rules=rules, fetcher=noonnu_fetch
    )
    assert [noonnu_store.finding_draft(item).proposed_value for item in noonnu_report.finding_ids] == [
        "https://clova.ai/handwriting/list.html"
    ]
    mismatch_report = run_legal_audit(
        [replace(noonnu_target, name_ko="다른 폰트")],
        InMemoryAuditStore(),
        registry={"version": 1, "entries": []},
        rules=rules,
        fetcher=noonnu_fetch,
    )
    assert mismatch_report.finding_ids == []


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

    with pytest.raises(AuditInputError, match="at least one"):
        run_legal_audit(
            [],
            InMemoryAuditStore(fail_on_write=True),
            registry={"version": 1, "entries": []},
            rules={"version": 1, "standard_licenses": [], "maker_templates": []},
            dry_run=True,
            fetcher=_forbidden_fetch,
        )

    legacy_manifest = tmp_path / "bootstrap.json"
    legacy_manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "font_id": str(uuid4()),
                        "slug": "legacy-font",
                        "provider": "noonnu",
                        "provider_record_id": "999",
                        "source_url": "https://noonnu.cc/font_page/999",
                        "before": {
                            "name_ko": "레거시 폰트",
                            "source_tier": "B",
                            "foundry": "레거시 제작사",
                            "official_url": "https://legacy.example/download",
                            "foundry_url": "https://legacy.example/",
                            "download_url": "https://legacy.example/file",
                            "license_source_url": "https://legacy.example/license",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    legacy_target = load_bootstrap_targets(legacy_manifest)[0]
    assert (
        legacy_target.foundry_url,
        legacy_target.download_url,
        legacy_target.license_source_url,
    ) == (
        "https://legacy.example/",
        "https://legacy.example/file",
        "https://legacy.example/license",
    )
    assert {(item.document_role, item.url, item.source) for item in legacy_target.candidates} == {
        ("metadata", "https://legacy.example/download", "existing-db"),
    }

    raw = b"observed source bytes"
    snapshot = _fetched_snapshot(
        _targets()[0],
        CandidateUrl("https://source.example/license", "license", "official", "name", "maker"),
        FetchResult(200, "https://source.example/license", raw, hashlib.sha256(raw).hexdigest(), 0),
        "official",
        {},
        {},
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )
    assert snapshot.raw_text is None
    assert snapshot.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert snapshot.extracted["raw_sha256"] == hashlib.sha256(raw).hexdigest()

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

    incomplete_target = replace(
        fixture_target,
        candidates=(replace(fixture_target.candidates[0], dry_run_status="verified"),),
    )
    incomplete_report = run_legal_audit(
        [incomplete_target],
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
    assert incomplete_report.verified_count == 0
    assert incomplete_report.pending_count == 1

    with pytest.raises(ValueError, match="ALLOWLIST"):
        AuditSettings(
            supabase_dev_url="https://unapproved.supabase.co",
            supabase_dev_secret_key="not-logged",
            supabase_prod_url="https://prod-ref.supabase.co",
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


def test_scheduled_download_import_requires_distinct_runs_24_hours_apart() -> None:
    """한 번의 404는 검수 대상이고, 24시간 뒤 별도 실행만 broken이다."""
    store = InMemoryAuditStore()
    font_id = uuid4()
    started = datetime(2026, 7, 18, tzinfo=UTC)
    first = build_scheduled_artifact(
        "download",
        [
            ScheduledObservation(
                font_id=font_id,
                normalized_url="https://fonts.example/file.zip",
                observed_at=started,
                http_status=404,
                final_url="https://fonts.example/file.zip",
                content_sha256=hashlib.sha256(b"missing").hexdigest(),
            )
        ],
        run_id=uuid4(),
        generated_at=started,
    )
    first_result = import_observations(first.canonical_bytes, first.sha256, store)
    assert (first_result.status, first_result.applied_count) == ("needs_review", 0)

    second = build_scheduled_artifact(
        "download",
        [replace(first.observations[0], observed_at=started + timedelta(hours=25))],
        run_id=uuid4(),
        generated_at=started + timedelta(hours=25),
    )
    second_result = import_observations(second.canonical_bytes, second.sha256, store)
    assert (second_result.status, second_result.applied_count) == ("broken", 0)
    assert import_observations(second.canonical_bytes, second.sha256, store).status == "already_imported"
    spoofed = build_scheduled_artifact(
        "download",
        [replace(second.observations[0], http_status=200)],
        run_id=second.run_id,
        generated_at=second.generated_at,
    )
    with pytest.raises(AuditGateError, match="run_id"):
        import_observations(spoofed.canonical_bytes, spoofed.sha256, store)


def test_scheduled_artifact_rejects_empty_open_schema_bad_hash_and_symlink(tmp_path: Path) -> None:
    """빈 실행, 알 수 없는 필드, 해시 불일치는 저장 전에 모두 막는다."""
    with pytest.raises(AuditGateError, match="empty artifact"):
        build_scheduled_artifact("download", [], run_id=uuid4())

    valid = build_scheduled_artifact(
        "download",
        [
            ScheduledObservation(
                font_id=uuid4(),
                normalized_url="https://fonts.example/font.zip",
                observed_at=datetime(2026, 7, 18, tzinfo=UTC),
                http_status=200,
                final_url="https://fonts.example/font.zip",
                content_sha256="a" * 64,
            )
        ],
        run_id=uuid4(),
    )
    opened = json.loads(valid.canonical_bytes)
    opened["raw_html"] = "must never be accepted"
    opened_bytes = json.dumps(opened, sort_keys=True, separators=(",", ":")).encode()
    store = InMemoryAuditStore()
    with pytest.raises(AuditGateError, match="schema"):
        import_observations(opened_bytes, hashlib.sha256(opened_bytes).hexdigest(), store)
    with pytest.raises(AuditGateError, match="SHA-256"):
        import_observations(valid.canonical_bytes, "0" * 64, store)
    artifact_path = tmp_path / "observations.json"
    artifact_path.write_bytes(valid.canonical_bytes)
    symlink_path = tmp_path / "artifact-link.json"
    symlink_path.symlink_to(artifact_path)
    with pytest.raises(AuditGateError, match="safe regular file"):
        read_regular_file_once(symlink_path, max_bytes=8 * 1024 * 1024)
    assert store.write_calls == 0


def test_scheduled_license_hash_change_creates_review_without_public_apply() -> None:
    """라이선스 본문 hash 변화는 finding만 만들고 공개값은 자동 변경하지 않는다."""
    store = InMemoryAuditStore()
    font_id = uuid4()
    started = datetime(2026, 7, 18, tzinfo=UTC)
    first = build_scheduled_artifact(
        "license",
        [
            ScheduledObservation(
                font_id=font_id,
                normalized_url="https://foundry.example/license",
                observed_at=started,
                http_status=200,
                final_url="https://foundry.example/license",
                content_sha256="a" * 64,
            )
        ],
        run_id=uuid4(),
        generated_at=started,
    )
    assert import_observations(first.canonical_bytes, first.sha256, store).status == "verified"

    changed = build_scheduled_artifact(
        "license",
        [replace(first.observations[0], observed_at=started + timedelta(days=90), content_sha256="b" * 64)],
        run_id=uuid4(),
        generated_at=started + timedelta(days=90),
    )
    result = import_observations(changed.canonical_bytes, changed.sha256, store)
    assert (result.status, result.applied_count) == ("needs_review", 0)
    assert store.finding_count == 1
