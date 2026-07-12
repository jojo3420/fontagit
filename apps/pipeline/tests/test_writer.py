import json
from pathlib import Path

from fontagit_pipeline.models import OutputDocument
from fontagit_pipeline.writer import write_output


def test_write_output_creates_valid_json(tmp_path: Path):
    doc = OutputDocument(generated_at="2026-07-12T10:00:00Z", record_count=0, fonts=[])
    out = tmp_path / "sub" / "tier-a.json"
    write_output(doc, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == 1
    assert loaded["source"] == "google-fonts-webfonts-api"
    assert loaded["fonts"] == []


def test_write_output_leaves_no_temp_file(tmp_path: Path):
    doc = OutputDocument(generated_at="2026-07-12T10:00:00Z", record_count=0, fonts=[])
    out = tmp_path / "tier-a.json"
    write_output(doc, out)
    assert list(tmp_path.iterdir()) == [out]
