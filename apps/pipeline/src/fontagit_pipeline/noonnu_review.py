"""눈누 라이선스 제안 검수 및 승인/반려 처리."""
import logging
from datetime import datetime, timezone
from math import ceil
from typing import TYPE_CHECKING, Any, Optional, cast

from .noonnu_enrich import map_license_rows

if TYPE_CHECKING:
    from postgrest._sync.client import SyncPostgrestClient

logger = logging.getLogger(__name__)


def build_font_update_from_proposal(
    proposal: dict[str, Any],
    official_url: str,
) -> dict[str, Any]:
    """제안을 fonts 발행 업데이트로 변환(사람 승인 경로 → auto_approved=False).

    Args:
        proposal: license_proposals 테이블 행
        official_url: fonts.official_url

    Returns:
        fonts 테이블 업데이트용 dict
    """
    # raw_permissions에서 license_note 재계산
    raw_permissions = cast(dict[str, str], proposal.get("raw_permissions", {}))
    proposed_license_type = cast(str, proposal.get("proposed_license_type", ""))
    license_info = map_license_rows(raw_permissions, proposed_license_type)

    return {
        "is_commercial_free": bool(proposal.get("proposed_commercial_free")),
        "allow_embedding": proposal.get("proposed_embedding"),
        "allow_redistribute": proposal.get("proposed_redistribute"),
        "allow_modify": proposal.get("proposed_modify"),
        "license_type": proposed_license_type,
        "license_note": license_info.get("license_note"),
        "weights": proposal.get("proposed_weights") or [],
        "variants": ["italic"] if proposal.get("proposed_italic") else [],
        "license_verified": True,
        "auto_approved": False,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "license_source_url": official_url,
        "status": "published",
    }


def sample_size(total: int, pct: int) -> int:
    """표본 크기 계산.

    Args:
        total: 전체 개수
        pct: 표본 백분율 (0~100)

    Returns:
        표본 크기. total<=0이면 0, 아니면 max(1, ceil(total*pct/100))
    """
    if total <= 0:
        return 0
    return max(1, ceil(total * pct / 100))


def list_pending(schema: "SyncPostgrestClient") -> list[dict[str, Any]]:
    """검수 대기 중인 제안 조회.

    Args:
        schema: Supabase SyncPostgrestClient

    Returns:
        review_status=='proposed'인 제안들, proposed_license_type 순정렬
    """
    response = schema.table("license_proposals").select("*").eq(
        "review_status", "proposed"
    ).order("proposed_license_type").execute()
    return cast(list[dict[str, Any]], response.data or [])


def approve(
    schema: "SyncPostgrestClient",
    slug: str,
    note: Optional[str] = None,
) -> None:
    """라이선스 제안 승인.

    Args:
        schema: Supabase SyncPostgrestClient
        slug: fonts.slug
        note: 검수자 코멘트(선택)

    제안을 조회하여 fonts에 적용하고, 제안 상태를 approved로 변경.
    """
    # license_proposals에서 해당 slug의 제안 조회
    proposal_response = schema.table("license_proposals").select("*").eq(
        "slug", slug
    ).execute()
    if not proposal_response.data:
        logger.warning("제안 없음: %s", slug)
        return

    proposal = cast(dict[str, Any], proposal_response.data[0])

    # fonts에서 official_url 조회
    font_response = schema.table("fonts").select("font_id,official_url").eq(
        "slug", slug
    ).execute()
    if not font_response.data:
        logger.warning("폰트 없음: %s", slug)
        return

    font = cast(dict[str, Any], font_response.data[0])
    official_url = font.get("official_url", "")

    # 업데이트 dict 구성
    update_data = build_font_update_from_proposal(proposal, official_url)

    # fonts 업데이트
    schema.table("fonts").update(update_data).eq(
        "slug", slug
    ).execute()
    logger.info("폰트 발행: %s", slug)

    # license_proposals 상태 변경
    reviewed_at = datetime.now(timezone.utc).isoformat()
    schema.table("license_proposals").update({
        "review_status": "approved",
        "reviewed_at": reviewed_at,
        "reviewer_note": note,
    }).eq("slug", slug).execute()
    logger.info("제안 승인: %s", slug)


def reject(
    schema: "SyncPostgrestClient",
    slug: str,
    note: str,
) -> None:
    """라이선스 제안 반려.

    Args:
        schema: Supabase SyncPostgrestClient
        slug: fonts.slug
        note: 반려 사유(필수)

    제안을 rejected로 변경하고, fonts는 draft 유지.
    """
    reviewed_at = datetime.now(timezone.utc).isoformat()
    schema.table("license_proposals").update({
        "review_status": "rejected",
        "reviewed_at": reviewed_at,
        "reviewer_note": note,
    }).eq("slug", slug).execute()
    logger.info("제안 반려: %s (사유: %s)", slug, note)


def sample_auto_published(
    schema: "SyncPostgrestClient",
    pct: int = 5,
) -> list[dict[str, Any]]:
    """자동 발행 폰트 표본 조회.

    Args:
        schema: Supabase SyncPostgrestClient
        pct: 표본 백분율 (기본값 5%)

    Returns:
        auto_approved=True, status='published'인 폰트 중 표본
    """
    # 조건에 맞는 모든 폰트 조회
    response = schema.table("fonts").select(
        "slug,name_ko,official_url,license_source_url"
    ).eq("auto_approved", True).eq("status", "published").execute()

    if not response.data:
        return []

    total = len(response.data)
    sample_count = sample_size(total, pct)
    return cast(list[dict[str, Any]], response.data[:sample_count])


def unpublish(
    schema: "SyncPostgrestClient",
    slug: str,
    note: str,
) -> None:
    """발행된 폰트 취소 및 연관 제안 반려.

    Args:
        schema: Supabase SyncPostgrestClient
        slug: fonts.slug
        note: 취소 사유(필수)

    fonts를 draft로 되돌리고, 연관 제안을 rejected로 변경.
    """
    # fonts 업데이트
    schema.table("fonts").update({
        "status": "draft",
        "license_verified": False,
    }).eq("slug", slug).execute()
    logger.info("폰트 취소: %s", slug)

    # license_proposals 반려 처리
    reviewed_at = datetime.now(timezone.utc).isoformat()
    schema.table("license_proposals").update({
        "review_status": "rejected",
        "reviewed_at": reviewed_at,
        "reviewer_note": f"unpublished: {note}",
    }).eq("slug", slug).execute()
    logger.info("제안 반려(취소): %s", slug)
