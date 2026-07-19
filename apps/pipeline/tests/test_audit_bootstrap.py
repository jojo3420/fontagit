"""prod 기준선과 안정 출처키 bootstrap 테스트."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from fontagit_pipeline.audit_bootstrap import (
    BootstrapError,
    build_bootstrap_manifest,
    load_prod_baseline,
    write_bootstrap_manifest,
    write_prod_baseline,
)
from fontagit_pipeline.audit_http import FetchResult
from fontagit_pipeline.audit_manifest import build_manifest
from fontagit_pipeline.audit_metadata import BASIC_LATIN, FontFileMetadata
from fontagit_pipeline.audit_runner import load_bootstrap_targets, run_metadata_audit
from fontagit_pipeline.audit_store import InMemoryAuditStore

INSTAGRAM_URL = "https://www.instagram.com/p/example/"


def prod_font(
    slug: str,
    name_ko: str,
    official_url: str,
    *,
    source_tier: str = "B",
    name_en: str = "",
) -> dict[str, object]:
    return {
        "id": str(uuid5(NAMESPACE_URL, f"fontagit-test:{slug}")),
        "slug": slug,
        "name_ko": name_ko,
        "name_en": name_en or slug,
        "source_tier": source_tier,
        "official_url": official_url,
        "foundry": None,
        "foundry_url": None,
        "download_url": None,
        "license_source_url": None,
        "category_ko": "고딕",
        "tags": ["본문"],
        "weights": [400],
        "variants": ["regular"],
        "subsets": ["korean"],
        "script_status": "pending",
        "script_checked_at": None,
        "script_evidence_id": None,
        "download_source_kind": None,
        "download_status": "pending",
        "download_evidence_id": None,
        "status": "published",
        "updated_at": "2026-07-18T00:00:00+00:00",
    }


def tier_b_seed(
    page_id: str,
    name_ko: str,
    official_url: str,
) -> dict[str, object]:
    return {
        "name_ko": name_ko,
        "name_en": None,
        "official_url": official_url,
        "source_page": f"https://noonnu.cc/font_page/{page_id}",
    }


def test_tier_b_exact_match_builds_no_public_update_and_atomic_artifact(
    tmp_path: Path,
) -> None:
    """완전 일치는 안정키만 연결하고 공개 필드는 바꾸지 않는다."""
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[
            {
                **tier_b_seed("613", "흰꼬리수리", INSTAGRAM_URL),
                "slug": "시드에-존재하지-않는-값",
            }
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (1, 0, 0)
    entry = result.entries[0]
    assert (entry.provider, entry.provider_record_id) == ("noonnu", "613")
    assert entry.public_updates == {}
    assert entry.before["source_tier"] == "B"
    assert entry.before["foundry"] is None
    assert entry.current["weights"] == [400]
    assert entry.current["subsets"] == ["korean"]
    assert entry.current["download_status"] == "pending"

    out = tmp_path / "nested" / "bootstrap.json"
    digest = write_bootstrap_manifest(result, out)

    assert out.exists()
    assert out.with_suffix(".json.sha256").read_text(encoding="utf-8") == f"{digest}\n"
    assert hashlib.sha256(out.read_bytes()).hexdigest() == digest
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["provider_record_id"] == "613"


def test_zero_or_multiple_candidates_are_review_only() -> None:
    """후보가 없거나 여럿이면 추측하지 않고 검수 대상으로 남긴다."""
    result = build_bootstrap_manifest(
        prod_rows=[
            prod_font("동일", "동일", INSTAGRAM_URL),
            prod_font("missing", "없음", INSTAGRAM_URL),
            {
                **prod_font("제작사-있음", "제작사 있음", INSTAGRAM_URL),
                "foundry": "기존 제작사",
            },
            prod_font(
                "wrong-tier",
                "잘못된 Tier A",
                INSTAGRAM_URL,
                source_tier="A",
                name_en="Wrong Tier",
            ),
        ],
        tier_a=[
            {
                "source_tier": "B",
                "slug": "wrong-tier",
                "name_en": "Wrong Tier",
                "official_url": INSTAGRAM_URL,
            }
        ],
        tier_b=[
            tier_b_seed("1", "동일", INSTAGRAM_URL),
            tier_b_seed("2", "동일", INSTAGRAM_URL),
            tier_b_seed("3", "제작사 있음", INSTAGRAM_URL),
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (0, 3, 1)
    assert result.entries == []
    assert {row["reason"] for row in result.review_rows} == {
        "no_exact_candidate",
        "multiple_candidates",
        "foundry_precondition_not_null",
    }
    assert next(row for row in result.review_rows if row["slug"] == "wrong-tier")[
        "reason"
    ] == "no_exact_candidate"


def test_invalid_tier_b_source_page_is_never_used_as_provider_id() -> None:
    """눈누 페이지 번호를 엄격히 파싱하지 못하면 자동 연결하지 않는다."""
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[
            {
                **tier_b_seed("613/extra", "흰꼬리수리", INSTAGRAM_URL),
                "source_page": "https://noonnu.cc/font_page/613/extra",
            }
        ],
    )

    assert (result.matched, result.unmatched, result.conflicts) == (0, 1, 0)
    assert result.review_rows[0]["reason"] == "invalid_provider_record_id"


def test_prod_baseline_sorts_slug_before_hashing(tmp_path: Path) -> None:
    """기준선은 DB 정렬 환경과 무관하게 slug 순서를 고정한다."""
    rows = [
        prod_font(
            f"font-{index:04d}",
            f"폰트 {index}",
            INSTAGRAM_URL,
            source_tier="A" if index < 130 else "B",
        )
        for index in reversed(range(1240))
    ]
    out = tmp_path / "prod-baseline.json"

    write_prod_baseline(rows, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    slugs = [row["slug"] for row in payload["rows"]]
    assert slugs == sorted(slugs)


def test_prod_baseline_requires_complete_sorted_hashed_snapshot(tmp_path: Path) -> None:
    """부분-변조-정렬 오류 기준선은 bootstrap 전에 거부한다."""
    rows = [
        prod_font("a", "가", INSTAGRAM_URL),
        prod_font("b", "나", INSTAGRAM_URL),
    ]
    baseline = tmp_path / "prod-baseline.json"
    file_sha256 = write_prod_baseline(
        rows,
        baseline,
        expected_record_count=2,
        expected_tier_counts=None,
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))

    assert payload["baseline_content_sha256"]
    assert baseline.with_suffix(".json.sha256").read_text(encoding="utf-8") == f"{file_sha256}\n"
    assert load_prod_baseline(
        baseline,
        expected_record_count=2,
        expected_tier_counts=None,
    ) == rows

    payload["baseline_content_sha256"] = "0" * 64
    changed_content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    baseline.write_bytes(changed_content)
    baseline.with_suffix(".json.sha256").write_text(
        f"{hashlib.sha256(changed_content).hexdigest()}\n", encoding="ascii"
    )
    with pytest.raises(BootstrapError, match="baseline content SHA-256"):
        load_prod_baseline(
            baseline,
            expected_record_count=2,
            expected_tier_counts=None,
        )

    write_prod_baseline(
        rows,
        baseline,
        expected_record_count=2,
        expected_tier_counts=None,
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    payload["rows"] = list(reversed(rows))
    baseline.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BootstrapError, match="file SHA-256"):
        load_prod_baseline(
            baseline,
            expected_record_count=2,
            expected_tier_counts=None,
        )

def test_prod_baseline_rejects_partial_default_cli_contract(tmp_path: Path) -> None:
    """기본 계약은 1,240건과 A 130/B 1,110 분포를 모두 강제한다."""
    baseline = tmp_path / "partial.json"
    write_prod_baseline(
        [prod_font("only", "하나", INSTAGRAM_URL)],
        baseline,
        expected_record_count=1,
        expected_tier_counts=None,
    )

    with pytest.raises(BootstrapError, match="expected=1240"):
        load_prod_baseline(baseline)

    wrong_distribution = [
        prod_font(f"wrong-{index:04d}", f"잘못된 분포 {index}", INSTAGRAM_URL)
        for index in range(1240)
    ]
    with pytest.raises(BootstrapError, match="source_tier 분포"):
        write_prod_baseline(wrong_distribution, tmp_path / "wrong-distribution.json")


def test_prod_baseline_rejects_unknown_schema(tmp_path: Path) -> None:
    """기준선 스키마 버전이 바뀌면 자동 bootstrap을 막는다."""
    rows = [prod_font("only", "하나", INSTAGRAM_URL)]
    baseline = tmp_path / "unknown-schema.json"
    write_prod_baseline(
        rows,
        baseline,
        expected_record_count=1,
        expected_tier_counts=None,
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    payload["schema_version"] = 2
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    baseline.write_bytes(content)
    baseline.with_suffix(".json.sha256").write_text(
        f"{hashlib.sha256(content).hexdigest()}\n",
        encoding="ascii",
    )

    with pytest.raises(BootstrapError, match="schema_version"):
        load_prod_baseline(
            baseline,
            expected_record_count=1,
            expected_tier_counts=None,
        )


def test_prod_contract_rejects_missing_or_wrong_typed_current_values(tmp_path: Path) -> None:
    """감사 current 값은 누락이나 기본값 대체 없이 DB 타입 그대로여야 한다."""
    missing = prod_font("missing", "누락", INSTAGRAM_URL)
    missing.pop("weights")
    with pytest.raises(BootstrapError, match="columns"):
        write_prod_baseline(
            [missing],
            tmp_path / "missing.json",
            expected_record_count=1,
            expected_tier_counts=None,
        )

    wrong_type = prod_font("wrong-type", "타입 오류", INSTAGRAM_URL)
    wrong_type["weights"] = [True]
    with pytest.raises(BootstrapError, match="weights"):
        write_prod_baseline(
            [wrong_type],
            tmp_path / "wrong-type.json",
            expected_record_count=1,
            expected_tier_counts=None,
        )


def test_bootstrap_current_flows_to_metadata_and_accepted_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """export current가 metadata before와 승인 manifest까지 같은 값으로 이어진다."""
    row = prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)
    baseline = tmp_path / "baseline.json"
    write_prod_baseline(
        [row], baseline, expected_record_count=1, expected_tier_counts=None
    )
    loaded_rows = load_prod_baseline(
        baseline, expected_record_count=1, expected_tier_counts=None
    )
    result = build_bootstrap_manifest(
        loaded_rows,
        [],
        [tier_b_seed("613", "흰꼬리수리", INSTAGRAM_URL)],
    )
    bootstrap = tmp_path / "bootstrap.json"
    write_bootstrap_manifest(result, bootstrap)
    target = load_bootstrap_targets(bootstrap)[0]
    assert (target.weights, target.subsets, target.script_status) == (
        (400,),
        ("korean",),
        "pending",
    )

    fixture = Path(__file__).parent / "fixtures" / "audit" / "noonnu-white-tailed-eagle.html"

    def page_fetch(url: str) -> FetchResult:
        content = fixture.read_bytes()
        return FetchResult(200, url, content, hashlib.sha256(content).hexdigest(), 0)

    def font_fetch(url: str, max_bytes: int = 32 * 1024 * 1024) -> FetchResult:
        content = b"synthetic-font-fixture"
        return FetchResult(200, url, content, hashlib.sha256(content).hexdigest(), 0)

    monkeypatch.setattr("fontagit_pipeline.audit_runner.sys.platform", "linux")
    monkeypatch.setattr(
        "fontagit_pipeline.audit_metadata.inspect_font_metadata",
        lambda _path: FontFileMetadata(
            families=("흰꼬리수리",),
            weight=700,
            italic=False,
            codepoints=frozenset(BASIC_LATIN),
            file_sha256="f" * 64,
        ),
    )
    store = InMemoryAuditStore()
    report = run_metadata_audit(
        [target],
        store,
        {"version": 1, "entries": []},
        fetcher=page_fetch,
        font_fetcher=font_fetch,
    )
    finding_id = next(
        item
        for item in report.finding_ids
        if store.finding_draft(item).field_name == "script_status"
    )
    finding = store.finding_draft(finding_id)
    assert finding.before_value == row["script_status"]
    assert finding.evidence_id is not None
    snapshot_run, snapshot = store.snapshot_draft(finding.evidence_id)
    assert snapshot_run == report.run_id

    now = datetime(2026, 7, 18, tzinfo=UTC).isoformat()
    snapshot_row = {
        **asdict(snapshot),
        "id": str(finding.evidence_id),
        "run_id": str(report.run_id),
        "font_id": str(target.font_id),
        "collected_at": (snapshot.collected_at or datetime(2026, 7, 18, tzinfo=UTC)).isoformat(),
        "raw_retention_allowed": False,
    }
    current_row = {
        **row,
        "source_key": {
            "provider": target.provider,
            "provider_record_id": target.provider_record_id,
        },
        "evidence_snapshots": [snapshot_row],
    }
    approved_finding = {
        **asdict(finding),
        "id": str(finding_id),
        "run_id": str(report.run_id),
        "font_id": str(target.font_id),
        "evidence_id": str(finding.evidence_id),
        "status": "approved",
        "reviewed_by": "reviewer",
        "reviewed_at": now,
    }
    run_row = {
        "id": str(report.run_id),
        "stage": "metadata",
        "target_environment": "dev",
        "target_count": 1,
        "success_count": 1,
        "verified_count": report.verified_count,
        "review_count": report.needs_review_count,
        "broken_count": 0,
        "parser_version": "audit-runner-v1",
        "baseline_sha256": "a" * 64,
        "manifest_sha256": None,
        "dry_run": False,
        "status": "completed",
        "started_at": now,
        "finished_at": now,
    }

    bundle = build_manifest(run_row, [approved_finding], [current_row])

    assert bundle.forward.entries[0].before["script_status"] == row["script_status"]
