"""prod 기준선과 안정 출처키 bootstrap 테스트."""

import hashlib
import json
from pathlib import Path

from fontagit_pipeline.audit_bootstrap import (
    build_bootstrap_manifest,
    write_bootstrap_manifest,
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
    slug: str,
    official_url: str,
) -> dict[str, object]:
    return {
        "name_ko": name_ko,
        "name_en": None,
        "slug": slug,
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
        tier_b=[tier_b_seed("613", "흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (1, 0, 0)
    entry = result.entries[0]
    assert (entry.provider, entry.provider_record_id) == ("noonnu", "613")
    assert entry.public_updates == {}
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
            prod_font("same", "동일", INSTAGRAM_URL),
            prod_font("missing", "없음", INSTAGRAM_URL),
        ],
        tier_a=[],
        tier_b=[
            tier_b_seed("1", "동일", "same", INSTAGRAM_URL),
            tier_b_seed("2", "동일", "same", INSTAGRAM_URL),
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (0, 1, 1)
    assert result.entries == []
    assert {row["reason"] for row in result.review_rows} == {
        "no_exact_candidate",
        "multiple_candidates",
    }


def test_invalid_tier_b_source_page_is_never_used_as_provider_id() -> None:
    """눈누 페이지 번호를 엄격히 파싱하지 못하면 자동 연결하지 않는다."""
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[
            {
                **tier_b_seed("613/extra", "흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL),
                "source_page": "https://noonnu.cc/font_page/613/extra",
            }
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (0, 1, 0)
    assert result.review_rows[0]["reason"] == "invalid_provider_record_id"
