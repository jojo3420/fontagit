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


def build_alias_rows(font_id: str, aliases: list[str]) -> list[dict[str, Any]]:
    """aliases upsert용 행을 만든다(alias_norm 기준 중복 제거)."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for alias in aliases:
        norm = normalize_alias(alias)
        if norm and norm not in seen:
            seen.add(norm)
            rows.append({"font_id": font_id, "alias": alias, "alias_norm": norm})
    return rows


def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """레코드를 fontagit.fonts/aliases에 멱등 upsert하고 처리 건수를 반환한다."""
    client = create_client(url, secret_key)
    table = client.schema("fontagit")
    count = 0
    for rec in records:
        res = (
            table.table("fonts")
            .upsert(build_font_row(rec), on_conflict="slug")
            .execute()
        )
        data: Any = res.data
        if not data:
            logger.error("fonts upsert 응답이 비어있음 (slug=%s)", rec.slug)
            raise RuntimeError(f"fonts upsert 응답 없음: {rec.slug}")
        font_id = str(data[0]["id"])
        alias_rows = build_alias_rows(font_id, rec.aliases)
        if alias_rows:
            table.table("aliases").upsert(
                alias_rows, on_conflict="font_id,alias_norm"
            ).execute()
        count += 1
    logger.info("업로드 완료: %d개", count)
    return count
