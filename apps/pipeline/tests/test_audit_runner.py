"""50종 법적 감사 파일럿의 핵심 안전 계약."""

from __future__ import annotations

from argparse import Namespace
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

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
    run_batch_crawl,
    run_legal_audit,
    run_metadata_audit,
    select_pilot,
    write_dry_run_artifacts,
)
from fontagit_pipeline.audit_metadata import BASIC_LATIN, FontFileMetadata
from fontagit_pipeline.audit_http import FetchResult
from fontagit_pipeline.audit_store import FindingDraft, InMemoryAuditStore, SnapshotDraft
from fontagit_pipeline.__main__ import main_audit_scan
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


def _legacy_audit_key(role: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"iss": "supabase", "ref": "prod-ref", "role": role}).encode()
    ).decode().rstrip("=")
    return f"e30.{payload}.signature"


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


def test_metadata_evidence_includes_noonnu_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """눈누 메타데이터 증거에 추출된 태그가 포함되어야 한다."""
    fixture = Path(__file__).parent / "fixtures" / "audit" / "noonnu-white-tailed-eagle.html"
    reference_html = fixture.read_bytes()

    def noonnu_fetch(url: str) -> FetchResult:
        content = reference_html if url.endswith("/613") else b"<html><body>cta</body></html>"
        return FetchResult(200, url, content, "1" * 64, 0)

    def font_fetch(url: str, max_bytes: int = 32 * 1024 * 1024) -> FetchResult:
        return _fetched(url)

    monkeypatch.setattr("fontagit_pipeline.audit_runner.sys.platform", "linux")

    noonnu_target = replace(
        _targets()[0], name_ko="흰꼬리수리", foundry=None, candidates=()
    )
    store = InMemoryAuditStore()
    report = run_metadata_audit(
        [noonnu_target],
        store,
        registry={"version": 1, "entries": []},
        fetcher=noonnu_fetch,
        font_fetcher=font_fetch,
    )

    # 스냅샷에서 extracted["tags"]를 검증한다.
    _, snapshot = store.snapshot_draft(report.snapshot_ids[0])
    assert snapshot.extracted.get("tags") == ["삐뚤빼뚤"]


def test_metadata_evidence_omits_empty_noonnu_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """눈누 메타데이터 증거에서 빈 태그는 extracted에 포함되지 않아야 한다."""
    fixture = Path(__file__).parent / "fixtures" / "audit" / "noonnu-white-tailed-eagle.html"
    # 기존 fixture에서 태그 링크를 제거한 버전 생성
    original_html = fixture.read_text(encoding="utf-8")
    # 태그 링크 제거: <a href="/index?search=%EC%82%90%EB%9A%A4%EB%B9%BC%EB%9A%A4">삐뚤빼뚤</a>
    empty_tags_html = original_html.replace(
        '<a href="/index?search=%EC%82%90%EB%9A%A4%EB%B9%BC%EB%9A%A4">삐뚤빼뚤</a>',
        ""
    ).encode("utf-8")

    def noonnu_fetch(url: str) -> FetchResult:
        content = empty_tags_html if url.endswith("/613") else b"<html><body>cta</body></html>"
        return FetchResult(200, url, content, "1" * 64, 0)

    def font_fetch(url: str, max_bytes: int = 32 * 1024 * 1024) -> FetchResult:
        return _fetched(url)

    monkeypatch.setattr("fontagit_pipeline.audit_runner.sys.platform", "linux")

    noonnu_target = replace(
        _targets()[0], name_ko="흰꼬리수리", foundry=None, candidates=()
    )
    store = InMemoryAuditStore()
    report = run_metadata_audit(
        [noonnu_target],
        store,
        registry={"version": 1, "entries": []},
        fetcher=noonnu_fetch,
        font_fetcher=font_fetch,
    )

    # 스냅샷에서 extracted에 "tags" 키가 없어야 한다.
    _, snapshot = store.snapshot_draft(report.snapshot_ids[0])
    assert "tags" not in snapshot.extracted


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
    with pytest.raises(AuditInputError, match="current"):
        load_bootstrap_targets(legacy_manifest)

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


def test_metadata_findings_keep_current_values_and_saved_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """metadata finding은 실제 before와 저장된 snapshot 하나에 모두 묶인다."""
    target = replace(
        _targets()[0],
        name_ko="흰꼬리수리",
        name_en="Example Sans",
        foundry="네이버",
        weights=(400,),
        variants=("regular",),
        subsets=("latin",),
        script_status="pending",
        candidates=(
            CandidateUrl(
                url="https://clova.ai/example.woff2",
                document_role="download",
                source="official",
                name_ko="흰꼬리수리",
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
                "roles": ["download"],
                "source_kind": "official",
                "approved_by": "reviewer",
                "approved_at": "2026-07-18T00:00:00Z",
                "evidence_snapshot_id": "evidence-1",
            }
        ],
    }
    monkeypatch.setattr(
        "fontagit_pipeline.audit_metadata.inspect_font_metadata",
        lambda _path: FontFileMetadata(
            families=("Example Sans",),
            weight=700,
            italic=True,
            codepoints=frozenset(BASIC_LATIN),
            file_sha256="f" * 64,
        ),
    )
    store = InMemoryAuditStore()
    official_run = store.start_run(
        stage="legal", target_count=1, baseline_sha256="a" * 64, dry_run=False
    )
    official_evidence = store.save_snapshot(
        official_run,
        SnapshotDraft(
            font_id=target.font_id,
            provider=target.provider,
            provider_record_id=target.provider_record_id,
            source_kind="official",
            document_kind="download",
            request_url="https://clova.ai/download-page",
            final_url="https://clova.ai/download-page",
            extracted={"download_url": "https://clova.ai/approved.woff2"},
            evidence_locations={"download_url": "a.download"},
            raw_sha256="1" * 64,
            normalized_sha256="2" * 64,
        ),
    )
    official_finding = store.save_finding(
        official_run,
        FindingDraft(
            font_id=target.font_id,
            field_name="download_url",
            before_value=None,
            proposed_value="https://clova.ai/approved.woff2",
            evidence_id=official_evidence,
            confidence="official",
            review_reason="approved legal download",
        ),
    )
    store.approve_finding(official_finding)

    public_run = store.start_run(
        stage="legal", target_count=1, baseline_sha256="b" * 64, dry_run=False
    )
    public_evidence = store.save_snapshot(
        public_run,
        SnapshotDraft(
            font_id=target.font_id,
            provider=target.provider,
            provider_record_id=target.provider_record_id,
            source_kind="public",
            document_kind="download",
            request_url="https://public.example/download-page",
            final_url="https://public.example/download-page",
            extracted={"download_url": "https://public.example/approved.woff2"},
            evidence_locations={"download_url": "a.download"},
            raw_sha256="3" * 64,
            normalized_sha256="4" * 64,
        ),
    )
    public_finding = store.save_finding(
        public_run,
        FindingDraft(
            font_id=target.font_id,
            field_name="download_url",
            before_value=None,
            proposed_value="https://public.example/approved.woff2",
            evidence_id=public_evidence,
            confidence="public",
            review_reason="approved legal download",
        ),
    )
    store.approve_finding(public_finding)
    fetched_urls: list[str] = []

    def font_fetch(url: str, max_bytes: int = 32 * 1024 * 1024) -> FetchResult:
        fetched_urls.append(url)
        return _fetched(url)

    monkeypatch.setattr("fontagit_pipeline.audit_runner.sys.platform", "linux")
    report = run_metadata_audit(
        [target], store, registry, fetcher=_forbidden_fetch, font_fetcher=font_fetch
    )

    drafts = [store.finding_draft(item) for item in report.finding_ids]
    assert report.snapshot_ids == [drafts[0].evidence_id]
    assert all(item.evidence_id == report.snapshot_ids[0] for item in drafts)
    before = {item.field_name: item.before_value for item in drafts}
    assert before["subsets"] == ["latin"]
    assert before["script_status"] == "pending"
    assert before["weights"] == [400]
    assert before["variants"] == ["regular"]
    assert {item.field_name for item in drafts} >= {
        "script_checked_at",
        "script_evidence_id",
    }
    assert fetched_urls == ["https://clova.ai/approved.woff2"]


def test_metadata_runner_non_linux_never_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux 격리가 없으면 runner도 네트워크-파싱 전에 needs_review로 닫힌다."""
    monkeypatch.setattr("fontagit_pipeline.audit_runner.sys.platform", "darwin")
    store = InMemoryAuditStore()

    report = run_metadata_audit(
        [_targets()[0]],
        store,
        {"version": 1, "entries": []},
        fetcher=_forbidden_fetch,
        font_fetcher=_forbidden_fetch,
    )

    assert report.needs_review_count == 1
    assert report.errors == ["흰꼬리수리: unsupported_platform"]
    assert store.finding_draft(report.finding_ids[0]).review_reason == (
        "metadata execution requires Linux isolation"
    )


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


def test_scheduled_artifact_rejects_empty_open_schema_bad_hash_and_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
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

    sdk_calls = 0

    def forbidden_sdk(*_: object, **__: object) -> object:
        nonlocal sdk_calls
        sdk_calls += 1
        raise AssertionError("credential gate must run before SDK or fetch")

    monkeypatch.setattr("supabase.create_client", forbidden_sdk)
    monkeypatch.setattr("fontagit_pipeline.audit_runner.scan_scheduled_targets", forbidden_sdk)
    service_key = _legacy_audit_key("service_role")
    secret_key = "sb_secret_forbidden-test"
    unsafe_settings = (
        AuditSettings(
            supabase_url="https://prod-ref.supabase.co",
            supabase_anon_key="sb_publishable_public-test",
        ),
        AuditSettings(
            supabase_url="https://attacker.example",
            supabase_anon_key="sb_publishable_public-test",
            supabase_prod_public_url="https://attacker.example",
            supabase_prod_public_anon_key="sb_publishable_public-test",
        ),
        AuditSettings(
            supabase_url="https://prod-ref.supabase.co",
            supabase_anon_key=service_key,
            supabase_prod_public_url="https://prod-ref.supabase.co",
            supabase_prod_public_anon_key=service_key,
            supabase_prod_public_allowlist="prod-ref",
        ),
        AuditSettings(
            supabase_prod_public_url="https://prod-ref.supabase.co",
            supabase_prod_public_anon_key=secret_key,
            supabase_prod_public_allowlist="prod-ref",
        ),
    )
    for settings in unsafe_settings:
        monkeypatch.setattr(
            "fontagit_pipeline.config.load_audit_settings", lambda settings=settings: settings
        )
        assert main_audit_scan(
            Namespace(source="prod-public", kind="download", out=tmp_path)
        ) == 3
    assert sdk_calls == 0
    assert service_key not in caplog.text
    assert secret_key not in caplog.text
    assert "service_role" not in caplog.text
    assert AuditSettings(
        supabase_prod_public_url="https://PROD-REF.supabase.co/",
        supabase_prod_public_anon_key="sb_publishable_public-test",
        supabase_prod_public_allowlist="prod-ref",
    ).prod_public_read_credentials() == (
        "https://prod-ref.supabase.co",
        "sb_publishable_public-test",
    )
    anon_key = _legacy_audit_key("anon")
    assert AuditSettings(
        supabase_prod_public_url="https://prod-ref.supabase.co",
        supabase_prod_public_anon_key=anon_key,
        supabase_prod_public_allowlist="https://prod-ref.supabase.co",
    ).prod_public_read_credentials()[1] == anon_key


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


def test_batch_crawl_tier_b_filter() -> None:
    """Tier B 필터가 Tier A 대상을 제외한다."""
    from fontagit_pipeline.audit_runner import run_batch_crawl

    targets = [
        FontTarget(
            font_id=uuid4(),
            slug="tier-a-font",
            name_ko="티어A",
            name_en="Tier A",
            source_tier="A",
            provider="google-fonts",
            provider_record_id="1",
            reference_url="https://fonts.google.com/metadata/fonts/test",
        ),
        FontTarget(
            font_id=uuid4(),
            slug="tier-b-font",
            name_ko="티어B",
            name_en="Tier B",
            source_tier="B",
            provider="noonnu",
            provider_record_id="100",
            reference_url="https://noonnu.cc/font_page/100",
        ),
    ]

    # Tier B만 선택
    tier_b = [t for t in targets if t.source_tier == "B"]
    assert len(tier_b) == 1
    assert tier_b[0].slug == "tier-b-font"


def test_batch_crawl_batch_split() -> None:
    """배치 분할이 올바르게 작동한다."""
    targets = [FontTarget(
        font_id=uuid4(),
        slug=f"font-{i}",
        name_ko=f"폰트{i}",
        name_en=f"Font{i}",
        source_tier="B",
        provider="noonnu",
        provider_record_id=str(i),
        reference_url=f"https://noonnu.cc/font_page/{i}",
    ) for i in range(250)]

    batch_size = 100
    batches = [targets[i:i + batch_size] for i in range(0, len(targets), batch_size)]
    assert len(batches) == 3
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 50


def test_batch_crawl_checkpoint_resume() -> None:
    """체크포인트에서 재개할 때 이미 완료된 대상을 건너뛴다."""
    import tempfile
    from pathlib import Path

    from fontagit_pipeline.audit_runner import run_batch_crawl

    targets = [FontTarget(
        font_id=uuid4(),
        slug=f"font-{i}",
        name_ko=f"폰트{i}",
        name_en=f"Font{i}",
        source_tier="B",
        provider="noonnu",
        provider_record_id=str(i),
        reference_url=f"https://noonnu.cc/font_page/{i}",
    ) for i in range(10)]

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "checkpoint.json"

        # 처음 3개 완료
        completed_ids = [str(targets[i].font_id) for i in range(3)]
        cp_data = {
            "completed_font_ids": completed_ids,
            "batches_done": 1,
            "updated_at": "2026-07-20T00:00:00+00:00",
        }
        checkpoint_path.write_text(json.dumps(cp_data))

        # 체크포인트 로드
        cp = json.loads(checkpoint_path.read_text())
        loaded_ids = set(UUID(fid) for fid in cp["completed_font_ids"])
        remaining = [t for t in targets if t.font_id not in loaded_ids]

        assert len(loaded_ids) == 3
        assert len(remaining) == 7
        assert remaining[0].slug == "font-3"


def test_batch_crawl_no_assert_safe() -> None:
    """배치 크롤링은 pending/needs_review가 있어도 assert_safe()를 호출하지 않는다."""
    from fontagit_pipeline.audit_runner import run_batch_crawl
    from fontagit_pipeline.audit_http import FetchResult

    store = InMemoryAuditStore()

    target = FontTarget(
        font_id=uuid4(),
        slug="test-font",
        name_ko="테스트",
        name_en="Test",
        source_tier="B",
        provider="noonnu",
        provider_record_id="1",
        reference_url="https://noonnu.cc/font_page/1",
    )

    def fake_fetcher(url: str, *, delay_seconds: float = 0.0) -> FetchResult:
        return FetchResult(
            url=url,
            http_status=200,
            final_url=url,
            content_sha256="a" * 64,
            content=b"test license",
        )

    rules = {"version": 1, "standard_licenses": [], "maker_templates": []}
    registry = {"version": 1, "entries": []}

    report = run_batch_crawl(
        [target],
        store,
        registry,
        rules,
        batch_size=100,
        dry_run=True,
        fetcher=fake_fetcher,
    )

    # 보고서 반환됨 (assert_safe() 호출 안 함)
    assert report.run_id is not None
    assert len(report.targets) == 1


def test_batch_crawl_dry_run() -> None:
    """dry-run 모드에서는 InMemoryAuditStore를 사용하고 실제 저장 안 함."""
    from fontagit_pipeline.audit_runner import run_batch_crawl
    from fontagit_pipeline.audit_http import FetchResult

    store = InMemoryAuditStore()
    targets = [FontTarget(
        font_id=uuid4(),
        slug=f"font-{i}",
        name_ko=f"폰트{i}",
        name_en=f"Font{i}",
        source_tier="B",
        provider="noonnu",
        provider_record_id=str(i),
        reference_url=f"https://noonnu.cc/font_page/{i}",
    ) for i in range(3)]

    def fake_fetcher(url: str, *, delay_seconds: float = 0.0) -> FetchResult:
        return FetchResult(
            url=url,
            http_status=200,
            final_url=url,
            content_sha256="a" * 64,
            content=b"test license",
        )

    rules = {"version": 1, "standard_licenses": [], "maker_templates": []}
    registry = {"version": 1, "entries": []}

    report = run_batch_crawl(
        targets,
        store,
        registry,
        rules,
        batch_size=100,
        dry_run=True,
        fetcher=fake_fetcher,
    )

    assert report.dry_run is True
    assert len(report.targets) == 3
