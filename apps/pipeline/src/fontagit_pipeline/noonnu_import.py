"""눈누(noonnu.cc) Tier B 시드를 draft로 Supabase에 임포트한다.

멱등 upsert: slug 기준, published 폰트는 절대 덮어쓰지 말 것.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from supabase import create_client

from fontagit_pipeline.models import NoonnuSeedOutput
from fontagit_pipeline.noonnu_seed import clean_font_name, derive_noonnu_slug

logger = logging.getLogger(__name__)


class NoonnuImportError(Exception):
    """눈누 임포트 오류."""

    pass


def _build_draft_font_row(
    name_ko: str,
    name_en: Optional[str],
    official_url: str,
    slug: str,
) -> dict[str, Any]:
    """draft 폰트 행을 만든다.

    Args:
        name_ko: 한글 이름.
        name_en: 영문 이름 (선택사항).
        official_url: 공식 URL.
        slug: URL 슬러그.

    Returns:
        upsert용 폰트 행 데이터.
    """
    return {
        "slug": slug,
        "name_ko": name_ko,
        "name_en": name_en or slug,
        "source_tier": "B",
        "category_ko": "고딕",
        "category_google": "sans-serif",
        "official_url": official_url,
        "status": "draft",
    }


def _load_seed_records(seed_path: Path) -> list[dict[str, Any]]:
    """tier-b-noonnu-seed.json에서 레코드를 로드한다.

    Args:
        seed_path: seed JSON 경로.

    Returns:
        레코드 리스트.

    Raises:
        NoonnuImportError: 파일 로드 실패.
    """
    try:
        with open(seed_path, encoding="utf-8") as f:
            doc = json.load(f)
        output = NoonnuSeedOutput(**doc)
        return [rec.model_dump() for rec in output.records]
    except FileNotFoundError as exc:
        raise NoonnuImportError(f"seed JSON 파일 없음: {seed_path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise NoonnuImportError(f"seed JSON 파싱 오류: {exc}") from exc


def import_noonnu_seeds(
    seed_path: Optional[Path] = None,
    supabase_url: Optional[str] = None,
    supabase_secret_key: Optional[str] = None,
) -> tuple[int, int]:
    """눈누 seed를 dev Supabase에 draft로 임포트한다.

    멱등성: slug 기준, 기존 published 폰트는 건드리지 않음.

    Args:
        seed_path: seed JSON 경로 (기본: output/tier-b-noonnu-seed.json).
        supabase_url: Supabase URL.
        supabase_secret_key: Supabase secret key.

    Returns:
        (삽입/업데이트 건수, 스킵 건수) 튜플.

    Raises:
        NoonnuImportError: 임포트 실패.
    """
    if seed_path is None:
        seed_path = Path("output") / "tier-b-noonnu-seed.json"

    if not supabase_url or not supabase_secret_key:
        raise NoonnuImportError(
            "SUPABASE_URL과 SUPABASE_SECRET_KEY가 필요합니다"
        )

    logger.info("눈누 seed 임포트 시작: %s", seed_path)

    # Seed 로드
    records = _load_seed_records(seed_path)
    logger.info("로드된 레코드: %d개", len(records))

    # Supabase 클라이언트 초기화
    client = create_client(supabase_url, supabase_secret_key)
    schema = client.schema("fontagit")

    upserted_count = 0
    skipped_count = 0

    for idx, rec in enumerate(records, 1):
        try:
            # 이름 정리 (눈누 접미사 제거)
            name_ko = clean_font_name(rec.get("name_ko"))
            name_en = clean_font_name(rec.get("name_en"))
            official_url = rec.get("official_url")

            # 필수 필드 검증
            if not name_ko or not official_url:
                logger.warning(
                    "[%d/%d] 스킵 - 필수 필드 누락 (name_ko=%s, url=%s)",
                    idx,
                    len(records),
                    name_ko,
                    official_url,
                )
                skipped_count += 1
                continue

            # slug 생성 (영문명이 있으면 사용, 아니면 한글명 정규화)
            slug = derive_noonnu_slug(name_ko, name_en)
            if not slug:
                logger.warning(
                    "[%d/%d] 스킵 - slug 생성 실패: name_ko=%s",
                    idx,
                    len(records),
                    name_ko,
                )
                skipped_count += 1
                continue

            # 폰트 행 생성
            font_row = _build_draft_font_row(
                name_ko=name_ko,
                name_en=name_en,
                official_url=official_url,
                slug=slug,
            )

            logger.debug(
                "[%d/%d] 임포트 시도: slug=%s, name_ko=%s",
                idx,
                len(records),
                slug,
                name_ko,
            )

            # Supabase 임포트 (멱등 upsert)
            # published 폰트는 절대 덮어쓰지 않도록 RPC 호출
            try:
                rpc_params: Any = {"p_font": font_row}
                response = schema.rpc(
                    "upsert_noonnu_draft",
                    rpc_params,
                ).execute()

                if response.data:
                    # upsert 성공 또는 skip
                    if isinstance(response.data, dict) and response.data.get(
                        "skipped"
                    ):
                        logger.info(
                            "[%d/%d] 스킵 - 기존 폰트: slug=%s",
                            idx,
                            len(records),
                            slug,
                        )
                        skipped_count += 1
                    else:
                        logger.info(
                            "[%d/%d] 임포트 성공: slug=%s, name_ko=%s",
                            idx,
                            len(records),
                            slug,
                            name_ko,
                        )
                        upserted_count += 1

            except Exception as rpc_exc:
                # slug 조회 후 직접 update하면 조회 직후 published로 바뀐
                # 행을 덮어쓸 수 있다. 안전 RPC 실패 시는 쓰기 0건으로 중단한다.
                logger.error(
                    "[%d/%d] upsert_noonnu_draft RPC 실패: %s",
                    idx,
                    len(records),
                    rpc_exc,
                )
                raise NoonnuImportError(
                    "upsert_noonnu_draft 안전 RPC 실패; "
                    f"직접 fonts 쓰기는 차단됨 (slug={slug})"
                ) from rpc_exc

        except NoonnuImportError:
            raise
        except Exception as exc:
            logger.error(
                "[%d/%d] 예상치 못한 오류: %s",
                idx,
                len(records),
                exc,
            )
            raise NoonnuImportError(f"임포트 오류: {exc}") from exc

    logger.info(
        "임포트 완료: %d개 삽입/업데이트, %d개 스킵",
        upserted_count,
        skipped_count,
    )

    return upserted_count, skipped_count


if __name__ == "__main__":
    import sys

    from fontagit_pipeline.config import load_settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        settings = load_settings()
        upserted, skipped = import_noonnu_seeds(
            supabase_url=settings.supabase_url,
            supabase_secret_key=settings.supabase_secret_key,
        )
        print(
            f"임포트 완료: {upserted}개 삽입/업데이트, {skipped}개 스킵"
        )
        sys.exit(0)
    except Exception as exc:
        logger.error("임포트 실패: %s", exc)
        sys.exit(1)
