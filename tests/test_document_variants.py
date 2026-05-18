from io import BytesIO
from html import escape
from zipfile import ZIP_DEFLATED, ZipFile

from sqlmodel import Session

from documents.models import DocumentVariant


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


def test_docx_workspace_preview_and_private_variant_save(client, seeded_data, auth_headers):
    test_client, engine, _ = client

    upload_response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": "Word Workspace",
            "description": "DOCX upload",
            "directory_id": str(seeded_data["finance_directory_id"]),
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
