"""prod 기준선과 안정 출처키 bootstrap 테스트."""

import hashlib
import json
from pathlib import Path

import pytest

from fontagit_pipeline.audit_bootstrap import (
    BootstrapError,
    build_bootstrap_manifest,
    load_prod_baseline,
    write_bootstrap_manifest,
    write_prod_baseline,
)

INSTAGRAM_URL = "https://www.instagram.com/p/example/"


def prod_font(
    slug: str,
    name_ko: str,
    official_url: str,
    *,
    source_tier: str = "B",
    name_en: str = "",
) -> dict[str, object]:
    return {
        "id": f"font-{slug}",
        "slug": slug,
        "name_ko": name_ko,
        "name_en": name_en or slug,
        "source_tier": source_tier,
        "official_url": official_url,
        "foundry": None,
        "updated_at": "2026-07-18T00:00:00+00:00",
    }


def tier_b_seed(
    page_id: str,
    name_ko: str,
    official_url: str,
) -> dict[str, object]:
    return {
        "name_ko": name_ko,
        "name_en": None,
        "official_url": official_url,
        "source_page": f"https://noonnu.cc/font_page/{page_id}",
    }


def test_tier_b_exact_match_builds_no_public_update_and_atomic_artifact(
    tmp_path: Path,
) -> None:
    """완전 일치는 안정키만 연결하고 공개 필드는 바꾸지 않는다."""
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[
            {
                **tier_b_seed("613", "흰꼬리수리", INSTAGRAM_URL),
                "slug": "시드에-존재하지-않는-값",
            }
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (1, 0, 0)
    entry = result.entries[0]
    assert (entry.provider, entry.provider_record_id) == ("noonnu", "613")
    assert entry.public_updates == {}
    assert entry.before["source_tier"] == "B"
    assert entry.before["foundry"] is None

    out = tmp_path / "nested" / "bootstrap.json"
    digest = write_bootstrap_manifest(result, out)

    assert out.exists()
    assert out.with_suffix(".json.sha256").read_text(encoding="utf-8") == f"{digest}\n"
    assert hashlib.sha256(out.read_bytes()).hexdigest() == digest
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["provider_record_id"] == "613"


def test_zero_or_multiple_candidates_are_review_only() -> None:
    """후보가 없거나 여럿이면 추측하지 않고 검수 대상으로 남긴다."""
    result = build_bootstrap_manifest(
        prod_rows=[
            prod_font("동일", "동일", INSTAGRAM_URL),
            prod_font("missing", "없음", INSTAGRAM_URL),
            {
                **prod_font("제작사-있음", "제작사 있음", INSTAGRAM_URL),
                "foundry": "기존 제작사",
            },
            prod_font(
                "wrong-tier",
                "잘못된 Tier A",
                INSTAGRAM_URL,
                source_tier="A",
                name_en="Wrong Tier",
            ),
        ],
        tier_a=[
            {
                "source_tier": "B",
                "slug": "wrong-tier",
                "name_en": "Wrong Tier",
                "official_url": INSTAGRAM_URL,
            }
        ],
        tier_b=[
            tier_b_seed("1", "동일", INSTAGRAM_URL),
            tier_b_seed("2", "동일", INSTAGRAM_URL),
            tier_b_seed("3", "제작사 있음", INSTAGRAM_URL),
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (0, 3, 1)
    assert result.entries == []
    assert {row["reason"] for row in result.review_rows} == {
        "no_exact_candidate",
        "multiple_candidates",
        "foundry_precondition_not_null",
    }
    assert next(row for row in result.review_rows if row["slug"] == "wrong-tier")[
        "reason"
    ] == "no_exact_candidate"


def test_invalid_tier_b_source_page_is_never_used_as_provider_id() -> None:
    """눈누 페이지 번호를 엄격히 파싱하지 못하면 자동 연결하지 않는다."""
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[
            {
                **tier_b_seed("613/extra", "흰꼬리수리", INSTAGRAM_URL),
                "source_page": "https://noonnu.cc/font_page/613/extra",
            }
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (0, 1, 0)
    assert result.review_rows[0]["reason"] == "invalid_provider_record_id"


def test_prod_baseline_sorts_slug_before_hashing(tmp_path: Path) -> None:
    """기준선은 DB 정렬 환경과 무관하게 slug 순서를 고정한다."""
    rows = [
        prod_font(
            f"font-{index:04d}",
            f"폰트 {index}",
            INSTAGRAM_URL,
            source_tier="A" if index < 130 else "B",
        )
        for index in reversed(range(1240))
    ]
    out = tmp_path / "prod-baseline.json"

    write_prod_baseline(rows, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    slugs = [row["slug"] for row in payload["rows"]]
    assert slugs == sorted(slugs)


def test_prod_baseline_requires_complete_sorted_hashed_snapshot(tmp_path: Path) -> None:
    """부분·변조·정렬 오류 기준선은 bootstrap 전에 거부한다."""
    rows = [
        prod_font("a", "가", INSTAGRAM_URL),
        prod_font("b", "나", INSTAGRAM_URL),
    ]
    baseline = tmp_path / "prod-baseline.json"
    file_sha256 = write_prod_baseline(
        rows,
        baseline,
        expected_record_count=2,
        expected_tier_counts=None,
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))

    assert payload["baseline_content_sha256"]
    assert baseline.with_suffix(".json.sha256").read_text(encoding="utf-8") == f"{file_sha256}\n"
    assert load_prod_baseline(
        baseline,
        expected_record_count=2,
        expected_tier_counts=None,
    ) == rows

    payload["baseline_content_sha256"] = "0" * 64
    changed_content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    baseline.write_bytes(changed_content)
    baseline.with_suffix(".json.sha256").write_text(
        f"{hashlib.sha256(changed_content).hexdigest()}\n", encoding="ascii"
    )
    with pytest.raises(BootstrapError, match="baseline content SHA-256"):
        load_prod_baseline(
            baseline,
            expected_record_count=2,
            expected_tier_counts=None,
        )

    write_prod_baseline(
        rows,
        baseline,
        expected_record_count=2,
        expected_tier_counts=None,
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    payload["rows"] = list(reversed(rows))
    baseline.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BootstrapError, match="file SHA-256"):
        load_prod_baseline(
            baseline,
            expected_record_count=2,
            expected_tier_counts=None,
        )

def test_prod_baseline_rejects_partial_default_cli_contract(tmp_path: Path) -> None:
    """기본 계약은 1,240건과 A 130/B 1,110 분포를 모두 강제한다."""
    baseline = tmp_path / "partial.json"
    write_prod_baseline(
        [prod_font("only", "하나", INSTAGRAM_URL)],
        baseline,
        expected_record_count=1,
        expected_tier_counts=None,
    )

    with pytest.raises(BootstrapError, match="expected=1240"):
        load_prod_baseline(baseline)

    wrong_distribution = [
        prod_font(f"wrong-{index:04d}", f"잘못된 분포 {index}", INSTAGRAM_URL)
        for index in range(1240)
    ]
    with pytest.raises(BootstrapError, match="source_tier 분포"):
        write_prod_baseline(wrong_distribution, tmp_path / "wrong-distribution.json")


def test_prod_baseline_rejects_unknown_schema(tmp_path: Path) -> None:
    """기준선 스키마 버전이 바뀌면 자동 bootstrap을 막는다."""
    rows = [prod_font("only", "하나", INSTAGRAM_URL)]
    baseline = tmp_path / "unknown-schema.json"
    write_prod_baseline(
        rows,
        baseline,
        expected_record_count=1,
        expected_tier_counts=None,
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    baseline.write_bytes(content)
    baseline.with_suffix(".json.sha256").write_text(
        f"{hashlib.sha256(content).hexdigest()}\n",
        encoding="ascii",
    )

    with pytest.raises(BootstrapError, match="schema_version"):
        load_prod_baseline(
            baseline,
            expected_record_count=1,
            expected_tier_counts=None,
        )
