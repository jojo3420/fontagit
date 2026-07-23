"""build_document 함수 통합 테스트."""

import argparse
import hashlib
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from fontagit_pipeline.__main__ import build_document, main, main_audit_manifest_apply
from fontagit_pipeline.models import GoogleFontRaw, OutputDocument
from fontagit_pipeline.licenses import LicenseFetchError


def test_prod_manifest_apply_requires_every_extra_gate_without_second_file_read() -> None:
    """prod는 enable-승인 ID-승인 SHA 중 하나라도 없으면 RPC 전에 멈춘다."""
    manifest_bytes = b"{}"
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_path = MagicMock(read_bytes=MagicMock(return_value=manifest_bytes))
    sha_path = MagicMock(read_text=MagicMock(return_value=digest + "\n"))
    args = argparse.Namespace(
        manifest=manifest_path,
        sha256=sha_path,
        target="prod",
        confirm_hash=digest,
        approved_hash=digest,
        approval_id="human-approval-1",
    )
    fake_manifest = MagicMock(schema_version=1)

    with patch("fontagit_pipeline.audit_manifest.verify_manifest_bytes", return_value=fake_manifest), patch(
        "fontagit_pipeline.config.load_audit_settings", return_value=MagicMock()
    ), patch("builtins.input") as prompt, patch.dict("os.environ", {}, clear=True):
        assert main_audit_manifest_apply(args) == 3
        prompt.assert_not_called()

    with patch("fontagit_pipeline.audit_manifest.verify_manifest_bytes", return_value=fake_manifest), patch(
        "fontagit_pipeline.config.load_audit_settings", return_value=MagicMock()
    ), patch("builtins.input") as prompt, patch.dict(
        "os.environ", {"FONTAGIT_PROD_MANIFEST_ENABLED": "true"}, clear=True
    ):
        args.approved_hash = "0" * 64
        assert main_audit_manifest_apply(args) == 3
        prompt.assert_not_called()

    assert manifest_path.read_bytes.call_count == 2


def test_build_document_creates_output_document():
    """build_document는 fonts와 generated_at로부터 OutputDocument를 생성한다."""
    # Arrange
    fonts = [
        GoogleFontRaw(
            family="Noto Sans KR",
            variants=["regular", "700"],
            subsets=["korean", "latin"],
            version="v24.1.0",
            lastModified="2024-09-01",
            files={"regular": "http://example.com/font1.ttf", "700": "http://example.com/font1b.ttf"},
            category="sans-serif",
        ),
        GoogleFontRaw(
            family="Roboto",
            variants=["regular", "italic"],
            subsets=["latin"],
            version="v30.0.0",
            lastModified="2024-09-01",
            files={"regular": "http://example.com/font2.ttf", "italic": "http://example.com/font2i.ttf"},
            category="sans-serif",
        ),
    ]
    generated_at = datetime.now(timezone.utc).isoformat()

    # Act
    doc = build_document(fonts, {}, generated_at)

    # Assert
    assert isinstance(doc, OutputDocument)
    assert doc.generated_at == generated_at
    assert doc.source == "google-fonts-webfonts-api"
    assert doc.record_count == 2
    assert len(doc.fonts) == 2


def test_build_document_respects_latin_limit():
    """build_document는 latin_limit 파라미터를 존중한다."""
    # Arrange
    fonts = [
        GoogleFontRaw(
            family=f"Font{i}",
            variants=["regular"],
            subsets=["latin"],
            version="v1.0.0",
            lastModified="2024-09-01",
            files={"regular": f"http://example.com/font{i}.ttf"},
            category="sans-serif",
        )
        for i in range(150)
    ]
    generated_at = datetime.now(timezone.utc).isoformat()

    # Act
    doc = build_document(fonts, {}, generated_at, latin_limit=50)

    # Assert (latin_limit이 50이므로 정확히 50개여야 함)
    assert doc.record_count == 50
    assert len(doc.fonts) == 50


def test_build_document_passes_license_map():
    """build_document는 license_map을 전달받아 처리한다."""
    from fontagit_pipeline.models import GoogleFontRaw
    from fontagit_pipeline.__main__ import build_document

    raw = GoogleFontRaw(
        family="Jua", variants=["regular"], subsets=["korean"],
        version="v1", lastModified="2024-01-01", files={}, category="display",
    )
    doc = build_document([raw], {"jua": "OFL"}, "2026-07-14T00:00:00Z")
    assert doc.record_count == 1
    assert doc.fonts[0].status == "published"
    assert doc.fonts[0].category_ko == "장식"


def test_main_returns_3_on_empty_record_count(tmp_path):
    """record_count가 0일 때 main은 3을 반환하고 파일을 쓰지 않는다."""
    fonts_empty = []
    generated_at = datetime.now(timezone.utc).isoformat()
    doc = build_document(fonts_empty, {}, generated_at)

    # record_count가 0이면 main이 exit 3를 반환해야 함
    assert doc.record_count == 0

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.build_document") as mock_build:
                with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                    mock_settings.return_value = MagicMock(
                        google_fonts_api_key="test_key"
                    )
                    mock_fetch.return_value = []
                    mock_build.return_value = doc

                    result = main()

                    # write_output이 호출되지 않아야 함
                    mock_write.assert_not_called()
                    # exit code는 3이어야 함
                    assert result == 3


def test_main_returns_3_on_webfonts_error(tmp_path):
    """WebfontsError 발생 시 main은 3을 반환한다."""
    from fontagit_pipeline.client import WebfontsError

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            mock_settings.return_value = MagicMock(
                google_fonts_api_key="test_key"
            )
            mock_fetch.side_effect = WebfontsError("테스트 에러")

            result = main()

            # exit code는 3이어야 함
            assert result == 3


def test_main_returns_3_on_write_error(tmp_path):
    """파일 저장 실패 시 main은 3을 반환한다."""
    fonts = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v30",
            lastModified="2024-09-01",
            files={"regular": "https://x/r.ttf"},
            category="sans-serif",
        )
    ]

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                mock_settings.return_value = MagicMock(
                    google_fonts_api_key="test_key"
                )
                mock_fetch.return_value = fonts
                mock_write.side_effect = OSError("디스크 오류")

                result = main()

                # exit code는 3이어야 함
                assert result == 3


def test_main_returns_3_on_license_fetch_error(tmp_path):
    """라이선스 조회 실패 시 main은 산출물 미생성 후 즉시 3을 반환한다."""
    fonts = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v30",
            lastModified="2024-09-01",
            files={"regular": "https://x/r.ttf"},
            category="sans-serif",
        )
    ]

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.fetch_license_map") as mock_license:
                with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                    mock_settings.return_value = MagicMock(
                        google_fonts_api_key="test_key",
                        github_token="test_token",
                        supabase_url="https://test.supabase.co",
                        supabase_secret_key="test_secret_key",
                    )
                    mock_fetch.return_value = fonts
                    mock_license.side_effect = LicenseFetchError("네트워크 오류")

                    result = main()

                    # write_output은 호출되지 않음 (산출물 미생성)
                    mock_write.assert_not_called()
                    # exit code는 3이어야 함
                    assert result == 3


def test_main_returns_3_on_supabase_config_mismatch(tmp_path):
    """Supabase URL과 SECRET_KEY 중 하나만 있으면 main은 3을 반환한다."""
    fonts = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v30",
            lastModified="2024-09-01",
            files={"regular": "https://x/r.ttf"},
            category="sans-serif",
        )
    ]

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.fetch_license_map") as mock_license:
                with patch("fontagit_pipeline.__main__.load_korean_names") as mock_korean:
                    with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                        mock_settings.return_value = MagicMock(
                            google_fonts_api_key="test_key",
                            github_token="test_token",
                            supabase_url="https://test.supabase.co",
                            supabase_secret_key=None,
                        )
                        mock_fetch.return_value = fonts
                        mock_license.return_value = {}
                        mock_korean.return_value = {}

                        result = main()

                        mock_write.assert_called_once()
                        assert result == 3
"""Task 4: font-audit-manifest build CLI 테스트."""

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fontagit_pipeline.__main__ import main_audit_manifest_build
from fontagit_pipeline.audit_manifest import ManifestBundle, ManifestPaths


def _mock_run() -> dict:
    """build_manifest가 기대하는 run 구조."""
    return {
        "id": str(uuid4()),
        "baseline_sha256": "a" * 64,
        "finished_at": "2026-07-23T00:00:00Z",
        "started_at": "2026-07-22T00:00:00Z",
        "target_count": 10,
    }


def _mock_finding(run_id: str) -> dict:
    """build_manifest가 기대하는 finding 구조."""
    return {
        "id": str(uuid4()),
        "run_id": run_id,
        "font_id": str(uuid4()),
        "field_name": "tags",
        "before_value": ["old-tag"],
        "proposed_value": ["new-tag"],
        "evidence_id": str(uuid4()),
        "confidence": 0.95,
        "reviewed_by": "tester@example.com",
        "reviewed_at": "2026-07-23T00:00:00Z",
        "source_key": {"provider": "noonnu", "provider_record_id": "12345"},
        "status": "approved",
    }


def _mock_font_row(font_id: str) -> dict:
    """build_manifest가 기대하는 current font row 구조."""
    return {
        "id": font_id,
        "family": "Test Font",
        "tags": ["new-tag"],
        "weights": [400, 700],
        "evidence_snapshots": [
            {
                "id": str(uuid4()),
                "font_id": font_id,
                "provider": "noonnu",
                "provider_record_id": "12345",
                "captured_at": "2026-07-23T00:00:00Z",
                "tags": ["new-tag"],
                "weights": [400, 700],
            }
        ],
    }


def test_manifest_build_with_approved_findings() -> None:
    """정상: approved findings가 있으면 manifest 번들을 생성한다."""
    run = _mock_run()
    finding = _mock_finding(run["id"])
    font_row = _mock_font_row(finding["font_id"])

    out_dir = Path("/tmp/test_manifest_build")
    args = argparse.Namespace(
        out=out_dir,
        run_id=run["id"],
    )

    mock_bundle = MagicMock(spec=ManifestBundle)
    mock_bundle.forward_sha256 = "f" * 64
    mock_bundle.reverse_sha256 = "r" * 64

    mock_paths = MagicMock(spec=ManifestPaths)
    mock_paths.forward = out_dir / "forward.json"
    mock_paths.forward_sha256 = out_dir / "forward.sha256"
    mock_paths.reverse = out_dir / "reverse.json"
    mock_paths.reverse_sha256 = out_dir / "reverse.sha256"

    # Store와 헬퍼 함수들만 mock, load_audit_settings는 실제 사용
    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor, patch(
        "fontagit_pipeline.audit_manifest.build_manifest", return_value=mock_bundle
    ) as mock_build, patch(
        "fontagit_pipeline.audit_manifest.write_manifest_bundle", return_value=mock_paths
    ) as mock_write:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_approved_findings.return_value = [finding]
        mock_store.get_current_fonts_with_snapshots.return_value = [font_row]
        mock_store_ctor.return_value = mock_store

        result = main_audit_manifest_build(args)

        assert result == 0, f"Expected exit code 0 but got {result}"
        mock_store.get_run.assert_called_once()
        mock_store.get_approved_findings.assert_called_once()
        mock_store.get_current_fonts_with_snapshots.assert_called_once()
        mock_build.assert_called_once_with(run, [finding], [font_row])
        mock_write.assert_called_once_with(mock_bundle, out_dir)


def test_manifest_build_no_approved_findings_exits_nonzero() -> None:
    """비정상: approved findings가 0건이면 비정상 종료한다."""
    run = _mock_run()
    args = argparse.Namespace(
        out=Path("/tmp/test_manifest_build"),
        run_id=run["id"],
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_approved_findings.return_value = []  # 빈 목록
        mock_store_ctor.return_value = mock_store

        result = main_audit_manifest_build(args)

        assert result == 1, f"Expected exit code 1 but got {result}"


def test_manifest_build_run_not_found_exits_nonzero() -> None:
    """비정상: run을 찾을 수 없으면 비정상 종료한다."""
    run_id = str(uuid4())
    args = argparse.Namespace(
        out=Path("/tmp/test_manifest_build"),
        run_id=run_id,
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.side_effect = ValueError(f"Run {run_id} not found")
        mock_store_ctor.return_value = mock_store

        result = main_audit_manifest_build(args)

        assert result == 1, f"Expected exit code 1 but got {result}"
