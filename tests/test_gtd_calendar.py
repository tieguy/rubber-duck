"""Tests for GTD calendar integration."""

from unittest.mock import patch

from rubber_duck.gtd.calendar import _format_events, calendar_range, calendar_today


class TestFormatEvents:
    """Test event formatting."""

    def test_timed_event(self):
        """Timed event is formatted correctly."""
        events = [{
            "summary": "Meeting",
            "start": {"dateTime": "2026-01-05T14:00:00Z"},
            "end": {"dateTime": "2026-01-05T15:00:00Z"},
            "location": "Room 101",
        }]

        result = _format_events(events)

        assert len(result["events"]) == 1
        assert result["events"][0]["summary"] == "Meeting"
        assert result["events"][0]["start"] == "14:00"
        assert result["events"][0]["location"] == "Room 101"

    def test_all_day_event(self):
        """All-day event is categorized separately."""
        events = [{
            "summary": "Holiday",
            "start": {"date": "2026-01-05"},
            "end": {"date": "2026-01-06"},
        }]

        result = _format_events(events)

        assert len(result["all_day"]) == 1
        assert result["all_day"][0]["summary"] == "Holiday"

    def test_summary_counts(self):
        """Summary has correct counts."""
        events = [
            {
                "summary": "Meeting",
                "start": {"dateTime": "2026-01-05T14:00:00Z"},
                "end": {"dateTime": "2026-01-05T15:00:00Z"},
            },
            {"summary": "Holiday", "start": {"date": "2026-01-05"}, "end": {"date": "2026-01-06"}},
        ]

        result = _format_events(events)

        assert result["summary"]["timed_events"] == 1
        assert result["summary"]["all_day"] == 1

    def test_event_with_no_title(self):
        """Event without summary gets default title."""
        events = [{
            "start": {"dateTime": "2026-01-05T14:00:00Z"},
            "end": {"dateTime": "2026-01-05T15:00:00Z"},
        }]

        result = _format_events(events)

        assert result["events"][0]["summary"] == "(No title)"

    def test_event_with_no_location(self):
        """Event without location has None for location."""
        events = [{
            "summary": "Meeting",
            "start": {"dateTime": "2026-01-05T14:00:00Z"},
            "end": {"dateTime": "2026-01-05T15:00:00Z"},
        }]

        result = _format_events(events)

        assert result["events"][0]["location"] is None

    def test_empty_events_list(self):
        """Empty events list returns empty structure."""
        result = _format_events([])

        assert result["events"] == []
        assert result["all_day"] == []
        assert result["summary"]["timed_events"] == 0
        assert result["summary"]["all_day"] == 0


class TestCalendarToday:
    """Test calendar_today function."""

    @patch("rubber_duck.gtd.calendar._fetch_events")
    def test_calendar_today_returns_structured_output(self, mock_fetch):
        """calendar_today returns properly structured dict."""
        mock_fetch.return_value = [
            {
                "summary": "Meeting",
                "start": {"dateTime": "2026-01-05T14:00:00Z"},
                "end": {"dateTime": "2026-01-05T15:00:00Z"},
            },
        ]

        result = calendar_today()

        assert "generated_at" in result
        assert "events" in result
        assert "all_day" in result
        assert "summary" in result
        assert len(result["events"]) == 1

    @patch("rubber_duck.gtd.calendar._fetch_events")
    def test_calendar_today_empty_when_no_events(self, mock_fetch):
        """calendar_today handles empty events list."""
        mock_fetch.return_value = []

        result = calendar_today()

        assert result["events"] == []
        assert result["summary"]["timed_events"] == 0


class TestCalendarRange:
    """Test calendar_range function."""

    @patch("rubber_duck.gtd.calendar._fetch_events")
    def test_calendar_range_returns_structured_output(self, mock_fetch):
        """calendar_range returns properly structured dict with range info."""
        mock_fetch.return_value = [
            {
                "summary": "Meeting",
                "start": {"dateTime": "2026-01-05T14:00:00Z"},
                "end": {"dateTime": "2026-01-05T15:00:00Z"},
            },
        ]

        result = calendar_range(days_back=1, days_forward=7)

        assert "generated_at" in result
        assert "events" in result
        assert "range" in result
        assert "from" in result["range"]
        assert "to" in result["range"]

    @patch("rubber_duck.gtd.calendar._fetch_events")
    def test_calendar_range_default_params(self, mock_fetch):
        """calendar_range uses sensible defaults."""
        mock_fetch.return_value = []

        result = calendar_range()

        # Default is 0 days back, 7 days forward
        assert "range" in result
