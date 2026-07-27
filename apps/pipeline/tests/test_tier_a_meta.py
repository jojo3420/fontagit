"""Tier A 공식 메타데이터 수집기 테스트."""

from fontagit_pipeline.tier_a_meta import (
    BrandEntry,
    BrandNormalization,
    build_specimen_url,
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
