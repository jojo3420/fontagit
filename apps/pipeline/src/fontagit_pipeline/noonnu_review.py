"""눈누 감사 finding 검수 경계.

이 모듈은 ``fonts`` 공개값을 바꾸지 않는다. 승인된 finding을 실제
공개값에 반영하는 유일한 경로는 ``font-audit-manifest apply``다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from math import ceil
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from postgrest._sync.client import SyncPostgrestClient

logger = logging.getLogger(__name__)


def sample_size(total: int, pct: int) -> int:
    """전체가 있을 때 최소 1건을 보장하는 표본 크기를 계산한다."""
    if total <= 0:
        return 0
    return max(1, ceil(total * pct / 100))


def list_pending(schema: "SyncPostgrestClient") -> list[dict[str, Any]]:
    """새 감사 테이블에서 검수 대기 finding을 조회한다."""
    response = (
        schema.table("font_audit_findings")
        .select("*")
        .eq("status", "proposed")
        .order("run_id")
        .order("font_id")
        .order("field_name")
        .execute()
    )
    return cast(list[dict[str, Any]], response.data or [])


def approve(
    schema: "SyncPostgrestClient",
    finding_id: str,
    *,
    reviewed_by: str,
    note: str | None = None,
) -> None:
    """지정한 proposed finding 하나만 승인한다.

    finding ID와 현재 ``proposed`` 상태를 둘 다 조건으로 사용해 다른
    실행이나 다른 폰트, 이미 applied된 finding을 덮어쓰지 않는다.
    """
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ValueError("reviewed_by가 필요합니다")

    table = schema.table("font_audit_findings")
    response = table.select("id,status").eq("id", finding_id).maybe_single().execute()
    finding = response.data if response else None
    if not isinstance(finding, dict):
        raise ValueError(f"finding을 찾을 수 없음: {finding_id}")
    if finding.get("status") != "proposed":
        raise ValueError(f"finding이 proposed 상태가 아님: {finding_id}")

    reviewed_at = datetime.now(UTC).isoformat()
    update_data = {
        "status": "approved",
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
    }
    if note and note.strip():
        update_data["review_reason"] = note.strip()
    updated = (
        table.update(update_data)
        .eq("id", finding_id)
        .eq("status", "proposed")
        .execute()
    )
    if not updated.data:
        raise ValueError(f"finding 상태가 동시에 변경됨: {finding_id}")
    logger.info("finding 승인: %s (reviewed_by=%s, note=%s)", finding_id, reviewer, note)


def reject(
    schema: "SyncPostgrestClient",
    finding_id: str,
    *,
    reviewed_by: str,
    note: str,
) -> None:
    """지정한 proposed finding 하나를 반려한다."""
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ValueError("reviewed_by가 필요합니다")
    reason = note.strip()
    if not reason:
        raise ValueError("반려 사유가 필요합니다")

    table = schema.table("font_audit_findings")
    response = table.select("id,status").eq("id", finding_id).maybe_single().execute()
    finding = response.data if response else None
    if not isinstance(finding, dict) or finding.get("status") != "proposed":
        raise ValueError(f"finding이 proposed 상태가 아님: {finding_id}")
    updated = (
        table.update(
            {
                "status": "rejected",
                "reviewed_by": reviewer,
                "reviewed_at": datetime.now(UTC).isoformat(),
                "review_reason": reason,
            }
        )
        .eq("id", finding_id)
        .eq("status", "proposed")
        .execute()
    )
    if not updated.data:
        raise ValueError(f"finding 상태가 동시에 변경됨: {finding_id}")
    logger.info("finding 반려: %s (reviewed_by=%s, note=%s)", finding_id, reviewer, note)


def sample_auto_published(
    schema: "SyncPostgrestClient",
    pct: int = 5,
) -> list[dict[str, Any]]:
    """이전 자동 발행 데이터를 읽기 전용으로 표본 조회한다."""
    response = (
        schema.table("fonts")
        .select("slug,name_ko,official_url,license_source_url")
        .eq("auto_approved", True)
        .eq("status", "published")
        .eq("source_tier", "B")
        .execute()
    )
    if not response.data:
        return []
    count = sample_size(len(response.data), pct)
    return cast(list[dict[str, Any]], response.data[:count])


def unpublish(
    schema: "SyncPostgrestClient",
    slug: str,
    note: str,
) -> None:
    """예전 직접 취소 경로를 차단한다."""
    _ = (schema, slug, note)
    raise RuntimeError(
        "noonnu-review unpublish는 폐기됐습니다. "
        "font-audit-manifest apply 역방향 manifest를 사용하세요."
    )
