"""수집 레코드를 Supabase fontagit 스키마에 업로드한다."""

import logging
import re
from typing import Any

from supabase import create_client

from fontagit_pipeline.models import FontRecord

logger = logging.getLogger(__name__)

_FONT_COLS = (
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
    "version",
    "last_modified",
)


def normalize_alias(alias: str) -> str:
    """별칭을 정규화한다(소문자, 공백 제거). 한글은 유지."""
    return re.sub(r"\s+", "", alias.lower())


def build_font_row(rec: FontRecord) -> dict[str, Any]:
    """fonts upsert용 행을 만든다(id/created_at 제외)."""
    data = rec.model_dump()
    return {col: data[col] for col in _FONT_COLS}


def build_alias_rows(aliases: list[str]) -> list[dict[str, Any]]:
    """aliases 배열을 만든다(alias_norm 기준 중복 제거)."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for alias in aliases:
        norm = normalize_alias(alias)
        if norm and norm not in seen:
            seen.add(norm)
            rows.append({"alias": alias, "alias_norm": norm})
    return rows


def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """RPC upsert_font로 레코드를 폰트당 원자 트랜잭션으로 업로드한다."""
    client = create_client(url, secret_key)
    schema = client.schema("fontagit")
    count = 0
    for rec in records:
        try:
            rpc_params: dict[str, Any] = {
                "p_font": build_font_row(rec),
                "p_aliases": build_alias_rows(rec.aliases),
            }
            schema.rpc("upsert_font", rpc_params).execute()
            count += 1
        except Exception as err:
            logger.error("RPC upsert_font 실패 (slug=%s): %s", rec.slug, err)
            raise
    logger.info("업로드 완료: %d개", count)
    return count
