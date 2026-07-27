# 홈화면 개편 구현 계획 (이슈 #128)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 홈에 즉시 필터 미리보기 그리드-컬렉션 스트립-페어링 프리셋을 추가하고, /collections 목록을 홈으로 통합하며, 태그 근거로 분류 데이터를 재정비한다.

**Architecture:** 웹은 Next.js 정적 export(SSG)라 데이터는 빌드 시점에 선별해 클라이언트 컴포넌트에 props로 넘긴다. 분류 재정비와 컬렉션 시드는 apps/pipeline의 httpx + Supabase REST(PostgREST) 패턴(dry-run 리포트 → --apply PATCH/POST)을 따른다. TOP 10 패널(WeeklyRankPanel)과 비교 보드 UI는 수정 금지(비교 보드는 프리셋 prop 추가만 허용).

**Tech Stack:** Next.js(정적 export), React, CSS Modules, vitest + testing-library, Python(httpx, pydantic-settings), pytest, Supabase REST

**Spec:** `docs/superpowers/specs/2026-07-27-home-revamp-design.md`

## Global Constraints

- 작업 디렉터리: 웹 `apps/web`, 파이프라인 `apps/pipeline`. 웹 테스트 `cd apps/web && pnpm test`(vitest run), 파이프라인 테스트 `cd apps/pipeline && uv run pytest`
- TOP 10 패널(`WeeklyRankPanel.tsx`, `TrendRow.tsx`) 절대 수정 금지 (사용자 확정)
- 그리드 컬럼은 `minmax(0, 1fr)` 사용 (모바일 가로 넘침 방지, 커밋 a62edf8 패턴)
- Supabase REST 읽기는 `Accept-Profile: fontagit`, 쓰기는 `Content-Profile: fontagit` 헤더 필수
- PostgREST 응답은 기본 1,000행 제한 → 전체 조회는 limit/offset 페이지네이션 필수
- prod DB 쓰기 전 반드시 사용자 확인을 받고 멈춘다 (Task 2, Task 8의 게이트 스텝)
- Python: Type Hints 100%, Docstring 한국어, print 금지(logging)
- 커밋 형식: `<타입>: <설명>` (feat/fix/refactor/docs/test/chore)
- 데코 심볼-가운뎃점 금지 (저장 훅이 하이픈으로 치환함)

---

### Task 1: 파이프라인 분류 재정비 엔진 (recategorize)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/recategorize.py`
- Test: `apps/pipeline/tests/test_recategorize.py`

**Interfaces:**
- Consumes: `fontagit_pipeline.config.load_audit_settings()` — `AuditSettings`에 `dev_write_credentials() -> tuple[str, str]`, `prod_write_credentials() -> tuple[str, str]` 존재 (ofl_verify.py:202-206 참고)
- Produces: `resolve_category(tags: list[str] | None, current: str) -> str`, `plan_recategorization(rows: list[dict]) -> dict` (키: changes/counts/distribution_after — 구조는 Step 1 테스트가 고정), CLI `python -m fontagit_pipeline.recategorize [--apply] [--target dev|prod]` (Task 2가 실행)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# apps/pipeline/tests/test_recategorize.py
"""recategorize 매핑 규칙 테스트."""

from fontagit_pipeline.recategorize import plan_recategorization, resolve_category


def test_손글씨_태그는_손글씨로_교정() -> None:
    assert resolve_category(["캘리그라피", "귀여운"], "고딕") == "손글씨"
    assert resolve_category(["붓글씨"], "고딕") == "손글씨"
    assert resolve_category(["어른 손글씨"], "고딕") == "손글씨"


def test_명조_장식_태그_교정() -> None:
    assert resolve_category(["바탕체"], "고딕") == "명조"
    assert resolve_category(["고전체"], "고딕") == "명조"
    assert resolve_category(["장식체"], "고딕") == "장식"
    assert resolve_category(["레트로"], "고딕") == "장식"


def test_복수_매칭이면_우선순위_손글씨_장식_명조() -> None:
    assert resolve_category(["캘리그라피", "장식체"], "고딕") == "손글씨"
    assert resolve_category(["레트로", "바탕체"], "고딕") == "장식"


def test_매칭_없으면_현재_분류_유지() -> None:
    assert resolve_category(["귀여운", "제목용"], "고딕") == "고딕"
    assert resolve_category([], "명조") == "명조"
    assert resolve_category(None, "고딕") == "고딕"


def test_plan은_변경_행만_담고_분포를_집계한다() -> None:
    rows = [
        {"id": "1", "slug": "a", "tags": ["캘리그라피"], "category_ko": "고딕"},
        {"id": "2", "slug": "b", "tags": ["제목용"], "category_ko": "고딕"},
        {"id": "3", "slug": "c", "tags": ["바탕체"], "category_ko": "명조"},
    ]
    report = plan_recategorization(rows)
    assert len(report["changes"]) == 1
    change = report["changes"][0]
    assert change == {
        "id": "1",
        "slug": "a",
        "from": "고딕",
        "to": "손글씨",
        "matched_tags": ["캘리그라피"],
    }
    assert report["counts"] == {"total": 3, "changed": 1, "unchanged": 2}
    assert report["distribution_after"] == {"고딕": 1, "명조": 1, "손글씨": 1}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_recategorize.py -v`
Expected: FAIL — `ModuleNotFoundError: fontagit_pipeline.recategorize`

- [ ] **Step 3: 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_recategorize.py -v`
Expected: PASS (5개)

- [ ] **Step 5: 기존 파이프라인 테스트 회귀 확인**

Run: `cd apps/pipeline && uv run pytest -q`
Expected: 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/recategorize.py apps/pipeline/tests/test_recategorize.py
git commit -m "feat: 태그 근거 분류 재정비 엔진 추가 (#128)"
```

---

### Task 2: 분류 재정비 dev 적용 - 검증 - prod 게이트

**Files:** 코드 변경 없음 (Task 1의 CLI 실행과 리포트 검증만)

> 경로 기준: 셸 명령은 `apps/pipeline`에서 실행하며 리포트는 `apps/pipeline/output/audit/`에 생성된다. `git add`는 저장소 루트 기준 경로를 쓴다.

**Interfaces:**
- Consumes: Task 1의 CLI. env는 `apps/web/.env.local`(dev)-`.env.production`(prod)을 config.py가 로드함 (별도 .env 없음)

- [ ] **Step 1: dev dry-run 리포트 생성**

Run: `cd apps/pipeline && uv run python -m fontagit_pipeline.recategorize --target dev`
Expected: exit 0, `output/audit/recategorize-dev-report.json` 생성. 로그에 changed 수와 분포 출력

- [ ] **Step 2: 리포트 타당성 검토**

리포트의 `distribution_after`가 상식적인지 확인한다 (예: 손글씨가 8 → 수백으로 증가, 고딕 감소). `changes` 상위 20건의 slug-matched_tags를 눈으로 확인해 오분류(예: 고딕인데 손글씨로 가는 건)가 없는지 본다. 이상하면 Task 1의 `CATEGORY_TAG_RULES`를 조정하고 테스트-리포트를 다시 돌린다.

- [ ] **Step 3: dev 적용 및 수렴 확인**

Run: `cd apps/pipeline && uv run python -m fontagit_pipeline.recategorize --target dev --apply`
Expected: `PATCH 완료: 성공=N, 실패=0`

Run(재실행): `uv run python -m fontagit_pipeline.recategorize --target dev`
Expected: `changed=0` (모든 변경이 반영되어 더 바꿀 게 없음 = 수렴 증거)

Run(리포트 JSON 기준 재확인): `jq '.counts.changed' output/audit/recategorize-dev-report.json`
Expected: `0` (로그 문자열이 아닌 리포트 파일로 증명)

- [ ] **Step 4: 🛑 prod 적용 전 사용자 확인 (게이트)**

dev 리포트 요약(변경 수, 전후 분포)을 사용자에게 보여주고 prod 적용 승인을 받는다. **승인 없이 다음 스텝 진행 금지.**

- [ ] **Step 5: prod dry-run 및 리포트 검토 (이 스텝에서는 apply 금지)**

```bash
cd apps/pipeline && uv run python -m fontagit_pipeline.recategorize --target prod
```

`output/audit/recategorize-prod-report.json`의 changed 수와 분포를 확인한다. dev 리포트와 크게 다르면(prod 데이터 상이) 적용하지 말고 사용자에게 보고한다.

- [ ] **Step 5-1: prod 적용 및 수렴 확인** (Step 4 승인 + Step 5 리포트 이상 없음 전제)

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline.recategorize --target prod --apply
uv run python -m fontagit_pipeline.recategorize --target prod          # 재실행 dry-run
jq '.counts.changed' output/audit/recategorize-prod-report.json        # Expected: 0
```

- [ ] **Step 6: 리포트 파일 커밋**

```bash
git add apps/pipeline/output/audit/recategorize-dev-report.json apps/pipeline/output/audit/recategorize-prod-report.json
git commit -m "chore: 분류 재정비 dev/prod 적용 리포트 기록 (#128)"
```

(output/이 .gitignore 대상이면 이 스텝은 건너뛰고 리포트 요약을 PR 본문에 첨부)

---

### Task 3: Font 타입에 createdAt 노출

**Files:**
- Modify: `apps/web/types/font.ts` (Font 인터페이스)
- Modify: `apps/web/lib/db/types.ts` (FontRow)
- Modify: `apps/web/lib/db/mappers.ts` (rowToFont)

**Interfaces:**
- Produces: `Font.createdAt?: string` (ISO 문자열) — Task 4의 `badgeFor`가 NEW 뱃지 판정에 사용

- [ ] **Step 1: 타입-매퍼 수정**

`apps/web/types/font.ts`의 `Font` 인터페이스에서 `subsets: string[];` 줄 아래에 추가:

```typescript
  createdAt?: string;
```

`apps/web/lib/db/types.ts`의 `FontRow` 인터페이스에 추가 (기존 테스트 픽스처가 깨지지 않도록 optional):

```typescript
  created_at?: string;
```

`apps/web/lib/db/mappers.ts`의 `rowToFont` 반환 객체에서 `subsets: row.subsets ?? [],` 줄 아래에 추가:

```typescript
    createdAt: row.created_at,
```

> 근거: `getAllFonts`는 `.select("*")`(lib/db/fonts.ts:13)라 `created_at`이 이미 조회된다. 쿼리 수정은 불필요.

- [ ] **Step 2: 타입-테스트 회귀 확인**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm test`
Expected: 컴파일 에러 0, 기존 테스트 전부 PASS

- [ ] **Step 3: 커밋**

```bash
git add apps/web/types/font.ts apps/web/lib/db/types.ts apps/web/lib/db/mappers.ts
git commit -m "feat: Font 타입에 createdAt 노출 (#128)"
```

---

### Task 4: 홈 큐레이션 유틸 (lib/homeCuration.ts)

**Files:**
- Create: `apps/web/lib/homeCuration.ts`
- Test: `apps/web/lib/homeCuration.test.ts`

**Interfaces:**
- Consumes: `Font`(createdAt 포함, Task 3), `TrendItem` (`@/types/font`)
- Produces (Task 5가 사용):
  - `type ChipKey = "all" | "고딕" | "명조" | "손글씨" | "장식" | "free" | "paid"`
  - `CHIP_DEFS: ChipDef[]` — `{ key: ChipKey; label: string; query: string }`
  - `interface HomePreview { chips: Record<ChipKey, Font[]>; hotSlugs: string[] }`
  - `buildHomePreview(fonts: Font[], trends: TrendItem[], perChip?: number): HomePreview`
  - `badgeFor(font: Font, hotSlugs: string[], now?: Date): "인기" | "NEW" | undefined`

- [ ] **Step 1: 실패하는 테스트 작성**

```typescript
// apps/web/lib/homeCuration.test.ts
import { describe, it, expect } from "vitest";
import { buildHomePreview, badgeFor } from "@/lib/homeCuration";
import { fonts } from "@/data/fonts";
import type { Font, TrendItem } from "@/types/font";

const trend = (slug: string, rank: number): TrendItem => ({
  rank,
  change: "new",
  font: { slug, nameKo: slug, fontKey: null, tier: "free" },
  moves: 100 - rank,
});

describe("buildHomePreview", () => {
  it("주간 클릭 순위 폰트를 앞세우고 나머지는 최신순으로 채운다", () => {
    const trends = [trend("gaegu", 1), trend("jua", 2)];
    const preview = buildHomePreview(fonts, trends, 4);
    expect(preview.chips.all.slice(0, 2).map((f) => f.slug)).toEqual(["gaegu", "jua"]);
    expect(preview.chips.all).toHaveLength(4);
  });

  it("분류 칩에는 해당 분류 폰트만 담는다", () => {
    const preview = buildHomePreview(fonts, [], 8);
    expect(preview.chips["고딕"].every((f) => f.category === "고딕")).toBe(true);
    expect(preview.chips["고딕"].length).toBeGreaterThan(0);
  });

  it("대상이 없으면 빈 배열 (유료 0종 시나리오)", () => {
    const freeOnly = fonts.filter((f) => f.tier === "free");
    const preview = buildHomePreview(freeOnly, [], 8);
    expect(preview.chips.paid).toEqual([]);
  });

  it("perChip 개수를 넘지 않는다", () => {
    const preview = buildHomePreview(fonts, [], 3);
    expect(preview.chips.all).toHaveLength(3);
  });
});

describe("badgeFor", () => {
  const base = fonts[0];

  it("주간 클릭 상위면 인기 뱃지", () => {
    expect(badgeFor(base, [base.slug])).toBe("인기");
  });

  it("14일 이내 등록이면 NEW 뱃지", () => {
    const recent: Font = { ...base, createdAt: new Date().toISOString() };
    expect(badgeFor(recent, [])).toBe("NEW");
  });

  it("오래된 폰트는 뱃지 없음", () => {
    const old: Font = { ...base, createdAt: "2020-01-01T00:00:00Z" };
    expect(badgeFor(old, [])).toBeUndefined();
  });

  it("createdAt 없으면 NEW 판정 안 함", () => {
    const noDate: Font = { ...base, createdAt: undefined };
    expect(badgeFor(noDate, [])).toBeUndefined();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/homeCuration.test.ts`
Expected: FAIL — `Cannot find module '@/lib/homeCuration'`

- [ ] **Step 3: 구현**

```typescript
// apps/web/lib/homeCuration.ts
import type { Font, TrendItem } from "@/types/font";

export type ChipKey = "all" | "고딕" | "명조" | "손글씨" | "장식" | "free" | "paid";

export interface ChipDef {
  key: ChipKey;
  label: string;
  /** /fonts로 넘길 쿼리스트링 */
  query: string;
}

// 기존 lib/filters.ts buildFilterQuery와 동일하게 URLSearchParams로 인코딩 통일
const toQuery = (params: Record<string, string>): string =>
  new URLSearchParams(params).toString();

export const CHIP_DEFS: ChipDef[] = [
  { key: "all", label: "전체", query: toQuery({ sort: "popular" }) },
  { key: "고딕", label: "고딕", query: toQuery({ category: "고딕", sort: "popular" }) },
  { key: "명조", label: "명조", query: toQuery({ category: "명조", sort: "popular" }) },
  { key: "손글씨", label: "손글씨", query: toQuery({ category: "손글씨", sort: "popular" }) },
  { key: "장식", label: "장식", query: toQuery({ category: "장식", sort: "popular" }) },
  { key: "free", label: "무료", query: toQuery({ tier: "free", sort: "popular" }) },
  { key: "paid", label: "유료", query: toQuery({ tier: "paid", sort: "popular" }) },
];

export const PER_CHIP = 8;
const NEW_BADGE_DAYS = 14;
const HOT_BADGE_COUNT = 10;

export interface HomePreview {
  chips: Record<ChipKey, Font[]>;
  /** 주간 클릭 상위 slug — 인기 뱃지 기준 */
  hotSlugs: string[];
}

export function buildHomePreview(
  fonts: Font[],
  trends: TrendItem[],
  perChip: number = PER_CHIP,
): HomePreview {
  const clickRank = new Map<string, number>();
  trends.forEach((t, i) => clickRank.set(t.font.slug, i));
  // fonts는 getAllFonts의 최신 등록순. 클릭 순위 보유 폰트를 앞세우고
  // 미보유는 stable sort 특성으로 최신순이 유지된다.
  const ranked = [...fonts].sort((a, b) => {
    const ra = clickRank.get(a.slug) ?? Number.MAX_SAFE_INTEGER;
    const rb = clickRank.get(b.slug) ?? Number.MAX_SAFE_INTEGER;
    return ra - rb;
  });
  const pick = (pred: (f: Font) => boolean): Font[] =>
    ranked.filter(pred).slice(0, perChip);
  return {
    chips: {
      all: pick(() => true),
      고딕: pick((f) => f.category === "고딕"),
      명조: pick((f) => f.category === "명조"),
      손글씨: pick((f) => f.category === "손글씨"),
      장식: pick((f) => f.category === "장식"),
      free: pick((f) => f.tier === "free"),
      paid: pick((f) => f.tier === "paid"),
    },
    hotSlugs: trends.slice(0, HOT_BADGE_COUNT).map((t) => t.font.slug),
  };
}

export function badgeFor(
  font: Font,
  hotSlugs: string[],
  now: Date = new Date(),
): "인기" | "NEW" | undefined {
  if (hotSlugs.includes(font.slug)) return "인기";
  if (font.createdAt) {
    const ageDays = (now.getTime() - new Date(font.createdAt).getTime()) / 86_400_000;
    if (ageDays <= NEW_BADGE_DAYS) return "NEW";
  }
  return undefined;
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/homeCuration.test.ts`
Expected: PASS (8개)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/homeCuration.ts apps/web/lib/homeCuration.test.ts
git commit -m "feat: 홈 미리보기 큐레이션 유틸 추가 (#128)"
```

---

### Task 5: HomeExplorer 컴포넌트 + Hero 칩 제거 + 홈 통합

**Files:**
- Create: `apps/web/components/HomeExplorer.tsx`, `apps/web/components/HomeExplorer.module.css`
- Modify: `apps/web/components/FontCard.tsx`, `apps/web/components/FontCard.module.css` (badge prop)
- Modify: `apps/web/components/Hero.tsx` (칩 제거), `apps/web/components/Hero.module.css` (.chips 삭제)
- Modify: `apps/web/app/page.tsx`, `apps/web/app/page.module.css`
- Test: `apps/web/components/HomeExplorer.test.tsx`, `apps/web/app/page.test.tsx` (mock 갱신)

**Interfaces:**
- Consumes: Task 4의 `HomePreview`, `CHIP_DEFS`, `badgeFor`, `ChipKey`. 기존 `FilterChip`(`{active?, children, onClick?}`), `EmptyState`(`{title, description, actionHref?, actionLabel?}`), `FontCard`
- Produces: `HomeExplorer({ preview }: { preview: HomePreview })` 클라이언트 컴포넌트, `FontCard`의 새 optional prop `badge?: "인기" | "NEW"`

> "전체를 다음으로 교체" 공통 지시: 교체 전 반드시 현재 파일을 열어 이 계획이 전제한 구조(props-import)와 일치하는지 확인한다. 다르면(다른 작업이 먼저 수정한 경우) 전체 교체하지 말고 필요한 변경분만 이식하고 차이를 보고한다.

- [ ] **Step 1: 실패하는 테스트 작성**

```typescript
// apps/web/components/HomeExplorer.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HomeExplorer } from "@/components/HomeExplorer";
import { buildHomePreview } from "@/lib/homeCuration";
import { fonts } from "@/data/fonts";

const preview = buildHomePreview(fonts, [], 4);

describe("HomeExplorer", () => {
  it("기본으로 전체 칩이 활성화되고 폰트 카드가 보인다", () => {
    render(<HomeExplorer preview={preview} />);
    expect(screen.getByRole("button", { name: "전체" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(preview.chips.all[0].nameKo)).toBeInTheDocument();
  });

  it("칩 클릭 시 활성 칩과 그리드가 즉시 바뀐다", () => {
    render(<HomeExplorer preview={preview} />);
    fireEvent.click(screen.getByRole("button", { name: "고딕" }));
    expect(screen.getByRole("button", { name: "고딕" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "전체" })).toHaveAttribute("aria-pressed", "false");
  });

  it("결과 0건 칩은 EmptyState를 보여준다", () => {
    const empty = { ...preview, chips: { ...preview.chips, paid: [] } };
    render(<HomeExplorer preview={empty} />);
    fireEvent.click(screen.getByRole("button", { name: "유료" }));
    expect(screen.getByText("아직 준비 중이에요")).toBeInTheDocument();
  });

  it("전체 보기 링크가 활성 칩의 필터 쿼리를 담는다", () => {
    render(<HomeExplorer preview={preview} />);
    fireEvent.click(screen.getByRole("button", { name: "고딕" }));
    const link = screen.getByRole("link", { name: /전체 보기/ });
    expect(link.getAttribute("href")).toContain("category=");
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run components/HomeExplorer.test.tsx`
Expected: FAIL — `Cannot find module '@/components/HomeExplorer'`

- [ ] **Step 3: FontCard에 badge prop 추가**

`apps/web/components/FontCard.tsx` 전체를 다음으로 교체:

```typescript
import Link from "next/link";
import type { Font } from "@/types/font";
import { getSpecimenText } from "@/lib/specimen";
import { LazyFontPreview } from "./LazyFontPreview";
import { TierChip } from "./TierChip";
import styles from "./FontCard.module.css";

export function FontCard({
  font,
  previewText,
  badge,
}: {
  font: Font;
  previewText?: string;
  badge?: "인기" | "NEW";
}) {
  const custom = previewText?.trim();
  const words = (custom || getSpecimenText(font, false)).split(" ");
  const line1 = words.slice(0, 2).join(" ");
  const line2 = words.slice(2, 4).join(" ");

  return (
    <Link href={`/fonts/${font.slug}`} className={styles.card}>
      <LazyFontPreview font={font} className={styles.specimen}>
        {custom ? custom : (<>{line1}<br />{line2}</>)}
      </LazyFontPreview>
      <div className={styles.foot}>
        <h3 className={styles.name}>{font.nameKo}</h3>
        <span className={styles.footRight}>
          {badge && <span className={styles.badge}>{badge}</span>}
          <TierChip tier={font.tier} />
        </span>
      </div>
    </Link>
  );
}
```

`apps/web/components/FontCard.module.css`에 추가:

```css
.footRight {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* 긴 폰트명이 뱃지-티어칩과 겹치지 않게 말줄임 */
.foot .name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 8px;
  color: var(--accent, #5e81f4);
  border: 1px solid currentColor;
}
```

- [ ] **Step 4: HomeExplorer 구현**

```typescript
// apps/web/components/HomeExplorer.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { CHIP_DEFS, badgeFor, type ChipKey, type HomePreview } from "@/lib/homeCuration";
import { FilterChip } from "./FilterChip";
import { FontCard } from "./FontCard";
import { EmptyState } from "./EmptyState";
import styles from "./HomeExplorer.module.css";

export function HomeExplorer({ preview }: { preview: HomePreview }) {
  const [active, setActive] = useState<ChipKey>("all");
  const chip = CHIP_DEFS.find((c) => c.key === active) ?? CHIP_DEFS[0];
  const fonts = preview.chips[active] ?? [];
  const moreHref = `/fonts?${chip.query}`;

  return (
    <section className={styles.wrap} aria-label="분류별 폰트 미리보기">
      <div className={styles.chips}>
        {CHIP_DEFS.map((c) => (
          <FilterChip key={c.key} active={c.key === active} onClick={() => setActive(c.key)}>
            {c.label}
          </FilterChip>
        ))}
      </div>
      {fonts.length === 0 ? (
        <EmptyState
          title="아직 준비 중이에요"
          description="이 분류의 폰트가 등록되면 바로 보여드릴게요."
          actionHref={moreHref}
          actionLabel="전체 폰트 보기"
        />
      ) : (
        <div className={styles.grid}>
          {fonts.map((f) => (
            <FontCard key={f.slug} font={f} badge={badgeFor(f, preview.hotSlugs)} />
          ))}
          <Link href={moreHref} className={styles.more}>전체 보기 →</Link>
        </div>
      )}
    </section>
  );
}
```

```css
/* apps/web/components/HomeExplorer.module.css */
.wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.more {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 72px;
  border: 1px dashed var(--line, #d0d0d8);
  border-radius: 12px;
  font-size: 13px;
  color: var(--sub);
}

@media (min-width: 900px) {
  .grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
```

- [ ] **Step 5: Hero 칩 제거**

`apps/web/components/Hero.tsx` 전체를 다음으로 교체 (인터랙션이 없어져 "use client" 제거):

```typescript
import styles from "./Hero.module.css";

export function Hero() {
  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>당신의 폰트 아지트</h1>
      <p className={styles.sub}>
        설치 없이, 웹에서. 좋은 폰트를 골라두고 지금 뜨는 흐름까지 챙겨드려요.
      </p>
    </section>
  );
}
```

`apps/web/components/Hero.module.css`에서 `.chips { ... }` 블록 삭제.

- [ ] **Step 6: 홈 page.tsx 통합**

`apps/web/app/page.tsx` 전체를 다음으로 교체:

```typescript
import type { Metadata } from "next";
import { Hero } from "@/components/Hero";
import { HomeExplorer } from "@/components/HomeExplorer";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { AdFitUnit } from "@/components/AdFitUnit";
import { CompareLazy } from "@/components/CompareLazy";
import { ADFIT_UNIT_HOME } from "@/lib/analytics/constants";
import { getTrends, getAllFonts } from "@/lib/data";
import { buildHomePreview } from "@/lib/homeCuration";
import styles from "./page.module.css";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

export default async function Home() {
  const [{ items, source }, fonts] = await Promise.all([getTrends(), getAllFonts()]);
  const preview = buildHomePreview(fonts, items);
  return (
    <main className={styles.main}>
      <div className={styles.grid}>
        <div className={styles.left}>
          <Hero />
          <HomeExplorer preview={preview} />
        </div>
        <WeeklyRankPanel items={items} source={source} />
      </div>
      <section id="compare" className={styles.compareSection} aria-labelledby="compare-heading">
        <div className={styles.container}>
          <CompareLazy
            placeholder={<div className={styles.comparePlaceholder} />}
          />
        </div>
      </section>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdFitUnit unit={ADFIT_UNIT_HOME ?? ""} width={320} height={100} label />
        </div>
      </section>
    </main>
  );
}
```

`apps/web/app/page.module.css`에 추가:

```css
.left {
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-width: 0;
}
```

- [ ] **Step 7: 홈 페이지 테스트 mock 갱신**

`apps/web/app/page.test.tsx`의 `vi.mock("@/lib/data", ...)` 블록을 다음으로 교체 (getAllFonts 추가):

```typescript
vi.mock("@/lib/data", () => ({
  getTrends: vi.fn(() => Promise.resolve(mockTrendsClicksResult)),
  getAllFonts: vi.fn(() => Promise.resolve(fonts)),
}));
```

같은 파일 describe 블록에 테스트 1개 추가:

```typescript
  it("즉시 필터 칩과 미리보기 그리드를 렌더한다", async () => {
    await renderHome();
    expect(screen.getByRole("button", { name: "전체" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "손글씨" })).toBeInTheDocument();
  });
```

- [ ] **Step 8: 테스트-타입 전체 확인**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm test`
Expected: 전부 PASS (HomeExplorer 4개 + page 3개 포함)

- [ ] **Step 9: 커밋**

```bash
git add apps/web/components/HomeExplorer.tsx apps/web/components/HomeExplorer.module.css \
  apps/web/components/HomeExplorer.test.tsx apps/web/components/FontCard.tsx \
  apps/web/components/FontCard.module.css apps/web/components/Hero.tsx \
  apps/web/components/Hero.module.css apps/web/app/page.tsx \
  apps/web/app/page.module.css apps/web/app/page.test.tsx
git commit -m "feat: 홈 즉시 필터 미리보기 그리드 추가 (#128)"
```

---

### Task 6: 컬렉션 홈 통합 (/collections 목록 제거)

**Files:**
- Create: `apps/web/components/HomeCollectionsStrip.tsx`, `apps/web/components/HomeCollectionsStrip.module.css`
- Modify: `apps/web/app/page.tsx`, `apps/web/app/page.module.css`, `apps/web/components/Header.tsx`, `apps/web/app/sitemap.ts`, `apps/web/public/_redirects`
- Delete: `apps/web/app/collections/page.tsx`, `apps/web/app/collections/page.module.css` (`[slug]/`는 유지)
- Test: `apps/web/app/page.test.tsx` (mock에 getAllCollections 추가)

**Interfaces:**
- Consumes: `getAllCollections(): Promise<Collection[]>` (`@/lib/data`), 기존 `CollectionCard({ collection })`
- Produces: `HomeCollectionsStrip({ collections }: { collections: Collection[] })` 서버 컴포넌트, 홈 섹션 앵커 `id="collections"`

- [ ] **Step 1: HomeCollectionsStrip 구현**

```typescript
// apps/web/components/HomeCollectionsStrip.tsx
import type { Collection } from "@/types/font";
import { CollectionCard } from "./CollectionCard";
import styles from "./HomeCollectionsStrip.module.css";

export function HomeCollectionsStrip({ collections }: { collections: Collection[] }) {
  if (collections.length === 0) return null;
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 id="collections-heading" className={styles.title}>추천 컬렉션</h2>
        <span className={styles.hint}>테마별로 골라 담은 폰트 모음</span>
      </div>
      <div className={styles.strip}>
        {collections.map((c) => (
          <div key={c.slug} className={styles.item}>
            <CollectionCard collection={c} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

```css
/* apps/web/components/HomeCollectionsStrip.module.css */
.wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.title {
  font-size: 20px;
  font-weight: 800;
  margin: 0;
}

.hint {
  font-size: 13px;
  color: var(--sub);
}

.strip {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 260px;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 6px;
  scroll-snap-type: x proximity;
}

.item {
  scroll-snap-align: start;
  min-width: 0;
}
```

- [ ] **Step 2: 홈에 섹션 추가**

`apps/web/app/page.tsx`에서 import에 추가:

```typescript
import { HomeCollectionsStrip } from "@/components/HomeCollectionsStrip";
```

`getAllCollections`를 `@/lib/data` import에 추가하고, 데이터 로딩을 다음으로 교체:

```typescript
  const [{ items, source }, fonts, collections] = await Promise.all([
    getTrends(),
    getAllFonts(),
    getAllCollections(),
  ]);
```

`</div>`(styles.grid 닫힘)과 `<section id="compare"` 사이에 삽입:

```typescript
      <section id="collections" className={styles.collectionsSection} aria-labelledby="collections-heading">
        <div className={styles.container}>
          <HomeCollectionsStrip collections={collections} />
        </div>
      </section>
```

`apps/web/app/page.module.css`에 추가:

```css
.collectionsSection {
  padding: 8px var(--pad-page) 24px;
  scroll-margin-top: 64px;
}
```

- [ ] **Step 3: Header 앵커 전환, sitemap-리다이렉트 정리**

`apps/web/components/Header.tsx`에서:

```typescript
          <Link href="/collections">컬렉션</Link>
```

를 다음으로 교체:

```typescript
          <Link href="/#collections">컬렉션</Link>
```

`apps/web/app/sitemap.ts`의 staticEntries 배열에서 `"/collections/",` 줄 삭제 (컬렉션 상세 entries는 유지).

`apps/web/public/_redirects` 끝에 추가 (기존 /playground 줄 유지):

```
/collections/ / 301
/collections / 301
```

- [ ] **Step 4: 목록 페이지 삭제**

```bash
git rm apps/web/app/collections/page.tsx apps/web/app/collections/page.module.css
```

삭제 후 참조 잔재 확인: `grep -rn "collections/page" apps/web --include="*.ts*"` → 0건이어야 함. `apps/web/app/collections/[slug]/` 디렉터리는 남아 있어야 함.

- [ ] **Step 5: 홈 테스트 갱신**

`apps/web/app/page.test.tsx`의 mock을 다음으로 교체:

```typescript
vi.mock("@/lib/data", () => ({
  getTrends: vi.fn(() => Promise.resolve(mockTrendsClicksResult)),
  getAllFonts: vi.fn(() => Promise.resolve(fonts)),
  getAllCollections: vi.fn(() =>
    Promise.resolve([
      {
        slug: "dawn-serif",
        title: "새벽 감성 명조 모음",
        intro: "고요한 새벽에 어울리는 명조",
        items: [],
      },
    ])
  ),
}));
```

테스트 1개 추가:

```typescript
  it("추천 컬렉션 스트립을 렌더한다", async () => {
    await renderHome();
    expect(screen.getByText("추천 컬렉션")).toBeInTheDocument();
    expect(screen.getByText("새벽 감성 명조 모음")).toBeInTheDocument();
  });
```

- [ ] **Step 6: 테스트-타입 확인**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm test`
Expected: 전부 PASS

- [ ] **Step 7: 커밋**

```bash
git add -A apps/web
git commit -m "feat: 컬렉션 목록을 홈 스트립으로 통합하고 /collections 리다이렉트 (#128)"
```

---

### Task 7: 페어링 프리셋 + 비교 보드 프리셋 로드

**Files:**
- Create: `apps/web/data/pairings.ts`, `apps/web/components/PairingPresets.tsx`, `apps/web/components/PairingPresets.module.css`, `apps/web/components/HomeCompareSection.tsx`, `apps/web/components/HomeCompareSection.module.css`
- Modify: `apps/web/components/CompareCanvas.tsx` (preset prop), `apps/web/components/CompareLazy.tsx` (preset 전달), `apps/web/app/page.tsx`, `apps/web/app/page.module.css`
- Test: `apps/web/components/PairingPresets.test.tsx`, `apps/web/components/CompareCanvas.test.tsx`

**Interfaces:**
- Consumes: `fonts` (`@/data/fonts` mock 9종 무료: pretendard, black-han-sans, jua, do-hyeon, gowun-batang, nanum-myeongjo, kirang-haerang, gaegu, song-myung), `familyOf` (`@/lib/fonts`)
- Produces:
  - `interface ComparePreset { heroSlug: string; gridSlugs: string[] }` (`@/data/pairings`)
  - `PAIRINGS: FontPairing[]`, `interface FontPairing { id; title; description; heroSlug; bodySlug: string }`
  - `CompareCanvas({ preset }?: { preset?: ComparePreset })`, `CompareLazy({ placeholder, preset })`
  - `HomeCompareSection()` — 홈에서 기존 compare 섹션을 대체

- [ ] **Step 1: 실패하는 테스트 작성**

```typescript
// apps/web/components/PairingPresets.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PairingPresets } from "@/components/PairingPresets";

describe("PairingPresets", () => {
  it("페어링 3세트를 렌더한다", () => {
    render(<PairingPresets onSelect={vi.fn()} />);
    expect(screen.getAllByRole("button")).toHaveLength(3);
  });

  it("클릭 시 onSelect가 대표+본문 조합으로 호출된다", () => {
    const onSelect = vi.fn();
    render(<PairingPresets onSelect={onSelect} />);
    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(onSelect).toHaveBeenCalledWith({
      heroSlug: "black-han-sans",
      gridSlugs: ["pretendard"],
    });
  });
});
```

```typescript
// apps/web/components/CompareCanvas.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompareCanvas } from "@/components/CompareCanvas";

describe("CompareCanvas preset", () => {
  it("preset이 주어지면 대표-그리드 선택에 반영된다", () => {
    render(<CompareCanvas preset={{ heroSlug: "jua", gridSlugs: ["gowun-batang"] }} />);
    expect(screen.getByLabelText("대표 폰트 선택")).toHaveValue("jua");
    expect(screen.getByLabelText("1번 폰트 선택")).toHaveValue("gowun-batang");
  });

  it("preset이 없으면 기존 기본값을 유지한다", () => {
    render(<CompareCanvas />);
    expect(screen.getByLabelText("대표 폰트 선택")).toHaveValue("pretendard");
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run components/PairingPresets.test.tsx components/CompareCanvas.test.tsx`
Expected: PairingPresets FAIL(모듈 없음), CompareCanvas preset 테스트 FAIL(prop 미지원)

- [ ] **Step 3: 데이터-컴포넌트 구현**

```typescript
// apps/web/data/pairings.ts
export interface ComparePreset {
  heroSlug: string;
  gridSlugs: string[];
}

export interface FontPairing {
  id: string;
  title: string;
  description: string;
  heroSlug: string;
  bodySlug: string;
}

/** 비교 보드에 로드할 제목+본문 추천 조합. slug는 data/fonts.ts 무료 폰트만 사용 */
export const PAIRINGS: FontPairing[] = [
  {
    id: "impact-title",
    title: "임팩트 헤드라인",
    description: "포스터-배너에 어울리는 조합",
    heroSlug: "black-han-sans",
    bodySlug: "pretendard",
  },
  {
    id: "warm-essay",
    title: "포근한 에세이",
    description: "블로그-에세이에 어울리는 조합",
    heroSlug: "jua",
    bodySlug: "gowun-batang",
  },
  {
    id: "classic-editorial",
    title: "고전 에디토리얼",
    description: "잡지-아티클에 어울리는 조합",
    heroSlug: "do-hyeon",
    bodySlug: "nanum-myeongjo",
  },
];
```

```typescript
// apps/web/components/PairingPresets.tsx
"use client";

import { PAIRINGS, type ComparePreset } from "@/data/pairings";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import styles from "./PairingPresets.module.css";

export function PairingPresets({ onSelect }: { onSelect: (preset: ComparePreset) => void }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 id="pairing-heading" className={styles.title}>페어링 추천</h2>
        <span className={styles.hint}>제목과 본문, 어울리는 조합을 바로 비교해 보세요</span>
      </div>
      <div className={styles.cards}>
        {PAIRINGS.map((p) => {
          const hero = fonts.find((f) => f.slug === p.heroSlug);
          const body = fonts.find((f) => f.slug === p.bodySlug);
          if (!hero || !body) return null;
          return (
            <button
              type="button"
              key={p.id}
              className={styles.card}
              onClick={() => onSelect({ heroSlug: p.heroSlug, gridSlugs: [p.bodySlug] })}
            >
              <span className={styles.sample} style={{ fontFamily: familyOf(hero.fontKey) }}>
                {p.title}
              </span>
              <span className={styles.desc}>
                {hero.nameKo} + {body.nameKo} — {p.description}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

```css
/* apps/web/components/PairingPresets.module.css */
.wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.title {
  font-size: 20px;
  font-weight: 800;
  margin: 0;
}

.hint {
  font-size: 13px;
  color: var(--sub);
}

.cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--line, #d0d0d8);
  border-radius: 12px;
  background: var(--surface-1, transparent);
  text-align: left;
  cursor: pointer;
}

.sample {
  font-size: 22px;
  line-height: 1.3;
}

.desc {
  font-size: 12px;
  color: var(--sub);
}

@media (max-width: 900px) {
  .cards {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

- [ ] **Step 4: CompareCanvas preset prop**

`apps/web/components/CompareCanvas.tsx`에서:

import 줄 `import { useState } from "react";` 를 다음으로 교체:

```typescript
import { useEffect, useState } from "react";
```

import에 추가:

```typescript
import type { ComparePreset } from "@/data/pairings";
```

`export function CompareCanvas() {` 를 다음으로 교체:

```typescript
export function CompareCanvas({ preset }: { preset?: ComparePreset } = {}) {
```

`const hero = OPTIONS.find((f) => f.slug === heroSlug);` 줄 바로 위에 추가:

```typescript
  useEffect(() => {
    if (!preset) return;
    setHeroSlug(preset.heroSlug);
    setGridSlugs(preset.gridSlugs);
  }, [preset]);
```

나머지 내부 UI-상태 로직은 변경 금지.

- [ ] **Step 5: CompareLazy preset 전달**

`apps/web/components/CompareLazy.tsx`에서:

```typescript
export function CompareLazy({ placeholder }: { placeholder: ReactNode }) {
```

를 다음으로 교체:

```typescript
import type { ComparePreset } from "@/data/pairings";

export function CompareLazy({
  placeholder,
  preset,
}: {
  placeholder: ReactNode;
  preset?: ComparePreset;
}) {
```

(import는 파일 상단 import 블록에 배치) 그리고 `<CompareCanvas />` 를 `<CompareCanvas preset={preset} />` 로 교체.

- [ ] **Step 6: HomeCompareSection으로 홈 조립**

```typescript
// apps/web/components/HomeCompareSection.tsx
"use client";

import { useState } from "react";
import type { ComparePreset } from "@/data/pairings";
import { PairingPresets } from "./PairingPresets";
import { CompareLazy } from "./CompareLazy";
import styles from "./HomeCompareSection.module.css";

export function HomeCompareSection() {
  const [preset, setPreset] = useState<ComparePreset | undefined>(undefined);

  const handleSelect = (next: ComparePreset) => {
    setPreset(next);
    document.getElementById("compare")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <>
      <section className={styles.pairingSection} aria-labelledby="pairing-heading">
        <div className={styles.container}>
          <PairingPresets onSelect={handleSelect} />
        </div>
      </section>
      <section id="compare" className={styles.compareSection} aria-labelledby="compare-heading">
        <div className={styles.container}>
          <CompareLazy placeholder={<div className={styles.comparePlaceholder} />} preset={preset} />
        </div>
      </section>
    </>
  );
}
```

```css
/* apps/web/components/HomeCompareSection.module.css */
.container {
  max-width: 1180px;
  margin: 0 auto;
}

.pairingSection {
  padding: 24px var(--pad-page) 0;
}

.compareSection {
  padding: 48px var(--pad-page);
  scroll-margin-top: 64px;
}

.comparePlaceholder {
  min-height: 480px;
  background: var(--surface-2);
}

@media (max-width: 900px) {
  .compareSection {
    padding: 28px var(--pad-page);
  }

  .comparePlaceholder {
    min-height: 320px;
  }
}
```

`apps/web/app/page.tsx`에서 기존 compare 섹션 블록:

```typescript
      <section id="compare" className={styles.compareSection} aria-labelledby="compare-heading">
        <div className={styles.container}>
          <CompareLazy
            placeholder={<div className={styles.comparePlaceholder} />}
          />
        </div>
      </section>
```

를 다음으로 교체하고, `CompareLazy` import를 `HomeCompareSection` import로 바꾼다:

```typescript
      <HomeCompareSection />
```

`apps/web/app/page.module.css`에서 `.compareSection`, `.comparePlaceholder` 블록 삭제 (`.container`는 adSection이 쓰므로 유지).

- [ ] **Step 7: 테스트-타입 확인**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm test`
Expected: 전부 PASS (신규 4개 포함)

- [ ] **Step 8: 커밋**

```bash
git add apps/web/data/pairings.ts apps/web/components/PairingPresets.tsx \
  apps/web/components/PairingPresets.module.css apps/web/components/PairingPresets.test.tsx \
  apps/web/components/HomeCompareSection.tsx apps/web/components/HomeCompareSection.module.css \
  apps/web/components/CompareCanvas.tsx apps/web/components/CompareCanvas.test.tsx \
  apps/web/components/CompareLazy.tsx apps/web/app/page.tsx apps/web/app/page.module.css
git commit -m "feat: 페어링 프리셋과 비교 보드 프리셋 로드 추가 (#128)"
```

---

### Task 8: 신규 컬렉션 4개 시드 (collections_seed)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/collections_seed.py`
- Test: `apps/pipeline/tests/test_collections_seed.py`

**Interfaces:**
- Consumes: Task 1과 동일한 config-헤더 패턴. DB 스키마: `fontagit.collections(slug, title, intro, status, sort_order)`, `fontagit.collection_items(collection_id, font_id, comment, sort_order)`
- Produces: CLI `python -m fontagit_pipeline.collections_seed [--apply] [--target dev|prod]` — dry-run 시 후보 리포트 JSON

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# apps/pipeline/tests/test_collections_seed.py
"""collections_seed 후보 선정 로직 테스트."""

from fontagit_pipeline.collections_seed import (
    NEW_COLLECTIONS,
    pick_candidates,
    should_create,
)


def _font(slug: str, tags: list[str]) -> dict:
    return {"id": f"id-{slug}", "slug": slug, "name_ko": slug, "tags": tags}


def test_태그가_겹치는_폰트만_후보가_된다() -> None:
    fonts = [
        _font("a", ["귀여운"]),
        _font("b", ["제목용"]),
        _font("c", ["동글동글", "귀여운"]),
    ]
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "cute-round")
    picked = pick_candidates(fonts, spec, limit=15)
    assert [f["slug"] for f in picked] == ["a", "c"]


def test_limit을_넘지_않는다() -> None:
    fonts = [_font(f"f{i}", ["레트로"]) for i in range(30)]
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "retro-classic")
    assert len(pick_candidates(fonts, spec, limit=15)) == 15


def test_신규_컬렉션은_4종이고_sort_order가_기존_10개_뒤다() -> None:
    assert len(NEW_COLLECTIONS) == 4
    assert [c["sort_order"] for c in NEW_COLLECTIONS] == [10, 11, 12, 13]
    assert all(c["status"] == "published" for c in NEW_COLLECTIONS)


def test_후보가_최소_기준_미만이면_생성하지_않는다() -> None:
    assert should_create({"candidates": [{}] * 4}) is False
    assert should_create({"candidates": [{}] * 5}) is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_collections_seed.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
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
    },
    {
        "slug": "retro-classic",
        "title": "다시 만난 레트로 감성",
        "intro": "뉴트로 무드의 포스터와 간판에 어울리는 폰트 모음이에요.",
        "status": "published",
        "sort_order": 11,
        "tags": ["레트로", "고전체"],
    },
    {
        "slug": "calligraphy-brush",
        "title": "붓끝의 캘리그라피",
        "intro": "손맛이 살아 있는 붓글씨-캘리그라피 폰트를 골랐어요.",
        "status": "published",
        "sort_order": 12,
        "tags": ["캘리그라피", "붓글씨"],
    },
    {
        "slug": "title-impact",
        "title": "시선을 붙잡는 제목용 임팩트",
        "intro": "배너와 썸네일 제목에 힘을 실어 주는 두꺼운 폰트 모음이에요.",
        "status": "published",
        "sort_order": 13,
        "tags": ["제목용", "두꺼운"],
    },
]


def pick_candidates(fonts: list[dict], spec: dict, limit: int = ITEM_LIMIT) -> list[dict]:
    """컬렉션 spec의 태그와 겹치는 폰트를 입력 순서(최신순) 그대로 최대 limit개 고른다."""
    wanted = set(spec["tags"])
    picked = [f for f in fonts if wanted & set(f.get("tags") or [])]
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
            f"&select=id,slug,name_ko,tags&order=created_at.desc,slug"
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_collections_seed.py -v`
Expected: PASS (4개)

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/collections_seed.py apps/pipeline/tests/test_collections_seed.py
git commit -m "feat: 신규 컬렉션 4종 시드 엔진 추가 (#128)"
```

- [ ] **Step 6: 🛑 후보 리포트 사용자 검수 (게이트)**

Run: `cd apps/pipeline && uv run python -m fontagit_pipeline.collections_seed --target dev`

`output/audit/collections-seed-dev-report.json`의 컬렉션별 후보 폰트 목록을 사용자에게 보여주고 승인을 받는다. **승인 없이 apply 금지.** (Task 2의 재분류가 dev에 적용된 뒤 실행할 것 — 태그는 재분류와 무관하지만 데이터 상태 일관성을 위해)

- [ ] **Step 7: dev 적용 - 확인 - 🛑 prod 게이트 - prod 적용**

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline.collections_seed --target dev --apply
```

dev 확인(Expected): dry-run 재실행 시 리포트의 `existing.count`가 14이고, 신규 4개 slug가 `existing.slugs`에 포함되며, 적용 로그에 각 컬렉션 "반영 완료 (N종, N >= 5)"가 찍혀야 한다. 이상 없으면 **사용자에게 prod 적용 승인을 다시 받고**:

```bash
uv run python -m fontagit_pipeline.collections_seed --target prod          # dry-run: existing/sort_order 충돌 확인
uv run python -m fontagit_pipeline.collections_seed --target prod --apply
uv run python -m fontagit_pipeline.collections_seed --target prod          # 재실행 dry-run: existing.count=14 = 수렴
```

prod 확인(Expected): 재실행 dry-run 리포트에서 `existing.count` = 14, 신규 4개 slug 포함. apply 로그에서 각 신규 컬렉션 아이템 5종 이상.

---

### Task 9: 통합 검증

**Files:** 변경 없음 (검증만)

- [ ] **Step 1: 웹 전체 테스트-린트-타입**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm lint && pnpm test`
Expected: 전부 PASS. ⚠️ 테스트는 env 노출 셸에 의존할 수 있으므로 깨끗한 셸에서 실측 (프로젝트 메모리: client.ts 로드 throw 함정)

- [ ] **Step 2: 파이프라인 전체 테스트**

Run: `cd apps/pipeline && uv run pytest -q`
Expected: 전부 PASS

- [ ] **Step 3: 정적 빌드 확인**

Run: `cd apps/web && pnpm build`
Expected: 성공. `out/` 산출물에 `collections/` 상세 페이지들이 존재하고, 목록 `collections/index.html`은 생성되지 않아야 함 (`ls out/collections/`로 확인)

- [ ] **Step 4: 수동 스모크 체크리스트**

`cd apps/web && pnpm start` (out/ 서빙) 후:
- 칩 클릭 → 그리드 즉시 교체, 유료 칩 → EmptyState
- 전체 보기 → /fonts?category=... 필터 적용 상태로 진입
- Header 컬렉션 → 홈 컬렉션 섹션으로 스크롤
- 페어링 카드 클릭 → 비교 보드로 스크롤 + 대표/본문 폰트 반영
- TOP 10 패널이 기존과 동일하게 렌더 (변경 없음 확인)
- 모바일 폭(375px, 개발자도구): 칩 줄바꿈 정상, 그리드 2열 유지(가로 넘침 없음), 컬렉션 스트립 가로 스크롤 동작, 카드 뱃지-폰트명 말줄임 정상

- [ ] **Step 5: 커밋 (잔여 변경이 있으면)**

```bash
git status --short   # 잔여 변경 확인 후 필요 시
git add -A && git commit -m "test: 홈 개편 통합 검증 보완 (#128)"
```

---

## 실행 순서와 의존성

- Task 1 → Task 2 (재분류는 웹 작업과 독립이라 병행 가능하나, Task 2의 prod 게이트는 사용자 승인 필수)
- Task 3 → Task 4 → Task 5 (createdAt → 큐레이션 → UI 순서 고정)
- Task 6, Task 7은 Task 5 이후 (page.tsx 충돌 방지 위해 순차)
- Task 8은 Task 2(dev 적용) 이후 + 두 번의 사용자 게이트
- Task 9는 마지막

## 마무리 절차 (구현 완료 후)

1. `/pr` 스킬로 PR 생성 (base: main, 이슈 #128 연결). Codex 리뷰는 사용자가 직접 실행하므로 자동 실행하지 않는다
2. 배포는 사용자 승인 후 `scripts/deploy.sh` (main 전용, 배포 전 `.next` 수동 정리 필요 - 프로젝트 메모리 참조)
3. 배포 후 prod에서 `/collections` 301 리다이렉트와 홈 섹션 실측 확인
4. `/progress`로 세션 일지 기록
