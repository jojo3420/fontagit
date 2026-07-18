"""폰트 감사 출처 및 수집 정책 테스트."""

import json
from pathlib import Path

import pytest

from fontagit_pipeline.audit_policy import (
    assert_collection_allowed,
    load_source_registry,
)


def test_registry_requires_approval_evidence(tmp_path: Path) -> None:
    """공식 출처 주장은 사람 승인 근거 없이는 등록할 수 없다."""
    path = tmp_path / "registry.json"
    path.write_text(
        '{"version":1,"entries":[{"maker":"네이버","domain":"clova.ai",'
        '"roles":["download"],"source_kind":"official","approved_by":"",'
        '"approved_at":"","evidence_snapshot_id":""}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="approval evidence"):
        load_source_registry(path)


def test_unknown_domain_is_discovery_only() -> None:
    """승인 레지스트리에 없는 도메인은 discovery를 벗어나지 못한다."""
    registry = load_source_registry()

    assert registry.classify("https://example.org/font") == "discovery"


def test_collection_policy_defaults_to_structured_only_and_blocks_raw_text(
    tmp_path: Path,
) -> None:
    """사람이 승인하지 않은 정책은 원문 보관을 막는다."""
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

    assert assert_collection_allowed(policy_path, retain_raw_text=False) == "structured-only"
    with pytest.raises(ValueError, match="raw_text"):
        assert_collection_allowed(policy_path, retain_raw_text=True)

    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "source": "noonnu",
                "robots_url": "https://noonnu.cc/robots.txt",
                "terms_url": None,
                "checked_at": "2026-07-18T00:00:00Z",
                "crawl_allowed": "allowed",
                "raw_retention_allowed": "allowed",
                "robots_sha256": None,
                "terms_sha256": None,
                "approved_by": "reviewer",
                "approved_at": "2026-07-18T00:05:00Z",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="raw_text"):
        assert_collection_allowed(policy_path, retain_raw_text=True)
