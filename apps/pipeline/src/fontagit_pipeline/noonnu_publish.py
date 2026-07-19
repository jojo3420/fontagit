"""이전 Noonnu dev→prod 행별 발행 명령의 읽기 전용 호환 경계."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def publish_to_prod(
    dev_schema: Any,
    prod_url: str,
    prod_key: str,
    *,
    dry_run: bool = True,
) -> tuple[int, int]:
    """예전 대상 수만 조회하고 실제 쓰기는 항상 차단한다.

    실제 반영은 before 값과 근거, 해시를 전체 검사하는
    ``font-audit-manifest apply``만 사용해야 한다.
    """
    _ = (prod_url, prod_key)
    if not dry_run:
        raise RuntimeError(
            "noonnu-publish 실제 쓰기는 폐기됐습니다. "
            "font-audit-manifest apply를 사용하세요."
        )

    rows: list[dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        response = (
            dev_schema.table("fonts")
            .select("slug")
            .eq("source_tier", "B")
            .eq("status", "published")
            .order("slug")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    logger.warning(
        "[deprecated dry-run] 대상 %d건. legacy official_url/is_commercial_free/"
        "license_verified 소비자는 직접 반영하지 않습니다. "
        "font-audit-manifest apply를 사용하세요.",
        len(rows),
    )
    return len(rows), 0
