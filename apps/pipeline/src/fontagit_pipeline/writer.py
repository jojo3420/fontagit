"""출력 JSON 원자적 저장."""

import os
import tempfile
from pathlib import Path

from fontagit_pipeline.models import OutputDocument


def write_output(doc: OutputDocument, path: Path) -> None:
    """OutputDocument를 JSON 파일로 원자적으로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # 같은 디렉토리에 임시 파일 생성
    temp_fd, temp_path_str = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    temp_path = Path(temp_path_str)

    try:
        # 임시 파일에 JSON 쓰기
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            f.write(doc.model_dump_json(indent=2))
        # 원자적으로 최종 위치로 이동
        os.replace(temp_path, path)
    except Exception:
        # 실패 시 임시 파일 제거 (원본 예외 전파 우선)
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass  # unlink 실패는 무시하고 원본 예외 전파
        raise
