"""Tier A 공식 메타데이터 수집기 테스트."""

from uuid import UUID, uuid4

from fontagit_pipeline.audit_http import FetchResult
from fontagit_pipeline.audit_policy import SourceRegistry, RegistryEntry
from fontagit_pipeline.audit_store import InMemoryAuditStore
from fontagit_pipeline.tier_a_meta import (
    BrandEntry,
    BrandNormalization,
    TierATarget,
    build_specimen_url,
    collect_tier_a_meta,
    extract_rights_holder,
    parse_metadata_pb,
    resolve_foundry,
)


METADATA_FIXTURE = '''name: "Nanum Myeongjo"
designer: "Sandoll Communication"
license: "OFL"
category: "SERIF"
fonts {
  copyright: "Copyright © 2010 NHN Corporation."
}
'''


def test_parse_metadata_pb() -> None:
    meta = parse_metadata_pb(METADATA_FIXTURE)
    assert meta.designer == "Sandoll Communication"
    assert meta.copyright == "Copyright © 2010 NHN Corporation."


def test_extract_rights_holder() -> None:
    assert extract_rights_holder("Copyright © 2010 NHN Corporation.") == "NHN Corporation"
    assert extract_rights_holder("Copyright (c) 2015, Spoqa Inc.") == "Spoqa Inc"
    assert extract_rights_holder("") is None


def test_resolve_foundry_normalized_match() -> None:
    """눈누 표기와 정규화된 권리사가 일치(approved 항목)하면 auto, 아니면 needs_review."""
    norm = BrandNormalization(entries=[BrandEntry(
        source_name="NHN Corporation", display_name="네이버",
        evidence_url="https://hangeul.naver.com/fonts", status="approved")])
    ok = resolve_foundry("네이버", "NHN Corporation", norm)
    assert ok.value == "네이버" and ok.status == "auto"
    miss = resolve_foundry("어딘가", "NHN Corporation", norm)
    assert miss.status == "needs_review"
    pending = resolve_foundry("네이버", "NHN Corporation", BrandNormalization(entries=[BrandEntry(
        source_name="NHN Corporation", display_name="네이버",
        evidence_url="https://hangeul.naver.com/fonts", status="needs_review")]))
    assert pending.status == "needs_review"


def test_build_specimen_url() -> None:
    assert build_specimen_url("Nanum Myeongjo") == "https://fonts.google.com/specimen/Nanum+Myeongjo"


# Integration tests

def test_collect_tier_a_meta_success() -> None:
    """성공 시 5개 필드 findings 생성 및 저장."""
    # Setup
    run_id = uuid4()
    store = InMemoryAuditStore()
    font_id = uuid4()

    registry = SourceRegistry(
        version=1,
        entries=[
            RegistryEntry(
                maker="Google Fonts (archive)",
                domain="fonts.google.com",
                roles=["download", "homepage"],
                source_kind="archive",
            ),
            RegistryEntry(
                maker="google/fonts GitHub (archive)",
                domain="raw.githubusercontent.com",
                roles=["license", "metadata"],
                source_kind="archive",
            ),
        ],
    )

    norm = BrandNormalization(entries=[BrandEntry(
        source_name="NHN Corporation", display_name="네이버",
        evidence_url="https://hangeul.naver.com/fonts", status="approved")])

    targets = [
        TierATarget(
            font_id=font_id,
            name_en="Noto Sans",
            license_type="OFL",
            slug="noto-sans",
            noonnu_foundry="네이버",
        )
    ]

    # Fake fetcher
    def fake_fetcher(url: str, **kwargs: object) -> FetchResult:
        if "METADATA.pb" in url:
            content = '''name: "Noto Sans"
designer: "Google"
license: "OFL"
fonts {
  copyright: "Copyright © 2012 NHN Corporation."
}
'''
            return FetchResult(
                status=200,
                final_url=url,
                content=content.encode(),
                content_sha256="abc123",
                redirect_count=0,
            )
        return FetchResult(
            status=404,
            final_url=url,
            content=b"",
            content_sha256="def456",
            redirect_count=0,
        )

    # Execute
    result = collect_tier_a_meta(
        run_id,
        targets,
        store,
        registry,
        norm,
        dry_run=False,
        fetcher=fake_fetcher,
    )

    # Verify
    assert result["target_count"] == 1
    assert result["success_count"] == 1
    assert result["error_count"] == 0
    # 5개 필드: foundry, foundry_url, download_url, download_source_kind, license_source_url
    assert result["findings_created"] >= 5

    # dry-run 검수용 findings 상세: 개수가 findings_created와 일치하고 필수 키를 담는다
    findings = result["findings"]
    assert len(findings) == result["findings_created"]
    expected_keys = {
        "slug",
        "name_en",
        "field_name",
        "before_value",
        "proposed_value",
        "auto_applicable",
        "review_reason",
    }
    for finding in findings:
        assert expected_keys.issubset(finding.keys())
        assert finding["slug"] == "noto-sans"
        assert finding["name_en"] == "Noto Sans"

    foundry_finding = next(f for f in findings if f["field_name"] == "foundry")
    assert foundry_finding["before_value"] == "네이버"
    assert foundry_finding["proposed_value"] == "네이버"
    assert foundry_finding["auto_applicable"] is True
    assert result["errors"] == []

    # 이슈 #131: dry_run=False면 Tier A 근거 스냅샷이 저장되고,
    # 5개 finding 모두 같은 evidence_id(스냅샷 id)로 연결된다.
    evidence_ids = {finding["evidence_id"] for finding in findings}
    assert None not in evidence_ids
    assert len(evidence_ids) == 1
    snapshot_id = UUID(next(iter(evidence_ids)))
    run_id_stored, snapshot = store.snapshot_draft(snapshot_id)
    assert run_id_stored == run_id
    assert snapshot.provider == "google-fonts"
    assert snapshot.provider_record_id == "Noto Sans"
    # 이슈 #133: google/fonts raw.githubusercontent.com 근거는 archive 등급으로 저장한다
    # (public으로 저장하면 일반 metadata 승인 분기의 official/public 허용과 겹친다).
    assert snapshot.source_kind == "archive"
    assert snapshot.document_kind == "metadata"
    assert snapshot.extracted["evidence_role"] == "tier-a-metadata-pb"

    # 이슈 #133: extracted에 각 필드의 최종 제안값을 담아 auto-approve CLI의 evidence 대조
    # (derive_proposed_value)가 실제 파싱 결과와 맞물리게 한다.
    proposed_by_field = {f["field_name"]: f["proposed_value"] for f in findings}
    assert snapshot.extracted["foundry"] == proposed_by_field["foundry"]
    assert snapshot.extracted["foundry_url"] == proposed_by_field["foundry_url"]
    assert snapshot.extracted["download_url"] == proposed_by_field["download_url"]
    assert snapshot.extracted["download_source_kind"] == proposed_by_field["download_source_kind"]
    assert snapshot.extracted["license_source_url"] == proposed_by_field["license_source_url"]


def test_collect_tier_a_meta_dry_run_skips_snapshot() -> None:
    """이슈 #131: dry_run=True면 스냅샷을 저장하지 않고 evidence_id는 None으로 남는다."""
    run_id = uuid4()
    store = InMemoryAuditStore()
    font_id = uuid4()

    registry = SourceRegistry(
        version=1,
        entries=[
            RegistryEntry(
                maker="Google Fonts (archive)",
                domain="fonts.google.com",
                roles=["download", "homepage"],
                source_kind="archive",
            ),
            RegistryEntry(
                maker="google/fonts GitHub (archive)",
                domain="raw.githubusercontent.com",
                roles=["license", "metadata"],
                source_kind="archive",
            ),
        ],
    )
    norm = BrandNormalization(entries=[])
    targets = [
        TierATarget(font_id=font_id, name_en="Noto Sans", license_type="OFL", noonnu_foundry=None)
    ]

    def fake_fetcher(url: str, **kwargs: object) -> FetchResult:
        if "METADATA.pb" in url:
            content = '''name: "Noto Sans"
designer: "Google"
license: "OFL"
fonts {
  copyright: "Copyright © 2012 Google Inc."
}
'''
            return FetchResult(
                status=200, final_url=url, content=content.encode(),
                content_sha256="abc123", redirect_count=0,
            )
        return FetchResult(status=404, final_url=url, content=b"", content_sha256="def456", redirect_count=0)

    result = collect_tier_a_meta(run_id, targets, store, registry, norm, dry_run=True, fetcher=fake_fetcher)

    assert result["success_count"] == 1
    assert store._snapshot_drafts == {}
    assert store._finding_drafts == {}
    for finding in result["findings"]:
        assert finding["evidence_id"] is None


def test_collect_tier_a_meta_fetch_failure() -> None:
    """fetch 실패 시 skip + 로그 + findings 0건."""
    run_id = uuid4()
    store = InMemoryAuditStore()
    font_id = uuid4()

    registry = SourceRegistry(version=1, entries=[])
    norm = BrandNormalization(entries=[])

    targets = [
        TierATarget(
            font_id=font_id,
            name_en="Unknown Font",
            license_type="OFL",
            slug="unknown-font",
            noonnu_foundry=None,
        )
    ]

    # Fake fetcher returning 404
    def fake_fetcher(url: str, **kwargs: object) -> FetchResult:
        return FetchResult(
            status=404,
            final_url=url,
            content=b"",
            content_sha256="notfound",
            redirect_count=0,
        )

    # Execute
    result = collect_tier_a_meta(
        run_id,
        targets,
        store,
        registry,
        norm,
        dry_run=False,
        fetcher=fake_fetcher,
    )

    # Verify
    assert result["target_count"] == 1
    assert result["success_count"] == 0
    assert result["error_count"] == 1
    assert result["findings_created"] == 0
    assert result["findings"] == []

    # 실패 건 상세: slug/name_en/reason으로 사람이 원인을 확인할 수 있어야 한다
    assert len(result["errors"]) == 1
    error = result["errors"][0]
    assert error["slug"] == "unknown-font"
    assert error["name_en"] == "Unknown Font"
    assert "404" in error["reason"]


def test_collect_tier_a_meta_downgrade_block() -> None:
    """may_update_source_kind 강등 차단: 현재 official인데 archive를 제안하면 건너뛴다."""
    run_id = uuid4()
    store = InMemoryAuditStore()
    font_id = uuid4()

    # registry: 정상적으로 archive 등급 등록
    registry = SourceRegistry(
        version=1,
        entries=[
            RegistryEntry(
                maker="Google Fonts (archive)",
                domain="fonts.google.com",
                roles=["download"],
                source_kind="archive",
            ),
            RegistryEntry(
                maker="google/fonts GitHub (archive)",
                domain="raw.githubusercontent.com",
                roles=["license"],
                source_kind="archive",
            ),
        ],
    )

    norm = BrandNormalization(entries=[])

    targets = [
        TierATarget(
            font_id=font_id,
            name_en="Test Font",
            license_type="OFL",
            noonnu_foundry=None,
            # 현재 official 등급인데 archive를 제안받는 강등 시나리오
            download_source_kind="official",
            license_source_kind="official",
        )
    ]

    def fake_fetcher(url: str, **kwargs: object) -> FetchResult:
        if "METADATA.pb" in url:
            content = '''name: "Test Font"
designer: "Test"
license: "OFL"
fonts {
  copyright: "Copyright © 2024, Test Inc."
}
'''
            return FetchResult(
                status=200,
                final_url=url,
                content=content.encode(),
                content_sha256="test123",
                redirect_count=0,
            )
        return FetchResult(
            status=404,
            final_url=url,
            content=b"",
            content_sha256="notfound",
            redirect_count=0,
        )

    # Execute
    result = collect_tier_a_meta(
        run_id,
        targets,
        store,
        registry,
        norm,
        dry_run=False,
        fetcher=fake_fetcher,
    )

    # Verify: 현재(official)보다 낮은 archive 제안은 강등 차단되어 foundry만 생성됨
    # (download_url/download_source_kind/license_source_url은 모두 강등이라 건너뜀)
    assert result["target_count"] == 1
    assert result["success_count"] == 1
    assert result["findings_created"] == 1  # foundry만 (no foundry_url: no norm entry)

    created_fields = {draft.field_name for draft in store._finding_drafts.values()}
    assert created_fields == {"foundry"}
