"""OFL 표준 라이선스 공식 확인 엔진."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fontagit_pipeline.config import load_audit_settings
from fontagit_pipeline.licenses import (
    LicenseFetchError,
    fetch_license_map,
    normalize_family_dir,
    resolve_license_type,
)

logger = logging.getLogger(__name__)


# OFL 표준 권한 필드 (정적 값)
OFL_FIELDS = {
    "license_status": "verified",
    "allow_commercial": "allowed",
    "allow_modify": "allowed",
    "allow_redistribute": "allowed",
    "allow_embedding": "allowed",
    "allow_font_sale": "denied",
    "attribution_requirement": "required",
    "license_source_kind": "official",
    "auto_approved": True,
}


def plan_font_update(
    font: dict, license_map: dict[str, str], checked_at: str
) -> dict | None:
    """폰트의 OFL 확인 여부를 판정하고 업데이트 필드를 제안한다.

    Args:
        font: fonts 테이블 행 (name_en 포함)
        license_map: resolve_license_type 호출용 맵
        checked_at: 확인 시각 ISO8601 UTC

    Returns:
        OFL 확인 시 업데이트 필드 dict, 미확인/오류 시 None
    """
    name_en = font.get("name_en")
    if not name_en or not isinstance(name_en, str) or not name_en.strip():
        return None

    if resolve_license_type(name_en, license_map) != "OFL":
        return None

    normalized = normalize_family_dir(name_en)
    return {
        **OFL_FIELDS,
        "license_source_url": f"https://github.com/google/fonts/tree/main/ofl/{normalized}",
        "license_checked_at": checked_at,
    }


def build_report(
    candidates: list[dict],
    license_map: dict[str, str],
    checked_at: str,
    dev_verified_keys: set[str] | None = None,
) -> dict:
    """OFL 후보 폰트들을 분류하여 report를 생성한다.

    Args:
        candidates: fonts 테이블에서 조회한 폰트 행 리스트
        license_map: resolve_license_type 호출용 맵
        checked_at: 확인 시각 ISO8601 UTC
        dev_verified_keys: dev의 OFL verified 정규화된 name_en 집합 (기본 None)

    Returns:
        {"confirmed": [...], "unconfirmed": [...], "counts": {...}} 형태의 report dict
    """
    confirmed = []
    unconfirmed = []

    for font in candidates:
        proposal = plan_font_update(font, license_map, checked_at)
        if proposal is None:
            unconfirmed.append(font)
            continue
        if (
            dev_verified_keys is not None
            and normalize_family_dir(font.get("name_en", "")) not in dev_verified_keys
        ):
            unconfirmed.append({**font, "reason": "dev-verified-mismatch"})
            continue
        confirmed.append({**font, "proposal": proposal})

    return {
        "confirmed": confirmed,
        "unconfirmed": unconfirmed,
        "counts": {
            "confirmed": len(confirmed),
            "unconfirmed": len(unconfirmed),
            "total": len(candidates),
        },
    }


def fetch_ofl_candidates(
    client: httpx.Client, base: str, headers: dict[str, str]
) -> list[dict]:
    """dev Supabase에서 OFL 폰트 후보들을 조회한다.

    Args:
        client: httpx.Client 인스턴스
        base: REST API base URL (e.g., https://dev.example.com/rest/v1)
        headers: API 헤더 (apikey, Authorization 포함)

    Returns:
        fonts 테이블에서 license_type=OFL인 행 리스트
    """
    url = f"{base}/fonts?license_type=eq.OFL"
    response = client.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_dev_verified_keys(
    client: httpx.Client, base: str, headers: dict[str, str]
) -> set[str]:
    """dev에서 OFL verified 폰트의 정규화된 name_en 집합을 조회한다.

    prod 승격 시 게이트 2(dev 교차 확인)의 기준 집합으로 쓴다.

    Args:
        client: httpx.Client 인스턴스
        base: dev REST API base URL
        headers: dev API 헤더

    Returns:
        normalize_family_dir 적용된 name_en 집합
    """
    url = f"{base}/fonts?license_type=eq.OFL&license_status=eq.verified&select=name_en"
    response = client.get(url, headers=headers)
    response.raise_for_status()
    return {
        normalize_family_dir(row["name_en"])
        for row in response.json()
        if row.get("name_en")
    }


def apply_update(
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    font_id: str,
    fields: dict,
) -> bool:
    """폰트 ID에 대해 필드를 PATCH한다.

    Args:
        client: httpx.Client 인스턴스
        base: REST API base URL
        headers: API 헤더
        font_id: 폰트 UUID
        fields: PATCH할 필드 dict

    Returns:
        성공 시 True, 실패 시 False
    """
    url = f"{base}/fonts?id=eq.{font_id}"
    patch_headers = {
        **headers,
        "Content-Profile": "fontagit",
        "Prefer": "return=representation",
    }
    try:
        response = client.patch(url, json=fields, headers=patch_headers)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("폰트 업데이트 실패 (id=%s): %s", font_id, str(exc))
        return False


def main(apply: bool = False, report_path: str | None = None, target: str = "dev") -> int:
    """OFL 공식 확인 엔진의 메인 진입점.

    Args:
        apply: True일 때만 confirmed 폰트를 DB에 PATCH
        report_path: 결과 report JSON 저장 경로. None일 때 target별 기본값 적용
        target: "dev" 또는 "prod". 대상 Supabase 환경

    Returns:
        성공 시 0, 오류 시 0이 아닌 값
    """
    try:
        logger.info("OFL 공식 확인 엔진 시작 (target=%s)", target)

        # 자격증명 로드 및 base URL 설정
        settings = load_audit_settings()
        if target == "prod":
            write_url, write_key = settings.prod_write_credentials()
        else:
            write_url, write_key = settings.dev_write_credentials()

        base = write_url.rstrip("/") + "/rest/v1"
        headers = {
            "apikey": write_key,
            "Authorization": f"Bearer {write_key}",
            "Accept-Profile": "fontagit",
        }

        # Report path 기본값 설정
        if report_path is None:
            if target == "prod":
                report_path = "output/audit/ofl-verify-prod-report.json"
            else:
                report_path = "output/audit/ofl-verify-report.json"

        # Google Fonts 라이선스 맵 조회
        logger.info("Google Fonts 라이선스 맵 조회 중...")
        try:
            license_map = fetch_license_map()
        except LicenseFetchError as exc:
            logger.error("라이선스 맵 조회 실패: %s", str(exc))
            return 1

        # OFL 후보 폰트 조회 및 dev verified 게이트 처리
        logger.info("OFL 후보 폰트 조회 중...")
        dev_verified_keys = None
        with httpx.Client(timeout=10.0) as client:
            candidates = fetch_ofl_candidates(client, base, headers)
            logger.info("%d개 OFL 후보 폰트 조회 완료", len(candidates))

            # Prod 모드: dev에서 verified 폰트 목록 조회 (게이트 2)
            if target == "prod":
                dev_url, dev_key = settings.dev_write_credentials()
                dev_base = dev_url.rstrip("/") + "/rest/v1"
                dev_headers = {
                    "apikey": dev_key,
                    "Authorization": f"Bearer {dev_key}",
                    "Accept-Profile": "fontagit",
                }
                logger.info("Dev에서 OFL verified 폰트 목록 조회 중...")
                dev_verified_keys = fetch_dev_verified_keys(client, dev_base, dev_headers)
                logger.info("Dev verified 폰트 %d개 조회 완료", len(dev_verified_keys))

            # Report 생성
            checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            report = build_report(candidates, license_map, checked_at, dev_verified_keys=dev_verified_keys)

            # Report 저장
            report_dir = Path(report_path).parent
            report_dir.mkdir(parents=True, exist_ok=True)
            Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(
                "보고서 저장 완료: confirmed=%d, unconfirmed=%d",
                report["counts"]["confirmed"],
                report["counts"]["unconfirmed"],
            )

            # Apply 모드: confirmed 폰트 PATCH
            if apply:
                logger.info("PATCH 모드: confirmed 폰트 업데이트 시작...")
                success_count = 0
                fail_count = 0

                for item in report["confirmed"]:
                    font_id = item["id"]
                    fields = item["proposal"]
                    if apply_update(client, base, headers, font_id, fields):
                        success_count += 1
                    else:
                        fail_count += 1

                logger.info(
                    "PATCH 완료: 성공=%d, 실패=%d",
                    success_count,
                    fail_count,
                )
                if fail_count > 0:
                    return 1

        logger.info("OFL 공식 확인 엔진 정상 종료")
        return 0

    except Exception as exc:
        logger.error("예상치 못한 오류: %s", str(exc))
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="OFL 표준 라이선스 공식 확인 엔진"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="confirmed 폰트를 DB에 PATCH한다",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="결과 report JSON 저장 경로. 미지정 시 target별 기본값 적용",
    )
    parser.add_argument(
        "--target",
        choices=["dev", "prod"],
        default="dev",
        help="대상 Supabase 환경 (기본: dev)",
    )

    args = parser.parse_args()
    sys.exit(main(apply=args.apply, report_path=args.report_path, target=args.target))
