"""OCR engines used for scanned PDF pages."""

from __future__ import annotations

import csv
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import DependencyUnavailableError
from app.models.document import BoundingBox, DocumentRegion, RegionType


@dataclass(frozen=True)
class OcrLine:
    text: str
    bbox: BoundingBox
    confidence: float | None


class OcrEngine:
    def extract(self, image_path: Path, page_number: int, document_id: str) -> list[DocumentRegion]:
        raise NotImplementedError


class TesseractOcrEngine(OcrEngine):
    def __init__(self, command: str = "tesseract", language: str = "eng", dpi: int = 220) -> None:
        self._command = command
        self._language = language
        self._dpi = dpi

    def extract(self, image_path: Path, page_number: int, document_id: str) -> list[DocumentRegion]:
        try:
            completed = subprocess.run(  # noqa: S603
                [
                    self._command,
                    str(image_path),
                    "stdout",
                    "-l",
                    self._language,
                    "--dpi",
                    str(self._dpi),
                    "--psm",
                    "6",
                    "tsv",
                ],
                capture_output=True,
                check=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise DependencyUnavailableError("OCR command is unavailable") from exc
        except subprocess.CalledProcessError as exc:
            raise DependencyUnavailableError("OCR extraction failed") from exc

        lines = self._parse_tsv(completed.stdout)
        regions: list[DocumentRegion] = []
        for index, line in enumerate(lines):
            regions.append(
                DocumentRegion(
                    region_id=f"{document_id}-p{page_number}-ocr-{index}",
                    page_number=page_number,
                    region_type=RegionType.OCR_LINE,
                    text=line.text,
                    bbox=line.bbox,
                    confidence=line.confidence,
                    source="ocr",
                    metadata={"engine": "tesseract", "language": self._language},
                )
            )
        return regions

    def _parse_tsv(self, raw_output: str) -> list[OcrLine]:
        rows = list(csv.DictReader(raw_output.splitlines(), delimiter="\t"))
        grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row.get("level") != "5":
                continue
            if not row.get("text", "").strip():
                continue
            key = (row.get("block_num", "0"), row.get("par_num", "0"), row.get("line_num", "0"))
            grouped[key].append(row)

        parsed_lines: list[OcrLine] = []
        for words in grouped.values():
            parsed_lines.append(self._merge_line(words))
        return parsed_lines

    def _merge_line(self, words: Iterable[dict[str, str]]) -> OcrLine:
        word_list = list(words)
        left = min(int(word["left"]) for word in word_list)
        top = min(int(word["top"]) for word in word_list)
        right = max(int(word["left"]) + int(word["width"]) for word in word_list)
        bottom = max(int(word["top"]) + int(word["height"]) for word in word_list)
        confidence_values = [
            float(word["conf"]) for word in word_list if word.get("conf") not in {"", "-1"}
        ]
        confidence = (
            sum(confidence_values) / len(confidence_values) / 100 if confidence_values else None
        )
        text = " ".join(
            word["text"].strip() for word in word_list if word.get("text", "").strip()
        )
        return OcrLine(
            text=text,
            bbox=BoundingBox(x0=left, y0=top, x1=right, y1=bottom),
            confidence=confidence,
        )