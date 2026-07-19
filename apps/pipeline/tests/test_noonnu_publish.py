"""예전 Noonnu prod 발행 경계의 핵심 회귀 테스트."""

from unittest.mock import MagicMock

import pytest

from fontagit_pipeline.noonnu_publish import publish_to_prod


def test_dry_run_counts_all_pages_without_writing() -> None:
    """dry-run은 전량 대상 수만 세고 쓰기를 0건으로 유지한다."""
    first = MagicMock(data=[{"slug": f"font-{index}"} for index in range(1000)])
    second = MagicMock(data=[{"slug": f"font-{index}"} for index in range(1000, 1080)])
    first_query = MagicMock()
    first_query.execute.return_value = first
    second_query = MagicMock()
    second_query.execute.return_value = second
    schema = MagicMock()
    order = (
        schema.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value
    )
    order.range.side_effect = [first_query, second_query]

    assert publish_to_prod(schema, "", "", dry_run=True) == (1080, 0)
    assert [call.args for call in order.range.call_args_list] == [(0, 999), (1000, 1999)]
    schema.table.return_value.upsert.assert_not_called()


def test_non_dry_run_is_always_rejected_before_db_access() -> None:
    """예전 confirm 경로로는 prod 행별 upsert를 시작할 수 없다."""
    schema = MagicMock()

    with pytest.raises(RuntimeError, match="font-audit-manifest apply"):
        publish_to_prod(
            schema,
            "https://prod.example.com",
            "prod-key",
            dry_run=False,
        )

    schema.table.assert_not_called()
