"""Tests for GTD deadline scanning."""

from datetime import date
from unittest.mock import patch

from rubber_duck.gtd.deadlines import _categorize_by_urgency, scan_deadlines


class TestCategorizeByUrgency:
    """Test task categorization by deadline urgency."""

    def test_overdue_task(self):
        """Task with past due date is categorized as overdue."""
        today = date(2026, 1, 5)
        task = {
            "id": "123",
            "content": "Overdue task",
            "due": {"date": "2026-01-03"},
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["overdue"]) == 1
        assert result["overdue"][0]["id"] == "123"
        assert result["overdue"][0]["days_overdue"] == 2

    def test_due_today_task(self):
        """Task due today is categorized correctly."""
        today = date(2026, 1, 5)
        task = {
            "id": "456",
            "content": "Due today",
            "due": {"date": "2026-01-05"},
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["due_today"]) == 1
        assert result["due_today"][0]["id"] == "456"

    def test_due_this_week_task(self):
        """Task due within 7 days is categorized as due_this_week."""
        today = date(2026, 1, 5)
        task = {
            "id": "789",
            "content": "Due this week",
            "due": {"date": "2026-01-08"},
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["due_this_week"]) == 1
        assert result["due_this_week"][0]["days_until"] == 3

    def test_task_with_no_due_date_excluded(self):
        """Task without due date is not included in any category."""
        today = date(2026, 1, 5)
        task = {
            "id": "999",
            "content": "No due date",
            "due": None,
            "project_id": "proj1",
        }

        result = _categorize_by_urgency([task], today)

        assert len(result["overdue"]) == 0
        assert len(result["due_today"]) == 0
        assert len(result["due_this_week"]) == 0

    def test_summary_counts(self):
        """Summary contains correct counts."""
        today = date(2026, 1, 5)
        tasks = [
            {"id": "1", "content": "Overdue", "due": {"date": "2026-01-01"}, "project_id": "p"},
            {"id": "2", "content": "Today", "due": {"date": "2026-01-05"}, "project_id": "p"},
            {"id": "3", "content": "This week", "due": {"date": "2026-01-10"}, "project_id": "p"},
        ]

        result = _categorize_by_urgency(tasks, today)

        assert result["summary"]["overdue"] == 1
        assert result["summary"]["due_today"] == 1
        assert result["summary"]["due_this_week"] == 1


class TestScanDeadlines:
    """Test the main scan_deadlines function."""

    @patch("rubber_duck.gtd.deadlines._fetch_tasks")
    @patch("rubber_duck.gtd.deadlines._fetch_projects")
    def test_scan_deadlines_returns_structured_output(self, mock_projects, mock_tasks):
        """scan_deadlines returns properly structured dict."""
        mock_tasks.return_value = [
            {"id": "1", "content": "Task", "due": {"date": "2026-01-03"}, "project_id": "p1"},
        ]
        mock_projects.return_value = {"p1": "Work"}

        result = scan_deadlines()

        assert "generated_at" in result
        assert "overdue" in result
        assert "due_today" in result
        assert "due_this_week" in result
        assert "summary" in result
        # Project name should be resolved
        assert result["overdue"][0]["project"] == "Work"

    @patch("rubber_duck.gtd.deadlines._fetch_tasks")
    @patch("rubber_duck.gtd.deadlines._fetch_projects")
    def test_scan_deadlines_empty_when_no_tasks(self, mock_projects, mock_tasks):
        """scan_deadlines handles empty task list."""
        mock_tasks.return_value = []
        mock_projects.return_value = {}

        result = scan_deadlines()

        assert result["overdue"] == []
        assert result["summary"]["overdue"] == 0
