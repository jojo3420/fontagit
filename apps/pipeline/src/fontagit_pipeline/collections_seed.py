# apps/pipeline/src/fontagit_pipeline/collections_seed.py
"""신규 컬렉션 4종 시드 엔진 (이슈 #128, 10 → 14개).

태그 기반으로 각 컬렉션 후보 폰트를 추출해 dry-run 리포트를 만들고,
--apply일 때 collections + collection_items에 INSERT한다.
"""

import argparse
import json
import logging
from pathlib import Path

import httpx

from fontagit_pipeline.config import load_audit_settings

logger = logging.getLogger(__name__)

PAGE_SIZE = 500
ITEM_LIMIT = 15
MIN_ITEMS = 5

NEW_COLLECTIONS: list[dict] = [
    {
        "slug": "cute-round",
        "title": "동글동글 귀여운 폰트",
        "intro": "카드뉴스와 SNS에 어울리는 말랑한 곡선의 폰트를 모았어요.",
        "status": "published",
        "sort_order": 10,
        "tags": ["귀여운", "동글동글", "둥근 고딕", "굴린 고딕"],
        "categories": ["고딕", "손글씨"],
    },
    {
        "slug": "retro-classic",
        "title": "다시 만난 레트로 감성",
        "intro": "뉴트로 무드의 포스터와 간판에 어울리는 폰트 모음이에요.",
        "status": "published",
        "sort_order": 11,
        "tags": ["레트로", "고전체"],
        "categories": ["고딕", "장식", "명조"],
    },
    {
        "slug": "calligraphy-brush",
        "title": "붓끝의 캘리그라피",
        "intro": "손맛이 살아 있는 붓글씨-캘리그라피 폰트를 골랐어요.",
        "status": "published",
        "sort_order": 12,
        "tags": ["캘리그라피", "붓글씨"],
        "categories": ["손글씨"],
    },
    {
        "slug": "title-impact",
        "title": "시선을 붙잡는 제목용 임팩트",
        "intro": "배너와 썸네일 제목에 힘을 실어 주는 두꺼운 폰트 모음이에요.",
        "status": "published",
        "sort_order": 13,
        "tags": ["제목용", "두꺼운"],
        "categories": ["고딕", "장식"],
    },
]


def pick_candidates(fonts: list[dict], spec: dict, limit: int = ITEM_LIMIT) -> list[dict]:
    """컬렉션 spec의 태그와 겹치고 분류(categories) 조건도 만족하는 폰트를 입력
    순서(최신순) 그대로 최대 limit개 고른다. spec에 categories가 없으면 태그
    조건만으로 고르는 하위호환을 유지한다.
    """
    wanted = set(spec["tags"])
    allowed_categories = spec.get("categories")
    picked = [
        f
        for f in fonts
        if wanted & set(f.get("tags") or [])
        and (allowed_categories is None or f.get("category_ko") in allowed_categories)
    ]
    return picked[:limit]


def should_create(plan: dict) -> bool:
    """후보 수가 최소 기준(MIN_ITEMS) 이상일 때만 컬렉션을 생성한다."""
    return len(plan["candidates"]) >= MIN_ITEMS


def fetch_published_fonts(
    client: httpx.Client, base: str, headers: dict[str, str]
) -> list[dict]:
    """published 폰트를 최신 등록순으로 전체 조회한다 (1,000행 제한 회피 페이지네이션)."""
    rows: list[dict] = []
    offset = 0
    while True:
        url = (
            f"{base}/fonts?status=eq.published"
            f"&select=id,slug,name_ko,tags,category_ko&order=created_at.desc,slug"
            f"&limit={PAGE_SIZE}&offset={offset}"
        )
        response = client.get(url, headers=headers)
        response.raise_for_status()
        batch = response.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def build_report(fonts: list[dict], existing: list[dict]) -> dict:
    """컬렉션별 후보 리포트를 만든다 (사용자 검수용). 기존 컬렉션과의 충돌 정보 포함."""
    existing_orders = {c["sort_order"] for c in existing}
    plans = []
    for spec in NEW_COLLECTIONS:
        picked = pick_candidates(fonts, spec)
        plans.append({
            "slug": spec["slug"],
            "title": spec["title"],
            "sort_order": spec["sort_order"],
            "candidates": [
                {"font_id": f["id"], "slug": f["slug"], "name_ko": f.get("name_ko")}
                for f in picked
            ],
        })
    return {
        "existing": {
            "count": len(existing),
            "slugs": sorted(c["slug"] for c in existing),
            "sort_orders": sorted(existing_orders),
        },
        "sort_order_conflicts": sorted(
            existing_orders & {c["sort_order"] for c in NEW_COLLECTIONS}
        ),
        "collections": plans,
    }


def insert_collection(
    client: httpx.Client, base: str, headers: dict[str, str], spec: dict, plan: dict
) -> bool:
    """컬렉션 1건과 아이템을 멱등하게 반영한다.

    재실행 안전성: 직전 실행이 items INSERT에서 실패해 "컬렉션은 있는데
    아이템이 없는 반쪽 상태"가 되면, 다음 실행에서 아이템만 보정한다.
    """
    write_headers = {
        **headers,
        "Content-Profile": "fontagit",
        "Prefer": "return=representation",
    }
    exists = client.get(
        f"{base}/collections?slug=eq.{spec['slug']}&select=id", headers=headers
    )
    exists.raise_for_status()
    rows = exists.json()
    if rows:
        collection_id = rows[0]["id"]
        current = client.get(
            f"{base}/collection_items?collection_id=eq.{collection_id}&select=font_id",
            headers=headers,
        )
        current.raise_for_status()
        if current.json():
            logger.info(
                "이미 존재하는 컬렉션 건너뜀: %s (아이템 %d종)",
                spec["slug"], len(current.json()),
            )
            return True
        logger.info("빈 컬렉션 감지 - 아이템만 보정: %s", spec["slug"])
    else:
        body = {
            "slug": spec["slug"],
            "title": spec["title"],
            "intro": spec["intro"],
            "status": spec["status"],
            "sort_order": spec["sort_order"],
        }
        created = client.post(f"{base}/collections", json=body, headers=write_headers)
        created.raise_for_status()
        collection_id = created.json()[0]["id"]
    items = [
        {
            "collection_id": collection_id,
            "font_id": c["font_id"],
            "comment": f"{spec['title']} 추천",
            "sort_order": i,
        }
        for i, c in enumerate(plan["candidates"])
    ]
    if items:
        resp = client.post(f"{base}/collection_items", json=items, headers=write_headers)
        resp.raise_for_status()
    logger.info("컬렉션 반영 완료: %s (%d종)", spec["slug"], len(items))
    return True


def main(apply: bool = False, report_path: str | None = None, target: str = "dev") -> int:
    """시드 엔진 진입점. apply=False면 후보 리포트만 남긴다."""
    try:
        logger.info("컬렉션 시드 시작 (target=%s, apply=%s)", target, apply)
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
            report_path = f"output/audit/collections-seed-{target}-report.json"

        with httpx.Client(timeout=10.0) as client:
            existing_resp = client.get(
                f"{base}/collections?select=slug,sort_order", headers=headers
            )
            existing_resp.raise_for_status()
            fonts = fetch_published_fonts(client, base, headers)
            report = build_report(fonts, existing_resp.json())
            Path(report_path).parent.mkdir(parents=True, exist_ok=True)
            Path(report_path).write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(
                "기존 컬렉션 %d개, sort_order 충돌: %s",
                report["existing"]["count"], report["sort_order_conflicts"],
            )
            for plan in report["collections"]:
                logger.info("%s: 후보 %d종", plan["slug"], len(plan["candidates"]))

            if apply:
                if report["sort_order_conflicts"]:
                    logger.error(
                        "sort_order 충돌로 중단: %s", report["sort_order_conflicts"]
                    )
                    return 1
                for spec, plan in zip(NEW_COLLECTIONS, report["collections"]):
                    if not should_create(plan):
                        logger.warning(
                            "후보 %d종(<%d) - %s 생성 건너뜀",
                            len(plan["candidates"]), MIN_ITEMS, spec["slug"],
                        )
                        continue
                    if not insert_collection(client, base, headers, spec, plan):
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
    parser = argparse.ArgumentParser(description="신규 컬렉션 4종 시드 엔진")
    parser.add_argument("--apply", action="store_true", help="컬렉션-아이템 INSERT 실행")
    parser.add_argument("--target", choices=["dev", "prod"], default="dev")
    parser.add_argument("--report", default=None, help="리포트 저장 경로")
    args = parser.parse_args()
    raise SystemExit(main(apply=args.apply, report_path=args.report, target=args.target))
