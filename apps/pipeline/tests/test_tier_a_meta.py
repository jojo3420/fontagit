"""Tier A 공식 메타데이터 수집기 테스트."""

from uuid import UUID, uuid4

from fontagit_pipeline.audit_http import FetchResult
from fontagit_pipeline.audit_metadata import derive_proposed_value
from fontagit_pipeline.audit_policy import SourceRegistry, RegistryEntry
from fontagit_pipeline.audit_store import InMemoryAuditStore, _report_count
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


def test_extract_rights_holder_ignores_ofl_boilerplate() -> None:
    """OFL copyright 관용구("이 프로젝트의 저작자들")는 실제 제작사가 아니므로 None."""
    # "The X Project Authors"
    assert extract_rights_holder(
        "Copyright 2020 The Playfair Display Project Authors "
        "(https://github.com/clauseggers/Playfair-Display)"
    ) is None
    assert extract_rights_holder(
        "Copyright 2015 The BM JUA Project Authors (https://github.com/dalgty12/BMJUA)"
    ) is None
    # "The X Authors" (Project 없이)
    assert extract_rights_holder(
        "Copyright 2019 The Nanum Gothic Authors (https://github.com/naver/nanumfont)"
    ) is None
    # "X Project Authors" (The 없이)
    assert extract_rights_holder(
        "Copyright 2021 Noto Sans Project Authors (https://github.com/googlefonts/noto-fonts)"
    ) is None


def test_extract_rights_holder_keeps_real_foundry_names() -> None:
    """실제 제작사명은 관용구 패턴에 걸리지 않고 그대로 추출된다."""
    assert extract_rights_holder("Copyright 2012 NHN Corporation.") == "NHN Corporation"
    assert extract_rights_holder("Copyright 2018 YoonDesign Inc") == "YoonDesign Inc"
    assert extract_rights_holder("Copyright 1999 ParaType Ltd.") == "ParaType Ltd"


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

    # 이슈 #133 재리뷰: extracted에는 designer/copyright 원문과 name_en/license_type/
    # noonnu_foundry 식별자만 남고, 구성된 제안값(foundry/foundry_url/download_url/
    # download_source_kind/license_source_url)은 담지 않는다. auto-approve CLI의 evidence
    # 대조(derive_proposed_value)는 이 원문 근거로부터 각 필드를 독립 재계산해 수집기가
    # 만든 제안값과 비교한다 - 같은 출처를 그대로 베껴 자기 자신과 비교하지 않는다.
    assert "foundry" not in snapshot.extracted
    assert "foundry_url" not in snapshot.extracted
    assert "download_url" not in snapshot.extracted
    assert "download_source_kind" not in snapshot.extracted
    assert "license_source_url" not in snapshot.extracted
    assert snapshot.extracted["name_en"] == "Noto Sans"
    assert snapshot.extracted["license_type"] == "OFL"
    assert snapshot.extracted["noonnu_foundry"] == "네이버"

    proposed_by_field = {f["field_name"]: f["proposed_value"] for f in findings}
    for field_name in (
        "foundry",
        "foundry_url",
        "download_url",
        "download_source_kind",
        "license_source_url",
    ):
        assert derive_proposed_value(field_name, snapshot.extracted) == proposed_by_field[field_name]


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


def test_collect_tier_a_meta_ofl_boilerplate_skips_foundry_finding() -> None:
    """copyright가 OFL 관용구("The X Project Authors")면 foundry/foundry_url finding은
    생성되지 않지만, download_url/download_source_kind/license_source_url은 그대로 생성된다.
    """
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
        TierATarget(
            font_id=font_id,
            name_en="Playfair Display",
            license_type="OFL",
            slug="playfair-display",
            noonnu_foundry=None,
        )
    ]

    def fake_fetcher(url: str, **kwargs: object) -> FetchResult:
        if "METADATA.pb" in url:
            content = '''name: "Playfair Display"
designer: "Claus Eggers Sørensen"
license: "OFL"
fonts {
  copyright: "Copyright 2020 The Playfair Display Project Authors (https://github.com/clauseggers/Playfair-Display)"
}
'''
            return FetchResult(
                status=200,
                final_url=url,
                content=content.encode(),
                content_sha256="pf123",
                redirect_count=0,
            )
        return FetchResult(status=404, final_url=url, content=b"", content_sha256="notfound", redirect_count=0)

    result = collect_tier_a_meta(
        run_id,
        targets,
        store,
        registry,
        norm,
        dry_run=False,
        fetcher=fake_fetcher,
    )

    assert result["target_count"] == 1
    assert result["success_count"] == 1

    created_fields = {draft.field_name for draft in store._finding_drafts.values()}
    assert "foundry" not in created_fields
    assert "foundry_url" not in created_fields
    assert "download_url" in created_fields
    assert "download_source_kind" in created_fields
    assert "license_source_url" in created_fields


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


def test_collect_tier_a_meta_report_satisfies_complete_run_contract() -> None:
    """collect_tier_a_meta의 non-dry-run 반환 dict는 AuditStore.complete_run이
    요구하는 4개 정수 키(success_count/verified_count/needs_review_count/broken_count)를
    전부 담아야 한다.

    이 계약이 깨지면 _report_count가 ValueError("invalid audit report count: ...")를
    던져 non-dry-run Tier A 수집이 항상 실패한다(회귀 재현: 이슈 없음, 실측 버그).
    InMemoryAuditStore.complete_run은 이 검증을 하지 않으므로 여기서 실제 _report_count를
    직접 호출해 계약을 잠근다.
    """
    run_id = uuid4()
    store = InMemoryAuditStore()

    # 두 도메인 모두 official 등급으로 등록해 verified_target의 5개 finding이
    # 전부 auto_applicable=True가 되도록 한다(대조군: 아래 broken_target은 fetch 실패).
    registry = SourceRegistry(
        version=1,
        entries=[
            RegistryEntry(
                maker="Google Fonts (official)",
                domain="fonts.google.com",
                roles=["download", "homepage"],
                source_kind="official",
                approved_by="reviewer",
                approved_at="2026-07-18T00:00:00Z",
                evidence_snapshot_id="evidence-1",
            ),
            RegistryEntry(
                maker="google/fonts GitHub (official)",
                domain="raw.githubusercontent.com",
                roles=["license", "metadata"],
                source_kind="official",
                approved_by="reviewer",
                approved_at="2026-07-18T00:00:00Z",
                evidence_snapshot_id="evidence-2",
            ),
        ],
    )
    norm = BrandNormalization(entries=[BrandEntry(
        source_name="NHN Corporation", display_name="네이버",
        evidence_url="https://hangeul.naver.com/fonts", status="approved")])

    verified_target = TierATarget(
        font_id=uuid4(),
        name_en="Verified Font",
        license_type="OFL",
        slug="verified-font",
        noonnu_foundry="네이버",
    )
    broken_target = TierATarget(
        font_id=uuid4(),
        name_en="Broken Font",
        license_type="OFL",
        slug="broken-font",
        noonnu_foundry=None,
    )

    def fake_fetcher(url: str, **kwargs: object) -> FetchResult:
        if "verifiedfont" in url.lower() and "METADATA.pb" in url:
            content = '''name: "Verified Font"
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
                content_sha256="verified123",
                redirect_count=0,
            )
        return FetchResult(
            status=404,
            final_url=url,
            content=b"",
            content_sha256="notfound",
            redirect_count=0,
        )

    result = collect_tier_a_meta(
        run_id,
        [verified_target, broken_target],
        store,
        registry,
        norm,
        dry_run=False,
        fetcher=fake_fetcher,
    )

    assert result["target_count"] == 2
    assert result["success_count"] == 1
    assert result["error_count"] == 1
    assert result["verified_count"] == 1
    assert result["needs_review_count"] == 0
    assert result["broken_count"] == 1
    # 성공 대상은 verified/needs_review 어느 한쪽으로만 집계되고, broken은 error와 같다
    assert result["verified_count"] + result["needs_review_count"] == result["success_count"]
    assert result["broken_count"] == result["error_count"]

    # complete_run이 실제로 호출하는 _report_count를 직접 통과시켜 계약을 잠근다
    for key in ("success_count", "verified_count", "needs_review_count", "broken_count"):
        assert isinstance(result[key], int)
        assert _report_count(result, key) == result[key]
