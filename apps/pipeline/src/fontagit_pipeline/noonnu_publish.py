"""dev에서 검증-발행된 Tier B 폰트를 prod DB로 동기화한다.

prod 쓰기는 명시적 확인이 필수다.
"""

import logging
from typing import Any

from supabase import create_client

logger = logging.getLogger(__name__)

# 동기화할 컬럼들
_COLS = [
    "slug",
    "name_en",
    "name_ko",
    "source_tier",
    "category_ko",
    "category_google",
    "subsets",
    "variants",
    "weights",
    "is_commercial_free",
    "license_type",
    "license_verified",
    "official_url",
    "status",
    "allow_embedding",
    "allow_redistribute",
    "allow_modify",
    "license_note",
    "verified_at",
    "license_source_url",
    "auto_approved",
]


def publish_to_prod(
    dev_schema: Any,
    prod_url: str,
    prod_key: str,
    *,
    dry_run: bool = True,
) -> tuple[int, int]:
    """dev에서 검증-발행된 Tier B 폰트를 prod DB로 동기화한다.

    Args:
        dev_schema: Dev Supabase 스키마 객체 (client.schema("fontagit")).
        prod_url: Prod Supabase URL.
        prod_key: Prod Supabase secret key.
        dry_run: True면 조회만, False면 실제 upsert 수행 (기본값: True).

    Returns:
        tuple[총 행수, 쓰기 성공 수]. dry_run=True면 (total, 0).
    """
    # Dev에서 발행된 Tier B 폰트 조회
    try:
        cols_str = ",".join(_COLS)
        response = (
            dev_schema.table("fonts")
            .select(cols_str)
            .eq("source_tier", "B")
            .eq("status", "published")
            .execute()
        )
        rows: list[dict[str, Any]] = response.data or []
    except Exception as exc:
        logger.error("Dev에서 폰트 조회 실패: %s", exc)
        raise

    logger.info("조회 완료: %d개 폰트 (source_tier='B' AND status='published')", len(rows))

    if dry_run:
        logger.info("[dry-run] 실제 쓰기는 진행하지 않습니다")
        return len(rows), 0

    # Prod에 upsert
    logger.info("Prod에 %d개 폰트 동기화 중...", len(rows))
    prod_client = create_client(prod_url, prod_key)
    prod_schema = prod_client.schema("fontagit")
    written_count = 0

    for idx, font_row in enumerate(rows, start=1):
        try:
            slug = font_row.get("slug", "?")
            prod_schema.table("fonts").upsert(
                font_row, on_conflict="slug"
            ).execute()
            written_count += 1
            logger.debug("[%d/%d] Upsert 성공: %s", idx, len(rows), slug)
        except Exception as exc:
            logger.error("[%d/%d] Upsert 실패: %s", idx, len(rows), exc)
            raise

    logger.info("동기화 완료: %d개 쓰기 성공", written_count)
    return len(rows), written_count
