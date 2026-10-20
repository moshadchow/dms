import json
from io import BytesIO
from html import escape
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlmodel import Session

from documents.models import DocumentAnnotation, DocumentAnnotationType, DocumentVariant


def _make_xlsx_bytes(rows: list[list[str]] | None = None) -> bytes:
    """Create a minimal XLSX file in memory with optional cell data."""
    if rows is None:
        rows = [["Name", "Value"], ["Alice", "100"], ["Bob", "200"]]

    shared_strings = []
    sheet_rows = []
    for row in rows:
        cells = []
        for value in row:
            idx = len(shared_strings)
            shared_strings.append(value)
            cells.append(f'<c t="s"><v>{idx}</v></c>')
        sheet_rows.append(f'<row>{"".join(cells)}</row>')

    ss_items = "".join(
        f"<si><t>{escape(s)}</t></si>" for s in shared_strings
    )
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        f"{ss_items}</sst>"
    )

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(sheet_rows) +
        "</sheetData></worksheet>"
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
        "</sheets></workbook>"
    )

    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        "</Relationships>"
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml)
    return buffer.getvalue()


def _make_docx_bytes(text: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>""",
        )
    return buffer.getvalue()


def _make_pdf_bytes(pages: int = 2) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for page_number in range(1, pages + 1):
        pdf.drawString(72, 720, f"Page {page_number}")
        pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def test_docx_workspace_preview_and_private_variant_save(client, seeded_data, auth_headers):
    test_client, engine, _ = client

    upload_response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": "Word Workspace",
            "description": "DOCX upload",
            "directory_id": str(seeded_data["finance_directory_id"]),
            "user_level_ids": json.dumps([seeded_data["high_level_id"], seeded_data["medium_level_id"]]),
        },
        files={
            "file": (
                "workspace.docx",
                _make_docx_bytes("Quarterly update"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=auth_headers["maker"],
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    workspace_response = test_client.get(
        f"/api/v1/documents/{document_id}/workspace",
        headers=auth_headers["maker"],
    )

    assert workspace_response.status_code == 200
    workspace_payload = workspace_response.json()
    assert workspace_payload["preview_html"] is not None
    assert "Quarterly update" in workspace_payload["preview_html"]
    assert workspace_payload["has_private_variant"] is False

    save_response = test_client.post(
        f"/api/v1/documents/{document_id}/variants",
        json={
            "annotations": [
                {
                    "page_number": 1,
                    "anchor_type": "point",
                    "anchor_data": {"x_pct": 22.5, "y_pct": 18.0},
                    "note_text": "Needs review",
                    "color": "#f59e0b",
                }
            ]
        },
        headers=auth_headers["maker"],
    )

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload["has_private_variant"] is True
    assert len(saved_payload["annotations"]) == 1
    assert saved_payload["annotations"][0]["note_text"] == "Needs review"
    variant_id = saved_payload["variant"]["id"]

    with Session(engine) as session:
        variant = session.get(DocumentVariant, variant_id)
        assert variant is not None
        assert "_variants" in variant.storage_path
        assert str(seeded_data["finance_category_id"]) in variant.storage_path

    variant_metadata = test_client.get(
        f"/api/v1/documents/variants/{variant_id}",
        headers=auth_headers["maker"],
    )
    assert variant_metadata.status_code == 200

    admin_forbidden = test_client.get(
        f"/api/v1/documents/variants/{variant_id}",
        headers=auth_headers["admin"],
    )
    assert admin_forbidden.status_code == 404

    variant_view = test_client.get(
        f"/api/v1/documents/variants/{variant_id}/view",
        headers=auth_headers["maker"],
    )
    assert variant_view.status_code == 200


def test_pdf_workspace_saves_user_specific_strokes_and_exports_variant(client, seeded_data, auth_headers):
    test_client, engine, _ = client

    upload_response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": "Annotated PDF",
            "description": "PDF upload",
            "directory_id": str(seeded_data["finance_directory_id"]),
            "user_level_ids": json.dumps([seeded_data["high_level_id"], seeded_data["medium_level_id"]]),
        },
        files={
            "file": (
                "annotated.pdf",
                _make_pdf_bytes(),
                "application/pdf",
            )
        },
        headers=auth_headers["admin"],
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    workspace_response = test_client.get(
        f"/api/v1/documents/{document_id}/workspace",
        headers=auth_headers["maker"],
    )
    assert workspace_response.status_code == 200
    assert workspace_response.json()["has_private_variant"] is False

    payload = {
        "annotations": [
            {
                "page_number": 1,
                "annotation_type": "stroke",
                "drawing_tool": "pen",
                "thickness": 4,
                "anchor_data": {
                    "points": [
                        {"x": 0.2, "y": 0.2},
                        {"x": 0.3, "y": 0.25},
                        {"x": 0.45, "y": 0.35},
                    ],
                    "thickness_ratio": 0.005,
                },
                "color": "#ef4444",
            }
        ]
    }

    save_response = test_client.post(
        f"/api/v1/documents/{document_id}/variants",
        json=payload,
        headers=auth_headers["maker"],
    )
    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload["has_private_variant"] is True
    assert saved_payload["variant"]["source_document_id"] == document_id
    assert saved_payload["annotations"][0]["annotation_type"] == "stroke"
    variant_id = saved_payload["variant"]["id"]

    with Session(engine) as session:
        variant = session.get(DocumentVariant, variant_id)
        assert variant is not None
        assert variant.file_size > 0
        from sqlmodel import select

        annotations = session.exec(
            select(DocumentAnnotation).where(DocumentAnnotation.variant_id == variant_id)
        ).all()
        assert len(annotations) == 1
        assert annotations[0].annotation_type == DocumentAnnotationType.STROKE

    reopen_response = test_client.get(
        f"/api/v1/documents/{document_id}/workspace",
        headers=auth_headers["maker"],
    )
    assert reopen_response.status_code == 200
    reopened = reopen_response.json()
    assert reopened["annotations"][0]["anchor_data"]["points"][1]["x"] == 0.3

    admin_variant = test_client.get(
        f"/api/v1/documents/variants/{variant_id}",
        headers=auth_headers["admin"],
    )
    assert admin_variant.status_code == 404

    download_response = test_client.get(
        f"/api/v1/documents/variants/{variant_id}/download",
        headers=auth_headers["maker"],
    )
    assert download_response.status_code == 200
    exported_reader = PdfReader(BytesIO(download_response.content))
    assert len(exported_reader.pages) == 2

    second_save_response = test_client.post(
        f"/api/v1/documents/{document_id}/variants",
        json={
            "annotations": [
                {
                    "page_number": 2,
                    "annotation_type": "stroke",
                    "drawing_tool": "pen",
                    "thickness": 6,
                    "anchor_data": {
                        "points": [
                            {"x": 0.1, "y": 0.1},
                            {"x": 0.2, "y": 0.2},
                        ],
                        "thickness_ratio": 0.007,
                    },
                    "color": "#2563eb",
                }
            ]
        },
        headers=auth_headers["maker"],
    )
    assert second_save_response.status_code == 200
    second_payload = second_save_response.json()
    assert len(second_payload["annotations"]) == 1
    assert second_payload["annotations"][0]["page_number"] == 2


def test_excel_workspace_preview_and_view(client, seeded_data, auth_headers):
    test_client, engine, _ = client

    upload_response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": "Excel Workspace",
            "description": "XLSX upload",
            "directory_id": str(seeded_data["finance_directory_id"]),
            "user_level_ids": json.dumps([seeded_data["high_level_id"], seeded_data["medium_level_id"]]),
        },
        files={
            "file": (
                "workspace.xlsx",
                _make_xlsx_bytes([["Name", "Value"], ["Alice", "100"], ["Bob", "200"]]),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=auth_headers["maker"],
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    workspace_response = test_client.get(
        f"/api/v1/documents/{document_id}/workspace",
        headers=auth_headers["maker"],
    )

    assert workspace_response.status_code == 200
    workspace_payload = workspace_response.json()
    assert workspace_payload["preview_html"] is not None
    assert "xlsx-preview" in workspace_payload["preview_html"]
    assert "Alice" in workspace_payload["preview_html"]
    assert "100" in workspace_payload["preview_html"]
    assert workspace_payload["preview_error"] is None
    assert workspace_payload["has_private_variant"] is False

    view_response = test_client.get(
        f"/api/v1/documents/{document_id}/view",
        headers=auth_headers["maker"],
    )
    assert view_response.status_code == 200
    content_disposition = view_response.headers.get("content-disposition", "")
    assert "inline" in content_disposition

    download_response = test_client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_headers["maker"],
    )
    assert download_response.status_code == 200
    download_disposition = download_response.headers.get("content-disposition", "")
    assert "attachment" in download_disposition


def _make_jpeg_bytes() -> bytes:
    """Create a minimal valid JPEG file in memory."""
    # Minimal JPEG: SOI marker + APP0 + a tiny 1x1 image
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00\x43\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07"
        b"\x07\x09\x09\x08\x0a\x0c\x14\x0d\x0c\x0b\x0b\x0c\x19\x12"
        b"\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $\x27 \x22"
        b"\x2c( \x23#,\x1c\x1c(7,(00444\x201444\x204444444\x204444"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01"
        b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04"
        b"\x05\x06\x07\x08\x09\x0a\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x7b\x40"
        b"\xff\xd9"
    )


def test_image_workspace_and_view(client, seeded_data, auth_headers):
    test_client, engine, _ = client

    upload_response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": "Test Image",
            "description": "JPEG upload",
            "directory_id": str(seeded_data["finance_directory_id"]),
            "user_level_ids": json.dumps([seeded_data["high_level_id"], seeded_data["medium_level_id"]]),
        },
        files={
            "file": (
                "test.jpg",
                _make_jpeg_bytes(),
                "image/jpeg",
            )
        },
        headers=auth_headers["maker"],
    )

    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    workspace_response = test_client.get(
        f"/api/v1/documents/{document_id}/workspace",
        headers=auth_headers["maker"],
    )

    assert workspace_response.status_code == 200
    workspace_payload = workspace_response.json()
    assert workspace_payload["preview_html"] is None
    assert workspace_payload["preview_error"] is None
    assert workspace_payload["has_private_variant"] is False

    view_response = test_client.get(
        f"/api/v1/documents/{document_id}/view",
        headers=auth_headers["maker"],
    )
    assert view_response.status_code == 200
    assert view_response.headers.get("content-type") == "image/jpeg"
    content_disposition = view_response.headers.get("content-disposition", "")
    assert "inline" in content_disposition

    download_response = test_client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_headers["maker"],
    )
    assert download_response.status_code == 200
    download_disposition = download_response.headers.get("content-disposition", "")
    assert "attachment" in download_disposition
