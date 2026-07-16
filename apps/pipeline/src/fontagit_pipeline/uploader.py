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
_MIN_TIER_A_SNAPSHOT_SIZE = 100


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


def _upload_records(schema: Any, records: list[FontRecord]) -> int:
    """주입된 fontagit 스키마 클라이언트로 레코드를 업로드한다."""
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
    return count


def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """레코드를 부분 업로드한다. stale 폰트 상태는 변경하지 않는다."""
    client = create_client(url, secret_key)
    count = _upload_records(client.schema("fontagit"), records)
    logger.info("업로드 완료: %d개", count)
    return count


def _validate_tier_a_snapshot(records: list[FontRecord]) -> list[str]:
    """전체 Tier A 스냅샷을 DB 쓰기 전에 검증한다."""
    if any(rec.source_tier != "A" for rec in records):
        raise ValueError("전체 스냅샷에는 Tier A 레코드만 허용됩니다")
    slugs = [rec.slug for rec in records]
    if any(not slug.strip() for slug in slugs):
        raise ValueError("전체 스냅샷에 빈 slug가 있습니다")
    unique_slugs = sorted(set(slugs))
    if len(unique_slugs) != len(slugs):
        raise ValueError("전체 스냅샷에 중복 slug가 있습니다")
    if len(unique_slugs) < _MIN_TIER_A_SNAPSHOT_SIZE:
        raise ValueError(
            f"active Tier A가 100종 미만입니다: {len(unique_slugs)}"
        )
    return unique_slugs


def upload_tier_a_snapshot(
    records: list[FontRecord], url: str, secret_key: str
) -> tuple[int, int]:
    """전체 Tier A 스냅샷을 업로드하고 stale published를 draft 처리한다."""
    active_slugs = _validate_tier_a_snapshot(records)
    client = create_client(url, secret_key)
    schema = client.schema("fontagit")
    uploaded = _upload_records(schema, records)
    sync_params: dict[str, Any] = {"p_active_slugs": active_slugs}
    response = schema.rpc("sync_tier_a_fonts", sync_params).execute()
    if not isinstance(response.data, int):
        raise RuntimeError("sync_tier_a_fonts 응답이 정수가 아닙니다")
    logger.info("Tier A stale draft 완료: %d개", response.data)
    return uploaded, response.data
