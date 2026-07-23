"""bootstrap-apply CLI 기본 회귀 테스트."""

import argparse
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fontagit_pipeline.__main__ import main_audit_bootstrap_apply


def _mock_manifest_file(tmp_path: Path, content: str) -> tuple[Path, str]:
    """테스트용 manifest 파일과 SHA256 생성."""
    file_path = tmp_path / "bootstrap-manifest.json"
    manifest_bytes = content.encode("utf-8")
    file_path.write_bytes(manifest_bytes)
    file_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    return file_path, file_sha256


def test_bootstrap_apply_confirm_hash_mismatch(tmp_path: Path) -> None:
    """confirm-hash 불일치 → exit 3."""
    file_path, file_sha256 = _mock_manifest_file(tmp_path, '{"schema_version":1}')
    wrong_hash = "a" * 64

    args = argparse.Namespace(
        manifest=file_path,
        target="dev",
        confirm_hash=wrong_hash,
    )

    result = main_audit_bootstrap_apply(args)
    assert result == 3


def test_bootstrap_apply_success(tmp_path: Path) -> None:
    """정상: confirm-hash 일치 → RPC 호출 → exit 0."""
    file_path, file_sha256 = _mock_manifest_file(
        tmp_path, '{"schema_version":1,"entries":[]}'
    )

    args = argparse.Namespace(
        manifest=file_path,
        target="dev",
        confirm_hash=file_sha256,
    )

    with patch("fontagit_pipeline.config.load_audit_settings") as mock_settings, patch(
        "fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials"
    ) as mock_store_ctor:
        mock_settings_obj = MagicMock()
        mock_settings_obj.dev_write_credentials.return_value = ("http://dev", "secret")
        mock_settings.return_value = mock_settings_obj

        mock_store = MagicMock()
        mock_schema = MagicMock()
        mock_rpc = MagicMock()
        mock_result = MagicMock()
        mock_result.data = 1240  # 등록 건수

        mock_rpc.execute.return_value = mock_result
        mock_schema.rpc.return_value = mock_rpc
        mock_store._schema = mock_schema
        mock_store_ctor.return_value = mock_store

        result = main_audit_bootstrap_apply(args)

        # RPC 호출 검증
        mock_schema.rpc.assert_called_once()
        call_args = mock_schema.rpc.call_args
        assert call_args[0][0] == "apply_font_source_bootstrap"
        payload = call_args[0][1]
        assert "p_manifest_text" in payload
        assert "p_expected_sha256" in payload
        assert payload["p_expected_sha256"] == file_sha256
        assert payload["p_schema_version"] == 1

        assert result == 0


def test_export_baseline_dev_service(tmp_path: Path) -> None:
    """export-baseline dev-service: dev credentials로 분기."""
    from fontagit_pipeline.__main__ import main_audit_export_baseline

    args = argparse.Namespace(
        source="dev-service",
        out=tmp_path / "baseline.json",
    )

    with patch("fontagit_pipeline.config.load_audit_settings") as mock_settings, patch(
        "fontagit_pipeline.audit_bootstrap.fetch_dev_service_rows"
    ) as mock_fetch_dev, patch(
        "fontagit_pipeline.audit_bootstrap.calculate_baseline_content_sha256"
    ) as mock_calc, patch(
        "fontagit_pipeline.audit_bootstrap.write_prod_baseline"
    ) as mock_write:
        mock_settings_obj = MagicMock()
        mock_settings_obj.dev_write_credentials.return_value = ("http://dev", "secret")
        mock_settings.return_value = mock_settings_obj

        mock_fetch_dev.return_value = []
        mock_calc.return_value = "a" * 64
        mock_write.return_value = "b" * 64

        result = main_audit_export_baseline(args)

        # dev credentials 호출 확인
        mock_settings_obj.dev_write_credentials.assert_called_once()
        mock_fetch_dev.assert_called_once_with("http://dev", "secret")

        assert result == 0
