"""수집 레코드를 Supabase fontagit 스키마에 업로드한다."""

import logging
import re
import unicodedata
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
    """별칭을 정규화한다(NFC → 공백 제거 → 소문자). 한글은 유지."""
    alias = unicodedata.normalize("NFC", alias)
    alias = re.sub(r"\s+", "", alias)
    return alias.lower()


def build_font_row(rec: FontRecord) -> dict[str, Any]:
    """fonts upsert용 행을 만든다(id/created_at 제외)."""
    data = rec.model_dump()
    return {col: data[col] for col in _FONT_COLS}


def build_alias_rows(aliases: list[str]) -> list[dict[str, Any]]:
    """aliases 행을 만든다(alias_norm 기준 중복/빈값 제거). font_id는 DB 함수가 채운다."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for alias in aliases:
        norm = normalize_alias(alias)
        if norm and norm not in seen:
            seen.add(norm)
            rows.append({"alias": alias, "alias_norm": norm})
    return rows


def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """레코드를 fontagit.upsert_font RPC로 폰트별 원자 업로드하고 처리 건수를 반환한다.

    각 폰트는 단일 트랜잭션(fonts upsert + aliases 재삽입)으로 처리된다.
    첫 실패 시 즉시 중단하며, 이미 처리된 폰트는 유지된다(파이프라인 멱등 재실행).
    """
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
        except Exception:
            logger.error("업로드 실패(중단): slug=%s", rec.slug)
            raise
        count += 1
    logger.info("업로드 완료: %d개", count)
    return count
