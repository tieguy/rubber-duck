"""Tests for GTD project health checking."""

from unittest.mock import patch

from rubber_duck.gtd.projects import _compute_project_health, check_projects


class TestComputeProjectHealth:
    """Test project health computation."""

    def test_active_project(self):
        """Project with recent completions is active."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": []}]
        completions = [{"task_id": "2"}]  # completed task

        status = _compute_project_health(proj_tasks, completions)

        assert status == "active"

    def test_stalled_project(self):
        """Project with tasks but no completions is stalled."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": []}]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "stalled"

    def test_waiting_project(self):
        """Project with only waiting tasks is waiting."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": ["waiting"]}]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "waiting"

    def test_incomplete_project(self):
        """Project with no actionable tasks is incomplete."""
        proj_tasks = []  # No tasks
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "incomplete"

    def test_backburner_tasks_excluded(self):
        """Tasks with backburner labels are excluded from stalled check."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": ["someday-maybe"]}]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        # Only backburner tasks, so incomplete
        assert status == "incomplete"

    def test_mixed_waiting_and_actionable(self):
        """Project with both waiting and actionable tasks is stalled."""
        proj_tasks = [
            {"id": "1", "content": "Waiting task", "labels": ["waiting"]},
            {"id": "2", "content": "Actionable task", "labels": []},
        ]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        # Has actionable tasks but no completions
        assert status == "stalled"

    def test_labels_case_insensitive(self):
        """Labels should be matched case-insensitively."""
        proj_tasks = [{"id": "1", "content": "Task", "labels": ["WAITING"]}]
        completions = []

        status = _compute_project_health(proj_tasks, completions)

        assert status == "waiting"


class TestGetNextAction:
    """Test next action selection."""

    def test_get_next_action_prioritized(self):
        """Prioritized task is selected as next action."""
        from rubber_duck.gtd.projects import _get_next_action

        tasks = [
            {"id": "1", "content": "Low priority", "labels": [], "priority": 4},
            {"id": "2", "content": "High priority", "labels": [], "priority": 1},
        ]

        result = _get_next_action(tasks)

        assert result["id"] == "2"

    def test_get_next_action_excludes_waiting(self):
        """Waiting tasks are excluded from next action."""
        from rubber_duck.gtd.projects import _get_next_action

        tasks = [
            {"id": "1", "content": "Waiting", "labels": ["waiting"], "priority": 1},
            {"id": "2", "content": "Actionable", "labels": [], "priority": 4},
        ]

        result = _get_next_action(tasks)

        assert result["id"] == "2"

    def test_get_next_action_returns_none_when_empty(self):
        """Returns None when no actionable tasks."""
        from rubber_duck.gtd.projects import _get_next_action

        tasks = [
            {"id": "1", "content": "Waiting", "labels": ["waiting"]},
        ]

        result = _get_next_action(tasks)

        assert result is None


class TestCheckProjects:
    """Test the main check_projects function."""

    @patch("rubber_duck.gtd.projects._fetch_tasks")
    @patch("rubber_duck.gtd.projects._fetch_projects")
    @patch("rubber_duck.gtd.projects._fetch_completed_tasks")
    def test_check_projects_returns_structured_output(
        self, mock_completed, mock_projects, mock_tasks
    ):
        """check_projects returns properly structured dict."""
        mock_tasks.return_value = [
            {"id": "1", "content": "Task", "labels": [], "project_id": "p1", "priority": 4},
        ]
        mock_projects.return_value = [{"id": "p1", "name": "Work"}]
        mock_completed.return_value = []

        result = check_projects()

        assert "generated_at" in result
        assert "active" in result
        assert "stalled" in result
        assert "waiting" in result
        assert "incomplete" in result
        assert "summary" in result

    @patch("rubber_duck.gtd.projects._fetch_tasks")
    @patch("rubber_duck.gtd.projects._fetch_projects")
    @patch("rubber_duck.gtd.projects._fetch_completed_tasks")
    def test_check_projects_active_project(
        self, mock_completed, mock_projects, mock_tasks
    ):
        """Project with completions is marked active."""
        mock_tasks.return_value = [
            {"id": "1", "content": "Task", "labels": [], "project_id": "p1", "priority": 4},
        ]
        mock_projects.return_value = [{"id": "p1", "name": "Work"}]
        mock_completed.return_value = [{"task_id": "2", "project_id": "p1"}]

        result = check_projects()

        assert len(result["active"]) == 1
        assert result["active"][0]["name"] == "Work"
        assert result["active"][0]["completed_this_week"] == 1

    @patch("rubber_duck.gtd.projects._fetch_tasks")
    @patch("rubber_duck.gtd.projects._fetch_projects")
    @patch("rubber_duck.gtd.projects._fetch_completed_tasks")
    def test_check_projects_stalled_includes_next_action(
        self, mock_completed, mock_projects, mock_tasks
    ):
        """Stalled project includes next action info."""
        mock_tasks.return_value = [
            {"id": "1", "content": "Do something", "labels": [], "project_id": "p1", "priority": 4},
        ]
        mock_projects.return_value = [{"id": "p1", "name": "Stalled Project"}]
        mock_completed.return_value = []

        result = check_projects()

        assert len(result["stalled"]) == 1
        assert result["stalled"][0]["next_action"]["content"] == "Do something"

    @patch("rubber_duck.gtd.projects._fetch_tasks")
    @patch("rubber_duck.gtd.projects._fetch_projects")
    @patch("rubber_duck.gtd.projects._fetch_completed_tasks")
    def test_check_projects_empty_projects_skipped(
        self, mock_completed, mock_projects, mock_tasks
    ):
        """Projects with no tasks and no completions are skipped."""
        mock_tasks.return_value = []
        mock_projects.return_value = [{"id": "p1", "name": "Empty Project"}]
        mock_completed.return_value = []

        result = check_projects()

        assert len(result["active"]) == 0
        assert len(result["stalled"]) == 0
        assert len(result["waiting"]) == 0
        assert len(result["incomplete"]) == 0
