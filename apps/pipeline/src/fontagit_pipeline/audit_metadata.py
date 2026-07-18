"""신뢰하지 않는 폰트 파일에서 제한된 메타데이터만 추출한다."""

from __future__ import annotations

import hashlib
import math
import multiprocessing
import os
import stat
import struct
import sys
import tempfile
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from uuid import UUID

from fontagit_pipeline.audit_store import FindingDraft

MAX_FONT_FILE_BYTES = 32 * 1024 * 1024
MAX_SFNT_BYTES = 128 * 1024 * 1024
DEFAULT_PARSE_TIMEOUT_SECONDS = 8.0
PARSER_VERSION = "fonttools-v1"

KS_X_1001_HANGUL = frozenset(
    ord(bytes((lead, trail)).decode("euc_kr"))
    for lead in range(0xB0, 0xC9)
    for trail in range(0xA1, 0xFF)
)
assert len(KS_X_1001_HANGUL) == 2350
BASIC_LATIN = frozenset(range(0x41, 0x5B)) | frozenset(range(0x61, 0x7B))

_ALLOWED_SIGNATURES = {
    b"\x00\x01\x00\x00": "ttf",
    b"true": "ttf",
    b"OTTO": "otf",
    b"ttcf": "ttc",
    b"wOFF": "woff",
    b"wOF2": "woff2",
}


@dataclass(frozen=True)
class ScriptCoverage:
    """cmap에서 직접 확인한 문자 범위 판정."""

    subsets: list[str]
    status: Literal["verified", "needs_review"]
    hangul_glyph_count: int
    common_hangul_count: int
    codepoint_count: int


@dataclass(frozen=True)
class FontFileMetadata:
    """원본 바이너리를 제외한 폰트 파일의 구조화된 증거."""

    families: tuple[str, ...] = ()
    weight: int | None = None
    italic: bool | None = None
    codepoints: frozenset[int] = frozenset()
    file_sha256: str | None = None
    parser_version: str = PARSER_VERSION
    format: str | None = None
    units_per_em: int | None = None
    italic_angle: float | None = None
    inspection_status: Literal["parsed", "needs_review"] = "parsed"
    error_kind: str | None = None
    face_conflict: bool = False
    partial_file: bool = False

    def extracted(self) -> dict[str, object]:
        """DB snapshot에 저장 가능한 구조화 값만 반환한다."""
        payload = asdict(self)
        payload.pop("codepoints")
        payload["codepoint_count"] = len(self.codepoints)
        return payload


class _MetadataTarget(Protocol):
    @property
    def font_id(self) -> UUID: ...

    @property
    def name_ko(self) -> str | None: ...

    @property
    def name_en(self) -> str | None: ...

    @property
    def weights(self) -> tuple[int, ...]: ...

    @property
    def variants(self) -> tuple[str, ...]: ...

    @property
    def subsets(self) -> tuple[str, ...]: ...

    @property
    def script_status(self) -> str: ...

    @property
    def category_ko(self) -> str | None: ...

    @property
    def tags(self) -> tuple[str, ...]: ...


class _MetadataSnapshot(Protocol):
    @property
    def source_kind(self) -> str: ...

    @property
    def extracted(self) -> Mapping[str, object]: ...


def classify_scripts(codepoints: Iterable[int]) -> ScriptCoverage:
    """KS X 1001 한글 2,350자와 기본 라틴 52자를 exact 판정한다."""
    values = frozenset(codepoints)
    common_count = len(values & KS_X_1001_HANGUL)
    hangul_count = sum(0xAC00 <= value <= 0xD7A3 for value in values)
    subsets: list[str] = []
    if common_count == len(KS_X_1001_HANGUL):
        subsets.append("korean")
    if BASIC_LATIN <= values:
        subsets.append("latin")
    partial_hangul = 0 < common_count < len(KS_X_1001_HANGUL) or (
        hangul_count > 0 and common_count < len(KS_X_1001_HANGUL)
    )
    status: Literal["verified", "needs_review"] = (
        "verified" if subsets and not partial_hangul else "needs_review"
    )
    return ScriptCoverage(
        subsets=subsets,
        status=status,
        hangul_glyph_count=hangul_count,
        common_hangul_count=common_count,
        codepoint_count=len(values),
    )


def classify_face_scripts(cmaps: Sequence[Iterable[int]]) -> ScriptCoverage:
    """같은 family·weight·style로 확인된 분할 cmap을 먼저 합친다."""
    union: set[int] = set()
    for cmap in cmaps:
        union.update(cmap)
    return classify_scripts(union)


def inspect_font_metadata(
    path: Path, *, timeout_seconds: float = DEFAULT_PARSE_TIMEOUT_SECONDS
) -> FontFileMetadata:
    """격리 프로세스에서 폰트를 읽고 timeout 시 강제로 종료한다."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("font parse timeout is outside the permitted range")
    if os.name == "nt":
        return _review_metadata("unsupported_platform")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return _review_metadata("unreadable")
    private_path: Path | None = None
    try:
        with os.fdopen(descriptor, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size < 1:
                return _review_metadata("unsafe_file")
            if before.st_size > MAX_FONT_FILE_BYTES:
                return _review_metadata("oversize")
            header = source.read(20)
            signature = header[:4]
            font_format = _ALLOWED_SIGNATURES.get(signature)
            if font_format is None:
                return _review_metadata("unsupported_format")
            if font_format in {"woff", "woff2"}:
                if len(header) < 20 or struct.unpack(">I", header[16:20])[0] > MAX_SFNT_BYTES:
                    return _review_metadata("declared_size_oversize")
            source.seek(0)
            digest_builder = hashlib.sha256()
            copied = 0
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix="fontagit-private-font-", suffix=f".{font_format}", delete=False
            ) as private:
                private_path = Path(private.name)
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > MAX_FONT_FILE_BYTES:
                        private_path.unlink(missing_ok=True)
                        private_path = None
                        return _review_metadata("oversize")
                    digest_builder.update(chunk)
                    private.write(chunk)
                private.flush()
                os.fsync(private.fileno())
            after = os.fstat(source.fileno())
            if (
                before.st_dev != after.st_dev
                or before.st_ino != after.st_ino
                or before.st_size != after.st_size
                or copied != after.st_size
            ):
                private_path.unlink(missing_ok=True)
                private_path = None
                return _review_metadata("source_changed")
            digest = digest_builder.hexdigest()
    except OSError:
        if private_path is not None:
            private_path.unlink(missing_ok=True)
        return _review_metadata("unreadable")

    assert private_path is not None
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_inspect_worker,
        args=(child, os.fspath(private_path), font_format, timeout_seconds),
        daemon=True,
    )
    try:
        process.start()
        child.close()
        if not parent.poll(timeout_seconds):
            return _review_metadata("parse_timeout", digest=digest, font_format=font_format)
        result = parent.recv()
    except (EOFError, OSError, RuntimeError):
        return _review_metadata("parse_failed", digest=digest, font_format=font_format)
    finally:
        child.close()
        parent.close()
        _stop_worker(process)
        private_path.unlink(missing_ok=True)
    if not isinstance(result, dict) or result.get("status") != "parsed":
        error_kind = (
            result.get("error_kind")
            if isinstance(result, dict) and result.get("error_kind") in {"resource_limit", "parse_failed"}
            else "parse_failed"
        )
        return _review_metadata(str(error_kind), digest=digest, font_format=font_format)
    try:
        return FontFileMetadata(
            families=tuple(cast(list[str], result["families"])),
            weight=cast(int | None, result["weight"]),
            italic=cast(bool | None, result["italic"]),
            codepoints=frozenset(cast(list[int], result["codepoints"])),
            file_sha256=digest,
            format=font_format,
            units_per_em=cast(int | None, result["units_per_em"]),
            italic_angle=cast(float | None, result["italic_angle"]),
            face_conflict=cast(bool, result["face_conflict"]),
            inspection_status=(
                "needs_review" if cast(bool, result["face_conflict"]) else "parsed"
            ),
            error_kind=("face_conflict" if cast(bool, result["face_conflict"]) else None),
        )
    except (KeyError, TypeError, ValueError):
        return _review_metadata("parse_failed", digest=digest, font_format=font_format)


def compare_metadata(
    target: _MetadataTarget,
    official_snapshot: _MetadataSnapshot,
    file_metadata: FontFileMetadata,
) -> list[FindingDraft]:
    """공식·공공기관 파일의 exact identity가 맞을 때만 자동 후보를 만든다."""
    coverage = classify_scripts(file_metadata.codepoints)
    target_names = {
        normalized
        for value in (target.name_en, target.name_ko)
        if value and (normalized := _normalize_family(value))
    }
    file_names = {_normalize_family(value) for value in file_metadata.families}
    family_exact = len(file_names) == 1 and bool(target_names & file_names)
    cmap_parsed = (
        file_metadata.inspection_status == "parsed"
        and bool(file_metadata.codepoints)
        and not file_metadata.face_conflict
        and not file_metadata.partial_file
    )
    trusted_metadata = official_snapshot.source_kind in {"official", "public"}
    script_auto = family_exact and cmap_parsed and coverage.status == "verified"
    metadata_auto = family_exact and cmap_parsed and trusted_metadata
    identity_reason = (
        "verified font family and cmap"
        if family_exact and cmap_parsed
        else "font family conflict or incomplete cmap"
    )
    findings = [
        FindingDraft(
            font_id=target.font_id,
            field_name="subsets",
            before_value=list(target.subsets),
            proposed_value=coverage.subsets,
            evidence_id=None,
            confidence=(official_snapshot.source_kind if trusted_metadata else "reference"),
            review_reason=identity_reason,
            auto_applicable=script_auto,
        ),
        FindingDraft(
            font_id=target.font_id,
            field_name="script_status",
            before_value=target.script_status,
            proposed_value=("verified" if script_auto else "needs_review"),
            evidence_id=None,
            confidence=(official_snapshot.source_kind if trusted_metadata else "reference"),
            review_reason=identity_reason,
            auto_applicable=script_auto,
        ),
    ]
    if file_metadata.weight is not None and file_metadata.weight not in target.weights:
        findings.append(
            FindingDraft(
                font_id=target.font_id,
                field_name="weights",
                before_value=list(target.weights),
                proposed_value=[file_metadata.weight],
                evidence_id=None,
                confidence=(official_snapshot.source_kind if trusted_metadata else "reference"),
                review_reason=identity_reason,
                auto_applicable=metadata_auto,
            )
        )
    if file_metadata.italic and "italic" not in target.variants:
        findings.append(
            FindingDraft(
                font_id=target.font_id,
                field_name="variants",
                before_value=list(target.variants),
                proposed_value=["italic"],
                evidence_id=None,
                confidence=(official_snapshot.source_kind if trusted_metadata else "reference"),
                review_reason=identity_reason,
                auto_applicable=metadata_auto,
            )
        )
    for field_name in ("category", "tags"):
        value = official_snapshot.extracted.get(field_name)
        if value is not None:
            public_field = "category_ko" if field_name == "category" else field_name
            findings.append(
                FindingDraft(
                    font_id=target.font_id,
                    field_name=public_field,
                    before_value=(
                        target.category_ko if public_field == "category_ko" else list(target.tags)
                    ),
                    proposed_value=value,
                    evidence_id=None,
                    confidence=(official_snapshot.source_kind if trusted_metadata else "reference"),
                    review_reason="category and tags require human review",
                    auto_applicable=False,
                )
            )
    return findings


def merge_font_metadata(
    files: Sequence[FontFileMetadata], *, partial_file: bool = False
) -> FontFileMetadata:
    """동일 face로 확인된 분할 파일만 cmap 합집합으로 병합한다."""
    parsed = [item for item in files if item.inspection_status == "parsed"]
    if len(parsed) != len(files) or not parsed:
        return _review_metadata("incomplete_font_files", digest=_combined_sha256(files))
    identities = {
        (item.families, item.weight, item.italic)
        for item in parsed
    }
    if len(identities) != 1 or any(item.face_conflict for item in parsed):
        return FontFileMetadata(
            families=tuple(sorted({name for item in parsed for name in item.families})),
            codepoints=frozenset(value for item in parsed for value in item.codepoints),
            file_sha256=_combined_sha256(parsed),
            inspection_status="needs_review",
            error_kind="face_conflict",
            face_conflict=True,
            partial_file=partial_file,
        )
    first = parsed[0]
    return FontFileMetadata(
        families=first.families,
        weight=first.weight,
        italic=first.italic,
        codepoints=frozenset(value for item in parsed for value in item.codepoints),
        file_sha256=_combined_sha256(parsed),
        format=first.format if len(parsed) == 1 else "split-face",
        units_per_em=first.units_per_em,
        italic_angle=first.italic_angle,
        partial_file=partial_file,
    )


def _review_metadata(
    error_kind: str, *, digest: str | None = None, font_format: str | None = None
) -> FontFileMetadata:
    return FontFileMetadata(
        file_sha256=digest,
        format=font_format,
        inspection_status="needs_review",
        error_kind=error_kind,
    )


def _normalize_family(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _combined_sha256(files: Sequence[FontFileMetadata]) -> str:
    digests = sorted(item.file_sha256 or "" for item in files)
    if len(digests) == 1:
        return digests[0]
    return hashlib.sha256("\n".join(digests).encode("ascii")).hexdigest()


def _inspect_worker(
    connection: Connection, path_text: str, font_format: str, timeout_seconds: float
) -> None:
    try:
        payload = (
            _parse_font(path_text, font_format)
            if _limit_worker_resources(timeout_seconds)
            else {"status": "error", "error_kind": "resource_limit"}
        )
    except BaseException:
        payload = {"status": "error", "error_kind": "parse_failed"}
    try:
        connection.send(payload)
    finally:
        connection.close()


def _limit_worker_resources(timeout_seconds: float) -> bool:
    try:
        import resource

        memory_limit = 2 * 1024 * 1024 * 1024
        memory_resource = (
            resource.RLIMIT_AS
            if sys.platform.startswith("linux")
            else resource.RLIMIT_RSS
        )
        resource.setrlimit(memory_resource, (memory_limit, memory_limit))
        cpu_limit = max(1, math.ceil(timeout_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
        return True
    except (ImportError, OSError, ValueError):
        # CPython/macOS can expose resource constants while rejecting any
        # finite value from the inherited infinity limit. The hard parent
        # timeout remains enforced; Linux must fail closed if limits fail.
        return sys.platform == "darwin"


def _stop_worker(process: Any) -> None:
    """모든 parent 경로에서 worker를 회수한다."""
    process.join(0.1)
    if not process.is_alive():
        return
    process.terminate()
    process.join(1)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(1)


def _parse_font(path_text: str, font_format: str) -> dict[str, object]:
    from fontTools.ttLib import TTCollection, TTFont  # type: ignore[import-untyped]

    fonts: list[Any]
    collection: Any | None = None
    if font_format == "ttc":
        collection = TTCollection(
            path_text,
            lazy=True,
            recalcBBoxes=False,
            recalcTimestamp=False,
        )
        fonts = list(collection.fonts)
    else:
        fonts = [
            TTFont(
                path_text,
                lazy=True,
                recalcBBoxes=False,
                recalcTimestamp=False,
            )
        ]
    try:
        faces = [_parse_face(font) for font in fonts]
    finally:
        if collection is not None:
            collection.close()
        else:
            fonts[0].close()
    groups: set[tuple[tuple[str, ...], int | None, bool]] = set()
    for face in faces:
        groups.add(
            (
                tuple(cast(list[str], face["families"])),
                cast(int | None, face["weight"]),
                cast(bool, face["italic"]),
            )
        )
    codepoints: set[int] = set()
    for face in faces:
        codepoints.update(cast(list[int], face["codepoints"]))
    first = faces[0]
    return {
        "status": "parsed",
        "families": first["families"],
        "weight": first["weight"],
        "italic": first["italic"],
        "codepoints": sorted(codepoints),
        "units_per_em": first["units_per_em"],
        "italic_angle": first["italic_angle"],
        "face_conflict": font_format == "ttc" or len(groups) != 1,
    }


def _parse_face(font: Any) -> dict[str, object]:
    name_table = font["name"]
    families: set[str] = set()
    for name_id in (16, 1):
        values = {
            _normalize_family(record.toUnicode())
            for record in name_table.names
            if record.nameID == name_id and record.toUnicode().strip()
        }
        if values:
            families = values
            break
    cmap = font.getBestCmap() or {}
    os2 = font["OS/2"] if "OS/2" in font else None
    head = font["head"] if "head" in font else None
    post = font["post"] if "post" in font else None
    weight = getattr(os2, "usWeightClass", None)
    mac_style = getattr(head, "macStyle", 0)
    italic_angle = getattr(post, "italicAngle", None)
    fs_selection = getattr(os2, "fsSelection", 0)
    italic = (
        bool(mac_style & 0x02)
        or bool(fs_selection & 0x01)
        or bool(italic_angle and italic_angle != 0)
    )
    return {
        "families": sorted(families),
        "weight": weight if isinstance(weight, int) else None,
        "italic": italic,
        "codepoints": sorted(cmap),
        "units_per_em": getattr(head, "unitsPerEm", None),
        "italic_angle": float(italic_angle) if isinstance(italic_angle, (int, float)) else None,
    }
