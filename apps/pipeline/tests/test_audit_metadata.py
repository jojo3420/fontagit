"""cmap 기반 문자 지원과 메타데이터 비교의 핵심 계약."""

import hashlib
from pathlib import Path
from uuid import uuid4

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont

from fontagit_pipeline.audit_metadata import (
    BASIC_LATIN,
    KS_X_1001_HANGUL,
    FontFileMetadata,
    classify_face_scripts,
    classify_scripts,
    compare_metadata,
    inspect_font_metadata,
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
        variants=("regular",),
        subsets=("latin",),
        script_status="pending",
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


def _font(path: Path, *, family: str = "Example Sans", italic: bool = False) -> None:
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder([".notdef", "A"])
    pen = TTGlyphPen(None)
    glyph = pen.glyph()
    builder.setupGlyf({".notdef": glyph, "A": glyph})
    builder.setupHorizontalMetrics({".notdef": (500, 0), "A": (500, 0)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupCharacterMap({0x41: "A"})
    builder.setupNameTable(
        {
            "familyName": family,
            "styleName": "Italic" if italic else "Regular",
            "uniqueFontIdentifier": f"{family}-fixture",
            "fullName": family,
            "psName": family.replace(" ", ""),
        }
    )
    builder.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        usWinAscent=800,
        usWinDescent=200,
        usWeightClass=400,
        fsSelection=1 if italic else 0,
    )
    builder.setupPost(italicAngle=0)
    builder.setupMaxp()
    builder.save(path)


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
    before = {finding.field_name: finding.before_value for finding in findings}
    assert proposed["weights"] == [700]
    assert proposed["variants"] == ["italic"]
    assert before["subsets"] == ["latin"]
    assert before["script_status"] == "pending"
    assert before["weights"] == [400]
    assert before["variants"] == ["regular"]


def test_page_file_family_conflict_requires_review() -> None:
    findings = compare_metadata(
        _target(),
        _official_snapshot(),
        _metadata(family="Other Font", weight=400, italic=False),
    )

    assert findings
    assert all(item.auto_applicable is False for item in findings)


def test_inspect_uses_full_sha_and_os2_italic_bit(tmp_path: Path) -> None:
    path = tmp_path / "italic.ttf"
    _font(path, italic=True)

    metadata = inspect_font_metadata(path)

    assert metadata.file_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert metadata.italic is True
    assert metadata.inspection_status == "parsed"


def test_collection_is_never_verified_as_one_face(tmp_path: Path) -> None:
    first_path = tmp_path / "first.ttf"
    second_path = tmp_path / "second.ttf"
    collection_path = tmp_path / "same-family.ttc"
    _font(first_path)
    _font(second_path)
    collection = TTCollection()
    collection.fonts = [TTFont(first_path), TTFont(second_path)]
    collection.save(collection_path)
    collection.close()

    metadata = inspect_font_metadata(collection_path)

    assert metadata.face_conflict is True
    assert metadata.inspection_status == "needs_review"
