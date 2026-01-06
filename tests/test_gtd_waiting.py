"""Tests for GTD waiting-for tracking."""

from datetime import date
from unittest.mock import patch

from rubber_duck.gtd.waiting import _categorize_waiting, check_waiting


class TestCategorizeWaiting:
    """Test waiting-for categorization."""

    def test_fresh_waiting_item(self):
        """Item waiting < 4 days is still_fresh."""
        today = date(2026, 1, 5)
        task = {
            "id": "1",
            "content": "Waiting on Bob",
            "labels": ["waiting"],
            "created_at": "2026-01-03T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert len(result["still_fresh"]) == 1
        assert result["still_fresh"][0]["days_waiting"] == 2

    def test_gentle_check_item(self):
        """Item waiting 4-7 days needs gentle check."""
        today = date(2026, 1, 10)
        task = {
            "id": "2",
            "content": "Waiting on vendor",
            "labels": ["waiting-for"],
            "created_at": "2026-01-04T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert len(result["gentle_check"]) == 1
        assert result["gentle_check"][0]["urgency"] == "gentle"

    def test_needs_followup_item(self):
        """Item waiting > 7 days needs followup."""
        today = date(2026, 1, 20)
        task = {
            "id": "3",
            "content": "Waiting on specs",
            "labels": ["waiting"],
            "created_at": "2026-01-05T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert len(result["needs_followup"]) == 1
        assert "suggested_action" in result["needs_followup"][0]

    def test_non_waiting_task_excluded(self):
        """Task without waiting label is excluded."""
        today = date(2026, 1, 5)
        task = {
            "id": "4",
            "content": "Regular task",
            "labels": ["work"],
            "created_at": "2026-01-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert result["summary"]["total"] == 0

    def test_waiting_labels_case_insensitive(self):
        """Waiting labels should be matched case-insensitively."""
        today = date(2026, 1, 5)
        task = {
            "id": "5",
            "content": "Waiting on approval",
            "labels": ["WAITING"],
            "created_at": "2026-01-03T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_waiting([task], today)

        assert result["summary"]["total"] == 1

    def test_sorting_by_days_waiting(self):
        """Items should be sorted by days waiting (oldest first)."""
        today = date(2026, 1, 20)
        tasks = [
            {
                "id": "1",
                "content": "Recent",
                "labels": ["waiting"],
                "created_at": "2026-01-15T10:00:00Z",
                "project_id": "p1",
            },
            {
                "id": "2",
                "content": "Oldest",
                "labels": ["waiting"],
                "created_at": "2026-01-01T10:00:00Z",
                "project_id": "p1",
            },
            {
                "id": "3",
                "content": "Middle",
                "labels": ["waiting"],
                "created_at": "2026-01-10T10:00:00Z",
                "project_id": "p1",
            },
        ]

        result = _categorize_waiting(tasks, today)

        # Oldest should come first in needs_followup
        assert result["needs_followup"][0]["content"] == "Oldest"
        assert result["needs_followup"][0]["days_waiting"] == 19


class TestCheckWaiting:
    """Test the main check_waiting function."""

    @patch("rubber_duck.gtd.waiting._fetch_tasks")
    @patch("rubber_duck.gtd.waiting._fetch_projects")
    def test_check_waiting_returns_structured_output(self, mock_projects, mock_tasks):
        """check_waiting returns properly structured dict."""
        mock_tasks.return_value = [
            {
                "id": "1",
                "content": "Waiting",
                "labels": ["waiting"],
                "created_at": "2026-01-01T10:00:00Z",
                "project_id": "p1",
            },
        ]
        mock_projects.return_value = {"p1": "Work"}

        result = check_waiting()

        assert "generated_at" in result
        assert "needs_followup" in result
        assert "gentle_check" in result
        assert "still_fresh" in result
        assert "summary" in result

    @patch("rubber_duck.gtd.waiting._fetch_tasks")
    @patch("rubber_duck.gtd.waiting._fetch_projects")
    def test_check_waiting_resolves_project_names(self, mock_projects, mock_tasks):
        """check_waiting resolves project IDs to names."""
        mock_tasks.return_value = [
            {
                "id": "1",
                "content": "Waiting",
                "labels": ["waiting"],
                "created_at": "2026-01-01T10:00:00Z",
                "project_id": "p1",
            },
        ]
        mock_projects.return_value = {"p1": "Work Projects"}

        result = check_waiting()

        # Find the item in one of the categories
        all_items = (
            result["needs_followup"] + result["gentle_check"] + result["still_fresh"]
        )
        assert len(all_items) > 0
        assert all_items[0]["project"] == "Work Projects"

    @patch("rubber_duck.gtd.waiting._fetch_tasks")
    @patch("rubber_duck.gtd.waiting._fetch_projects")
    def test_check_waiting_empty_when_no_waiting_tasks(self, mock_projects, mock_tasks):
        """check_waiting handles empty task list."""
        mock_tasks.return_value = []
        mock_projects.return_value = {}

        result = check_waiting()

        assert result["needs_followup"] == []
        assert result["gentle_check"] == []
        assert result["still_fresh"] == []
        assert result["summary"]["total"] == 0
