from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from documents.models import DocumentAnnotation, DocumentAnnotationType


def export_annotated_pdf(
    source_path: Path,
    destination_path: Path,
    annotations: Iterable[DocumentAnnotation],
) -> int:
    reader = PdfReader(str(source_path))
    writer = PdfWriter()

    by_page: dict[int, list[DocumentAnnotation]] = {}
    for annotation in annotations:
        if annotation.annotation_type != DocumentAnnotationType.STROKE:
            continue
        if annotation.page_number is None:
            continue
        by_page.setdefault(annotation.page_number, []).append(annotation)

    for page_index, page in enumerate(reader.pages, start=1):
        overlay_annotations = by_page.get(page_index, [])
        if overlay_annotations:
            overlay = _build_page_overlay(page, overlay_annotations)
            page.merge_page(overlay.pages[0])
        writer.add_page(page)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with destination_path.open("wb") as output_file:
        writer.write(output_file)
    return destination_path.stat().st_size


def _build_page_overlay(page, annotations: list[DocumentAnnotation]) -> PdfReader:
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))

    for annotation in annotations:
        points = annotation.anchor_data.get("points", [])
        if len(points) < 2:
            continue

        thickness_ratio = float(annotation.anchor_data.get("thickness_ratio") or 0)
        line_width = annotation.thickness or max(width * thickness_ratio, 1.0)
        if not line_width:
            line_width = 1.0

        pdf.setLineCap(1)
        pdf.setLineJoin(1)
        pdf.setStrokeColor(HexColor(annotation.color))
        pdf.setLineWidth(line_width)

        path = pdf.beginPath()
        first = points[0]
        path.moveTo(first["x"] * width, (1 - first["y"]) * height)
        for point in points[1:]:
            path.lineTo(point["x"] * width, (1 - point["y"]) * height)
        pdf.drawPath(path, stroke=1, fill=0)

    pdf.save()
    buffer.seek(0)
    return PdfReader(buffer)
