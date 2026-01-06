"""Tests for GTD someday-maybe triage."""

from datetime import date
from unittest.mock import patch

from rubber_duck.gtd.someday import (
    _categorize_someday,
    _is_backburner,
    check_someday,
)


class TestCategorizeSomeday:
    """Test someday-maybe categorization by age."""

    def test_old_item_consider_deleting(self):
        """Item > 365 days old should be considered for deletion."""
        today = date(2026, 1, 5)
        task = {
            "id": "1",
            "content": "Learn Esperanto",
            "labels": ["someday-maybe"],
            "created_at": "2024-06-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert len(result["consider_deleting"]) == 1
        assert result["consider_deleting"][0]["days_old"] > 365

    def test_medium_age_needs_decision(self):
        """Item 180-365 days old needs decision."""
        today = date(2026, 1, 5)
        task = {
            "id": "2",
            "content": "Build a shed",
            "labels": ["maybe"],
            "created_at": "2025-07-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert len(result["needs_decision"]) == 1

    def test_recent_item_keep(self):
        """Item < 180 days old should be kept."""
        today = date(2026, 1, 5)
        task = {
            "id": "3",
            "content": "Try pottery",
            "labels": ["someday"],
            "created_at": "2025-10-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert len(result["keep"]) == 1

    def test_non_backburner_excluded(self):
        """Task without backburner label is excluded."""
        today = date(2026, 1, 5)
        task = {
            "id": "4",
            "content": "Active task",
            "labels": ["work"],
            "created_at": "2024-01-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert result["summary"]["total"] == 0

    def test_backburner_labels_case_insensitive(self):
        """Backburner labels should be matched case-insensitively."""
        today = date(2026, 1, 5)
        task = {
            "id": "5",
            "content": "Learn piano",
            "labels": ["SOMEDAY-MAYBE"],
            "created_at": "2025-10-01T10:00:00Z",
            "project_id": "p1",
        }

        result = _categorize_someday([task], today, {})

        assert result["summary"]["total"] == 1

    def test_sorting_by_age(self):
        """Items should be sorted by age (oldest first)."""
        today = date(2026, 1, 5)
        tasks = [
            {
                "id": "1",
                "content": "Recent",
                "labels": ["someday"],
                "created_at": "2024-10-01T10:00:00Z",  # ~460 days old
                "project_id": "p1",
            },
            {
                "id": "2",
                "content": "Oldest",
                "labels": ["someday"],
                "created_at": "2024-06-01T10:00:00Z",  # ~580 days old
                "project_id": "p1",
            },
            {
                "id": "3",
                "content": "Middle",
                "labels": ["someday"],
                "created_at": "2024-08-01T10:00:00Z",  # ~520 days old
                "project_id": "p1",
            },
        ]

        result = _categorize_someday(tasks, today, {})

        # All should be in consider_deleting (> 365 days old)
        assert len(result["consider_deleting"]) == 3
        # Oldest should come first
        assert result["consider_deleting"][0]["content"] == "Oldest"
        assert result["consider_deleting"][1]["content"] == "Middle"
        assert result["consider_deleting"][2]["content"] == "Recent"


class TestIsBackburner:
    """Test backburner detection."""

    def test_backburner_by_label(self):
        """Task with backburner label is detected."""
        task = {"id": "1", "labels": ["someday-maybe"]}
        assert _is_backburner(task, {}) is True

    def test_backburner_by_project(self):
        """Task in someday-maybe project is detected."""
        task = {"id": "1", "labels": [], "project_id": "p1"}
        proj_by_id = {"p1": {"id": "p1", "name": "Someday/Maybe", "parent_id": None}}
        assert _is_backburner(task, proj_by_id) is True

    def test_backburner_by_parent_project(self):
        """Task in child of someday-maybe project is detected."""
        task = {"id": "1", "labels": [], "project_id": "p2"}
        proj_by_id = {
            "p1": {"id": "p1", "name": "Someday/Maybe", "parent_id": None},
            "p2": {"id": "p2", "name": "Hobbies", "parent_id": "p1"},
        }
        assert _is_backburner(task, proj_by_id) is True

    def test_not_backburner(self):
        """Regular task is not backburner."""
        task = {"id": "1", "labels": ["work"], "project_id": "p1"}
        proj_by_id = {"p1": {"id": "p1", "name": "Work", "parent_id": None}}
        assert _is_backburner(task, proj_by_id) is False


class TestCheckSomeday:
    """Test the main check_someday function."""

    @patch("rubber_duck.gtd.someday._fetch_tasks")
    @patch("rubber_duck.gtd.someday._fetch_projects")
    def test_check_someday_returns_structured_output(self, mock_projects, mock_tasks):
        """check_someday returns properly structured dict."""
        mock_tasks.return_value = [
            {
                "id": "1",
                "content": "Learn Klingon",
                "labels": ["someday-maybe"],
                "created_at": "2024-01-01T10:00:00Z",
                "project_id": "p1",
            },
        ]
        mock_projects.return_value = [{"id": "p1", "name": "Work", "parent_id": None}]

        result = check_someday()

        assert "generated_at" in result
        assert "consider_deleting" in result
        assert "needs_decision" in result
        assert "keep" in result
        assert "summary" in result

    @patch("rubber_duck.gtd.someday._fetch_tasks")
    @patch("rubber_duck.gtd.someday._fetch_projects")
    def test_check_someday_resolves_project_names(self, mock_projects, mock_tasks):
        """check_someday resolves project IDs to names."""
        mock_tasks.return_value = [
            {
                "id": "1",
                "content": "Learn Klingon",
                "labels": ["someday-maybe"],
                "created_at": "2024-01-01T10:00:00Z",
                "project_id": "p1",
            },
        ]
        mock_projects.return_value = [{"id": "p1", "name": "Dream Projects", "parent_id": None}]

        result = check_someday()

        # Find the item in one of the categories
        all_items = result["consider_deleting"] + result["needs_decision"] + result["keep"]
        assert len(all_items) > 0
        assert all_items[0]["project"] == "Dream Projects"

    @patch("rubber_duck.gtd.someday._fetch_tasks")
    @patch("rubber_duck.gtd.someday._fetch_projects")
    def test_check_someday_empty_when_no_backburner_tasks(self, mock_projects, mock_tasks):
        """check_someday handles empty task list."""
        mock_tasks.return_value = []
        mock_projects.return_value = []

        result = check_someday()

        assert result["consider_deleting"] == []
        assert result["needs_decision"] == []
        assert result["keep"] == []
        assert result["summary"]["total"] == 0
