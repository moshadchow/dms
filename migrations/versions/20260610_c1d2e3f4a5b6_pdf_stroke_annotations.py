"""pdf_stroke_annotations

Revision ID: c1d2e3f4a5b6
Revises: 8f1e2d3c4b5a
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "8f1e2d3c4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    annotation_type_enum = sa.Enum("NOTE", "STROKE", name="documentannotationtype")
    drawing_tool_enum = sa.Enum("PEN", name="drawingtool")

    annotation_type_enum.create(bind, checkfirst=True)
    drawing_tool_enum.create(bind, checkfirst=True)

    op.add_column(
        "document_annotations",
        sa.Column(
            "annotation_type",
            annotation_type_enum,
            nullable=False,
            server_default="NOTE",
        ),
    )
    op.add_column(
        "document_annotations",
        sa.Column(
            "drawing_tool",
            drawing_tool_enum,
            nullable=True,
        ),
    )
    op.add_column(
        "document_annotations",
        sa.Column("thickness", sa.Float(), nullable=True),
    )
    op.alter_column("document_annotations", "anchor_type", nullable=True)
    op.alter_column("document_annotations", "note_text", nullable=True)
    op.create_index(
        op.f("ix_document_annotations_annotation_type"),
        "document_annotations",
        ["annotation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_annotations_drawing_tool"),
        "document_annotations",
        ["drawing_tool"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_annotations_drawing_tool"), table_name="document_annotations")
    op.drop_index(op.f("ix_document_annotations_annotation_type"), table_name="document_annotations")
    op.alter_column("document_annotations", "note_text", nullable=False)
    op.alter_column("document_annotations", "anchor_type", nullable=False)
    op.drop_column("document_annotations", "thickness")
    op.drop_column("document_annotations", "drawing_tool")
    op.drop_column("document_annotations", "annotation_type")

    bind = op.get_bind()
    sa.Enum(name="drawingtool").drop(bind, checkfirst=True)
    sa.Enum(name="documentannotationtype").drop(bind, checkfirst=True)
