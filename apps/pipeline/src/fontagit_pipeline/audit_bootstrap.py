"""prod 읽기 전용 기준선에서 안정 출처키 bootstrap manifest를 만든다."""

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import httpx

from fontagit_pipeline.noonnu_seed import derive_noonnu_slug

_NOONNU_PAGE_ID = re.compile(r"^https://noonnu\.cc/font_page/([1-9][0-9]*)$")
_EXPECTED_PROD_PUBLISHED_COUNT = 1240
_PUBLIC_FONT_COLUMNS = (
    "id,slug,name_ko,name_en,foundry,source_tier,official_url,updated_at"
)


class BootstrapError(ValueError):
    """기준선 또는 bootstrap 입력이 안전하게 처리될 수 없을 때 발생한다."""


@dataclass(frozen=True)
class BootstrapEntry:
    """공개값을 바꾸지 않는 안정 출처키 연결 후보."""

    font_id: str
    slug: str
    provider: str
    provider_record_id: str
    source_url: str
    before: dict[str, object]
    public_updates: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "font_id": self.font_id,
            "slug": self.slug,
            "provider": self.provider,
            "provider_record_id": self.provider_record_id,
            "source_url": self.source_url,
            "before": self.before,
            "public_updates": self.public_updates,
        }


@dataclass(frozen=True)
class BootstrapResult:
    """자동 연결과 검수 대상의 분리 결과."""

    matched: int
    unmatched: int
    conflicts: int
    entries: list[BootstrapEntry]
    review_rows: list[dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "conflicts": self.conflicts,
            "entries": [entry.as_dict() for entry in self.entries],
            "review_rows": self.review_rows,
        }


def _text(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def _required_text(row: Mapping[str, object], key: str) -> str | None:
    value = _text(row, key)
    if value is None or not value.strip():
        return None
    return value


def _nfc(value: str | None) -> str | None:
    return unicodedata.normalize("NFC", value) if value is not None else None


def _tier_b_identity(seed: Mapping[str, object]) -> tuple[str, str, str, str] | None:
    """눈누 시드의 안정 페이지 번호와 당시 매칭 필드를 얻는다.

    시드의 ``page_id`` 같은 보조값은 신뢰하지 않고 URL 전체 형식만 허용한다.
    """
    source_page = _required_text(seed, "source_page")
    name_ko = _required_text(seed, "name_ko")
    official_url = _required_text(seed, "official_url")
    if source_page is None or name_ko is None or official_url is None:
        return None
    match = _NOONNU_PAGE_ID.fullmatch(source_page)
    if match is None:
        return None

    stated_slug = _text(seed, "slug")
    slug = stated_slug.strip() if stated_slug is not None and stated_slug.strip() else derive_noonnu_slug(
        name_ko, _text(seed, "name_en")
    )
    if not slug:
        return None
    return match.group(1), slug, _nfc(name_ko) or "", official_url


def _before(row: Mapping[str, object]) -> dict[str, object]:
    """후속 RPC가 다시 검증할 현재값 precondition을 고정한다."""
    return {
        "slug": row.get("slug"),
        "name_en": row.get("name_en"),
        "name_ko": row.get("name_ko"),
        "official_url": row.get("official_url"),
        "foundry": row.get("foundry"),
        "updated_at": row.get("updated_at"),
    }


def _review_row(row: Mapping[str, object], reason: str) -> dict[str, object]:
    return {
        "font_id": row.get("id"),
        "slug": row.get("slug"),
        "source_tier": row.get("source_tier"),
        "reason": reason,
    }


def build_bootstrap_manifest(
    prod_rows: Sequence[Mapping[str, object]],
    tier_a: Sequence[Mapping[str, object]],
    tier_b: Sequence[Mapping[str, object]],
) -> BootstrapResult:
    """prod 행과 고정 snapshot을 정확 비교해 안정 출처키를 만든다.

    후보가 0개 또는 2개 이상이면 추측하지 않는다. 이 함수는 공개 폰트 필드를
    절대 변경하지 않으므로 ``public_updates``는 항상 빈 객체다.
    """
    entries: list[BootstrapEntry] = []
    review_rows: list[dict[str, object]] = []
    unmatched = 0
    conflicts = 0

    tier_b_valid = [
        (seed, identity)
        for seed in tier_b
        if (identity := _tier_b_identity(seed)) is not None
    ]

    for row in prod_rows:
        tier = _text(row, "source_tier")
        slug = _required_text(row, "slug")
        font_id = _required_text(row, "id")
        if tier not in {"A", "B"} or slug is None or font_id is None:
            unmatched += 1
            review_rows.append(_review_row(row, "invalid_prod_precondition"))
            continue

        if tier == "A":
            name_en = _required_text(row, "name_en")
            official_url = _required_text(row, "official_url")
            tier_a_candidates = [
                seed
                for seed in tier_a
                if _required_text(seed, "name_en") == name_en
                and _required_text(seed, "slug") == slug
                and _required_text(seed, "official_url") == official_url
            ]
            candidate_count = len(tier_a_candidates)
            if candidate_count == 1 and name_en is not None:
                entries.append(
                    BootstrapEntry(
                        font_id=font_id,
                        slug=slug,
                        provider="google-fonts",
                        provider_record_id=name_en,
                        source_url=official_url or "",
                        before=_before(row),
                        public_updates={},
                    )
                )
                continue
        else:
            name_ko = _nfc(_required_text(row, "name_ko"))
            official_url = _required_text(row, "official_url")
            tier_b_candidates = [
                (seed, identity)
                for seed, identity in tier_b_valid
                if identity[1] == slug
                and identity[2] == name_ko
                and identity[3] == official_url
            ]
            candidate_count = len(tier_b_candidates)
            if candidate_count == 1:
                seed, identity = tier_b_candidates[0]
                entries.append(
                    BootstrapEntry(
                        font_id=font_id,
                        slug=slug,
                        provider="noonnu",
                        provider_record_id=identity[0],
                        source_url=_required_text(seed, "source_page") or "",
                        before=_before(row),
                        public_updates={},
                    )
                )
                continue

            invalid_matching_seed = not tier_b_candidates and any(
                _required_text(seed, "name_ko") is not None
                and _nfc(_required_text(seed, "name_ko")) == name_ko
                and _required_text(seed, "official_url") == official_url
                and (
                    (_text(seed, "slug") or "").strip()
                    or derive_noonnu_slug(
                        _required_text(seed, "name_ko"), _text(seed, "name_en")
                    )
                )
                == slug
                for seed in tier_b
            )
            if invalid_matching_seed:
                unmatched += 1
                review_rows.append(_review_row(row, "invalid_provider_record_id"))
                continue

        if candidate_count > 1:
            conflicts += 1
            review_rows.append(_review_row(row, "multiple_candidates"))
        else:
            unmatched += 1
            review_rows.append(_review_row(row, "no_exact_candidate"))

    return BootstrapResult(
        matched=len(entries),
        unmatched=unmatched,
        conflicts=conflicts,
        entries=entries,
        review_rows=review_rows,
    )


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_bootstrap_manifest(result: BootstrapResult, out: Path) -> str:
    """bootstrap 결과와 SHA-256을 원자적으로 저장한다."""
    content = _canonical_json(result.as_dict())
    digest = hashlib.sha256(content).hexdigest()
    _atomic_write(out, content)
    _atomic_write(out.with_suffix(f"{out.suffix}.sha256"), f"{digest}\n".encode("ascii"))
    return digest


def load_snapshot_records(path: Path, field: str) -> list[dict[str, object]]:
    """고정 JSON snapshot의 배열 필드를 안전하게 읽는다."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"snapshot을 읽을 수 없습니다: {path}") from exc
    records = payload if isinstance(payload, list) else payload.get(field) if isinstance(payload, dict) else None
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise BootstrapError(f"snapshot 배열이 올바르지 않습니다: {path}")
    return records


def fetch_prod_public_rows(supabase_url: str, anon_key: str) -> list[dict[str, object]]:
    """anon key로 published fonts만 페이지 단위로 읽는다. 쓰기 요청은 하지 않는다."""
    if not supabase_url.strip() or not anon_key.strip():
        raise BootstrapError("SUPABASE_URL과 SUPABASE_ANON_KEY가 필요합니다")
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/fonts"
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Prefer": "count=exact",
        "Accept-Profile": "fontagit",
    }
    rows: list[dict[str, object]] = []
    offset = 0
    page_size = 1000
    with httpx.Client(timeout=20.0) as client:
        while True:
            response = client.get(
                endpoint,
                headers={**headers, "Range": f"{offset}-{offset + page_size - 1}"},
                params={
                    "select": _PUBLIC_FONT_COLUMNS,
                    "status": "eq.published",
                    "order": "slug.asc",
                },
            )
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
                raise BootstrapError("prod 공개 API 응답 형식이 올바르지 않습니다")
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
    _validate_prod_rows(rows)
    return rows


def _validate_prod_rows(rows: Sequence[Mapping[str, object]]) -> None:
    slugs = [_required_text(row, "slug") for row in rows]
    if len(rows) != _EXPECTED_PROD_PUBLISHED_COUNT:
        raise BootstrapError(
            f"prod published 기준선 수가 다릅니다: expected={_EXPECTED_PROD_PUBLISHED_COUNT}, actual={len(rows)}"
        )
    if any(slug is None for slug in slugs) or len(set(slugs)) != len(slugs):
        raise BootstrapError("prod 기준선 slug가 비어 있거나 중복됩니다")
    clean_slugs = [slug for slug in slugs if slug is not None]
    if clean_slugs != sorted(clean_slugs):
        raise BootstrapError("prod 기준선이 slug 오름차순이 아닙니다")


def write_prod_baseline(rows: Sequence[Mapping[str, object]], out: Path) -> str:
    """검증된 공개 prod 기준선을 원자적으로 저장한다."""
    _validate_prod_rows(rows)
    baseline_payload: dict[str, object] = {
        "schema_version": 1,
        "record_count": len(rows),
        "rows": list(rows),
    }
    baseline_digest = hashlib.sha256(_canonical_json(baseline_payload)).hexdigest()
    payload = {**baseline_payload, "baseline_sha256": baseline_digest}
    final_content = _canonical_json(payload)
    final_digest = hashlib.sha256(final_content).hexdigest()
    _atomic_write(out, final_content)
    _atomic_write(out.with_suffix(f"{out.suffix}.sha256"), f"{final_digest}\n".encode("ascii"))
    return final_digest
