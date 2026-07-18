"""폰트 감사 출처 및 수집 정책 테스트."""

import json
from pathlib import Path

import pytest

from fontagit_pipeline.audit_policy import (
    assert_collection_allowed,
    load_source_registry,
)


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"maker": "   "},
        {"domain": "   "},
        {"roles": ["download", ""]},
        {"roles": ["download", "   "]},
        {"approved_by": "   "},
        {"evidence_snapshot_id": "   "},
    ],
)
def test_registry_requires_approval_evidence(
    tmp_path: Path,
    invalid_fields: dict[str, object],
) -> None:
    """공식 출처 주장은 사람 승인 근거 없이는 등록할 수 없다."""
    path = tmp_path / "registry.json"
    entry = {
        "maker": "네이버",
        "domain": "clova.ai",
        "roles": ["download"],
        "source_kind": "official",
        "approved_by": "reviewer",
        "approved_at": "2026-07-18T00:00:00Z",
        "evidence_snapshot_id": "snapshot-1",
    }
    entry.update(invalid_fields)
    path.write_text(json.dumps({"version": 1, "entries": [entry]}), encoding="utf-8")

    with pytest.raises(ValueError, match="approval evidence"):
        load_source_registry(path)


def test_unknown_domain_is_discovery_only() -> None:
    """승인 레지스트리에 없는 도메인은 discovery를 벗어나지 못한다."""
    registry = load_source_registry()

    assert registry.classify("https://example.org/font") == "discovery"


def test_registry_strips_approved_text_fields(tmp_path: Path) -> None:
    """승인 문자열은 비교와 기록 전에 앞뒤 공백을 제거한다."""
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "maker": " 네이버 ",
                        "domain": " clova.ai ",
                        "roles": [" download "],
                        "source_kind": "official",
                        "approved_by": " reviewer ",
                        "approved_at": "2026-07-18T00:00:00Z",
                        "evidence_snapshot_id": " snapshot-1 ",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    entry = load_source_registry(path).entries[0]

    assert (entry.maker, entry.domain, entry.roles) == (
        "네이버",
        "clova.ai",
        ["download"],
    )
    assert (entry.approved_by, entry.evidence_snapshot_id) == (
        "reviewer",
        "snapshot-1",
    )


def test_collection_policy_defaults_to_structured_only_and_blocks_raw_text(
    tmp_path: Path,
) -> None:
    """사람이 승인하지 않은 정책은 원문 보관을 막는다."""
    assert (
        assert_collection_allowed(None, expected_source="noonnu")
        == "structured-only"
    )

    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "source": "noonnu",
                "robots_url": "https://noonnu.cc/robots.txt",
                "terms_url": None,
                "checked_at": None,
                "crawl_allowed": "unknown",
                "raw_retention_allowed": "unknown",
                "robots_sha256": None,
                "terms_sha256": None,
                "approved_by": None,
                "approved_at": None,
            }
        ),
        encoding="utf-8",
    )

    assert (
        assert_collection_allowed(
            policy_path,
            expected_source="noonnu",
            retain_raw_text=False,
        )
        == "structured-only"
    )
    with pytest.raises(ValueError, match="raw_text"):
        assert_collection_allowed(
            policy_path,
            expected_source="noonnu",
            retain_raw_text=True,
        )


def test_collection_policy_is_bound_to_expected_source(tmp_path: Path) -> None:
    """다른 수집 대상용 승인은 재사용할 수 없다."""
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "source": "noonnu",
                "robots_url": "https://noonnu.cc/robots.txt",
                "terms_url": "https://noonnu.cc/page/terms",
                "checked_at": "2026-07-18T00:00:00Z",
                "crawl_allowed": "allowed",
                "raw_retention_allowed": "allowed",
                "robots_sha256": "a" * 64,
                "terms_sha256": "b" * 64,
                "approved_by": "reviewer",
                "approved_at": "2026-07-18T00:05:00Z",
            }
        ),
        encoding="utf-8",
    )

    assert (
        assert_collection_allowed(
            policy_path,
            expected_source="noonnu",
            retain_raw_text=True,
        )
        == "raw-retention"
    )
    with pytest.raises(ValueError, match="source"):
        assert_collection_allowed(
            policy_path,
            expected_source="google-fonts",
            retain_raw_text=True,
        )


def test_collection_policy_rejects_whitespace_approver(tmp_path: Path) -> None:
    """공백 승인자는 사람 승인으로 취급하지 않는다."""
    policy_path = tmp_path / "policy.json"

    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "source": "noonnu",
                "robots_url": "https://noonnu.cc/robots.txt",
                "terms_url": "https://noonnu.cc/page/terms",
                "checked_at": "2026-07-18T00:00:00Z",
                "crawl_allowed": "allowed",
                "raw_retention_allowed": "allowed",
                "robots_sha256": "a" * 64,
                "terms_sha256": "b" * 64,
                "approved_by": "   ",
                "approved_at": "2026-07-18T00:05:00Z",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="raw_text"):
        assert_collection_allowed(
            policy_path,
            expected_source="noonnu",
            retain_raw_text=True,
        )
