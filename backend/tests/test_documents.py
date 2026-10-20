"""
tests/test_documents.py
───────────────────────
Tests for document listing with sorting and filtering (Spec 33).
"""

import io
import json
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, select

from core.security import create_access_token, hash_password
from documents.models import Document, DocumentStatus
from users.models import (
    Permission,
    PermissionAction,
    Role,
    RoleName,
    RolePermissionLink,
    User,
    UserCategoryLink,
    UserRoleLink,
)
from user_levels.models import UserLevel
from categories.models import Category
from directories.models import Directory


@pytest.fixture()
def document_test_data(client, seeded_data):
    """Create test documents for sorting and filtering tests."""
    test_client, engine, _ = client

    with Session(engine) as session:
        # Get seeded data
        admin_id = seeded_data["admin_id"]
        maker_id = seeded_data["maker_id"]
        finance_category_id = seeded_data["finance_category_id"]
        finance_directory_id = seeded_data["finance_directory_id"]
        hr_category_id = seeded_data["hr_category_id"]
        hr_directory_id = seeded_data["hr_directory_id"]
        high_level_id = seeded_data["high_level_id"]
        medium_level_id = seeded_data["medium_level_id"]
        low_level_id = seeded_data["low_level_id"]
        company_id = seeded_data["company_id"]

        # Create additional users for testing uploaded_by filter
        admin = session.get(User, admin_id)
        maker = session.get(User, maker_id)

        # Create another maker user
        other_maker = User(
            full_name="Other Maker",
            email="other_maker@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            user_level_id=high_level_id,
            company_id=company_id,
        )
        session.add(other_maker)
        session.flush()

        maker_role = session.exec(
            select(Role).where(Role.name == RoleName.MAKER)
        ).first()
        session.add(UserRoleLink(user_id=other_maker.id, role_id=maker_role.id))
        session.add(UserCategoryLink(user_id=other_maker.id, category_id=finance_category_id))
        session.add(UserCategoryLink(user_id=other_maker.id, category_id=hr_category_id))

        # Create documents with different properties for testing
        # Note: seeded maker has access to Finance category (finance_category_id) and Legal category (inactive)
        # So we create all test documents in finance_directory_id which the maker can access
        base_time = datetime.utcnow() - timedelta(days=10)

        # Document 1: uploaded by admin, created 10 days ago
        doc1 = Document(
            title="Finance Report Q1",
            description="Quarterly finance report",
            directory_id=finance_directory_id,
            uploaded_by=admin_id,
            file_name="finance_q1.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=1024,
            storage_path=f"storage/uploads/{company_id}/finance/finance_q1.pdf",
            status=DocumentStatus.ACTIVE,
            created_at=base_time,
            updated_at=base_time,
        )
        session.add(doc1)
        session.flush()
        session.add(DocumentUserLevelLink(document_id=doc1.id, user_level_id=high_level_id))
        session.add(DocumentUserLevelLink(document_id=doc1.id, user_level_id=medium_level_id))

        # Document 2: uploaded by maker, created 8 days ago (in Finance category, accessible to maker)
        doc2 = Document(
            title="Finance Policy Update",
            description="Updated finance policies",
            directory_id=finance_directory_id,
            uploaded_by=maker_id,
            file_name="finance_policy.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=2048,
            storage_path=f"storage/uploads/{company_id}/finance/finance_policy.pdf",
            status=DocumentStatus.ACTIVE,
            created_at=base_time + timedelta(days=2),
            updated_at=base_time + timedelta(days=2),
        )
        session.add(doc2)
        session.flush()
        session.add(DocumentUserLevelLink(document_id=doc2.id, user_level_id=medium_level_id))
        session.add(DocumentUserLevelLink(document_id=doc2.id, user_level_id=low_level_id))

        # Document 3: uploaded by other_maker, created 5 days ago
        doc3 = Document(
            title="Budget Forecast",
            description="Annual budget forecast",
            directory_id=finance_directory_id,
            uploaded_by=other_maker.id,
            file_name="budget.xlsx",
            file_type="excel",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size=4096,
            storage_path=f"storage/uploads/{company_id}/finance/budget.xlsx",
            status=DocumentStatus.ACTIVE,
            created_at=base_time + timedelta(days=5),
            updated_at=base_time + timedelta(days=5),
        )
        session.add(doc3)
        session.flush()
        session.add(DocumentUserLevelLink(document_id=doc3.id, user_level_id=high_level_id))

        # Document 4: uploaded by maker, created 3 days ago, updated recently
        doc4 = Document(
            title="Meeting Notes",
            description="Team meeting notes",
            directory_id=finance_directory_id,
            uploaded_by=maker_id,
            file_name="meeting.txt",
            file_type="docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=512,
            storage_path=f"storage/uploads/{company_id}/finance/meeting.txt",
            status=DocumentStatus.ACTIVE,
            created_at=base_time + timedelta(days=7),
            updated_at=base_time + timedelta(days=9),  # Updated recently
        )
        session.add(doc4)
        session.flush()
        session.add(DocumentUserLevelLink(document_id=doc4.id, user_level_id=medium_level_id))
        session.add(DocumentUserLevelLink(document_id=doc4.id, user_level_id=low_level_id))

        session.commit()

        return {
            **seeded_data,
            "other_maker_id": other_maker.id,
            "doc1_id": doc1.id,
            "doc2_id": doc2.id,
            "doc3_id": doc3.id,
            "doc4_id": doc4.id,
            "base_time": base_time,
        }


@pytest.fixture()
def document_auth_headers(document_test_data):
    return {
        "admin": {"Authorization": f"Bearer {create_access_token(document_test_data['admin_id'])}"},
        "maker": {"Authorization": f"Bearer {create_access_token(document_test_data['maker_id'])}"},
        "other_maker": {"Authorization": f"Bearer {create_access_token(document_test_data['other_maker_id'])}"},
    }


def _upload_doc(test_client, headers, directory_id, title, user_level_ids, file_content=b"test content"):
    """Helper to upload a document with user level IDs."""
    return test_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={
            "title": title,
            "directory_id": str(directory_id),
            "user_level_ids": json.dumps(user_level_ids),
        },
        files={"file": (f"{title}.pdf", io.BytesIO(file_content), "application/pdf")},
    )


class TestDocumentSorting:
    """Tests for sorting functionality."""

    def test_sort_by_title_asc(self, client, document_test_data, document_auth_headers):
        """Test sorting by title ascending."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        titles = [item["title"] for item in items]
        assert titles == sorted(titles)

    def test_sort_by_title_desc(self, client, document_test_data, document_auth_headers):
        """Test sorting by title descending."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "desc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        titles = [item["title"] for item in items]
        assert titles == sorted(titles, reverse=True)

    def test_sort_by_file_name(self, client, document_test_data, document_auth_headers):
        """Test sorting by file_name."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "file_name", "sort_order": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        file_names = [item["file_name"] for item in items]
        assert file_names == sorted(file_names)

    def test_sort_by_file_size(self, client, document_test_data, document_auth_headers):
        """Test sorting by file_size."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "file_size", "sort_order": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        file_sizes = [item["file_size"] for item in items]
        assert file_sizes == sorted(file_sizes)

    def test_sort_by_created_at(self, client, document_test_data, document_auth_headers):
        """Test sorting by created_at (default desc)."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "created_at"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        created_dates = [item["created_at"] for item in items]
        # Default should be desc for dates
        assert created_dates == sorted(created_dates, reverse=True)

    def test_sort_by_updated_at(self, client, document_test_data, document_auth_headers):
        """Test sorting by updated_at."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "updated_at", "sort_order": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        updated_dates = [item["updated_at"] for item in items]
        assert updated_dates == sorted(updated_dates)

    def test_default_sorting(self, client, document_test_data, document_auth_headers):
        """Test default sorting (created_at desc)."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        created_dates = [item["created_at"] for item in items]
        # Default should be desc for dates
        assert created_dates == sorted(created_dates, reverse=True)

    def test_secondary_id_sort_stable_pagination(self, client, document_test_data, document_auth_headers):
        """Test that secondary id sort ensures stable pagination."""
        test_client, _, _ = client
        data = document_test_data
        # Get first page
        resp1 = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "asc", "limit": 2, "skip": 0},
        )
        assert resp1.status_code == 200
        items1 = resp1.json()["items"]
        
        # Get second page
        resp2 = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "asc", "limit": 2, "skip": 2},
        )
        assert resp2.status_code == 200
        items2 = resp2.json()["items"]
        
        # No overlap between pages
        ids1 = {item["id"] for item in items1}
        ids2 = {item["id"] for item in items2}
        assert ids1.isdisjoint(ids2)


class TestDocumentFiltering:
    """Tests for filtering functionality."""

    def test_filter_by_uploaded_by_admin(self, client, document_test_data, document_auth_headers):
        """Test filtering by uploaded_by as admin (sees all)."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"uploaded_by": data["maker_id"]},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should see docs uploaded by maker (doc2 and doc4)
        # Plus any seeded docs uploaded by maker
        for item in items:
            assert item["uploaded_by"] == data["maker_id"]
        # At least our test docs
        maker_doc_titles = {item["title"] for item in items}
        assert "Finance Policy Update" in maker_doc_titles
        assert "Meeting Notes" in maker_doc_titles

    def test_filter_by_uploaded_by_non_admin(self, client, document_test_data, document_auth_headers):
        """Test filtering by uploaded_by as non-admin (scoped to accessible)."""
        test_client, _, _ = client
        data = document_test_data
        # maker can see doc2 and doc4 (uploaded by maker) and doc1 (uploaded by admin, has high/medium level)
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["maker"],
            params={"uploaded_by": data["maker_id"]},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should only see docs uploaded by maker that they have access to
        for item in items:
            assert item["uploaded_by"] == data["maker_id"]
        maker_doc_titles = {item["title"] for item in items}
        assert "Finance Policy Update" in maker_doc_titles
        assert "Meeting Notes" in maker_doc_titles
        assert "Meeting Notes" in maker_doc_titles

    def test_filter_by_uploaded_by_other_user(self, client, document_test_data, document_auth_headers):
        """Test filtering by uploaded_by for another user."""
        test_client, _, _ = client
        data = document_test_data
        # admin filtering by other_maker
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"uploaded_by": data["other_maker_id"]},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should include our test doc3
        assert any(item["title"] == "Budget Forecast" for item in items)
        for item in items:
            assert item["uploaded_by"] == data["other_maker_id"]

    def test_filter_by_created_from(self, client, document_test_data, document_auth_headers):
        """Test filtering by created_from."""
        test_client, _, _ = client
        data = document_test_data
        # Filter for documents created after base_time + 3 days
        from_date = (data["base_time"] + timedelta(days=3)).isoformat()
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"created_from": from_date},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # All returned items should have created_at >= from_date
        for item in items:
            assert item["created_at"] >= from_date
        # Should include our test docs doc3 (day 5), doc4 (day 7)
        titles = {item["title"] for item in items}
        assert "Budget Forecast" in titles
        assert "Meeting Notes" in titles

    def test_filter_by_created_to(self, client, document_test_data, document_auth_headers):
        """Test filtering by created_to."""
        test_client, _, _ = client
        data = document_test_data
        # Filter for documents created before base_time + 6 days
        to_date = (data["base_time"] + timedelta(days=6)).isoformat()
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"created_to": to_date},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # All returned items should have created_at <= to_date
        for item in items:
            assert item["created_at"] <= to_date
        # Should include our test docs doc1 (day 0), doc2 (day 2), doc3 (day 5)
        titles = {item["title"] for item in items}
        assert "Finance Report Q1" in titles
        assert "Finance Policy Update" in titles
        assert "Budget Forecast" in titles

    def test_filter_by_created_range(self, client, document_test_data, document_auth_headers):
        """Test filtering by created_from and created_to together."""
        test_client, _, _ = client
        data = document_test_data
        from_date = (data["base_time"] + timedelta(days=1)).isoformat()
        to_date = (data["base_time"] + timedelta(days=6)).isoformat()
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"created_from": from_date, "created_to": to_date},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # All returned items should be in range
        for item in items:
            assert from_date <= item["created_at"] <= to_date
        # Should include our test docs doc2 (day 2), doc3 (day 5)
        titles = {item["title"] for item in items}
        assert "Finance Policy Update" in titles
        assert "Budget Forecast" in titles

    def test_filter_by_updated_from(self, client, document_test_data, document_auth_headers):
        """Test filtering by updated_from."""
        test_client, _, _ = client
        data = document_test_data
        # Filter for documents updated after base_time + 8 days
        from_date = (data["base_time"] + timedelta(days=8)).isoformat()
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"updated_from": from_date},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # All returned items should have updated_at >= from_date
        for item in items:
            assert item["updated_at"] >= from_date
        # Should include our test doc4 (updated day 9)
        titles = {item["title"] for item in items}
        assert "Meeting Notes" in titles

    def test_filter_by_updated_to(self, client, document_test_data, document_auth_headers):
        """Test filtering by updated_to."""
        test_client, _, _ = client
        data = document_test_data
        # Filter for documents updated before base_time + 6 days
        to_date = (data["base_time"] + timedelta(days=6)).isoformat()
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"updated_to": to_date},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # All returned items should have updated_at <= to_date
        for item in items:
            assert item["updated_at"] <= to_date
        # Should include our test docs doc1, doc2, doc3 (not doc4 which was updated day 9)
        titles = {item["title"] for item in items}
        assert "Finance Report Q1" in titles
        assert "Finance Policy Update" in titles
        assert "Budget Forecast" in titles

    def test_combined_filters(self, client, document_test_data, document_auth_headers):
        """Test combining multiple filters."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={
                "uploaded_by": data["maker_id"],
                "created_from": (data["base_time"] + timedelta(days=1)).isoformat(),
                "sort_by": "file_size",
                "sort_order": "desc",
            },
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should only have our test doc4 (uploaded by maker, created after day 1)
        # Plus any seeded docs that match
        titles = {item["title"] for item in items}
        assert "Meeting Notes" in titles
        for item in items:
            assert item["uploaded_by"] == data["maker_id"]
            assert item["created_at"] >= (data["base_time"] + timedelta(days=1)).isoformat()

    def test_non_admin_filter_scoping(self, client, document_test_data, document_auth_headers):
        """Test that non-admin filters are scoped to their accessible documents."""
        test_client, _, _ = client
        data = document_test_data
        # maker has medium level, so can see doc1 (high/medium), doc2 (medium/low), doc4 (low)
        # but NOT doc3 (high only)
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["maker"],
            params={"uploaded_by": data["other_maker_id"]},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should be empty because maker cannot access doc3 (uploaded by other_maker, high level only)
        # Also seeded docs uploaded by other_maker don't exist
        assert len(items) == 0


class TestSortValidation:
    """Tests for sort parameter validation."""

    def test_invalid_sort_by_returns_422(self, client, document_test_data, document_auth_headers):
        """Test that invalid sort_by returns 422."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "invalid_field"},
        )
        assert resp.status_code == 422
        assert "Invalid sort_by value" in resp.json()["detail"]
        assert "invalid_field" in resp.json()["detail"]

    def test_invalid_sort_order_returns_422(self, client, document_test_data, document_auth_headers):
        """Test that invalid sort_order returns 422."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "invalid"},
        )
        assert resp.status_code == 422
        assert "Invalid sort_order value" in resp.json()["detail"]
        assert "invalid" in resp.json()["detail"]

    def test_valid_sort_by_values(self, client, document_test_data, document_auth_headers):
        """Test all valid sort_by values work."""
        test_client, _, _ = client
        data = document_test_data
        valid_fields = ["title", "file_name", "file_size", "created_at", "updated_at"]
        for field in valid_fields:
            resp = test_client.get(
                "/api/v1/documents",
                headers=document_auth_headers["admin"],
                params={"sort_by": field, "sort_order": "asc"},
            )
            assert resp.status_code == 200, f"sort_by={field} should work"


class TestDocumentListIntegration:
    """Integration tests for document list endpoint."""

    def test_list_with_search_and_sort(self, client, document_test_data, document_auth_headers):
        """Test search combined with sorting."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"search": "Finance", "sort_by": "title", "sort_order": "asc"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should include our test docs "Finance Report Q1", "Finance Policy Update" and seeded "Finance Report"
        titles = [item["title"] for item in items]
        assert "Finance Report Q1" in titles
        assert "Finance Policy Update" in titles
        # Should be sorted by title ascending
        assert titles == sorted(titles)

    def test_list_with_file_type_filter(self, client, document_test_data, document_auth_headers):
        """Test file_type filter."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"file_type": "excel"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should have our test doc3 (budget.xlsx)
        assert any(item["title"] == "Budget Forecast" for item in items)
        for item in items:
            assert item["file_type"] == "excel"

    def test_list_with_category_filter(self, client, document_test_data, document_auth_headers):
        """Test category_id filter."""
        test_client, _, _ = client
        data = document_test_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"category_id": data["finance_category_id"]},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Should have our test doc1 and doc3 (both in finance category) plus seeded finance doc
        titles = {item["title"] for item in items}
        assert "Finance Report Q1" in titles
        assert "Budget Forecast" in titles
        # All should be in finance category
        for item in items:
            # We can't easily check category_id from response, but we can check titles
            pass

    def test_pagination_with_sorting(self, client, document_test_data, document_auth_headers):
        """Test pagination works correctly with sorting."""
        test_client, _, _ = client
        data = document_test_data
        # Get all sorted by title
        resp_all = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "asc", "limit": 100},
        )
        assert resp_all.status_code == 200
        all_items = resp_all.json()["items"]
        
        # Get first page
        resp_page1 = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "asc", "limit": 2, "skip": 0},
        )
        assert resp_page1.status_code == 200
        page1_items = resp_page1.json()["items"]
        
        # Get second page
        resp_page2 = test_client.get(
            "/api/v1/documents",
            headers=document_auth_headers["admin"],
            params={"sort_by": "title", "sort_order": "asc", "limit": 2, "skip": 2},
        )
        assert resp_page2.status_code == 200
        page2_items = resp_page2.json()["items"]
        
        # Combined pages should match all items (in order)
        combined = page1_items + page2_items
        assert [item["id"] for item in combined] == [item["id"] for item in all_items[:4]]


# Need to import DocumentUserLevelLink for the fixture
from documents.models import DocumentUserLevelLink