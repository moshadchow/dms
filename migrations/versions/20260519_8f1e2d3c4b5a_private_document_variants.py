"""private_document_variants

Revision ID: 8f1e2d3c4b5a
Revises: b7f9a1c2d3e4
Create Date: 2026-05-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
import sqlmodel


revision: str = "8f1e2d3c4b5a"
down_revision: Union[str, None] = "b7f9a1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_exists(enum_name: str) -> bool:
    """Check if a PostgreSQL enum type exists."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": enum_name},
    ).fetchone()
    return result is not None


def _create_enum_if_missing(enum_name: str, values: list[str]) -> None:
    """Create a PostgreSQL enum type only if it doesn't already exist."""
    if not _enum_exists(enum_name):
        quoted = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({quoted})")


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # ── Enum types ────────────────────────────────────────────────
    if is_pg:
        # Add DOCX to the existing filetype enum (idempotent)
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE filetype ADD VALUE IF NOT EXISTS 'DOCX'")

        # Create new enum types if they don't already exist
        _create_enum_if_missing("documentvarianttype", ["PRIVATE_ANNOTATION"])
        _create_enum_if_missing("documentvariantstatus", ["ACTIVE", "DELETED"])
        _create_enum_if_missing("annotationanchortype", ["POINT", "TEXT_RANGE"])

    # ── Tables ────────────────────────────────────────────────────
    # Use create_type=False so SQLAlchemy doesn't try to CREATE TYPE
    filetype_enum = PgEnum("PDF", "DOCX", "EXCEL", "IMAGE", name="filetype", create_type=False)
    variant_type_enum = PgEnum("PRIVATE_ANNOTATION", name="documentvarianttype", create_type=False)
    variant_status_enum = PgEnum("ACTIVE", "DELETED", name="documentvariantstatus", create_type=False)
    anchor_type_enum = PgEnum("POINT", "TEXT_RANGE", name="annotationanchortype", create_type=False)

    op.create_table(
        "document_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("directory_id", sa.Integer(), nullable=False),
        sa.Column("variant_type", variant_type_enum, nullable=False),
        sa.Column("status", variant_status_enum, nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("source_file_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("source_mime_type", sqlmodel.sql.sqltypes.AutoString(length=127), nullable=False),
        sa.Column("file_type", filetype_enum, nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["directory_id"], ["directories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "owner_user_id",
            "variant_type",
            name="uq_document_variants_source_owner_type",
        ),
    )
    op.create_index(op.f("ix_document_variants_source_document_id"), "document_variants", ["source_document_id"], unique=False)
    op.create_index(op.f("ix_document_variants_owner_user_id"), "document_variants", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_document_variants_category_id"), "document_variants", ["category_id"], unique=False)
    op.create_index(op.f("ix_document_variants_directory_id"), "document_variants", ["directory_id"], unique=False)
    op.create_index(op.f("ix_document_variants_variant_type"), "document_variants", ["variant_type"], unique=False)
    op.create_index(op.f("ix_document_variants_status"), "document_variants", ["status"], unique=False)
    op.create_index(op.f("ix_document_variants_file_type"), "document_variants", ["file_type"], unique=False)

    op.create_table(
        "document_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("anchor_type", anchor_type_enum, nullable=False),
        sa.Column("anchor_data", sa.JSON(), nullable=False),
        sa.Column("note_text", sqlmodel.sql.sqltypes.AutoString(length=5000), nullable=False),
        sa.Column("color", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["variant_id"], ["document_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_annotations_variant_id"), "document_annotations", ["variant_id"], unique=False)
    op.create_index(op.f("ix_document_annotations_page_number"), "document_annotations", ["page_number"], unique=False)
    op.create_index(op.f("ix_document_annotations_anchor_type"), "document_annotations", ["anchor_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_annotations_anchor_type"), table_name="document_annotations")
    op.drop_index(op.f("ix_document_annotations_page_number"), table_name="document_annotations")
    op.drop_index(op.f("ix_document_annotations_variant_id"), table_name="document_annotations")
    op.drop_table("document_annotations")

    op.drop_index(op.f("ix_document_variants_file_type"), table_name="document_variants")
    op.drop_index(op.f("ix_document_variants_status"), table_name="document_variants")
    op.drop_index(op.f("ix_document_variants_variant_type"), table_name="document_variants")
    op.drop_index(op.f("ix_document_variants_directory_id"), table_name="document_variants")
    op.drop_index(op.f("ix_document_variants_category_id"), table_name="document_variants")
    op.drop_index(op.f("ix_document_variants_owner_user_id"), table_name="document_variants")
    op.drop_index(op.f("ix_document_variants_source_document_id"), table_name="document_variants")
    op.drop_table("document_variants")
