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
_CONTENT_RANGE = re.compile(r"^(?:[0-9]+-[0-9]+|\*)/([0-9]+)$")
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

    slug = derive_noonnu_slug(name_ko, _text(seed, "name_en"))
    if not slug:
        return None
    return match.group(1), slug, _nfc(name_ko) or "", official_url


def _before(row: Mapping[str, object]) -> dict[str, object]:
    """후속 RPC가 다시 검증할 현재값 precondition을 고정한다."""
    return {
        "source_tier": row.get("source_tier"),
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
        if row.get("foundry") is not None:
            unmatched += 1
            review_rows.append(_review_row(row, "foundry_precondition_not_null"))
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
                and derive_noonnu_slug(
                    _required_text(seed, "name_ko"), _text(seed, "name_en")
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
    exact_total: int | None = None
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
            content_range = response.headers.get("Content-Range", "")
            count_match = _CONTENT_RANGE.fullmatch(content_range)
            if count_match is None:
                raise BootstrapError("prod 공개 API가 exact count를 반환하지 않았습니다")
            page_total = int(count_match.group(1))
            if exact_total is None:
                exact_total = page_total
            elif page_total != exact_total:
                raise BootstrapError("prod 공개 API exact count가 페이지마다 다릅니다")
            page = response.json()
            if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
                raise BootstrapError("prod 공개 API 응답 형식이 올바르지 않습니다")
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
    if exact_total != len(rows):
        raise BootstrapError(
            f"prod published exact count와 조회 수가 다릅니다: exact={exact_total}, rows={len(rows)}"
        )
    return _validated_sorted_prod_rows(rows)


def _validate_prod_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_record_count: int = _EXPECTED_PROD_PUBLISHED_COUNT,
    require_sorted: bool = False,
) -> None:
    slugs = [_required_text(row, "slug") for row in rows]
    if len(rows) != expected_record_count:
        raise BootstrapError(
            f"prod published 기준선 수가 다릅니다: expected={expected_record_count}, actual={len(rows)}"
        )
    if any(slug is None for slug in slugs) or len(set(slugs)) != len(slugs):
        raise BootstrapError("prod 기준선 slug가 비어 있거나 중복됩니다")
    clean_slugs = [slug for slug in slugs if slug is not None]
    if require_sorted and clean_slugs != sorted(clean_slugs):
        raise BootstrapError("prod 기준선이 slug 오름차순이 아닙니다")


def _validated_sorted_prod_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_record_count: int = _EXPECTED_PROD_PUBLISHED_COUNT,
) -> list[dict[str, object]]:
    """개수와 중복을 검증한 뒤 환경 독립적인 slug 순서로 고정한다."""
    _validate_prod_rows(rows, expected_record_count=expected_record_count)
    return sorted((dict(row) for row in rows), key=lambda row: str(row["slug"]))


def _baseline_content_payload(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_count": len(rows),
        "rows": list(rows),
    }


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def calculate_baseline_content_sha256(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_record_count: int = _EXPECTED_PROD_PUBLISHED_COUNT,
) -> str:
    """정렬·검증된 기준선 본문 해시를 계산한다."""
    sorted_rows = _validated_sorted_prod_rows(
        rows, expected_record_count=expected_record_count
    )
    return _sha256(_canonical_json(_baseline_content_payload(sorted_rows)))


def write_prod_baseline(
    rows: Sequence[Mapping[str, object]],
    out: Path,
    *,
    expected_record_count: int = _EXPECTED_PROD_PUBLISHED_COUNT,
) -> str:
    """검증된 공개 prod 기준선을 저장하고 파일 전체 SHA-256을 반환한다.

    JSON의 ``baseline_content_sha256``은 해시 필드를 제외한 본문 해시다.
    반환값과 동반 ``.sha256``은 최종 JSON 파일 전체의 해시다.
    """
    sorted_rows = _validated_sorted_prod_rows(
        rows, expected_record_count=expected_record_count
    )
    content_payload = _baseline_content_payload(sorted_rows)
    payload = {
        **content_payload,
        "baseline_content_sha256": _sha256(_canonical_json(content_payload)),
    }
    final_content = _canonical_json(payload)
    file_sha256 = _sha256(final_content)
    _atomic_write(out, final_content)
    _atomic_write(out.with_suffix(f"{out.suffix}.sha256"), f"{file_sha256}\n".encode("ascii"))
    return file_sha256


def load_prod_baseline(
    path: Path,
    *,
    expected_record_count: int = _EXPECTED_PROD_PUBLISHED_COUNT,
) -> list[dict[str, object]]:
    """완전성·본문 해시·파일 해시가 검증된 prod 기준선만 읽는다."""
    try:
        content = path.read_bytes()
        payload = json.loads(content.decode("utf-8"))
        sidecar_sha256 = path.with_suffix(f"{path.suffix}.sha256").read_text(
            encoding="ascii"
        ).strip()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"prod 기준선을 읽을 수 없습니다: {path}") from exc

    if not isinstance(payload, dict):
        raise BootstrapError("prod 기준선 JSON 객체가 올바르지 않습니다")
    if payload.get("schema_version") != 1:
        raise BootstrapError("prod 기준선 schema_version은 1이어야 합니다")
    if not re.fullmatch(r"[0-9a-f]{64}", sidecar_sha256):
        raise BootstrapError("prod 기준선 sidecar SHA-256 형식이 올바르지 않습니다")
    if _sha256(content) != sidecar_sha256:
        raise BootstrapError("prod 기준선 file SHA-256이 일치하지 않습니다")

    rows = payload.get("rows")
    record_count = payload.get("record_count")
    content_sha256 = payload.get("baseline_content_sha256")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise BootstrapError("prod 기준선 rows 배열이 올바르지 않습니다")
    if not isinstance(record_count, int) or record_count != len(rows):
        raise BootstrapError("prod 기준선 record_count가 rows 길이와 일치하지 않습니다")
    if not isinstance(content_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
        raise BootstrapError("prod 기준선 baseline_content_sha256 형식이 올바르지 않습니다")
    if _sha256(_canonical_json(_baseline_content_payload(rows))) != content_sha256:
        raise BootstrapError("prod 기준선 baseline content SHA-256이 일치하지 않습니다")

    _validate_prod_rows(
        rows,
        expected_record_count=expected_record_count,
        require_sorted=True,
    )
    return rows
