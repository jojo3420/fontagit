"""dev에서 검증-발행된 Tier B 폰트를 prod DB로 동기화하는 함수 테스트"""

from typing import Any
from unittest.mock import MagicMock

from fontagit_pipeline.noonnu_publish import publish_to_prod


class TestPublishToProdPagination:
    """publish_to_prod 함수의 페이지네이션 테스트"""

    def test_pagination_full_retrieval_1080_fonts(self):
        """PostgREST 페이지네이션: 1000 + 80 = 1080개 폰트 전량 조회"""
        # 배치 1: 1000개
        batch1 = [
            {
                "slug": f"font-{i:04d}",
                "name_en": f"Font {i}",
                "name_ko": f"폰트 {i}",
                "source_tier": "B",
                "status": "published",
                **{k: None for k in [
                    "category_ko", "category_google", "subsets", "variants", "weights",
                    "is_commercial_free", "license_type", "license_verified", "official_url",
                    "allow_embedding", "allow_redistribute", "allow_modify", "license_note",
                    "verified_at", "license_source_url", "auto_approved",
                ]},
            }
            for i in range(1000)
        ]

        # 배치 2: 80개
        batch2 = [
            {
                "slug": f"font-{1000+i:04d}",
                "name_en": f"Font {1000+i}",
                "name_ko": f"폰트 {1000+i}",
                "source_tier": "B",
                "status": "published",
                **{k: None for k in [
                    "category_ko", "category_google", "subsets", "variants", "weights",
                    "is_commercial_free", "license_type", "license_verified", "official_url",
                    "allow_embedding", "allow_redistribute", "allow_modify", "license_note",
                    "verified_at", "license_source_url", "auto_approved",
                ]},
            }
            for i in range(80)
        ]

        # Mock 응답 객체
        mock_response1 = MagicMock()
        mock_response1.data = batch1

        mock_response2 = MagicMock()
        mock_response2.data = batch2

        # range() 호출별로 다른 응답 반환
        range_mock1 = MagicMock()
        range_mock1.execute.return_value = mock_response1

        range_mock2 = MagicMock()
        range_mock2.execute.return_value = mock_response2

        # Dev schema mock 체인 구성
        dev_schema = MagicMock()
        dev_schema.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.side_effect = [
            range_mock1,
            range_mock2,
        ]

        # Dry run: prod client 불필요
        total, written = publish_to_prod(
            dev_schema,
            "https://prod.example.com",
            "prod-key",
            dry_run=True,
        )

        # 검증: 1080개 전량 조회됨, dry_run이므로 written=0
        assert total == 1080, f"Expected 1080 fonts, got {total}"
        assert written == 0, f"Expected 0 written in dry_run, got {written}"

    def test_pagination_single_batch(self):
        """단일 배치 (1000 미만): 30개만 조회"""
        # 배치: 30개
        batch = [
            {
                "slug": f"font-{i:04d}",
                "name_en": f"Font {i}",
                "name_ko": f"폰트 {i}",
                "source_tier": "B",
                "status": "published",
                **{k: None for k in [
                    "category_ko", "category_google", "subsets", "variants", "weights",
                    "is_commercial_free", "license_type", "license_verified", "official_url",
                    "allow_embedding", "allow_redistribute", "allow_modify", "license_note",
                    "verified_at", "license_source_url", "auto_approved",
                ]},
            }
            for i in range(30)
        ]

        # Mock 응답 객체
        mock_response = MagicMock()
        mock_response.data = batch

        range_mock = MagicMock()
        range_mock.execute.return_value = mock_response

        # Dev schema mock 체인 구성
        dev_schema = MagicMock()
        dev_schema.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value = range_mock

        # Dry run
        total, written = publish_to_prod(
            dev_schema,
            "https://prod.example.com",
            "prod-key",
            dry_run=True,
        )

        # 검증: 30개 조회됨, dry_run이므로 written=0
        assert total == 30, f"Expected 30 fonts, got {total}"
        assert written == 0, f"Expected 0 written in dry_run, got {written}"

    def test_pagination_calls_range_with_correct_offsets(self):
        """range() 호출 시 올바른 offset 인자 전달 확인"""
        batch1 = [{"slug": f"font-{i}", "source_tier": "B", "status": "published"} for i in range(1000)]
        batch2 = [{"slug": f"font-{1000+i}", "source_tier": "B", "status": "published"} for i in range(50)]

        mock_response1 = MagicMock()
        mock_response1.data = batch1

        mock_response2 = MagicMock()
        mock_response2.data = batch2

        range_mock1 = MagicMock()
        range_mock1.execute.return_value = mock_response1

        range_mock2 = MagicMock()
        range_mock2.execute.return_value = mock_response2

        dev_schema = MagicMock()
        order_mock = MagicMock()
        dev_schema.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value = order_mock
        order_mock.range.side_effect = [range_mock1, range_mock2]

        publish_to_prod(
            dev_schema,
            "https://prod.example.com",
            "prod-key",
            dry_run=True,
        )

        # range() 호출 확인
        assert order_mock.range.call_count == 2

        # 첫 호출: range(0, 999)
        first_call = order_mock.range.call_args_list[0]
        assert first_call[0] == (0, 999), f"Expected first call with (0, 999), got {first_call[0]}"

        # 둘째 호출: range(1000, 1999)
        second_call = order_mock.range.call_args_list[1]
        assert second_call[0] == (1000, 1999), f"Expected second call with (1000, 1999), got {second_call[0]}"
