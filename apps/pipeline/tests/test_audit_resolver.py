"""폰트 ID 해상도(prod → dev UUID 변환) 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from fontagit_pipeline.audit_runner import FontTarget, _resolve_dev_font_ids
from fontagit_pipeline.audit_store import InMemoryAuditStore, SupabaseAuditStore


class FakeSupabaseAuditStore(SupabaseAuditStore):
    """테스트용 mock Supabase store. resolve_font_id만 오버라이드."""

    def __init__(self, mapping: dict[tuple[str, str, str], object]) -> None:
        """매핑: (slug, name_ko_nfc, source_tier) → UUID 또는 None (0매칭)."""
        self.mapping = mapping
        self._resolved_calls: list[tuple[str, str | None, str | None, str]] = []

    def resolve_font_id(
        self,
        slug: str,
        name_ko: str | None,
        name_en: str | None,
        source_tier: str,
    ) -> object:
        """해시 기반 매칭."""
        self._resolved_calls.append((slug, name_ko, name_en, source_tier))
        # 기본: name_ko로 조회
        import unicodedata
        key = (slug, unicodedata.normalize("NFC", name_ko) if name_ko else None, source_tier)
        if key in self.mapping:
            return self.mapping[key]
        # name_ko가 None이면 name_en으로 보조매칭
        if name_ko is None and name_en is not None:
            key_en = (slug, None, source_tier)
            if key_en in self.mapping:
                return self.mapping[key_en]
        return None


def test_resolve_dev_font_ids_happy_path() -> None:
    """happy: prod UUID → dev UUID로 치환, 다른 필드는 유지."""
    prod_id = uuid4()
    dev_id = uuid4()
    target = FontTarget(
        font_id=prod_id,
        slug="test-font",
        name_ko="테스트폰트",
        name_en="Test Font",
        source_tier="B",
        provider="noonnu",
        provider_record_id="123",
        reference_url="https://example.com",
    )

    store = FakeSupabaseAuditStore({("test-font", "테스트폰트", "B"): dev_id})
    result = _resolve_dev_font_ids([target], store)

    assert len(result) == 1
    resolved = result[0]
    assert resolved.font_id == dev_id  # 변환됨
    assert resolved.slug == "test-font"  # 유지
    assert resolved.name_ko == "테스트폰트"  # 유지
    assert resolved.source_tier == "B"  # 유지


def test_resolve_dev_font_ids_no_match_raises() -> None:
    """0매칭: resolve_font_id가 None → ValueError."""
    prod_id = uuid4()
    target = FontTarget(
        font_id=prod_id,
        slug="missing-font",
        name_ko="없는폰트",
        name_en=None,
        source_tier="B",
        provider="noonnu",
        provider_record_id="999",
        reference_url="https://example.com",
    )

    store = FakeSupabaseAuditStore({})  # 매핑 없음
    with pytest.raises(ValueError, match="missing-font"):
        _resolve_dev_font_ids([target], store)


def test_resolve_dev_font_ids_multiple_targets() -> None:
    """여러 target 처리: 모두 변환 또는 첫 오류 시 중단."""
    prod_id_1 = uuid4()
    prod_id_2 = uuid4()
    dev_id_1 = uuid4()
    dev_id_2 = uuid4()

    targets = [
        FontTarget(
            font_id=prod_id_1,
            slug="font-1",
            name_ko="폰트1",
            name_en=None,
            source_tier="A",
            provider="google",
            provider_record_id="1",
            reference_url="https://example.com",
        ),
        FontTarget(
            font_id=prod_id_2,
            slug="font-2",
            name_ko="폰트2",
            name_en=None,
            source_tier="B",
            provider="noonnu",
            provider_record_id="2",
            reference_url="https://example.com",
        ),
    ]

    store = FakeSupabaseAuditStore({
        ("font-1", "폰트1", "A"): dev_id_1,
        ("font-2", "폰트2", "B"): dev_id_2,
    })
    result = _resolve_dev_font_ids(targets, store)

    assert len(result) == 2
    assert result[0].font_id == dev_id_1
    assert result[1].font_id == dev_id_2


def test_resolve_dev_font_ids_dry_run_passthrough() -> None:
    """dry-run (InMemoryAuditStore): prod UUID 그대로 pass-through."""
    prod_id = uuid4()
    target = FontTarget(
        font_id=prod_id,
        slug="test-font",
        name_ko="테스트폰트",
        name_en=None,
        source_tier="B",
        provider="noonnu",
        provider_record_id="123",
        reference_url="https://example.com",
    )

    store = InMemoryAuditStore()
    result = _resolve_dev_font_ids([target], store)

    assert len(result) == 1
    assert result[0].font_id == prod_id  # 변환 없음


def test_resolve_dev_font_ids_name_ko_nfc_normalization() -> None:
    """name_ko NFC 정규화: 합성 문자와 분해 문자가 같은 것으로 매칭."""
    import unicodedata

    prod_id = uuid4()
    dev_id = uuid4()

    # 분해형(NFD)으로 전달하면, store 매핑은 합성형(NFC)으로 저장
    nfd_name = unicodedata.normalize("NFD", "테스트")  # 분해형
    nfc_name = unicodedata.normalize("NFC", "테스트")  # 합성형

    target = FontTarget(
        font_id=prod_id,
        slug="test",
        name_ko=nfd_name,  # 분해형
        name_en=None,
        source_tier="B",
        provider="noonnu",
        provider_record_id="1",
        reference_url="https://example.com",
    )

    # store 매핑은 합성형으로
    store = FakeSupabaseAuditStore({("test", nfc_name, "B"): dev_id})
    result = _resolve_dev_font_ids([target], store)

    assert len(result) == 1
    assert result[0].font_id == dev_id  # NFC로 정규화되어 매칭됨


def test_resolve_dev_font_ids_name_en_fallback() -> None:
    """name_ko가 None이면 name_en으로 보조매칭."""
    prod_id = uuid4()
    dev_id = uuid4()

    target = FontTarget(
        font_id=prod_id,
        slug="test-font",
        name_ko=None,  # None
        name_en="Test Font",
        source_tier="B",
        provider="noonnu",
        provider_record_id="123",
        reference_url="https://example.com",
    )

    # (slug, None, source_tier) 매핑
    store = FakeSupabaseAuditStore({("test-font", None, "B"): dev_id})
    result = _resolve_dev_font_ids([target], store)

    assert len(result) == 1
    assert result[0].font_id == dev_id


def test_resolve_dev_font_ids_requires_name_ko_in_select_columns() -> None:
    """회귀: resolve_font_id에서 name_ko를 select해야 name_ko 비교 작동.

    버그 원인: select("id")만 하면 name_ko가 없어 row.get("name_ko")가 None
    → name_ko 비교 불가 → candidates 0개 → 항상 None 반환.
    수정: select("id, name_ko, name_en")으로 컬럼 포함.
    """
    import unicodedata

    prod_id = uuid4()
    dev_id = uuid4()

    target = FontTarget(
        font_id=prod_id,
        slug="흰꼬리수리",
        name_ko="흰꼬리수리",
        name_en=None,
        source_tier="B",
        provider="noonnu",
        provider_record_id="1",
        reference_url="https://example.com",
    )

    # 한글명을 NFC 정규화하여 매핑 저장
    nfc_name_ko = unicodedata.normalize("NFC", "흰꼬리수리")
    store = FakeSupabaseAuditStore({("흰꼬리수리", nfc_name_ko, "B"): dev_id})

    # select이 name_ko를 포함할 때만 매칭 성공
    result = _resolve_dev_font_ids([target], store)

    assert len(result) == 1
    assert result[0].font_id == dev_id
