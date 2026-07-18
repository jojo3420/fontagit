import hashlib

import pytest

from fontagit_pipeline.audit_license import classify_license
from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot


def _snapshot(*, extractor: str = "deterministic") -> NoonnuFontSnapshot:
    return NoonnuFontSnapshot(
        source_url="https://fonts.example.org/license",
        page_id="613",
        name_ko="검증 폰트",
        foundry="공식 제작사",
        license_text="Approved license wording v1.",
        license_id="TEST-1",
        license_version="1.0",
        extractor=extractor,
        evidence_locations={"license_text": "[data-license-body]"},
    )


def test_exact_approved_fingerprint_maps_only_declared_six_permissions() -> None:
    snapshot = _snapshot()
    fingerprint = hashlib.sha256(snapshot.license_text.encode("utf-8")).hexdigest()
    rules = {
        "version": 1,
        "standard_licenses": [
            {
                "id": "TEST-1",
                "version": "1.0",
                "fingerprint": fingerprint,
                "permissions": {
                    "allow_commercial": "allowed",
                    "allow_modify": "allowed",
                    "allow_redistribute": "allowed",
                    "allow_embedding": "conditional",
                    "allow_font_sale": "denied",
                    "attribution_requirement": "required",
                },
                "restrictions": ["상표명 사용 조건 확인"],
            }
        ],
        "maker_templates": [],
    }

    decision = classify_license(snapshot, registry={"version": 1, "entries": []}, rules=rules)

    assert decision.status == "verified"
    assert decision.allow_commercial == "allowed"
    assert decision.allow_redistribute == "allowed"
    assert decision.allow_font_sale == "denied"
    assert decision.evidence_locations["allow_redistribute"] == "[data-license-body]"
    assert "상표명 사용 조건 확인" in decision.summary


def test_llm_or_unapproved_custom_text_never_verifies_or_infers_permissions() -> None:
    decision = classify_license(
        _snapshot(extractor="llm"),
        registry={"version": 1, "entries": []},
        rules={"version": 1, "standard_licenses": [], "maker_templates": []},
    )

    assert decision.status == "needs_review"
    assert decision.auto_applicable is False
    assert decision.allow_commercial is None
    assert decision.allow_redistribute is None
    assert "라이선스 재확인 필요" in decision.summary


def test_template_match_rejects_unapproved_or_discovery_registry_mapping() -> None:
    """제작사 템플릿은 검증된 공식·공공 출처에만 쓸 수 있다."""
    snapshot = _snapshot().model_copy(
        update={
            "license_id": None,
            "license_version": None,
            "template_selector": "#license",
            "template_version": "1",
        }
    )
    fingerprint = hashlib.sha256(snapshot.license_text.encode("utf-8")).hexdigest()
    rules = {
        "version": 1,
        "standard_licenses": [],
        "maker_templates": [
            {
                "domain": "fonts.example.org",
                "selector": "#license",
                "template_version": "1",
                "fingerprint": fingerprint,
                "permissions": {"allow_commercial": "allowed"},
            }
        ],
    }

    with pytest.raises(ValueError, match="approval evidence"):
        classify_license(
            snapshot,
            registry={
                "version": 1,
                "entries": [
                    {
                        "maker": "제작사",
                        "domain": "fonts.example.org",
                        "roles": ["license"],
                        "source_kind": "official",
                    }
                ],
            },
            rules=rules,
        )

    decision = classify_license(
        snapshot,
        registry={
            "version": 1,
            "entries": [
                {
                    "maker": "제작사",
                    "domain": "fonts.example.org",
                    "roles": ["license"],
                    "source_kind": "discovery",
                }
            ],
        },
        rules=rules,
    )
    assert decision.status == "needs_review"


@pytest.mark.parametrize(
    "update",
    [
        {"reviewed_by": "   ", "reviewed_at": "2026-07-18T00:00:00Z", "reviewed_permissions": {"allow_commercial": "allowed"}},
        {"reviewed_by": "reviewer", "reviewed_at": "not-a-date", "reviewed_permissions": {"allow_commercial": "allowed"}},
        {"reviewed_by": "reviewer", "reviewed_at": "2026-07-18T00:00:00Z", "reviewed_permissions": {}},
    ],
)
def test_human_review_requires_identity_time_and_a_permission(
    update: dict[str, object],
) -> None:
    """형식만 갖춘 사람 검수는 verified 판정을 만들 수 없다."""
    snapshot = _snapshot().model_copy(update={"finding_status": "approved", **update})

    decision = classify_license(
        snapshot,
        registry={"version": 1, "entries": []},
        rules={"version": 1, "standard_licenses": [], "maker_templates": []},
    )

    assert decision.status == "needs_review"
    assert decision.auto_applicable is False
