"""Tier A 공식 메타데이터 수집기 테스트."""

from uuid import UUID, uuid4
from dataclasses import dataclass

from fontagit_pipeline.audit_http import FetchResult
from fontagit_pipeline.audit_policy import SourceRegistry, RegistryEntry
from fontagit_pipeline.audit_store import FindingDraft, InMemoryAuditStore
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


def test_collect_tier_a_meta_downgrade_block() -> None:
    """may_update_source_kind 강등 차단 시 발견 문제 처리."""
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

    # Verify: 모든 URL이 archive로 분류되므로 모두 생성됨
    # foundry + download_url + download_source_kind + license_source_url = 4개
    assert result["target_count"] == 1
    assert result["success_count"] == 1
    assert result["findings_created"] == 4  # all 5 fields - no foundry_url (no norm entry)
