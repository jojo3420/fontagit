# apps/pipeline/src/fontagit_pipeline/recategorize.py
"""태그 근거 분류(category_ko) 재정비 엔진.

눈누 태그를 근거로 잘못 분류된 category_ko를 교정한다.
dry-run이 기본이며 --apply일 때만 DB에 PATCH한다.
설계: docs/superpowers/specs/2026-07-27-home-revamp-design.md 상세 2절.
"""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

import httpx

from fontagit_pipeline.config import load_audit_settings

logger = logging.getLogger(__name__)

CATEGORY_TAG_RULES: dict[str, frozenset[str]] = {
    "손글씨": frozenset({"캘리그라피", "붓글씨", "어른 손글씨", "삐뚤빼뚤"}),
    "장식": frozenset({"장식체", "픽셀", "레트로"}),
    "명조": frozenset({"바탕체", "고전체"}),
}
CATEGORY_PRIORITY: list[str] = ["손글씨", "장식", "명조"]
PAGE_SIZE = 500


def resolve_category(tags: list[str] | None, current: str) -> str:
    """태그 목록으로 교정 분류를 결정한다. 매칭 없으면 현재 분류 유지."""
    tag_set = set(tags or [])
    for category in CATEGORY_PRIORITY:
        if tag_set & CATEGORY_TAG_RULES[category]:
            return category
    return current


def plan_recategorization(rows: list[dict]) -> dict:
    """published 폰트 행들에 대한 재분류 계획 리포트를 만든다.

    Args:
        rows: fonts 테이블 행 (id, slug, tags, category_ko 포함)

    Returns:
        changes(변경 행만), counts, distribution_after를 담은 dict
    """
    changes: list[dict] = []
    distribution: Counter[str] = Counter()
    for row in rows:
        current = row["category_ko"]
        tags = row.get("tags") or []
        resolved = resolve_category(tags, current)
        distribution[resolved] += 1
        if resolved != current:
            matched = sorted(set(tags) & CATEGORY_TAG_RULES[resolved])
            changes.append({
                "id": row["id"],
                "slug": row["slug"],
                "from": current,
                "to": resolved,
                "matched_tags": matched,
            })
    return {
        "changes": changes,
        "counts": {
            "total": len(rows),
            "changed": len(changes),
            "unchanged": len(rows) - len(changes),
        },
        "distribution_after": dict(distribution),
    }


def fetch_published_fonts(
    client: httpx.Client, base: str, headers: dict[str, str]
) -> list[dict]:
    """published 폰트 전체를 페이지네이션으로 조회한다 (PostgREST 1,000행 제한 회피)."""
    rows: list[dict] = []
    offset = 0
    while True:
        url = (
            f"{base}/fonts?status=eq.published"
            f"&select=id,slug,tags,category_ko&order=slug"
            f"&limit={PAGE_SIZE}&offset={offset}"
        )
        response = client.get(url, headers=headers)
        response.raise_for_status()
        batch = response.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def apply_update(
    client: httpx.Client,
    base: str,
    headers: dict[str, str],
    font_id: str,
    fields: dict,
) -> bool:
    """폰트 ID에 대해 필드를 PATCH한다. 실패 시 False."""
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
        logger.warning("분류 업데이트 실패 (id=%s): %s", font_id, str(exc))
        return False


def main(apply: bool = False, report_path: str | None = None, target: str = "dev") -> int:
    """재분류 엔진 진입점. apply=False면 리포트만 남기는 dry-run."""
    try:
        logger.info("분류 재정비 시작 (target=%s, apply=%s)", target, apply)
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
        if report_path is None:
            report_path = f"output/audit/recategorize-{target}-report.json"

        with httpx.Client(timeout=10.0) as client:
            rows = fetch_published_fonts(client, base, headers)
            logger.info("published 폰트 %d개 조회 완료", len(rows))
            report = plan_recategorization(rows)

            report_dir = Path(report_path).parent
            report_dir.mkdir(parents=True, exist_ok=True)
            Path(report_path).write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(
                "리포트 저장: changed=%d / total=%d, 분포=%s",
                report["counts"]["changed"],
                report["counts"]["total"],
                report["distribution_after"],
            )

            if apply:
                success = 0
                fail = 0
                for change in report["changes"]:
                    ok = apply_update(
                        client, base, headers, change["id"],
                        {"category_ko": change["to"]},
                    )
                    success += int(ok)
                    fail += int(not ok)
                logger.info("PATCH 완료: 성공=%d, 실패=%d", success, fail)
                if fail > 0:
                    return 1
        return 0
    except Exception as exc:
        logger.error("예상치 못한 오류: %s", str(exc))
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="태그 근거 분류 재정비 엔진")
    parser.add_argument("--apply", action="store_true", help="변경분을 DB에 PATCH")
    parser.add_argument("--target", choices=["dev", "prod"], default="dev")
    parser.add_argument("--report", default=None, help="리포트 저장 경로")
    args = parser.parse_args()
    raise SystemExit(main(apply=args.apply, report_path=args.report, target=args.target))
