"""cmap 기반 문자 지원과 메타데이터 비교의 핵심 계약."""

from uuid import uuid4

from fontagit_pipeline.audit_metadata import (
    BASIC_LATIN,
    KS_X_1001_HANGUL,
    FontFileMetadata,
    classify_face_scripts,
    classify_scripts,
    compare_metadata,
)
from fontagit_pipeline.audit_runner import FontTarget
from fontagit_pipeline.audit_store import SnapshotDraft


def _target(*, name_en: str = "Example Sans", weights: tuple[int, ...] = (400,)) -> FontTarget:
    return FontTarget(
        font_id=uuid4(),
        slug="example-sans",
        name_ko="예제 산스",
        name_en=name_en,
        source_tier="B",
        provider="noonnu",
        provider_record_id="1",
        reference_url="https://noonnu.cc/font_page/1",
        weights=weights,
    )


def _official_snapshot() -> SnapshotDraft:
    return SnapshotDraft(
        font_id=uuid4(),
        provider="official",
        provider_record_id="example-sans",
        source_kind="official",
        document_kind="metadata",
        request_url="https://example.com/font",
        final_url="https://example.com/example-sans.woff2",
        extracted={"family": "Example Sans"},
        evidence_locations={"font_file": "download"},
        normalized_sha256="1" * 64,
        raw_sha256="2" * 64,
    )


def _metadata(*, family: str, weight: int, italic: bool) -> FontFileMetadata:
    return FontFileMetadata(
        families=(family,),
        weight=weight,
        italic=italic,
        codepoints=frozenset(BASIC_LATIN),
        file_sha256="3" * 64,
        parser_version="fonttools-v1",
    )


def test_split_files_are_unioned_before_korean_classification() -> None:
    shard_a = set(sorted(KS_X_1001_HANGUL)[::2])
    shard_b = set(KS_X_1001_HANGUL) - shard_a

    coverage = classify_face_scripts([shard_a, shard_b | BASIC_LATIN])

    assert coverage.subsets == ["korean", "latin"]
    assert coverage.hangul_glyph_count >= 2350
    assert coverage.status == "verified"


def test_basic_latin_only_cmap_is_not_korean() -> None:
    coverage = classify_scripts(set(BASIC_LATIN))

    assert coverage.subsets == ["latin"]
    assert coverage.status == "verified"


def test_partial_hangul_requires_review() -> None:
    coverage = classify_scripts({0xAC00, 0xB098} | set(BASIC_LATIN))

    assert coverage.subsets == ["latin"]
    assert coverage.status == "needs_review"


def test_official_file_confirms_weight_and_italic() -> None:
    findings = compare_metadata(
        _target(),
        _official_snapshot(),
        _metadata(family="Example Sans", weight=700, italic=True),
    )

    proposed = {finding.field_name: finding.proposed_value for finding in findings}
    assert proposed["weights"] == [700]
    assert proposed["variants"] == ["italic"]


def test_page_file_family_conflict_requires_review() -> None:
    findings = compare_metadata(
        _target(),
        _official_snapshot(),
        _metadata(family="Other Font", weight=400, italic=False),
    )

    assert findings
    assert all(item.auto_applicable is False for item in findings)
